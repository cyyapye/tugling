"""Read bounded GitHub evidence and verify its provenance before interpreting it."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import stat
import subprocess
from typing import Any
from urllib.parse import urlencode
import zipfile

if __package__:
    from . import certify_release as certification
else:
    import certify_release as certification

REPOSITORY = certification.REPOSITORY
CERTIFY_WORKFLOW = ".github/workflows/certify-release.yml"
CONTROLLER_TAG = certification.controller.CONTROLLER_TAG
RUN_ID = re.compile(r"[1-9][0-9]{0,19}")
MAX_ARCHIVE_BYTES = 600 * 1024


class EvidenceError(RuntimeError):
    pass


def gh(*args: str, output: Path | None = None) -> bytes:
    # Do not inherit debug switches that could log authorization headers.
    env = {key: value for key, value in os.environ.items() if not key.startswith("GH_")}
    env["GH_HOST"] = "github.com"
    if os.environ.get("GH_TOKEN"):
        env["GH_TOKEN"] = os.environ["GH_TOKEN"]
    with (output.open("xb") if output else open(os.devnull, "wb")) as destination:
        result = subprocess.run(
            ["gh", *args], stdin=subprocess.DEVNULL,
            stdout=destination if output else subprocess.PIPE,
            stderr=subprocess.PIPE, env=env, timeout=120, check=False,
        )
    if result.returncode:
        raise EvidenceError("GitHub evidence request or attestation verification failed; no release is authorized")
    if output:
        if output.stat().st_size > MAX_ARCHIVE_BYTES:
            raise EvidenceError("certification archive exceeds its size limit")
        return b""
    if len(result.stdout) > 2 * 1024 * 1024:
        raise EvidenceError("GitHub evidence response exceeds its size limit")
    return result.stdout


def api(path: str) -> Any:
    endpoint = f"repos/{REPOSITORY}" + (f"/{path}" if path else "")
    return json.loads(gh("api", "--hostname", "github.com", endpoint))


def require_run(run: dict[str, Any], run_id: str, pin: str) -> str:
    tag = run.get("head_branch", "")
    if (run.get("id") != int(run_id) or run.get("run_attempt") != 1
            or run.get("event") != "workflow_dispatch" or run.get("path") != CERTIFY_WORKFLOW
            or run.get("head_sha") != pin or run.get("status") != "completed"
            or run.get("conclusion") != "success"
            or run.get("repository", {}).get("full_name") != REPOSITORY
            or run.get("head_repository", {}).get("full_name") != REPOSITORY
            or not isinstance(tag, str) or not CONTROLLER_TAG.fullmatch(tag)):
        raise EvidenceError("certification must be a successful first-attempt dispatch from the approved controller tag")
    return f"refs/tags/{tag}"


def unpack(archive: Path, output: Path) -> None:
    with zipfile.ZipFile(archive) as bundle:
        entries = bundle.infolist()
        if (len(entries) != 2
                or {entry.filename for entry in entries} != {"certificate.json", "certification.json"}):
            raise EvidenceError("certification archive must contain exactly the two evidence files")
        for entry in entries:
            kind = stat.S_IFMT(entry.external_attr >> 16)
            if (entry.is_dir() or kind not in {0, stat.S_IFREG} or entry.flag_bits & 1
                    or not 0 < entry.file_size <= certification.MAX_CERTIFICATE_BYTES):
                raise EvidenceError("certification archive must contain bounded regular JSON files")
        output.mkdir()
        for entry in entries:
            with (output / entry.filename).open("xb") as destination:
                destination.write(bundle.read(entry))


def verify_attestation(path: Path, *, pin: str, source_ref: str, run_id: str) -> None:
    verified = json.loads(gh(
        "attestation", "verify", str(path), "--hostname", "github.com",
        "--repo", REPOSITORY, "--signer-workflow", f"{REPOSITORY}/{CERTIFY_WORKFLOW}",
        "--signer-digest", pin, "--source-digest", pin, "--source-ref", source_ref,
        "--deny-self-hosted-runners", "--format", "json",
    ))
    invocation = f"https://github.com/{REPOSITORY}/actions/runs/{run_id}/attempts/1"
    # Inspect only successfully verified statements. The pinned attestation
    # action in the reviewed workflow supplies this signed invocation identity.
    if not isinstance(verified, list) or not any(
        item.get("verificationResult", {}).get("statement", {}).get("predicate", {})
        .get("runDetails", {}).get("metadata", {}).get("invocationId") == invocation
        for item in verified if isinstance(item, dict)
    ):
        raise EvidenceError("verified attestation belongs to a different certification run or attempt")


def fetch_verified(*, run_id: str, pin: str, candidate: str, digest: str,
                   scratch: Path) -> tuple[Path, dict[str, Any]]:
    if not RUN_ID.fullmatch(run_id):
        raise EvidenceError("invalid certification run ID")
    source_ref = require_run(api(f"actions/runs/{run_id}"), run_id, pin)
    name = f"certification-{candidate}-{run_id}-1"
    # Checkpoint artifacts may span many pages; bound this lookup to the exact
    # certificate name while retaining completeness and ambiguity checks.
    query = urlencode({"per_page": 100, "name": name})
    listing = api(f"actions/runs/{run_id}/artifacts?{query}")
    artifacts = listing.get("artifacts", [])
    if listing.get("total_count") != len(artifacts) or len(artifacts) > 100:
        raise EvidenceError("certification artifact listing is incomplete or excessive")
    matches = [item for item in artifacts if item.get("name") == name]
    if len(matches) != 1:
        raise EvidenceError("the exact certification artifact is missing or ambiguous")
    artifact = matches[0]
    if (artifact.get("expired") is not False or type(artifact.get("id")) is not int
            or artifact["id"] <= 0 or type(artifact.get("size_in_bytes")) is not int
            or not 0 < artifact["size_in_bytes"] <= MAX_ARCHIVE_BYTES
            or artifact.get("workflow_run", {}).get("id") != int(run_id)
            or artifact.get("workflow_run", {}).get("head_sha") != pin):
        raise EvidenceError("certification artifact is expired, oversized, or from another run")
    archive = scratch / "certification.zip"
    gh("api", "--hostname", "github.com",
       f"repos/{REPOSITORY}/actions/artifacts/{artifact['id']}/zip", output=archive)
    output = scratch / "evidence"
    unpack(archive, output)
    for name in ("certificate.json", "certification.json"):
        verify_attestation(output / name, pin=pin, source_ref=source_ref, run_id=run_id)
    # Nothing above interprets candidate-provided JSON as an authorization.
    envelope = certification.gate.read_json(output / "certification.json")
    baseline = envelope.get("baseline_sha", "")
    if not isinstance(baseline, str) or not certification.controller.SHA.fullmatch(baseline):
        raise EvidenceError("invalid certified stable baseline")
    limits = {}
    for key, ceiling in (("input_limit", 100_000_000), ("output_limit", 10_000_000)):
        value = envelope.get(key)
        if type(value) is not int or not 0 < value <= ceiling:
            raise EvidenceError("invalid certified token threshold")
        limits[key] = value
    request = {"repository": REPOSITORY, "controller_sha": pin, "candidate_sha": candidate,
               "baseline_sha": baseline, "run_id": run_id, "run_attempt": 1, **limits}
    certification.validate_artifact(output, request)
    if envelope["certificate_sha256"] != digest:
        raise EvidenceError("attested certificate differs from the maintainer-reviewed digest")
    # A rerun while downloading invalidates the original first-attempt request.
    require_run(api(f"actions/runs/{run_id}"), run_id, pin)
    return output / "certificate.json", envelope
