#!/usr/bin/env python3
"""Independent local oracle for first-time native enforcement setup.

The reviewer supplies invocation bindings after reading the completed setup.
Neither the task prompt nor its project contains this oracle or its mutations.
"""

from __future__ import annotations

import argparse
import ast
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


class Inconclusive(RuntimeError):
    """The evaluator cannot establish the requested proof boundary."""


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


def stop_group(process):
    """Stop only the process group this invocation created, including orphans."""
    try:
        os.killpg(process.pid, 0)
    except ProcessLookupError:
        return False
    os.killpg(process.pid, signal.SIGTERM)
    deadline = time.monotonic() + 0.5
    while time.monotonic() < deadline:
        process.poll()
        try:
            os.killpg(process.pid, 0)
        except ProcessLookupError:
            return True
        time.sleep(0.02)
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.wait(timeout=5)
    return True


def command(root, argv, *, extra=None, success=True):
    """Bound output and terminate only this command's owned process group."""
    with tempfile.TemporaryFile() as output:
        process = subprocess.Popen(argv, cwd=root, env=environment(extra),
                                   stdout=output, stderr=subprocess.STDOUT, start_new_session=True)
        deadline = time.monotonic() + TIMEOUT_SECONDS
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
    return command(root, ["git", *args])["output"].strip()


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


def require_receipt(hook, root, source):
    """Check native integration with the reviewed helper, not a printed label."""
    argv = [sys.executable, str(source / HELPER), "--repo", str(root),
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
    receipts = sorted((root / ".tugling/local/verification").glob("*.json"))
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
        steps.append(step)
    return steps


def expand_github(value, context, env):
    def substitute(match):
        expression = match[1].strip()
        parts = [part.strip() for part in expression.split("||")]
        values = []
        for part in parts:
            if part.startswith("env."):
                supported(part[4:] in env, f"unresolved workflow environment: {part}")
                values.append(env[part[4:]])
            else:
                supported(part in context, f"unsupported workflow expression: {part}")
                values.append(context[part])
        return next((item for item in values if item), "")
    return re.sub(r"\$\{\{(.*?)\}\}", substitute, value)


def clone_source(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    source_files(source)
    command(target.parent, ["git", "clone", "--shared", "--no-checkout", "--quiet", "--", str(source), str(target)])
    git(target, "checkout", "--detach", "--quiet", git(source, "rev-parse", "HEAD"))


def checkout_path(workspace, value):
    relative = Path(value or ".")
    supported(not relative.is_absolute() and ".." not in relative.parts and "${{" not in str(relative),
              "unsupported checkout path")
    return workspace / relative


def check_ci(hook, root, source):
    config = hook["ci"]
    path = root / config["workflow"]
    require(path.resolve() in [root / name for name in source_files(root)], "CI workflow is not intended source")
    text = path.read_text()
    require(not re.search(r"(?:contents|actions|id-token|pull-requests):\s*write\b", text),
            "fixture CI must remain unprivileged")
    steps = workflow_steps(text)
    checkout = steps[config["checkout_step"]]
    assertion = steps[config["identity_step"]]
    pr_revision = config.get("pr_revision")
    supported(pr_revision in {"head", "merge"}, "reviewer must declare the accepted PR head or merge identity")
    require(checkout.get("uses", "").startswith("actions/checkout@"), "CI checkout hook does not select checkout")
    require(config["checkout_step"] < config["identity_step"], "CI identity assertion precedes checkout")
    for selected in (checkout, assertion):
        require("continue-on-error" not in selected and "if" not in selected,
                "CI identity proof must be unconditional and fail closed")
    ref = checkout.get("with", {}).get("ref")
    require(isinstance(ref, str) and ref.strip(), "CI project checkout has no explicit revision")
    script = assertion.get("run")
    require(isinstance(script, str) and script.strip(), "CI identity hook needs executable run content")
    supported(assertion.get("shell", "bash") in {"bash", "sh", "bash --noprofile --norc -e -o pipefail {0}"},
              "unsupported CI identity shell")
    with tempfile.TemporaryDirectory(prefix="tugling-enforcement-ci-") as directory:
        workspace = Path(directory).resolve() / "workspace"
        project = checkout_path(workspace, checkout.get("with", {}).get("path", "."))
        project.parent.mkdir(parents=True, exist_ok=True)
        copy_source(root, project)
        ci_source = source
        if "source_checkout_step" in config:
            source_step = steps[config["source_checkout_step"]]
            require(source_step.get("uses", "").startswith("actions/checkout@") and
                    config["source_checkout_step"] < config["identity_step"],
                    "source checkout hook must precede CI execution")
            source_with = source_step.get("with", {})
            require(source_with.get("ref") == git(source, "rev-parse", "HEAD"),
                    "CI source checkout must select the reviewed candidate revision")
            ci_source = checkout_path(workspace, source_with.get("path", "."))
            supported(ci_source != project and not ci_source.exists(), "overlapping CI checkout paths")
            clone_source(source, ci_source)
        head = git(project, "rev-parse", "HEAD")
        other = "f" * 40 if head != "f" * 40 else "e" * 40
        _, gate_env = invocation(hook, project, ci_source)
        for event in ("pull_request", "push"):
            for matches in (True, False):
                expected = head if matches else other
                context = {"github.event.pull_request.head.sha": "",
                           "github.sha": expected, "github.workspace": str(workspace)}
                if event == "pull_request":
                    context["github.event.pull_request.head.sha"] = expected if pr_revision == "head" else other
                    context["github.sha"] = expected if pr_revision == "merge" else other
                require(expand_github(ref, context, {}) == expected,
                        f"CI checkout does not select the intended {event} revision")
                env = {**gate_env, "GITHUB_SHA": context["github.sha"], "GITHUB_EVENT_NAME": event,
                       "GITHUB_WORKSPACE": str(workspace)}
                for key, value in assertion.get("env", {}).items():
                    env[key] = expand_github(value, context, env)
                working = expand_github(assertion.get("working-directory", "."), context, env)
                cwd = (workspace / working).resolve()
                supported(cwd == project, "CI execution directory does not resolve to the selected project checkout")
                result = command(cwd, ["bash", "-e", "-o", "pipefail", "-c", expand_github(script, context, env)],
                                 extra=env, success=False)
                require(not result["forced_cleanup"], "CI command left a running owned child after exit")
                require((result["returncode"] == 0) == matches,
                        f"CI identity assertion failed its {event} {'matching' if matches else 'mismatched'} revision control: "
                        + result["output"][-1500:])
    return {"workflow": config["workflow"], "local_identity_controls": 4,
            "pull_request_identity": pr_revision, "hosted_ci_executed": False}


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
        ci = check_ci(hook, good, source)
        checks.append("ci_revision_identity_controls")
        require(run_gate(hook, good, source)["returncode"] == 0, "restored good gate failed")
        checks.append("restored_good_required_gate")
    require(tree_snapshot(root) == before, "oracle changed caller project")
    return {"schema_version": 1, "state": "LOCAL_ENFORCEMENT_PASS", "checks": checks,
            "source_revision": revision, "native_resource": "fake-third-party-request-quota",
            "ci": ci, "model_calls": 0, "release_certification": False}


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
