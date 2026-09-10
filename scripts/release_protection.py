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


class ProtectionVisibilityError(evidence.EvidenceError):
    """The caller cannot observe the protection policy; drift is not established."""


def require_protections(*, token: str | None = None) -> dict[str, Any]:
    """Read the full policy, using the App token only for ruleset requests.

    An explicit token is supplied by CI. Local maintainer audits may use their
    existing GitHub CLI identity, which must pass the same visibility check.
    """
    policy = json.loads(POLICY.read_text())
    if evidence.api("").get("visibility") != "public":
        raise evidence.EvidenceError("release controls require this reviewed public repository configuration")
    options = {} if token is None else {"token": token}
    listing = evidence.api("rulesets?per_page=100", **options)
    if not isinstance(listing, list) or len(listing) >= 100:
        raise evidence.EvidenceError("release ruleset listing is invalid or incomplete")
    for expected in policy["rulesets"]:
        matches = [item for item in listing if item.get("name") == expected["name"]]
        if len(matches) != 1:
            raise evidence.EvidenceError("required release ruleset is missing or ambiguous")
        actual = evidence.api(f"rulesets/{matches[0]['id']}", **options)
        for key in ("name", "target", "enforcement", "conditions"):
            if actual.get(key) != expected[key]:
                raise evidence.EvidenceError("release ruleset scope or enforcement drifted")
        if {item.get("type") for item in actual.get("rules", [])} != {
            item["type"] for item in expected["rules"]
        }:
            raise evidence.EvidenceError("required release ref restrictions drifted")
        # Repository contents:write is insufficient. GitHub reveals this field
        # only to callers with ruleset write access (Administration:write).
        # Omitted data must fail preflight, before candidate work or approval.
        if "bypass_actors" not in actual:
            raise ProtectionVisibilityError(
                f"GitHub omitted bypass_actors for {expected['name']}; "
                "configure the policy App with repository Administration:write access")
        if actual["bypass_actors"] != expected["bypass_actors"]:
            raise evidence.EvidenceError("release ruleset bypass actors changed")
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
    audit_name = policy["audit_environment_name"]
    audit = evidence.api(f"environments/{audit_name}")
    if (audit.get("name") != audit_name or audit.get("can_admins_bypass") is not False
            or audit.get("deployment_branch_policy") != expected_environment["deployment_branch_policy"]):
        raise evidence.EvidenceError("policy credential environment must restrict access to reviewed controller tags")
    audit_deployment = evidence.api(f"environments/{audit_name}/deployment-branch-policies?per_page=100")
    if (audit_deployment.get("total_count") != 1
            or [{key: item.get(key) for key in ("name", "type")}
                for item in audit_deployment.get("branch_policies", [])] != [policy["deployment_policy"]]):
        raise evidence.EvidenceError("policy credential environment must admit only reviewed controller tags")
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
