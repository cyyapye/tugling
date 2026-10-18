"""Declare unfinished runtime coverage without treating it as release evidence."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COVERAGE = ROOT / "evals/behavioral/catalog-coverage.json"


def validate(cases: list[dict], catalog: set[str], path: Path = COVERAGE) -> list[str]:
    try:
        record = json.loads(path.read_text())
    except (OSError, ValueError) as exc:
        return [f"catalog coverage: {exc}"]
    if not isinstance(record, dict) or record.get("schema_version") != 1:
        return ["catalog coverage must use schema_version 1"]
    covered = {case.get("skill") for case in cases if isinstance(case, dict)}
    pending = record.get("pending_skills")
    if not isinstance(pending, dict) or any(not isinstance(reason, str) or not reason.strip() for reason in pending.values()):
        return ["catalog coverage must explain every pending skill"]
    if set(pending) != catalog - covered:
        return ["catalog coverage pending skills must exactly match the untested catalog"]
    return []


def release_covered(catalog: set[str], required_skills: list[str]) -> bool:
    """Pending declarations never waive full catalog coverage for a release."""
    return bool(catalog) and catalog == set(required_skills)
