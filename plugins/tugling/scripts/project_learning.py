#!/usr/bin/env python3
"""Capture and review opt-in, local-only Tugling correction records."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


SECRET_PATTERNS = (
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bgh[oprsu]_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
)
VALID_DECISIONS = {"promote", "keep-local", "dismiss"}


class LearningError(RuntimeError):
    """A correction record would violate the project's local-learning contract."""


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LearningError(f"{path}: {exc}") from exc


def learning_path(root: Path) -> Path:
    config = read_json(root / ".tugling" / "project.json")
    learning = config.get("learning") if isinstance(config, dict) else None
    if not isinstance(learning, dict) or learning.get("mode") != "local":
        raise LearningError("local learning is not enabled in .tugling/project.json")
    value = learning.get("local_path")
    if not isinstance(value, str) or not value.startswith(".tugling/local/"):
        raise LearningError("learning.local_path must stay under .tugling/local/")
    path = root / value
    ignored = subprocess.run(
        ["git", "check-ignore", "-q", "--no-index", "--", value],
        cwd=root,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if ignored.returncode != 0:
        raise LearningError("local correction path is not ignored by Git")
    tracked = subprocess.run(
        ["git", "ls-files", "--error-unmatch", "--", value],
        cwd=root,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if tracked.returncode == 0:
        raise LearningError("local correction path is tracked by Git")
    return path


def safe_text(value: str, *, label: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise LearningError(f"{label} must not be empty")
    if len(normalized) > 2000:
        raise LearningError(f"{label} exceeds the 2000-character local record limit")
    if any(pattern.search(normalized) for pattern in SECRET_PATTERNS):
        raise LearningError(f"{label} appears to contain secret material")
    return normalized


def read_records(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise LearningError(f"{path}:{number}: {exc}") from exc
        if not isinstance(value, dict) or value.get("schema_version") != 1:
            raise LearningError(f"{path}:{number}: invalid correction record")
        records.append(value)
    return records


def write_records(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.parent.chmod(0o700)
    fd, temporary_name = tempfile.mkstemp(prefix="corrections.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            for record in records:
                handle.write(json.dumps(record, sort_keys=True) + "\n")
        os.chmod(temporary_name, 0o600)
        os.replace(temporary_name, path)
    finally:
        if os.path.exists(temporary_name):
            os.unlink(temporary_name)


def capture(
    *,
    root: Path,
    summary: str,
    observed: str,
    expected: str,
    scope: str,
) -> dict[str, Any]:
    path = learning_path(root)
    payload = {
        "summary": safe_text(summary, label="summary"),
        "observed": safe_text(observed, label="observed"),
        "expected": safe_text(expected, label="expected"),
        "scope": safe_text(scope, label="scope"),
    }
    captured_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True).encode("utf-8")
    ).hexdigest()[:12]
    record = {
        "schema_version": 1,
        "id": f"lesson-{captured_at[:10]}-{digest}",
        "captured_at": captured_at,
        **payload,
        "status": "pending",
        "review": None,
    }
    records = read_records(path)
    if any(existing.get("id") == record["id"] for existing in records):
        return record
    records.append(record)
    write_records(path, records)
    return record


def review(*, root: Path, record_id: str, decision: str, note: str) -> dict[str, Any]:
    if decision not in VALID_DECISIONS:
        raise LearningError(f"decision must be one of {sorted(VALID_DECISIONS)}")
    path = learning_path(root)
    records = read_records(path)
    for record in records:
        if record.get("id") != record_id:
            continue
        record["status"] = "reviewed"
        record["review"] = {
            "decision": decision,
            "note": safe_text(note, label="note"),
            "reviewed_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        }
        write_records(path, records)
        return record
    raise LearningError(f"correction record not found: {record_id}")


def digest_markdown(records: list[dict[str, Any]]) -> str:
    pending = [record for record in records if record.get("status") == "pending"]
    lines = [
        "# Tugling local learning digest",
        "",
        f"Pending corrections: **{len(pending)}**",
        "",
        "Nothing in this digest is uploaded automatically. Promote only a sanitized, synthetic case after review.",
    ]
    if not pending:
        lines.extend(["", "No pending corrections."])
        return "\n".join(lines) + "\n"
    for record in pending:
        lines.extend(
            [
                "",
                f"## {record['id']}",
                "",
                f"- Summary: {record['summary']}",
                f"- Observed: {record['observed']}",
                f"- Expected: {record['expected']}",
                f"- Scope: {record['scope']}",
                "- Review choices: promote, keep-local, dismiss",
            ]
        )
    return "\n".join(lines) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=".")
    subparsers = parser.add_subparsers(dest="command", required=True)

    capture_parser = subparsers.add_parser("capture")
    capture_parser.add_argument("--summary", required=True)
    capture_parser.add_argument("--observed", required=True)
    capture_parser.add_argument("--expected", required=True)
    capture_parser.add_argument("--scope", required=True)

    subparsers.add_parser("digest")

    review_parser = subparsers.add_parser("review")
    review_parser.add_argument("--id", required=True)
    review_parser.add_argument("--decision", choices=sorted(VALID_DECISIONS), required=True)
    review_parser.add_argument("--note", required=True)
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    root = Path(args.repo).resolve()
    try:
        if args.command == "capture":
            record = capture(
                root=root,
                summary=args.summary,
                observed=args.observed,
                expected=args.expected,
                scope=args.scope,
            )
            print(json.dumps(record, indent=2, sort_keys=True))
        elif args.command == "digest":
            print(digest_markdown(read_records(learning_path(root))), end="")
        else:
            record = review(
                root=root,
                record_id=args.id,
                decision=args.decision,
                note=args.note,
            )
            print(json.dumps(record, indent=2, sort_keys=True))
    except LearningError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
