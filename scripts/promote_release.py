#!/usr/bin/env python3
"""Verify attested release evidence, require approval, publish, and check installation.

Each workflow phase runs from the independently pinned controller on a fresh
runner. No phase executes candidate scripts or calls a model.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import certify_release as certification
import clean_room_install as clean_room
import release_controller as controller
import release_evidence as evidence
import release_protection as protection


def authorize(env: dict[str, str]) -> dict[str, str]:
    pin = env.get("CONTROLLER_SHA", "")
    cert_pin = env.get("CERTIFICATION_CONTROLLER_SHA", "")
    candidate, version = env.get("CANDIDATE_SHA", ""), env.get("RELEASE_VERSION", "")
    digest, run_id = env.get("CERTIFICATE_SHA256", ""), env.get("CERTIFICATION_RUN_ID", "")
    controller.validate_request(pin, candidate, version, digest)
    if (env.get("GITHUB_REPOSITORY") != evidence.REPOSITORY
            or env.get("GITHUB_EVENT_NAME") != "workflow_dispatch"
            or env.get("WORKFLOW_SHA") != pin or env.get("GITHUB_SHA") != pin
            or not env.get("GITHUB_REF", "").startswith("refs/tags/")
            or not evidence.CONTROLLER_TAG.fullmatch(env.get("GITHUB_REF_NAME", ""))
            or env.get("GITHUB_REF") != f"refs/tags/{env.get('GITHUB_REF_NAME')}"
            or not controller.SHA.fullmatch(cert_pin) or not evidence.RUN_ID.fullmatch(run_id)):
        raise controller.ControllerError("promotion requires a dispatch from the separately approved controller tag")
    if controller.text_git(ROOT, "rev-parse", "HEAD") != pin:
        raise controller.ControllerError("running checkout is not the approved controller SHA")
    if controller.text_git(ROOT, "status", "--porcelain", "--untracked-files=all"):
        raise controller.ControllerError("approved controller checkout must be clean")
    return {"controller": pin, "certification_controller": cert_pin, "candidate": candidate,
            "version": version, "certificate_digest": digest, "run_id": run_id}


def verify_and_promote(request: dict[str, str], *, apply: bool,
                       policy_token: str | None = None) -> dict[str, Any]:
    # Keep the App token in this process only; candidate checks, attestation
    # commands, and Git publication retain the normal workflow identity.
    token = os.environ.pop("TUGLING_POLICY_TOKEN", "") if policy_token is None else policy_token
    if not token:
        raise protection.ProtectionVisibilityError(
            "policy App token is missing; configure TUGLING_POLICY_APP_CLIENT_ID and "
            "TUGLING_POLICY_APP_PRIVATE_KEY in the protected release environments")
    environment = protection.require_protections(token=token)
    if apply:
        protection.require_approval(os.environ.get("GITHUB_RUN_ID", ""), environment)
    with tempfile.TemporaryDirectory(prefix="tugling-release-evidence-") as directory:
        path, envelope = evidence.fetch_verified(
            run_id=request["run_id"], pin=request["certification_controller"],
            candidate=request["candidate"], digest=request["certificate_digest"], scratch=Path(directory),
        )
        certification.require_successful_verify(request["candidate"])
        result = controller.promote(
            remote=controller.REMOTE, controller=request["controller"],
            certification_controller=request["certification_controller"], candidate=request["candidate"],
            version=request["version"], certificate_path=path,
            certificate_digest=request["certificate_digest"], apply=apply,
            token=os.environ.get("GH_TOKEN", "") if apply else "",
        )
        return {**result, "certification_run_id": request["run_id"], "certification_run_attempt": 1,
                "usage": envelope["usage"], "model": envelope["model"],
                "reasoning_effort": envelope["reasoning_effort"]}


def require_published(refs: dict[str, str], candidate: str, version: str) -> None:
    if (refs.get("refs/heads/stable") != candidate
            or refs.get(f"refs/tags/v{version}^{{}}") != candidate):
        raise controller.ControllerError("published stable and annotated version tag do not match the approved candidate")


def canary(request: dict[str, str], *, codex_bin: str | None = None,
           remote: str = controller.REMOTE) -> dict[str, Any]:
    binary, version = clean_room.resolve_codex(codex_bin)
    if version != f"codex-cli {certification.CODEX_VERSION}":
        raise clean_room.CleanRoomError("post-promotion canary requires the reviewed Codex runtime")
    with tempfile.TemporaryDirectory(prefix="tugling-stable-canary-") as directory:
        scratch = Path(directory)
        repository = scratch / "objects.git"
        repository.mkdir()
        controller.git(repository, "init", "--bare", "--template=", ".")
        controller.git(repository, "remote", "add", "origin", remote)
        controller.git(repository, "fetch", "--no-tags", "origin", request["candidate"], request["controller"])
        refs = controller.remote_refs(repository, request["version"], controller.git_env())
        require_published(refs, request["candidate"], request["version"])
        controller.require_reviewed_ruler(repository, request["controller"], request["candidate"])
        source = scratch / "candidate-data"
        controller.materialize_data(repository, request["candidate"], source)
        if clean_room.package_report(source)["version"] != request["version"]:
            raise clean_room.CleanRoomError("published package has a different version")
        proof = clean_room.public_install(
            source=evidence.REPOSITORY, ref="stable", expected_revision=request["candidate"],
            expected_root=source, codex_bin=binary, codex_version=version, auth_home=scratch / "no-auth",
            live=False, model="", reasoning_effort="", timeout=120,
        )
        if proof.get("passed") is not True or proof.get("live", {}).get("ran") is not False:
            raise clean_room.CleanRoomError("fresh public stable installation failed")
        require_published(controller.remote_refs(repository, request["version"], controller.git_env()),
                          request["candidate"], request["version"])
        return {"state": "PROMOTED_AND_INSTALL_VERIFIED", "candidate_sha": request["candidate"],
                "version": request["version"], "installation": proof}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("verify", "promote", "canary"))
    parser.add_argument("--out", required=True)
    parser.add_argument("--codex-bin")
    args = parser.parse_args()
    # authorize() invokes Git too. Remove the policy credential before even
    # those initial checkout checks, then pass it explicitly to policy reads.
    policy_token = os.environ.pop("TUGLING_POLICY_TOKEN", "")
    try:
        request = authorize(dict(os.environ))
        result = (canary(request, codex_bin=args.codex_bin) if args.phase == "canary"
                  else verify_and_promote(request, apply=args.phase == "promote", policy_token=policy_token))
        status = 0
    except (controller.ControllerError, certification.CertificationError, evidence.EvidenceError,
            clean_room.CleanRoomError, controller.gate.ReleaseGateError, OSError, ValueError,
            KeyError, TypeError, AttributeError, subprocess.TimeoutExpired, zipfile.BadZipFile) as exc:
        # A publication error can mean an uncertain write outcome. A canary
        # failure means refs may already be public. Neither authorizes rollback.
        result = {"state": "PROMOTED_CANARY_FAILED" if args.phase == "canary" else "PROMOTION_BLOCKED_OR_UNCONFIRMED",
                  "phase": args.phase,
                  "reason": str(exc) if isinstance(exc, (controller.ControllerError, evidence.EvidenceError,
                                                        certification.CertificationError)) else type(exc).__name__,
                  "recovery": "Inspect workflow evidence and live stable/tag refs; do not roll back or rerun paid certification automatically."}
        if isinstance(exc, protection.ProtectionVisibilityError):
            result["failure_kind"] = "PROTECTION_ACCESS_MISSING"
        status = 1
    controller.gate.write_json(Path(args.out), result)
    print(json.dumps(result, sort_keys=True))
    return status


if __name__ == "__main__":
    raise SystemExit(main())
