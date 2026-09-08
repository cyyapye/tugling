#!/usr/bin/env python3
"""Promote reviewed release data without checking out or executing candidate code.

Invoke this file from the separately approved controller checkout with python -I.
The CLI targets only this public repository. Tests exercise the same Git
transaction against disposable local bare remotes.
"""

from __future__ import annotations

import base64
import hashlib
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
CONTROLLER_TAG = re.compile(r"controller-[A-Za-z0-9][A-Za-z0-9._-]{0,100}")
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
    # These repositories are disposable. Background maintenance must not
    # outlive the command and race with TemporaryDirectory cleanup.
    result = subprocess.run(
        ["git", "-c", "maintenance.auto=false", "-c", f"core.hooksPath={os.devnull}", *args], cwd=root,
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


def materialize_data(root: Path, candidate: str, destination: Path) -> None:
    entries = {
        name: value for name, value in tree(root, candidate).items()
        if name.startswith("plugins/tugling/") or name == ".agents/plugins/marketplace.json"
    }
    if not entries or len(entries) > MAX_DATA_FILES:
        raise ControllerError("candidate package missing or data file limit exceeded")
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
    certificate_path: Path, certificate_digest: str, certification_controller: str,
    apply: bool = False, token: str = "",
) -> dict[str, Any]:
    """Publish using evidence already authenticated by promote_release.py.

    This transaction helper is deliberately not a command-line entrypoint. The
    production caller verifies CI provenance before supplying certificate bytes.
    """
    validate_request(controller, candidate, version, certificate_digest)
    if not SHA.fullmatch(certification_controller):
        raise ControllerError("certification controller must be a full lowercase commit SHA")
    if (certificate_path.is_symlink() or not certificate_path.is_file()
            or certificate_path.stat().st_size > 256 * 1024):
        raise ControllerError("certificate must be bounded regular JSON")
    env = git_env(token)
    with tempfile.TemporaryDirectory(prefix="tugling-controller-") as directory:
        scratch = Path(directory)
        repository = scratch / "objects.git"
        repository.mkdir()
        git(repository, "init", "--bare", "--template=", ".")
        git(repository, "remote", "add", "origin", remote)
        git(repository, "fetch", "--no-tags", "origin", controller, certification_controller,
            "refs/heads/main:refs/heads/main", "refs/heads/stable:refs/heads/stable", env=env)
        if text_git(repository, "rev-parse", "refs/heads/main") != candidate:
            raise ControllerError("candidate is no longer exact current main")
        require_reviewed_ruler(repository, controller, candidate)
        require_reviewed_ruler(repository, certification_controller, candidate)
        git(repository, "merge-base", "--is-ancestor", controller, candidate)
        git(repository, "merge-base", "--is-ancestor", certification_controller, candidate)
        source = scratch / "candidate-data"
        materialize_data(repository, candidate, source)
        if hashlib.sha256(certificate_path.read_bytes()).hexdigest() != certificate_digest:
            raise ControllerError("certificate differs from the reviewed attested digest")
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
        if evaluated != candidate or certificate["clean_room"].get("revision") != candidate:
            raise ControllerError("certificate must evaluate this exact candidate commit")
        git(repository, "merge-base", "--is-ancestor", baseline, candidate)
        tag = f"refs/tags/v{version}"
        refs = remote_refs(repository, version, env)
        if refs.get("refs/heads/main") != candidate:
            raise ControllerError("main moved during verification; certify and review the new candidate")
        tag_target = refs.get(f"{tag}^{{}}", refs.get(tag))
        report = {"candidate_sha": candidate, "controller_sha": controller, "version": version,
                  "certification_controller_sha": certification_controller,
                  "certificate_sha256": certificate_digest, "stable_baseline": baseline}
        if tag_target is not None:
            if refs.get(f"{tag}^{{}}") == candidate and refs.get("refs/heads/stable") == candidate:
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


if __name__ == "__main__":
    raise SystemExit("Use python3 -I scripts/promote_release.py; CI attestation verification is required")
