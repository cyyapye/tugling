#!/usr/bin/env python3
"""Independent local oracle for first-time native enforcement setup.

The reviewer supplies invocation bindings after reading the completed setup.
Neither the task prompt nor its project contains this oracle or its mutations.
"""

from __future__ import annotations

import argparse
import ast
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time


HERE = Path(__file__).resolve().parent
FIXTURE = HERE / "fixtures/quota-service/repo"
HELPER = Path("plugins/tugling/scripts/project_contract.py")
TEST_FILE = Path("tests/test_service.py")
MAX_FILES = 2000
MAX_BYTES = 16 * 1024 * 1024
MAX_OUTPUT_BYTES = 2 * 1024 * 1024
TIMEOUT_SECONDS = 45
TERMINATION_GRACE_SECONDS = 5


class Inconclusive(RuntimeError):
    """The evaluator cannot establish the requested proof boundary."""


class Cancelled(SystemExit):
    def __init__(self, signum):
        self.signum = signum
        super().__init__(128 + signum)


@contextmanager
def cancellation_scope():
    previous = signal.getsignal(signal.SIGTERM)

    def cancelled(signum, _frame):
        raise Cancelled(signum)

    signal.signal(signal.SIGTERM, cancelled)
    try:
        yield
    finally:
        signal.signal(signal.SIGTERM, previous)


@contextmanager
def cleanup_scope():
    previous = {item: signal.getsignal(item) for item in (signal.SIGTERM, signal.SIGINT)}
    try:
        for item in previous:
            signal.signal(item, signal.SIG_IGN)
        yield
    finally:
        for item, handler in previous.items():
            signal.signal(item, handler)


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def supported(condition, message):
    if not condition:
        raise Inconclusive(message)


def environment(extra=None):
    # Synthetic commands receive no provider tokens or application credentials.
    result = {key: os.environ[key] for key in ("PATH", "TMPDIR", "LANG", "LC_ALL") if key in os.environ}
    result.update({"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
                   "PYTHONDONTWRITEBYTECODE": "1", "PYTHONNOUSERSITE": "1"})
    result.update(extra or {})
    return result


@cleanup_scope()
def stop_group(process):
    """Stop only the process group this invocation created, including orphans."""
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return False
    # The native helper owns a separate flow group and allows up to three
    # seconds for its teardown. Give it time to reap that group before killing
    # the enclosing launcher/helper group.
    deadline = time.monotonic() + TERMINATION_GRACE_SECONDS
    while time.monotonic() < deadline:
        process.poll()
        try:
            os.killpg(process.pid, 0)
        except ProcessLookupError:
            return True
        except PermissionError:
            # Darwin can briefly report EPERM while a signalled group is reaped.
            # Keep waiting within the same deadline rather than claiming success.
            pass
        time.sleep(0.02)
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.wait(timeout=5)
    return True


@cancellation_scope()
def command(root, argv, *, extra=None, success=True, expires_at=None):
    """Bound output and terminate only this command's owned process group."""
    supported(expires_at is None or time.monotonic() < expires_at, "CI declared timeout expired before execution")
    with tempfile.TemporaryFile() as output:
        process = subprocess.Popen(argv, cwd=root, env=environment(extra),
                                   stdout=output, stderr=subprocess.STDOUT, start_new_session=True)
        deadline = time.monotonic() + TIMEOUT_SECONDS
        if expires_at is not None:
            deadline = min(deadline, expires_at)
        stopped = None
        try:
            while process.poll() is None:
                if time.monotonic() >= deadline or output.tell() > MAX_OUTPUT_BYTES:
                    stopped = "timeout" if time.monotonic() >= deadline else "output limit"
                    break
                time.sleep(0.02)
        finally:
            cleaned = stop_group(process)
        output.seek(0)
        text = output.read(MAX_OUTPUT_BYTES + 1).decode("utf-8", errors="replace")
    supported(stopped is None and len(text.encode()) <= MAX_OUTPUT_BYTES,
              f"command exceeded bounded execution: {stopped or 'output limit'}")
    result = {"argv": argv, "returncode": process.returncode, "output": text, "forced_cleanup": cleaned}
    if success:
        require(process.returncode == 0, f"command failed: {argv!r}\n{text[-3000:]}")
    return result


def git(root, *args):
    return command(root, ["git", "--no-replace-objects", *args])["output"].strip()


def initialize(root):
    git(root, "init", "-q")
    git(root, "config", "user.name", "Synthetic Enforcement Oracle")
    git(root, "config", "user.email", "oracle@example.invalid")
    commit(root)


def commit(root):
    git(root, "add", ".")
    git(root, "-c", "commit.gpgsign=false", "commit", "--allow-empty", "-qm", "synthetic oracle state")


def source_files(root):
    names = git(root, "ls-files", "--cached", "--others", "--exclude-standard", "-z")
    files = []
    size = 0
    for name in sorted(set(names.split("\0")) - {""}):
        path = root / name
        require(not path.is_symlink() and root in path.resolve().parents,
                "snapshot requires regular files inside the project")
        if path.is_file():
            size += path.stat().st_size
            files.append(Path(name))
    require(len(files) <= MAX_FILES and size <= MAX_BYTES, "source snapshot exceeds fixture budget")
    return files


