#!/usr/bin/env python3
"""Promote reviewed release data without checking out or executing candidate code.

Invoke this file from the separately approved controller checkout with python -I.
The CLI targets only this public repository. Tests exercise the same Git
transaction against disposable local bare remotes.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any

# -I excludes the working directory and PYTHONPATH. Only this trusted scripts
# directory is added; candidate modules are never on the import path.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import clean_room_install as clean_room
import release_gate as gate

REMOTE = "https://github.com/cyyapye/tugling.git"
SHA = re.compile(r"[0-9a-f]{40}")
DIGEST = re.compile(r"[0-9a-f]{64}")
VERSION = re.compile(r"(?:0|[1-9][0-9]*)(?:\.(?:0|[1-9][0-9]*)){2}")
MAX_DATA_BYTES = 16 * 1024 * 1024
MAX_DATA_FILES = 2000


class ControllerError(RuntimeError):
    """A request is unreviewed, stale, conflicting, or could not be confirmed."""


def git_env(token: str = "") -> dict[str, str]:
    env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull, GIT_TERMINAL_PROMPT="0")
    if token:
        authorization = base64.b64encode(f"x-access-token:{token}".encode()).decode()
        env.update(
            GIT_CONFIG_COUNT="1",
            GIT_CONFIG_KEY_0="http.https://github.com/.extraheader",
            GIT_CONFIG_VALUE_0=f"AUTHORIZATION: basic {authorization}",
        )
    return env


def git(root: Path, *args: str, env: dict[str, str] | None = None) -> bytes:
    result = subprocess.run(
        ["git", "-c", f"core.hooksPath={os.devnull}", *args], cwd=root,
        env=env if env is not None else git_env(), stdin=subprocess.DEVNULL,
        capture_output=True, timeout=120, check=False,
    )
    if result.returncode:
        # Do not print subprocess diagnostics from an authenticated command.
        raise ControllerError(f"git {args[0]} failed (exit {result.returncode}); inspect remote refs before retrying")
    return result.stdout


def text_git(root: Path, *args: str, env: dict[str, str] | None = None) -> str:
    return git(root, *args, env=env).decode().strip()


def tree(root: Path, revision: str) -> dict[str, tuple[str, str]]:
    entries = {}
    for record in git(root, "ls-tree", "-rz", "--full-tree", revision).split(b"\0"):
        if record:
            metadata, name = record.split(b"\t", 1)
            mode, _kind, oid = metadata.decode().split()
            entries[name.decode()] = (mode, oid)
    return entries


def ruler_path(name: str) -> bool:
    return name == "Makefile" or name.startswith((".github/", ".agents/", "scripts/", "tests/")) or (
        name.startswith("evals/") and not name.startswith("evals/releases/")
    )


def require_reviewed_ruler(root: Path, controller: str, candidate: str) -> None:
    approved = {name: value for name, value in tree(root, controller).items() if ruler_path(name)}
    proposed = {name: value for name, value in tree(root, candidate).items() if ruler_path(name)}
    if approved != proposed:
        raise ControllerError("grading or release machinery changed; separately review and pin a new controller")


def materialize_data(root: Path, candidate: str, version: str, destination: Path) -> Path:
    certificate_name = f"evals/releases/v{version}/certificate.json"
    entries = {
        name: value for name, value in tree(root, candidate).items()
        if name.startswith("plugins/tugling/") or name in {".agents/plugins/marketplace.json", certificate_name}
    }
    if certificate_name not in entries or len(entries) > MAX_DATA_FILES:
        raise ControllerError("certificate missing or candidate data file limit exceeded")
    total = 0
    for name, (mode, oid) in entries.items():
        relative = PurePosixPath(name)
        if mode not in {"100644", "100755"} or relative.is_absolute() or ".." in relative.parts:
            raise ControllerError("candidate data must contain only regular files within its package")
        total += int(text_git(root, "cat-file", "-s", oid))
        if total > MAX_DATA_BYTES:
            raise ControllerError("candidate data byte limit exceeded")
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(git(root, "cat-file", "blob", oid))
    return destination / certificate_name


def remote_refs(root: Path, version: str, env: dict[str, str]) -> dict[str, str]:
    output = text_git(root, "ls-remote", "origin", "refs/heads/main", "refs/heads/stable",
                      f"refs/tags/v{version}", f"refs/tags/v{version}^{{}}", env=env)
    return {name: oid for oid, name in (line.split() for line in output.splitlines())}


def validate_request(controller: str, candidate: str, version: str, certificate_digest: str) -> None:
    if not SHA.fullmatch(controller) or not SHA.fullmatch(candidate):
        raise ControllerError("controller and candidate must be full lowercase commit SHAs")
    if not VERSION.fullmatch(version) or not DIGEST.fullmatch(certificate_digest):
        raise ControllerError("version or reviewed certificate SHA256 is invalid")


def promote(
    *, remote: str, controller: str, candidate: str, version: str,
    certificate_digest: str, apply: bool = False, token: str = "",
) -> dict[str, Any]:
    validate_request(controller, candidate, version, certificate_digest)
    env = git_env(token)
    with tempfile.TemporaryDirectory(prefix="tugling-controller-") as directory:
        scratch = Path(directory)
        repository = scratch / "objects.git"
        repository.mkdir()
        git(repository, "init", "--bare", "--template=", ".")
        git(repository, "remote", "add", "origin", remote)
        git(repository, "fetch", "--no-tags", "origin", controller,
            "refs/heads/main:refs/heads/main", "refs/heads/stable:refs/heads/stable", env=env)
        if text_git(repository, "rev-parse", "refs/heads/main") != candidate:
            raise ControllerError("candidate is no longer exact current main")
        require_reviewed_ruler(repository, controller, candidate)
        source = scratch / "candidate-data"
        certificate_path = materialize_data(repository, candidate, version, source)
        if hashlib.sha256(certificate_path.read_bytes()).hexdigest() != certificate_digest:
            raise ControllerError("certificate differs from the manually reviewed digest")
        # Both helpers and their matrix come from the trusted controller, never
        # from candidate-data. The candidate's scripts are not even extracted.
        clean_room.package_report(source)
        certificate = gate.verify_certificate(path=certificate_path, package_source_root=source)
        if certificate["version"] != version:
            raise ControllerError("requested version differs from the certificate")
        baseline = certificate["behavioral"].get("released_revision", "")
        evaluated = certificate["behavioral"].get("evaluated_revision", "")
        if not isinstance(baseline, str) or not SHA.fullmatch(baseline):
            raise ControllerError("certificate stable baseline is invalid")
        if not isinstance(evaluated, str) or not SHA.fullmatch(evaluated):
            raise ControllerError("certificate evaluated revision is invalid")
        git(repository, "merge-base", "--is-ancestor", evaluated, candidate)
        git(repository, "merge-base", "--is-ancestor", baseline, candidate)
        tag = f"refs/tags/v{version}"
        refs = remote_refs(repository, version, env)
        if refs.get("refs/heads/main") != candidate:
            raise ControllerError("main moved during verification; certify and review the new candidate")
        tag_target = refs.get(f"{tag}^{{}}", refs.get(tag))
        report = {"candidate_sha": candidate, "controller_sha": controller, "version": version,
                  "certificate_sha256": certificate_digest, "stable_baseline": baseline}
        if tag_target is not None:
            if tag_target == candidate and refs.get("refs/heads/stable") == candidate:
                return {**report, "state": "ALREADY_PROMOTED"}
            raise ControllerError("version tag already exists in a conflicting or superseded release")
        if refs.get("refs/heads/stable") != baseline:
            raise ControllerError("stable baseline moved; do not reuse this certificate")
        if not apply:
            return {**report, "state": "READY_FOR_REVIEWED_PROMOTION"}
        git(repository, "-c", "user.name=github-actions[bot]", "-c",
            "user.email=41898282+github-actions[bot]@users.noreply.github.com",
            "tag", "--annotate", f"v{version}", "--message", f"Tugling v{version}", candidate)
        # Ancestry above enforces a fast-forward. The explicit lease additionally
        # rejects a concurrent different stable target, even if it would also
        # fast-forward. An already identical target safely converges.
        git(repository, "push", "--atomic", f"--force-with-lease=refs/heads/stable:{baseline}",
            "origin", f"{candidate}:refs/heads/stable", tag, env=env)
        observed = remote_refs(repository, version, env)
        if observed.get("refs/heads/stable") != candidate or observed.get(f"{tag}^{{}}") != candidate:
            raise ControllerError("push outcome is unconfirmed; inspect stable and tag before retrying")
        return {**report, "state": "PROMOTED"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--controller-sha", required=True)
    parser.add_argument("--candidate-sha", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--certificate-sha256", required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    try:
        validate_request(args.controller_sha, args.candidate_sha, args.version, args.certificate_sha256)
        if text_git(ROOT, "rev-parse", "HEAD") != args.controller_sha:
            raise ControllerError("running checkout is not the approved controller SHA")
        if text_git(ROOT, "status", "--porcelain", "--untracked-files=all"):
            raise ControllerError("approved controller checkout must be clean")
        result = promote(remote=REMOTE, controller=args.controller_sha, candidate=args.candidate_sha,
                         version=args.version, certificate_digest=args.certificate_sha256,
                         apply=args.apply, token=os.environ.get("GITHUB_TOKEN", ""))
        print(json.dumps(result, sort_keys=True))
    except (ControllerError, gate.ReleaseGateError, clean_room.CleanRoomError, OSError,
            ValueError, KeyError, TypeError, subprocess.TimeoutExpired) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
