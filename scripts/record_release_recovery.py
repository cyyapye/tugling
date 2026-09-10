#!/usr/bin/env python3
"""Record a verified local recovery without rewriting a failed Actions deployment.

This operator command never publishes refs or calls a model. It reconstructs the
approved intent from the failed run's successful preflight, rechecks the original
attestations and current publication, and performs a fresh public installation.
Only --apply writes deployment metadata, using the maintainer's GitHub identity.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import promote_release as promotion

controller = promotion.controller
evidence = promotion.evidence
TASK = "tugling:recovery"
ENVIRONMENT = "tugling-stable"


def recovery_intent(run_id: str) -> tuple[dict[str, str], dict[str, Any]]:
    if not evidence.RUN_ID.fullmatch(run_id):
        raise evidence.EvidenceError("invalid original promotion run ID")
    run = evidence.api(f"actions/runs/{run_id}")
    if (run.get("id") != int(run_id) or run.get("run_attempt") != 1
            or run.get("event") != "workflow_dispatch" or run.get("status") != "completed"
            or run.get("conclusion") != "failure" or run.get("path") != ".github/workflows/promote-stable.yml"
            or run.get("repository", {}).get("full_name") != evidence.REPOSITORY
            or run.get("head_repository", {}).get("full_name") != evidence.REPOSITORY
            or not evidence.CONTROLLER_TAG.fullmatch(run.get("head_branch", ""))):
        raise evidence.EvidenceError("recovery must reference a failed first-attempt protected promotion run")
    listing = evidence.api(f"actions/runs/{run_id}/jobs?per_page=100")
    jobs = listing.get("jobs", [])
    if listing.get("total_count") != len(jobs) or len(jobs) >= 100:
        raise evidence.EvidenceError("original promotion job listing is incomplete or excessive")
    for name in ("preflight", "verify-candidate"):
        matches = [job for job in jobs if job.get("name") == name]
        if (len(matches) != 1 or matches[0].get("status") != "completed"
                or matches[0].get("conclusion") != "success"):
            raise evidence.EvidenceError("recovery requires the original preflight and candidate checks to have passed")
    preflight = next(job for job in jobs if job["name"] == "preflight")
    if type(preflight.get("id")) is not int or preflight["id"] <= 0:
        raise evidence.EvidenceError("invalid original preflight job ID")
    log = evidence.gh("api", "--hostname", "github.com",
                      f"repos/{evidence.REPOSITORY}/actions/jobs/{preflight['id']}/logs")
    reviews = []
    for line in log.decode().splitlines():
        # GitHub prefixes each complete JSON result line with its timestamp.
        _, separator, value = line.partition(" ")
        if separator and value.startswith("{"):
            try:
                item = json.loads(value)
            except ValueError:
                continue
            if isinstance(item, dict) and item.get("state") in {"READY_FOR_REVIEWED_PROMOTION", "ALREADY_PROMOTED"}:
                reviews.append(item)
    if len(reviews) != 1:
        raise evidence.EvidenceError("original preflight must contain one unambiguous release identity")
    review = reviews[0]
    fields = {"controller": "controller_sha", "certification_controller": "certification_controller_sha",
              "candidate": "candidate_sha", "version": "version", "certificate_digest": "certificate_sha256",
              "run_id": "certification_run_id"}
    request = {key: review.get(source, "") for key, source in fields.items()}
    if not all(isinstance(value, str) for value in request.values()):
        raise evidence.EvidenceError("original preflight release identity is malformed")
    controller.validate_request(request["controller"], request["candidate"], request["version"],
                                request["certificate_digest"])
    if (request["controller"] != run.get("head_sha")
            or not controller.SHA.fullmatch(request["certification_controller"])
            or not evidence.RUN_ID.fullmatch(request["run_id"])
            or review.get("certification_run_attempt") != 1):
        raise evidence.EvidenceError("original preflight does not match its controller or certification")
    return request, run


def verify_recovery(run_id: str, *, codex_bin: str | None = None) -> dict[str, Any]:
    request, run = recovery_intent(run_id)
    environment = promotion.protection.require_protections()
    promotion.protection.require_approval(run_id, environment)
    with tempfile.TemporaryDirectory(prefix="tugling-recovery-evidence-") as directory:
        path, _envelope = evidence.fetch_verified(
            run_id=request["run_id"], pin=request["certification_controller"],
            candidate=request["candidate"], digest=request["certificate_digest"], scratch=Path(directory))
        promotion.certification.require_successful_verify(request["candidate"])
        published = controller.promote(
            remote=controller.REMOTE, controller=request["controller"],
            certification_controller=request["certification_controller"], candidate=request["candidate"],
            version=request["version"], certificate_path=path,
            certificate_digest=request["certificate_digest"], apply=False)
        if published.get("state") != "ALREADY_PROMOTED":
            raise evidence.EvidenceError("recovery reporting requires an already published stable and annotated tag")
        installation = promotion.canary(request, codex_bin=codex_bin)
        if installation.get("state") != "PROMOTED_AND_INSTALL_VERIFIED":
            raise evidence.EvidenceError("fresh public stable installation did not pass")
    # A rerun starting during verification changes the approval/run context.
    current_run = evidence.api(f"actions/runs/{run_id}")
    if any(current_run.get(key) != run.get(key)
           for key in ("id", "run_attempt", "head_sha", "status", "conclusion")):
        raise evidence.EvidenceError("original promotion run changed during recovery verification")
    return {"state": "RECOVERY_VERIFIED", "source_promotion_run_id": run_id,
            "original_ci_conclusion": "failure", "execution_environment": "local-operator-verification",
            "request": request, "installation": installation}


def post(path: str, payload: dict[str, Any]) -> dict[str, Any]:
    # Public metadata only. Credentials remain in gh's normal auth storage/env.
    with tempfile.TemporaryDirectory(prefix="tugling-deployment-request-") as directory:
        source = Path(directory) / "request.json"
        source.write_text(json.dumps(payload))
        return json.loads(evidence.gh("api", "--hostname", "github.com", "--method", "POST",
            f"repos/{evidence.REPOSITORY}/{path}", "--input", str(source)))


def record_recovery(proof: dict[str, Any]) -> dict[str, Any]:
    """Append metadata for fresh in-process proof; never load a success flag from disk."""
    request = proof["request"]
    candidate, version, run_id = request["candidate"], request["version"], proof["source_promotion_run_id"]
    payload = {"kind": "tugling-release-recovery-v1", "source_promotion_run_id": run_id,
               "candidate_sha": candidate, "version": version,
               "certificate_sha256": request["certificate_digest"],
               "original_ci_conclusion": "failure", "execution_environment": proof["execution_environment"]}
    query = urlencode({"environment": ENVIRONMENT, "task": TASK, "sha": candidate, "per_page": 100})
    deployments = evidence.api(f"deployments?{query}")
    if not isinstance(deployments, list) or len(deployments) >= 100:
        raise evidence.EvidenceError("recovery deployment listing is invalid or incomplete")
    matches = [item for item in deployments if isinstance(item.get("payload"), dict)
               and item["payload"].get("source_promotion_run_id") == run_id]
    if len(matches) > 1:
        raise evidence.EvidenceError("duplicate recovery records require operator inspection")
    # Refresh refs after installation and listing, immediately before metadata writes.
    output = controller.text_git(ROOT, "ls-remote", controller.REMOTE, "refs/heads/stable",
                                 f"refs/tags/v{version}", f"refs/tags/v{version}^{{}}")
    promotion.require_published({ref: sha for sha, ref in (line.split() for line in output.splitlines())},
                                candidate, version)
    if matches:
        deployment = matches[0]
        if (deployment.get("sha") != candidate or deployment.get("environment") != ENVIRONMENT
                or deployment.get("task") != TASK or deployment.get("payload") != payload):
            raise evidence.EvidenceError("existing recovery deployment conflicts with the verified intent")
    else:
        deployment = post("deployments", {"ref": candidate, "environment": ENVIRONMENT, "task": TASK,
            "auto_merge": False, "required_contexts": [], "production_environment": True,
            "description": f"Verified local recovery of v{version}; original CI run {run_id} failed",
            "payload": payload})
    identifier = deployment.get("id")
    if type(identifier) is not int or identifier <= 0 or deployment.get("sha") != candidate:
        raise evidence.EvidenceError("recovery deployment creation is unconfirmed; inspect records before retrying")
    statuses = evidence.api(f"deployments/{identifier}/statuses?per_page=100")
    if not isinstance(statuses, list):
        raise evidence.EvidenceError("recovery deployment status response is invalid")
    result = {**proof, "deployment_id": identifier,
              "url": f"https://github.com/{evidence.REPOSITORY}/deployments/{ENVIRONMENT}"}
    if statuses and statuses[0].get("state") == "success":
        return {**result, "state": "RECOVERY_ALREADY_RECORDED"}
    status = post(f"deployments/{identifier}/statuses", {"state": "success", "auto_inactive": False,
        "description": "Local recovery and fresh stable installation verified; original CI attempt remains failed",
        "environment_url": f"https://github.com/{evidence.REPOSITORY}/tree/v{version}",
        "log_url": f"https://github.com/{evidence.REPOSITORY}/actions/runs/{run_id}"})
    if status.get("state") != "success":
        raise evidence.EvidenceError("recovery status is unconfirmed; inspect records before retrying")
    return {**result, "state": "RECOVERY_RECORDED"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--promotion-run-id", required=True)
    parser.add_argument("--codex-bin")
    parser.add_argument("--out", required=True)
    parser.add_argument("--apply", action="store_true", help="append a separate verified recovery deployment")
    args = parser.parse_args()
    try:
        proof = verify_recovery(args.promotion_run_id, codex_bin=args.codex_bin)
        result = record_recovery(proof) if args.apply else proof
        status = 0
    except (controller.ControllerError, evidence.EvidenceError, promotion.certification.CertificationError,
            promotion.clean_room.CleanRoomError, controller.gate.ReleaseGateError,
            OSError, ValueError, KeyError, TypeError, AttributeError, subprocess.TimeoutExpired) as exc:
        result = {"state": "RECOVERY_RECORDING_BLOCKED_OR_UNCONFIRMED", "reason": str(exc),
                  "recovery": "Inspect current refs and recovery records before retrying; no release refs were written."}
        status = 1
    controller.gate.write_json(Path(args.out), result)
    print(json.dumps(result, sort_keys=True))
    return status


if __name__ == "__main__":
    raise SystemExit(main())