def copy_source(root, target):
    target.mkdir()
    for name in source_files(root):
        path = target / name
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(root / name, path)
    initialize(target)


def prepare(target):
    require(not target.exists(), "fixture target must not exist")
    shutil.copytree(FIXTURE, target, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    initialize(target)


def tree_snapshot(root):
    files = {}
    total = 0
    for directory, directories, names in os.walk(root, followlinks=False):
        directories[:] = sorted(name for name in directories if name != ".git")
        for name in sorted(directories + names):
            path = Path(directory) / name
            require(not path.is_symlink(), "assessment snapshot does not admit symlinks")
            if path.is_file():
                body = path.read_bytes()
                total += len(body)
                files[str(path.relative_to(root))] = hashlib.sha256(body).hexdigest()
    require(len(files) <= MAX_FILES and total <= MAX_BYTES, "assessment snapshot exceeds budget")
    return {"head": git(root, "rev-parse", "HEAD"),
            "status": git(root, "status", "--porcelain=v1", "--untracked-files=all", "--ignored"),
            "files": files}


def methods(body):
    tree = ast.parse(body)
    return {node.name: node for parent in tree.body if isinstance(parent, ast.ClassDef)
            for node in parent.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name.startswith("test_")}


def preserve_contract(root):
    require((root / "quota_sync.py").read_bytes() == (FIXTURE / "quota_sync.py").read_bytes(),
            "setup changed product implementation")
    before = methods((FIXTURE / TEST_FILE).read_text())
    after = methods((root / TEST_FILE).read_text())
    for name, original in before.items():
        require(name in after, f"setup removed an existing native case: {name}")
        supported(ast.dump(after[name]) == ast.dump(original),
                  f"existing native assertion changed; independent semantic review needed: {name}")


def alter_case(root, name, *, skip=False):
    path = root / TEST_FILE
    lines = path.read_text().splitlines(keepends=True)
    node = methods("".join(lines))[name]
    start = min([node.lineno] + [item.lineno for item in node.decorator_list]) - 1
    if skip:
        lines.insert(start, "    @unittest.skip('synthetic required-case omission')\n")
    else:
        del lines[start:node.end_lineno]
    path.write_text("".join(lines))


def invocation(hook, root, source):
    gate = hook["gate"]
    require(isinstance(gate.get("argv"), list) and gate["argv"] and
            all(isinstance(arg, str) and arg for arg in gate["argv"]), "gate needs nonempty argv")
    bindings = {"{repo}": str(root), "{source}": str(source)}

    def render(value):
        require(isinstance(value, str), "gate bindings must be strings")
        for token, target in bindings.items():
            value = value.replace(token, target)
        return value

    argv = [render(arg) for arg in gate["argv"]]
    env = {key: render(value) for key, value in gate.get("env", {}).items()}
    require("{source}" in json.dumps(gate), "reviewed invocation needs a caller source binding")
    return argv, env


def run_gate(hook, root, source, *, extra=None):
    argv, env = invocation(hook, root, source)
    env.update(extra or {})
    before = {str(path): hashlib.sha256((root / path).read_bytes()).hexdigest()
              for path in source_files(root)}
    result = command(root, argv, extra=env, success=False)
    require(not result["forced_cleanup"], "required gate left a running owned child after exit")
    after = {str(path): hashlib.sha256((root / path).read_bytes()).hexdigest()
             for path in source_files(root)}
    require(before == after, "required execution changed or automatically re-baselined intended source")
    return result


def receipt_paths(root):
    directory = root / ".tugling/local/verification"
    # Compare older candidates as well as the current owned retention layout.
    return set(directory.glob("*.json")) | set((directory / "managed-v1").glob("*.json"))


def require_receipt(hook, root, source, *, exclude=()):
    """Check native integration with the reviewed helper, not a printed label."""
    argv = [sys.executable, "-I", str(source / HELPER), "--repo", str(root),
            "--source-root", str(source), "--source-mode", "pinned",
            "--config", hook.get("config", ".tugling/project.json"), "--json"]
    report = json.loads(command(root, argv)["output"])
    require(isinstance(report.get("verification"), dict) and report["verification"].get("requirements"),
            "adapter has no required rule coverage")
    canonical = report["canonical_verify"]
    gate_argv, _ = invocation(hook, root, source)
    required_ids = {flow for rule in report["verification"]["requirements"] for flow in rule["flows"]}
    leaves = [flow["argv"] for flow in report["verification"]["flows"] if flow["id"] in required_ids]
    require(gate_argv == canonical or canonical in leaves,
            "reviewer gate is neither canonical nor a required wrapper around the canonical command")
    receipts = sorted(receipt_paths(root) - set(exclude))
    require(1 <= len(receipts) <= 32, "gate did not produce bounded native receipts")
    for receipt in receipts:
        require(not receipt.is_symlink() and receipt.stat().st_size <= 256 * 1024,
                "invalid native receipt file")
        if json.loads(receipt.read_text()).get("state") != "REQUIRED_PASS":
            continue
        result = command(root, argv + ["--check-required-evidence", str(receipt.relative_to(root))], success=False)
        if result["returncode"] == 0:
            return
    raise AssertionError("gate produced no complete valid required receipt")


def scalar(value):
    value = value.strip()
    if value.startswith('"'):
        return json.loads(value)
    if value.startswith("'") and value.endswith("'"):
        return value[1:-1].replace("''", "'")
    return value


def environment_block(lines, indent):
    result = {}
    for index, line in enumerate(lines):
        if line != " " * indent + "env:":
            continue
        for row in lines[index + 1:]:
            if not row.strip() or row.lstrip().startswith("#"):
                continue
            depth = len(row) - len(row.lstrip())
            if depth <= indent:
                break
            item = re.match(r"^\s*([\w-]+):\s*(.+)$", row)
            supported(depth == indent + 2 and item is not None, "unsupported inherited workflow environment")
            result[item[1]] = scalar(item[2])
    return result


def job_context(lines, step_start):
    jobs = [index for index, row in enumerate(lines) if row == "jobs:"]
    supported(len(jobs) == 1, "unsupported workflow jobs mapping")
    jobs_end = next((index for index in range(jobs[0] + 1, len(lines))
                     if lines[index].strip() and not lines[index].startswith((" ", "#"))), len(lines))
    headers = [(index, match[1]) for index, row in enumerate(lines[jobs[0] + 1:jobs_end], jobs[0] + 1)
               if (match := re.match(r"^  ([\w-]+):\s*$", row))]
    matching = [(index, name) for index, name in headers if index < step_start]
    supported(bool(matching), "workflow step has no supported parent job")
    start, name = matching[-1]
    supported(any(lines[index] == "    steps:" for index in range(start + 1, step_start)),
              "unsupported workflow steps mapping")
    stop = next((index for index, _name in headers if index > start), jobs_end)
    rows = lines[start + 1:stop]
    fields = {}
    for row in rows:
        if not row.strip() or row.lstrip().startswith("#") or len(row) - len(row.lstrip()) != 4:
            continue
        match = re.match(r"^    ([\w-]+):\s*(.*)$", row)
        supported(match is not None, "unsupported workflow job mapping")
        supported(match[1] not in fields, "unsupported duplicate workflow job field")
        fields[match[1]] = scalar(match[2])
    supported("defaults" not in fields and not any(row.startswith("defaults:") for row in lines),
              "unsupported workflow run defaults")
    return {"id": name, "fields": fields, "rows": rows, "env": environment_block(rows, 4),
            "workflow_env": environment_block(lines, 0)}


def nested_mapping(lines, index, indent):
    result = {}
    for row in lines[index + 1:]:
        if not row.strip() or row.lstrip().startswith("#"):
            continue
        depth = len(row) - len(row.lstrip())
        if depth <= indent:
            break
        match = re.match(r"^\s*([\w-]+):\s*(.*)$", row)
        supported(depth == indent + 2 and match is not None, "unsupported nested workflow policy")
        result[match[1]] = scalar(match[2])
    return result


def workflow_policy(text, job):
    lines = text.splitlines()
    events = [(index, match[1]) for index, row in enumerate(lines)
              if (match := re.match(r"^(?:on|['\"]on['\"]):\s*(.*)$", row))]
    require(len(events) == 1, "CI has no unique automatic event declaration")
    index, value = events[0]
    if value.startswith("[") and value.endswith("]"):
        enabled = {scalar(item.strip()) for item in value[1:-1].split(",")}
    elif not value:
        mapping = nested_mapping(lines, index, 0)
        supported(all(value in {"", "null", "{}"} for value in mapping.values()),
                  "unsupported CI event filters")
        enabled = set(mapping)
    else:
        enabled = {scalar(value)}
    require("pull_request_target" not in enabled, "CI uses a privileged pull-request event")
    require({"push", "pull_request"}.issubset(enabled), "CI does not run automatically for both push and pull_request")
    supported(enabled <= {"push", "pull_request", "workflow_dispatch"}, "unsupported CI event topology")

    permissions = []
    for rows, depth in ((lines, 0), (job["rows"], 4)):
        for index, row in enumerate(rows):
            match = re.match(r"^" + " " * depth + r"permissions:\s*(.*)$", row)
            if match:
                permissions.append((rows, index, depth, scalar(match[1])))
    supported(bool(permissions), "CI needs an explicit read-only token permission declaration")
    # A job-level declaration replaces the workflow-level token permissions.
    rows, index, depth, value = permissions[-1]
    require(value != "write-all", "CI required job grants write-all permissions")
    if value:
        supported(value in {"read-all", "{}"}, "unsupported CI token permission declaration")
    else:
        mapping = nested_mapping(rows, index, depth)
        require("write" not in mapping.values(), "CI required job grants write permissions")
        supported(all(value in {"read", "none"} for value in mapping.values()), "unsupported CI token permission value")


def unconditional(scope, label):
    if "if" in scope:
        condition = scope["if"].strip().lower()
        require(condition not in {"false", "${{ false }}"}, f"{label} is disabled")
        supported(condition in {"true", "${{ true }}"}, f"unsupported {label} condition")
    if "continue-on-error" in scope:
        condition = scope["continue-on-error"].strip().lower()
        require(condition not in {"true", "${{ true }}"}, f"{label} must be unconditional and fail closed")
        supported(condition in {"false", "${{ false }}"}, f"unsupported {label} failure policy")


def timeout_seconds(scope):
    if "timeout-minutes" not in scope:
        return None
    value = scope["timeout-minutes"]
    supported(isinstance(value, str) and re.fullmatch(r"[1-9]\d*", value) is not None
              and int(value) <= 360, "unsupported CI declared timeout")
    return int(value) * 60


def workflow_steps(text):
    """Parse the simple step mappings used by this offline fixture.

    This intentionally is not a permissive YAML implementation. Unsupported
    constructs require reviewer adaptation or separate evidence, never a pass.
    """
    lines = text.splitlines()
    starts = []
    for index, line in enumerate(lines):
        match = re.match(r"^(\s*)-\s+(name|uses|run|id):", line)
        if match:
            starts.append((index, len(match[1])))
    steps = []
    for position, (start, indent) in enumerate(starts):
        end = starts[position + 1][0] if position + 1 < len(starts) else len(lines)
        # A following job's mapping is not part of the previous job's final step.
        end = next((index for index in range(start + 1, end)
                    if lines[index].strip() and not lines[index].lstrip().startswith("#")
                    and len(lines[index]) - len(lines[index].lstrip()) < indent), end)
        segment = lines[start:end]
        segment[0] = " " * (indent + 2) + segment[0].lstrip()[2:]
        step = {}
        index = 0
        while index < len(segment):
            line = segment[index]
            if not line.strip() or line.lstrip().startswith("#"):
                index += 1
                continue
            match = re.match(r"^(\s*)([\w-]+):\s*(.*)$", line)
            supported(match is not None and len(match[1]) == indent + 2,
                      "unsupported workflow step layout")
            key, value = match.group(2), match.group(3)
            index += 1
            nested = []
            while index < len(segment) and (not segment[index].strip() or
                                           len(segment[index]) - len(segment[index].lstrip()) > indent + 2):
                nested.append(segment[index])
                index += 1
            if value in {"|", "|-", "|+"}:
                nonempty = [len(row) - len(row.lstrip()) for row in nested if row.strip()]
                trim = min(nonempty) if nonempty else indent + 4
                step[key] = "\n".join(row[trim:] for row in nested).rstrip() + "\n"
            elif key in {"with", "env"} and not value:
                mapping = {}
                for row in nested:
                    if not row.strip() or row.lstrip().startswith("#"):
                        continue
                    item = re.match(r"^\s*([\w-]+):\s*(.+)$", row)
                    supported(item is not None, "unsupported workflow mapping")
                    mapping[item[1]] = scalar(item[2])
                step[key] = mapping
            else:
                supported(not nested or not any(row.strip() for row in nested),
                          "unsupported workflow scalar continuation")
                step[key] = scalar(value)
        step["_job"] = job_context(lines, start)
        steps.append(step)
    return steps


def expand_github(value, context, env):
    def substitute(match):
        expression = match[1].strip()
        parts = [part.strip() for part in expression.split("||")]
        values = []
        for part in parts:
            if part.startswith("env."):
                supported(re.fullmatch(r"env\.[A-Za-z_][A-Za-z0-9_-]*", part),
                          f"unsupported workflow expression: {part}")
                # GitHub evaluates a missing property as an empty string. A
                # missing pin handoff must not be replaced with the expected pin.
                values.append(env.get(part[4:], ""))
            else:
                supported(part in context, f"unsupported workflow expression: {part}")
                values.append(context[part])
        return next((item for item in values if item), "")
    return re.sub(r"\$\{\{(.*?)\}\}", substitute, value)


def workflow_environment(layer, context, inherited):
    supported(isinstance(layer, dict) and all(isinstance(value, str) for value in layer.values()),
              "unsupported workflow environment mapping")
    supported(not any(key.startswith(("GITHUB_", "RUNNER_")) for key in layer),
              "unsupported override of runner-provided environment")
    # Entries in one env mapping do not become available to sibling entries.
    return {**inherited, **{key: expand_github(value, context, inherited) for key, value in layer.items()}}


def github_environment_file(path):
    """Read the bounded single-line file-command grammar after a real step."""
    supported(not path.is_symlink() and path.is_file() and path.stat().st_size <= 64 * 1024,
              "unsupported GITHUB_ENV file")
    updates = {}
    rows = path.read_text().splitlines()
    supported(len(rows) <= 256, "GITHUB_ENV exceeds the supported entry budget")
    for row in rows:
        if not row:
            continue
        match = re.fullmatch(r"([A-Za-z_][A-Za-z0-9_]*)=(.*)", row)
        supported(match is not None, "unsupported GITHUB_ENV command (only single-line assignments are modeled)")
        key, value = match.groups()
        supported(not key.startswith(("GITHUB_", "RUNNER_")) and key != "NODE_OPTIONS",
                  "unsupported GITHUB_ENV reserved-variable update")
        updates[key] = value
    return updates


def clone_source(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    source_files(source)
    command(target.parent, ["git", "clone", "--shared", "--no-checkout", "--quiet", "--", str(source), str(target)])
    git(target, "checkout", "--detach", "--quiet", git(source, "rev-parse", "HEAD"))


@cancellation_scope()
def check_source_import(hook, root, source):
    """New trust-boundary control: clean Git status does not isolate imports."""
    with tempfile.TemporaryDirectory(prefix="tugling-enforcement-import-") as directory:
        owned = Path(directory).resolve()
        alternate = owned / "source"
        clone_source(source, alternate)
        module = alternate / HELPER.with_name("json.py")
        supported(not module.exists(), "source already contains the import-control module path")
        marker = owned / "ignored-module-executed"
        module.write_text("with open(" + repr(str(marker)) + ", 'w') as stream:\n"
                          "    stream.write('executed')\n"
                          "raise RuntimeError('synthetic ignored-module substitution')\n")
        with (alternate / ".git/info/exclude").open("a") as file:
            file.write("\n/" + str(module.relative_to(alternate)) + "\n")
        require(not git(alternate, "status", "--porcelain=v1", "--untracked-files=all"),
                "ignored import control unexpectedly dirtied source status")
        prior = receipt_paths(root)
        result = run_gate(hook, root, alternate)
        require(not marker.exists(), "ignored source module executed before helper isolation")
        if result["returncode"] == 0:
            require_receipt(hook, root, alternate, exclude=prior)
        return "source_rejected" if result["returncode"] else "isolated_helper_passed"


@cancellation_scope()
def check_replacement_source(hook, root, source):
    """New trust-boundary control: a pinned name must select raw Git objects."""
    with tempfile.TemporaryDirectory(prefix="tugling-enforcement-replace-") as directory:
        owned = Path(directory).resolve()
        alternate = owned / "source"
        clone_source(source, alternate)
        revision = git(alternate, "rev-parse", "HEAD")
        marker = owned / "replacement-helper-executed"
        (alternate / HELPER).write_text("with open(" + repr(str(marker)) + ", 'w') as stream:\n"
                                       "    stream.write('executed')\n"
                                       "raise RuntimeError('synthetic Git replacement substitution')\n")
        git(alternate, "add", str(HELPER))
        tree = git(alternate, "write-tree")
        replacement = git(alternate, "-c", "user.name=Synthetic Oracle", "-c", "user.email=oracle@example.invalid",
                          "commit-tree", tree, "-p", revision, "-m", "Synthetic replacement control")
        git(alternate, "replace", revision, replacement)
        # Deliberately observe what a replacement-aware, status-only guard sees.
        status = command(alternate, ["git", "status", "--porcelain=v1", "--untracked-files=all"])["output"]
        require(not status.strip(), "replacement-aware source status unexpectedly differs")
        aware = command(alternate, ["git", "rev-parse", f"{revision}:{HELPER}"])["output"].strip()
        require(aware != git(alternate, "rev-parse", f"{revision}:{HELPER}"),
                "Git replacement control did not substitute the pinned helper object")
        # Do not supply a reviewer/caller environment setting that hides this
        # trust defect. The launcher must force raw-object reads itself.
        gate = {**hook["gate"], "env": {key: value for key, value in hook["gate"].get("env", {}).items()
                                      if key != "GIT_NO_REPLACE_OBJECTS"}}
        result = run_gate({**hook, "gate": gate}, root, alternate)
        require(result["returncode"] != 0 and not marker.exists(),
                "Git replacement helper was accepted or executed before raw-object validation")


def checkout_path(workspace, value):
    relative = Path(value or ".")
    supported(not relative.is_absolute() and ".." not in relative.parts and "${{" not in str(relative),
              "unsupported checkout path")
    return workspace / relative


@cancellation_scope()
def check_ci(hook, root, source):
    config = hook["ci"]
    path = root / config["workflow"]
    require(path.resolve() in [root / name for name in source_files(root)], "CI workflow is not intended source")
    text = path.read_text()
    steps = workflow_steps(text)
    checkout = steps[config["checkout_step"]]
    workflow_policy(text, checkout["_job"])
    assertion = steps[config["identity_step"]]
    supported("gate_step" in config, "reviewer must bind the actual CI required gate step")
    require(type(config["gate_step"]) is int and 0 <= config["gate_step"] < len(steps), "CI required gate step is missing")
    gate = steps[config["gate_step"]]
    pr_revision = config.get("pr_revision")
    supported(pr_revision in {"head", "merge"}, "reviewer must declare the accepted PR head or merge identity")
    require(checkout.get("uses", "").startswith("actions/checkout@"), "CI checkout hook does not select checkout")
    require(config["checkout_step"] < config["identity_step"], "CI identity assertion precedes checkout")
    require(config["identity_step"] <= config["gate_step"], "CI required gate precedes identity verification")
    for selected in (checkout, assertion, gate):
        supported(selected["_job"]["id"] == checkout["_job"]["id"], "unsupported CI proof across separate jobs")
        unconditional(selected["_job"]["fields"], "CI required job")
        unconditional(selected, "CI selected step")
    supported(not {"needs", "strategy"}.intersection(checkout["_job"]["fields"]),
              "unsupported CI dependency or matrix topology")
    # Never substitute the oracle host for an unmodeled job runtime or policy.
    # In particular, containers change both installed tools and shell defaults.
    supported(set(checkout["_job"]["fields"]) <= {
        "name", "runs-on", "steps", "env", "permissions", "if", "continue-on-error", "timeout-minutes",
    }, "unsupported CI job runtime or policy")
    job_timeout = timeout_seconds(checkout["_job"]["fields"])
    supported(re.fullmatch(r"ubuntu-(?:latest|\d{2}\.\d{2})", checkout["_job"]["fields"].get("runs-on", "")),
              "CI proof requires a supported Linux runner")
    ref = checkout.get("with", {}).get("ref")
    require(isinstance(ref, str) and ref.strip(), "CI project checkout has no explicit revision")
    for selected in (assertion, gate):
        require(isinstance(selected.get("run"), str) and selected["run"].strip(), "CI selected step needs executable run content")
    supported("source_checkout_step" in config, "reviewer must bind CI's actual pinned source checkout")
    source_step = steps[config["source_checkout_step"]]
    require(source_step.get("uses", "").startswith("actions/checkout@") and
            config["checkout_step"] != config["source_checkout_step"] < config["gate_step"],
            "source checkout hook must precede CI execution")
    supported(source_step["_job"]["id"] == checkout["_job"]["id"], "unsupported CI source checkout across jobs")
    source_with = source_step.get("with", {})
    adapter = json.loads((root / hook.get("config", ".tugling/project.json")).read_text())
    repository = adapter["tugling"]["repository"].removeprefix("https://github.com/").rstrip("/").removesuffix(".git")
    revision = git(source, "rev-parse", "HEAD")
    require(adapter["tugling"]["revision"] == revision, "adapter differs from the reviewed source revision")
    selected_steps = [(index, step) for index, step in enumerate(steps[:config["gate_step"] + 1])
                      if step["_job"]["id"] == checkout["_job"]["id"]]
    supported(len(selected_steps) <= 32, "CI job exceeds the supported step budget")
    declared_python_versions = []
    required_indices = {config[key] for key in ("checkout_step", "source_checkout_step", "identity_step", "gate_step")}
    for index, step in selected_steps:
        common = {"_job", "name", "id", "env", "if", "continue-on-error", "timeout-minutes"}
        specific = {"run", "working-directory", "shell"} if "run" in step else {"uses", "with"}
        supported(set(step) <= common | specific, "unsupported CI step runtime or policy")
        timeout_seconds(step)
        if index in required_indices:
            unconditional(step, "CI selected step")
        else:
            # Optional preparation steps can legitimately be conditional. Until
            # their branches are modeled, do not call that a failed required gate.
            supported(not {"if", "continue-on-error"}.intersection(step),
                      "unsupported CI preparation condition or failure policy")
        if index in {config["checkout_step"], config["source_checkout_step"]}:
            inputs = step.get("with", {})
            allowed = {"ref", "path", "persist-credentials"}
            if index == config["source_checkout_step"]:
                allowed.add("repository")
            supported(set(inputs) <= allowed, "unsupported CI checkout materialization inputs")
            continue
        if "run" in step:
            supported(step.get("shell", "bash") in {"bash", "sh", "bash --noprofile --norc -e -o pipefail {0}"},
                      "unsupported CI execution shell")
        else:
            # Runtime provisioning is declared, never downloaded or represented
            # as host/runtime parity by this offline command diagnostic.
            inputs = step.get("with", {})
            supported(step.get("uses", "").startswith("actions/setup-python@") and
                      set(inputs) == {"python-version"} and
                      re.fullmatch(r"3\.\d+(?:\.\d+)?", inputs["python-version"]),
                      "unsupported CI action or runtime provisioning inputs")
            declared_python_versions.append(inputs["python-version"])

    def control(event, *, matches=True, defect=False):
        # No environment file, source checkout or receipt survives into another
        # control. Each observed pin must be produced by this job's real steps.
        with tempfile.TemporaryDirectory(prefix="tugling-enforcement-ci-") as directory:
            job_deadline = time.monotonic() + job_timeout if job_timeout else None
            owned = Path(directory).resolve()
            workspace = owned / "workspace"
            project = checkout_path(workspace, checkout.get("with", {}).get("path", "."))
            project.parent.mkdir(parents=True, exist_ok=True)
            copy_source(root, project)
            if defect:
                product = project / "quota_sync.py"
                product.write_text(product.read_text().replace("POLL_SECONDS = 30", "POLL_SECONDS = 1"))
                commit(project)
            head = git(project, "rev-parse", "HEAD")
            other = "f" * 40 if head != "f" * 40 else "e" * 40
            expected = head if matches else other
            context = {"github.event.pull_request.head.sha": "", "github.sha": expected,
                       "github.workspace": str(workspace)}
            if event == "pull_request":
                context["github.event.pull_request.head.sha"] = expected if pr_revision == "head" else other
                context["github.sha"] = expected if pr_revision == "merge" else other
            job = checkout["_job"]
            variables = workflow_environment(job["workflow_env"], context, {})
            variables = workflow_environment(job["env"], context, variables)
            ci_source = None
            project_checked_out = False
            for index, step in selected_steps:
                supported(job_deadline is None or time.monotonic() < job_deadline, "CI declared job timeout expired")
                step_timeout = timeout_seconds(step)
                deadlines = ([job_deadline] if job_deadline is not None else [])
                if step_timeout:
                    deadlines.append(time.monotonic() + step_timeout)
                step_deadline = min(deadlines) if deadlines else None
                env = workflow_environment(step.get("env", {}), context, variables)
                if index == config["checkout_step"]:
                    require(expand_github(ref, context, env) == expected,
                            f"CI checkout does not select the intended {event} revision")
                    project_checked_out = True
                elif index == config["source_checkout_step"]:
                    require(expand_github(source_with.get("repository", ""), context, env).lower() == repository.lower(),
                            "CI source checkout repository differs from the accepted adapter source")
                    require(expand_github(source_with.get("ref", ""), context, env) == revision,
                            "CI source checkout must select the reviewed candidate revision")
                    ci_source = checkout_path(workspace, source_with.get("path", "."))
                    supported(ci_source != project and not ci_source.exists(), "overlapping CI checkout paths")
                    clone_source(source, ci_source)
                elif "run" in step:
                    supported(project_checked_out, "unsupported shell execution before project checkout")
                    working = expand_github(step.get("working-directory", "."), context, env)
                    cwd = (workspace / working).resolve()
                    supported(cwd == project, "CI execution directory does not resolve to the selected project checkout")
                    env_file = owned / f"environment-{index}"
                    env_file.touch()
                    runtime = {"CI": "true", **env, "GITHUB_SHA": context["github.sha"], "GITHUB_EVENT_NAME": event,
                               "GITHUB_WORKSPACE": str(workspace), "GITHUB_ENV": str(env_file)}
                    shell = step.get("shell")
                    shell_argv = (["sh", "-e"] if shell == "sh" else
                                  ["bash", "--noprofile", "--norc", "-e", "-o", "pipefail"] if shell else
                                  ["bash", "-e"])
                    prior = receipt_paths(project)
                    result = command(cwd, shell_argv + ["-c", expand_github(step["run"], context, env)],
                                     extra=runtime, success=False, expires_at=step_deadline)
                    require(not result["forced_cleanup"], "CI command left a running owned child after exit")
                    if index == config["identity_step"] and not (defect and index == config["gate_step"]):
                        require((result["returncode"] == 0) == matches,
                                f"CI identity assertion failed its {event} {'matching' if matches else 'mismatched'} revision control: "
                                + result["output"][-1500:])
                        if not matches:
                            return
                    if index == config["gate_step"]:
                        require(ci_source is not None, "CI gate ran before its reviewed source checkout")
                        if defect:
                            require(result["returncode"] != 0,
                                    f"CI required gate swallowed a real native failure for {event}")
                        else:
                            require(result["returncode"] == 0, "CI required gate failed: " + result["output"][-1500:])
                            require_receipt(hook, project, ci_source, exclude=prior)
                        return
                    require(result["returncode"] == 0, "CI preparation step failed: " + result["output"][-1500:])
                    variables.update(github_environment_file(env_file))
            raise Inconclusive("CI control did not reach its bound identity or gate")

    for event in ("pull_request", "push"):
        control(event)
        control(event, matches=False)
        control(event, defect=True)
    return {"workflow": config["workflow"], "local_identity_controls": 4,
            "fresh_required_receipts": 2, "native_failure_propagated": True,
            "native_failure_events": ["pull_request", "push"],
            "pull_request_identity": pr_revision, "hosted_ci_executed": False,
            "host_python_version": sys.version.split()[0], "declared_python_versions": declared_python_versions,
            "runtime_provisioned": False}


@cancellation_scope()
def verify(root, hook):
    require(hook.get("schema_version") == 1, "unsupported reviewer invocation schema")
    source = Path(hook["source_root"]).resolve()
    require(Path(git(source, "rev-parse", "--show-toplevel")).resolve() == source,
            "reviewed source must be its actual Git root")
    revision = git(source, "rev-parse", "HEAD")
    require(not git(source, "status", "--porcelain=v1", "--untracked-files=all"),
            "reviewed candidate source must be clean and committed")
    require((source / HELPER).is_file(), "reviewed source helper missing")
    preserve_contract(root)
    before = tree_snapshot(root)
    checks = []
    with tempfile.TemporaryDirectory(prefix="tugling-enforcement-oracle-") as directory:
        owned = Path(directory).resolve()
        good = owned / "good"
        copy_source(root, good)
        require(run_gate(hook, good, source)["returncode"] == 0, "good implementation failed required gate")
        require_receipt(hook, good, source)
        checks.append("good_required_gate")
        checks.append("existing_product_and_assertions_preserved")
        for defect in ("request-budget", "owned-cleanup", "missing-case", "skipped-case"):
            mutant = owned / defect
            copy_source(root, mutant)
            if defect in {"request-budget", "owned-cleanup"}:
                path = mutant / "quota_sync.py"
                old, new = (("POLL_SECONDS = 30", "POLL_SECONDS = 1") if defect == "request-budget"
                            else ("            owned.unlink()", "            pass"))
                require(old in path.read_text(), "fixture mutation anchor missing")
                path.write_text(path.read_text().replace(old, new))
            else:
                alter_case(mutant, "test_shared_request_budget", skip=defect == "skipped-case")
            commit(mutant)
            require(run_gate(hook, mutant, source)["returncode"] != 0, f"required gate accepted {defect}")
            checks.append(defect + "_rejected")
            if defect == "request-budget":
                # This is a real focused pass alongside a required failure.
                command(mutant, ["make", "test", "TEST_ARGS=tests.test_service.ServiceTests.test_idle_workload_makes_no_calls"])
                for selected in ("tests.test_service.ServiceTests.test_idle_workload_makes_no_calls", "-k no_such_case"):
                    result = run_gate(hook, mutant, source, extra={"TEST_ARGS": selected})
                    require(result["returncode"] != 0, "focused/empty selection bypassed required completion")
                checks.append("focused_pass_full_required_fail")
                checks.append("test_selection_cannot_bypass_required_gate")
        # Native-runner selection supplied on Make's command line has different
        # precedence from environment variables; exercise that actual path too.
        argv, env = invocation(hook, good, source)
        if Path(argv[0]).name in {"make", "gmake"}:
            broken = owned / "request-budget"
            argv, env = invocation(hook, broken, source)
            result = command(broken, argv + ["TEST_ARGS=-k no_such_case"], extra=env, success=False)
            require(result["returncode"] != 0, "Make command-line test selection bypassed required completion")
            checks.append("make_selection_cannot_bypass_required_gate")

        # Clone only this reviewed local source; no remote/network access. Shared
        # object reads avoid another full object database and remain read-only.
        alternate = owned / "candidate-copy"
        clone_source(source, alternate)
        sentinel = owned / "spoof-executed"
        spoof = "from pathlib import Path\nPath(" + repr(str(sentinel)) + ").write_text('executed')\nraise SystemExit(0)\n"
        nested = alternate / "ignored-source"
        (nested / HELPER).parent.mkdir(parents=True)
        (nested / HELPER).write_text(spoof)
        with (alternate / ".git/info/exclude").open("a") as file:
            file.write("\n/ignored-source/\n")
        require(not git(alternate, "status", "--porcelain=v1"), "ignored-source control unexpectedly dirtied source")
        require(run_gate(hook, good, nested)["returncode"] != 0 and not sentinel.exists(),
                "ignored nested helper was accepted or executed before source validation")
        checks.append("ignored_nested_source_rejected_before_execution")
        (alternate / HELPER).write_text(spoof)
        # A status-only guard can miss changed bytes hidden by this index flag.
        # The flag is set only in this owned disposable source clone.
        git(alternate, "update-index", "--assume-unchanged", "--", str(HELPER))
        require(not git(alternate, "status", "--porcelain=v1", "--untracked-files=all"),
                "masked helper control unexpectedly dirtied source status")
        require(run_gate(hook, good, alternate)["returncode"] != 0 and not sentinel.exists(),
                "mismatched helper was accepted or executed before source validation")
        checks.append("mismatched_helper_rejected_before_execution")
        import_control = check_source_import(hook, good, source)
        checks.append("ignored_source_import_did_not_execute")
        check_replacement_source(hook, good, source)
        checks.append("replacement_objects_cannot_substitute_helper")
        ci = check_ci(hook, good, source)
        checks.append("ci_revision_identity_controls")
        require(run_gate(hook, good, source)["returncode"] == 0, "restored good gate failed")
        checks.append("restored_good_required_gate")
    require(tree_snapshot(root) == before, "oracle changed caller project")
    return {"schema_version": 1, "state": "LOCAL_ENFORCEMENT_PASS", "checks": checks,
            "source_revision": revision, "native_resource": "fake-third-party-request-quota",
            "source_import_control": import_control,
            "ci": ci, "model_calls": 0, "release_certification": False}


@cancellation_scope()
def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    prepare_parser = sub.add_parser("prepare")
    prepare_parser.add_argument("--out", type=Path, required=True)
    snapshot_parser = sub.add_parser("snapshot")
    snapshot_parser.add_argument("--repo", type=Path, required=True)
    assess_parser = sub.add_parser("assess")
    assess_parser.add_argument("--repo", type=Path, required=True)
    assess_parser.add_argument("--before", type=Path, required=True)
    verify_parser = sub.add_parser("verify")
    verify_parser.add_argument("--repo", type=Path, required=True)
    verify_parser.add_argument("--invocation", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "prepare":
            prepare(args.out.resolve())
            result = {"state": "FIXTURE_READY"}
        elif args.command == "snapshot":
            result = tree_snapshot(args.repo.resolve())
        elif args.command == "assess":
            require(tree_snapshot(args.repo.resolve()) == json.loads(args.before.read_text()),
                    "assessment changed project files or Git state")
            result = {"state": "ADVISORY_ZERO_CHANGE"}
        else:
            result = verify(args.repo.resolve(), json.loads(args.invocation.read_text()))
    except (Cancelled, KeyboardInterrupt) as exc:
        print(json.dumps({"state": "ORACLE_INCONCLUSIVE", "error": "cancelled; owned execution cleaned up"}))
        return exc.code if isinstance(exc, Cancelled) else 130
    except AssertionError as exc:
        print(json.dumps({"state": "ORACLE_FAIL", "error": str(exc)}))
        return 1
    except (Inconclusive, KeyError, IndexError, OSError, ValueError, subprocess.SubprocessError) as exc:
        print(json.dumps({"state": "ORACLE_INCONCLUSIVE", "error": str(exc)}))
        return 2
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
