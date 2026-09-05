"""Fail closed when GitHub release rules or the approval environment drift.

This module only reads settings. Administrative setup is separate from CI.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

if __package__:
    from . import release_evidence as evidence
else:
    import release_evidence as evidence

POLICY = Path(__file__).resolve().parents[1] / ".github/release-policy.json"


def require_protections(*, writer: bool = False) -> dict[str, Any]:
    policy = json.loads(POLICY.read_text())
    if evidence.api("").get("visibility") != "public":
        raise evidence.EvidenceError("release controls require this reviewed public repository configuration")
    listing = evidence.api("rulesets?per_page=100")
    if not isinstance(listing, list) or len(listing) >= 100:
        raise evidence.EvidenceError("release ruleset listing is invalid or incomplete")
    for expected in policy["rulesets"]:
        matches = [item for item in listing if item.get("name") == expected["name"]]
        if len(matches) != 1:
            raise evidence.EvidenceError("required release ruleset is missing or ambiguous")
        actual = evidence.api(f"rulesets/{matches[0]['id']}")
        for key in ("name", "target", "enforcement", "conditions"):
            if actual.get(key) != expected[key]:
                raise evidence.EvidenceError("release ruleset scope or enforcement drifted")
        if {item.get("type") for item in actual.get("rules", [])} != {
            item["type"] for item in expected["rules"]
        }:
            raise evidence.EvidenceError("required release ref restrictions drifted")
        # GitHub hides bypass actors from callers without write access. The
        # writer must observe and verify them again after environment approval.
        if writer or "bypass_actors" in actual:
            if actual.get("bypass_actors") != expected["bypass_actors"]:
                raise evidence.EvidenceError("release ruleset bypass actors are unverified or changed")
    name = policy["environment_name"]
    environment = evidence.api(f"environments/{name}")
    expected_environment = policy["environment"]
    if (environment.get("name") != name or environment.get("can_admins_bypass") is not False
            or environment.get("deployment_branch_policy") != expected_environment["deployment_branch_policy"]):
        raise evidence.EvidenceError("release approval environment is missing or can be bypassed")
    rules = [rule for rule in environment.get("protection_rules", [])
             if rule.get("type") == "required_reviewers"]
    if (len(rules) != 1 or rules[0].get("prevent_self_review") is not False
            or [{"type": reviewer.get("type"), "id": reviewer.get("reviewer", {}).get("id")}
                for reviewer in rules[0].get("reviewers", [])] != expected_environment["reviewers"]):
        raise evidence.EvidenceError("release requires the configured maintainer's explicit environment approval")
    deployment = evidence.api(f"environments/{name}/deployment-branch-policies?per_page=100")
    if (deployment.get("total_count") != 1
            or [{key: item.get(key) for key in ("name", "type")}
                for item in deployment.get("branch_policies", [])] != [policy["deployment_policy"]]):
        raise evidence.EvidenceError("release environment must admit only reviewed controller tags")
    return environment


def require_approval(run_id: str, environment: dict[str, Any]) -> None:
    if not evidence.RUN_ID.fullmatch(run_id):
        raise evidence.EvidenceError("invalid promotion run ID")
    reviews = evidence.api(f"actions/runs/{run_id}/approvals")
    approved = any(
        review.get("state") == "approved" and review.get("user", {}).get("id") == 4515813
        and any(item.get("id") == environment["id"]
                for item in review.get("environments", []))
        for review in reviews
    )
    if not approved:
        raise evidence.EvidenceError("no maintainer approval is recorded for this promotion run")
