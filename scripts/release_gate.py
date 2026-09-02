#!/usr/bin/env python3
"""Assemble and verify review-gated Tugling release certificates."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins" / "tugling"
MANIFEST = PLUGIN / ".codex-plugin" / "plugin.json"
SUITE = ROOT / "evals" / "behavioral" / "cases.json"
MATRIX = ROOT / "evals" / "behavioral" / "release-matrix.json"
RELEASES = ROOT / "evals" / "releases"
REVISION_RE = re.compile(r"[0-9a-f]{40}")


class ReleaseGateError(RuntimeError):
    """Release evidence is incomplete, stale, or inconsistent."""


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReleaseGateError(f"{path}: {exc}") from exc


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tree_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if "__pycache__" in relative.parts:
            continue
        digest.update(relative.as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def plugin_identity() -> dict[str, Any]:
    manifest = read_json(MANIFEST)
    if not isinstance(manifest, dict):
        raise ReleaseGateError("plugin manifest must be an object")
    version = manifest.get("version")
    if not isinstance(version, str):
        raise ReleaseGateError("plugin manifest version is missing")
    skills = sorted(path.parent.name for path in (PLUGIN / "skills").glob("*/SKILL.md"))
    return {
        "name": manifest.get("name"),
        "version": version,
        "content_sha256": tree_digest(PLUGIN),
        "skills": skills,
    }


def validate_matrix() -> dict[str, Any]:
    matrix = read_json(MATRIX)
    if not isinstance(matrix, dict):
        raise ReleaseGateError("release matrix must be an object")
    expected_keys = {
        "schema_version",
        "minimum_attempts",
        "conditions",
        "required_case_ids",
        "required_skills",
        "project_types",
    }
    if set(matrix) != expected_keys:
        raise ReleaseGateError(
            f"release matrix fields differ: expected {sorted(expected_keys)}, found {sorted(matrix)}"
        )
    if matrix.get("schema_version") != 1:
        raise ReleaseGateError("release matrix schema_version must be 1")
    if not isinstance(matrix.get("minimum_attempts"), int) or matrix["minimum_attempts"] < 3:
        raise ReleaseGateError("release matrix requires at least three attempts")
    if matrix.get("conditions") != ["control", "released", "candidate"]:
        raise ReleaseGateError("release matrix conditions must be control, released, candidate")

    suite = read_json(SUITE)
    cases = suite.get("cases") if isinstance(suite, dict) else None
    if not isinstance(cases, list):
        raise ReleaseGateError("behavioral suite cases are missing")
    case_ids = [case.get("id") for case in cases if isinstance(case, dict)]
    skills = sorted({case.get("skill") for case in cases if isinstance(case, dict)})
    if matrix.get("required_case_ids") != case_ids:
        raise ReleaseGateError("release matrix must list every behavioral case in suite order")
    if matrix.get("required_skills") != skills:
        raise ReleaseGateError("release matrix required_skills must match behavioral coverage")

    project_types = matrix.get("project_types")
    if not isinstance(project_types, dict) or not project_types:
        raise ReleaseGateError("release matrix project_types must be a non-empty object")
    actual_by_type: dict[str, list[str]] = {}
    for case in cases:
        if not isinstance(case, dict):
            continue
        project_type = case.get("project_type")
        if not isinstance(project_type, str) or not project_type:
            raise ReleaseGateError(f"behavioral case {case.get('id')} lacks project_type")
        actual_by_type.setdefault(project_type, []).append(case["id"])
    if project_types != actual_by_type:
        raise ReleaseGateError("release matrix project_types must exactly map the behavioral suite")
    required_breadth = {"python-cli", "python-service", "typescript-worker", "react-ui"}
    if not required_breadth.issubset(project_types):
        raise ReleaseGateError(
            f"release matrix lacks required project breadth: {sorted(required_breadth - set(project_types))}"
        )
    return matrix


def check_pairs(
    *,
    per_case: Any,
    case_ids: list[str],
    attempts: int,
) -> bool:
    if not isinstance(per_case, list):
        return False
    observed = {
        (item.get("case_id"), item.get("attempt"))
        for item in per_case
        if isinstance(item, dict)
    }
    expected = {(case_id, attempt) for case_id in case_ids for attempt in range(1, attempts + 1)}
    return observed == expected and len(per_case) == len(expected)


def assemble_certificate(
    *,
    version: str,
    behavioral_path: Path,
    clean_room_path: Path,
) -> dict[str, Any]:
    matrix = validate_matrix()
    current = plugin_identity()
    behavioral = read_json(behavioral_path)
    clean_room = read_json(clean_room_path)
    if not isinstance(behavioral, dict) or not isinstance(clean_room, dict):
        raise ReleaseGateError("release proof inputs must be objects")
    reproducibility = behavioral.get("reproducibility", {})
    candidate = behavioral.get("candidate", {})
    released = behavioral.get("released", {})
    metrics = behavioral.get("metrics", {})
    surface = behavioral.get("plugin_surface_changes", {})
    privacy = behavioral.get("privacy_scan", {})
    policy = behavioral.get("policy_scan", {})
    clean_source = clean_room.get("source", {})
    clean_plugin = clean_room.get("plugin", {})
    clean_live = clean_room.get("live", {})
    attempts = reproducibility.get("attempts")
    case_ids = reproducibility.get("case_ids")
    candidate_revision = candidate.get("revision")
    checks = {
        "version_matches_manifest": version == current["version"],
        "behavioral_proof_passed": behavioral.get("passed") is True,
        "behavioral_candidate_version": candidate.get("version") == version,
        "behavioral_plugin_matches": candidate.get("plugin_content_sha256") == current["content_sha256"],
        "released_baseline_present": REVISION_RE.fullmatch(str(released.get("revision", ""))) is not None,
        "candidate_revision_present": REVISION_RE.fullmatch(str(candidate_revision or "")) is not None,
        "required_conditions": reproducibility.get("conditions") == matrix["conditions"],
        "minimum_attempts": isinstance(attempts, int) and attempts >= matrix["minimum_attempts"],
        "full_case_matrix": case_ids == matrix["required_case_ids"],
        "complete_attempt_pairs": (
            isinstance(attempts, int)
            and case_ids == matrix["required_case_ids"]
            and check_pairs(
                per_case=behavioral.get("per_case"),
                case_ids=matrix["required_case_ids"],
                attempts=attempts,
            )
        ),
        "promotion_gate": metrics.get("gates", {}).get("promotion", {}).get("passed") is True,
        "no_released_regressions": metrics.get("released_regressions") == 0,
        "privacy_scan": privacy.get("passed") is True,
        "policy_scan": policy.get("configured") is True and policy.get("passed") is True,
        "skills_only_surface": (
            surface.get("permissions_changed") is False and surface.get("hooks_changed") is False
        ),
        "clean_room_proof_passed": clean_room.get("passed") is True,
        "clean_room_live_mode": clean_room.get("mode") == "public-cli-live",
        "clean_room_exact_candidate": (
            clean_source.get("requested_revision") == candidate_revision
            and clean_source.get("resolved_revision") == candidate_revision
        ),
        "clean_room_plugin_matches": clean_plugin == current,
        "clean_room_fresh_task": (
            clean_live.get("ran") is True
            and clean_live.get("installed_skill_read") is True
            and clean_live.get("repository_unchanged") is True
            and clean_live.get("selected_skill") == "repo-verify"
        ),
    }
    certificate = {
        "schema_version": 1,
        "version": version,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "passed": all(checks.values()),
        "checks": checks,
        "plugin": current,
        "behavioral": {
            "evaluated_revision": candidate_revision,
            "released_revision": released.get("revision"),
            "model": reproducibility.get("model"),
            "reasoning_effort": reproducibility.get("reasoning_effort"),
            "attempts": attempts,
            "case_ids": case_ids,
            "metrics": metrics,
            "policy_pattern_file_sha256": policy.get("pattern_file_sha256"),
            "proof_sha256": file_digest(behavioral_path),
        },
        "clean_room": {
            "mode": clean_room.get("mode"),
            "repository": clean_source.get("repository"),
            "revision": clean_source.get("resolved_revision"),
            "codex_version": clean_room.get("codex", {}).get("version"),
            "model": clean_live.get("model"),
            "reasoning_effort": clean_live.get("reasoning_effort"),
            "selected_skill": clean_live.get("selected_skill"),
            "installed_skill_read": clean_live.get("installed_skill_read"),
            "repository_unchanged": clean_live.get("repository_unchanged"),
            "proof_sha256": file_digest(clean_room_path),
        },
        "matrix": {
            "minimum_attempts": matrix["minimum_attempts"],
            "conditions": matrix["conditions"],
            "required_case_ids": matrix["required_case_ids"],
            "required_skills": matrix["required_skills"],
            "project_types": matrix["project_types"],
        },
    }
    serialized = json.dumps(certificate, sort_keys=True)
    if any(value in serialized for value in ("/private/", "/tmp/", "auth.json")):
        raise ReleaseGateError("certificate contains a local path or authentication filename")
    return certificate


def git_output(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        stdin=subprocess.DEVNULL,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise ReleaseGateError(f"git {' '.join(args)} failed: {detail}")
    return completed.stdout.strip()


def verify_certificate(
    *,
    path: Path,
    stable_ref: str | None = None,
    require_ancestry: bool = False,
) -> dict[str, Any]:
    certificate = read_json(path)
    if not isinstance(certificate, dict):
        raise ReleaseGateError("release certificate must be an object")
    required = {
        "schema_version",
        "version",
        "created_at",
        "passed",
        "checks",
        "plugin",
        "behavioral",
        "clean_room",
        "matrix",
    }
    if set(certificate) != required or certificate.get("schema_version") != 1:
        raise ReleaseGateError("release certificate shape is invalid")
    checks = certificate.get("checks")
    if certificate.get("passed") is not True or not isinstance(checks, dict) or not all(checks.values()):
        raise ReleaseGateError("release certificate did not pass every recorded check")
    matrix = validate_matrix()
    current = plugin_identity()
    if certificate.get("plugin") != current:
        raise ReleaseGateError("release certificate does not match the current plugin content")
    if certificate.get("version") != current["version"]:
        raise ReleaseGateError("release certificate version does not match the manifest")
    recorded_matrix = certificate.get("matrix", {})
    if recorded_matrix.get("minimum_attempts") != matrix["minimum_attempts"]:
        raise ReleaseGateError("release certificate uses a stale attempt threshold")
    if recorded_matrix.get("required_case_ids") != matrix["required_case_ids"]:
        raise ReleaseGateError("release certificate uses a stale case matrix")
    serialized = json.dumps(certificate, sort_keys=True)
    if any(value in serialized for value in ("/private/", "/tmp/", "auth.json")):
        raise ReleaseGateError("release certificate contains local-only material")

    evaluated = certificate.get("behavioral", {}).get("evaluated_revision")
    if require_ancestry:
        if not REVISION_RE.fullmatch(str(evaluated or "")):
            raise ReleaseGateError("certificate evaluated revision is invalid")
        completed = subprocess.run(
            ["git", "merge-base", "--is-ancestor", str(evaluated), "HEAD"],
            cwd=ROOT,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            check=False,
        )
        if completed.returncode != 0:
            raise ReleaseGateError("evaluated revision is not an ancestor of the promotion candidate")
    if stable_ref:
        stable_revision = git_output("rev-parse", f"{stable_ref}^{{commit}}")
        recorded = certificate.get("behavioral", {}).get("released_revision")
        if stable_revision != recorded:
            raise ReleaseGateError(
                f"stable baseline moved: certificate {recorded}, current {stable_revision}"
            )
        completed = subprocess.run(
            ["git", "merge-base", "--is-ancestor", stable_revision, "HEAD"],
            cwd=ROOT,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            check=False,
        )
        if completed.returncode != 0:
            raise ReleaseGateError("promotion candidate is not a fast-forward of stable")
    return certificate


def validate_repository() -> dict[str, Any]:
    matrix = validate_matrix()
    certificates = sorted(RELEASES.glob("v*/certificate.json")) if RELEASES.is_dir() else []
    current_version = plugin_identity()["version"]
    current_path = RELEASES / f"v{current_version}" / "certificate.json"
    if current_path.is_file():
        verify_certificate(path=current_path)
    for path in certificates:
        value = read_json(path)
        if not isinstance(value, dict) or value.get("passed") is not True:
            raise ReleaseGateError(f"historical certificate is invalid: {path.relative_to(ROOT)}")
    return {
        "minimum_attempts": matrix["minimum_attempts"],
        "case_count": len(matrix["required_case_ids"]),
        "project_type_count": len(matrix["project_types"]),
        "certificate_count": len(certificates),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("validate", help="validate the release matrix and committed certificates")

    assemble = subparsers.add_parser("assemble", help="build a sanitized release certificate")
    assemble.add_argument("--version", required=True)
    assemble.add_argument("--behavioral-proof", required=True)
    assemble.add_argument("--clean-room-proof", required=True)
    assemble.add_argument("--out", required=True)

    verify = subparsers.add_parser("verify", help="verify a release certificate against this checkout")
    verify.add_argument("--certificate", required=True)
    verify.add_argument("--stable-ref")
    verify.add_argument("--require-ancestry", action="store_true")
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    try:
        if args.command == "validate":
            report = validate_repository()
            print(
                "Tugling release gate passed: "
                f"{report['case_count']} cases across {report['project_type_count']} project types, "
                f"{report['minimum_attempts']} attempts required."
            )
        elif args.command == "assemble":
            certificate = assemble_certificate(
                version=args.version,
                behavioral_path=Path(args.behavioral_proof).resolve(),
                clean_room_path=Path(args.clean_room_proof).resolve(),
            )
            output = Path(args.out).resolve()
            write_json(output, certificate)
            print(f"certificate: {output}")
            if not certificate["passed"]:
                return 2
        else:
            certificate = verify_certificate(
                path=Path(args.certificate).resolve(),
                stable_ref=args.stable_ref,
                require_ancestry=args.require_ancestry,
            )
            print(
                f"Tugling release certificate passed: v{certificate['version']} at "
                f"{certificate['behavioral']['evaluated_revision']}."
            )
    except ReleaseGateError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
