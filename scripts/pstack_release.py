#!/usr/bin/env python3
"""Certify human-reviewed Pstack compatibility evidence without running a model.

The dispatch approves the digest of a bounded report, not its individual flags.
Private evidence stays private. The signed report preserves its hashes and limits.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import certify_release as legacy
import clean_room_install as clean_room
import pstack_sources
import release_controller as controller
import release_gate as gate

POLICY = ROOT / "evals/pstack/release-policy.json"
METHOD = "pstack-eval"
SCOPE = "codex-port-compatibility"
AREAS = {"discovery-and-setup", "planning-scope", "repair-and-regression", "verification-honesty",
         "capability-fallbacks", "history-scope", "skill-authoring", "idle-scope"}
ENVIRONMENTS = {"workspace-write", "scoped-skill-directory"}
LIMITATIONS = {"same-family-review", "development-tasks-not-holdouts", "not-full-catalog-behavior",
               "not-enhancement-evidence", "builder-usage-only"}
EXTRA_LIMITATIONS = {"authoring-requires-explicit-directory-grant", "repeat-used-longer-timeout"}
CHECKS = {"reviewed_workflows", "exact_package", "attributed_sources", "public_policy",
          "fresh_public_install", "successful_verify", "reviewed_controller", "fresh_refs"}
INSTALL_CHECKS = {"marketplace_add", "plugin_add", "exact_public_revision", "isolated_install_path",
                  "marketplace_package_matches_candidate", "installed_plugin_matches_candidate"}
IDENTIFIER = re.compile(r"[a-z0-9][a-z0-9-]{0,79}")
RUNTIME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._ -]{0,79}")
REQUEST_KEYS = {"repository", "controller_sha", "candidate_sha", "baseline_sha", "run_id",
                "run_attempt", "review_sha256"}
MAX_BYTES = legacy.MAX_CERTIFICATE_BYTES


class ReviewedReleaseError(gate.ReleaseGateError):
    pass


def fields(value: Any, keys: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        raise ReviewedReleaseError(f"invalid {label} fields")
    return value


def integer(value: Any, *, minimum: int = 0, maximum: int = 100_000_000) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise ReviewedReleaseError("invalid bounded evidence count")
    return value


def match(value: Any, pattern: re.Pattern, label: str) -> str:
    if not isinstance(value, str) or pattern.fullmatch(value) is None:
        raise ReviewedReleaseError(f"invalid {label}")
    return value


def identifiers(value: Any, *, allowed: set[str] | None = None) -> list[str]:
    if not isinstance(value, list) or not 0 < len(value) <= 100:
        raise ReviewedReleaseError("invalid evidence identifier list")
    for item in value:
        match(item, IDENTIFIER, "evidence identifier")
    if len(set(value)) != len(value) or (allowed is not None and not set(value) <= allowed):
        raise ReviewedReleaseError("duplicate or unknown evidence identifier")
    return value


def read_json(path: Path) -> Any:
    if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= MAX_BYTES:
        raise ReviewedReleaseError("evidence must be bounded regular JSON")
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ReviewedReleaseError("duplicate JSON field")
            result[key] = value
        return result
    try:
        return json.loads(path.read_bytes(), object_pairs_hook=unique)
    except (UnicodeError, ValueError) as exc:
        raise ReviewedReleaseError("invalid evidence JSON") from exc


def policy() -> dict[str, Any]:
    value = fields(read_json(POLICY), {"schema_version", "method", "scope", "required_areas",
                                    "allowed_environments", "required_limitations", "allowed_limitations"}, "review policy")
    if (type(value["schema_version"]) is not int or value["schema_version"] != 1
            or value["method"] != METHOD or value["scope"] != SCOPE
            or set(identifiers(value["required_areas"])) != AREAS
            or set(identifiers(value["allowed_environments"])) != ENVIRONMENTS
            or set(identifiers(value["required_limitations"])) != LIMITATIONS
            or set(identifiers(value["allowed_limitations"])) != LIMITATIONS | EXTRA_LIMITATIONS):
        raise ReviewedReleaseError("unsupported reviewed release policy")
    return value


def validate_report(report: Any, plugin: dict[str, Any]) -> dict[str, Any]:
    rules = policy()
    fields(report, {"schema_version", "method", "scope", "plugin", "upstream_revision", "evidence_sets",
                    "runtimes", "attempts", "review", "limitations"}, "Pstack review")
    if (type(report["schema_version"]) is not int or report["schema_version"] != 1
            or report["method"] != rules["method"] or report["scope"] != rules["scope"]):
        raise ReviewedReleaseError("unsupported review method or claim")
    if report["plugin"] != plugin:
        raise ReviewedReleaseError("review does not match current plugin content")
    match(report["upstream_revision"], controller.SHA, "upstream revision")
    if not set(rules["required_limitations"]) <= set(identifiers(report["limitations"], allowed=LIMITATIONS | EXTRA_LIMITATIONS)):
        raise ReviewedReleaseError("review limitations are incomplete")
    for key, bound in (("evidence_sets", 20), ("runtimes", 20), ("attempts", 100)):
        if not isinstance(report[key], list) or not 0 < len(report[key]) <= bound:
            raise ReviewedReleaseError(f"invalid {key} inventory")
    sets = {}
    declared = []
    for item in report["evidence_sets"]:
        fields(item, {"id", "manifest_sha256", "attempt_ids"}, "evidence set")
        identity = match(item["id"], IDENTIFIER, "evidence set")
        match(item["manifest_sha256"], controller.DIGEST, "evidence manifest digest")
        if identity in sets:
            raise ReviewedReleaseError("duplicate evidence set")
        sets[identity] = identifiers(item["attempt_ids"])
        declared.extend(sets[identity])
    runtimes = {}
    for item in report["runtimes"]:
        fields(item, {"id", "codex_version", "model", "reasoning_effort"}, "observed runtime")
        identity = match(item["id"], IDENTIFIER, "runtime identifier")
        match(item["codex_version"], RUNTIME, "CLI version")
        match(item["model"], RUNTIME, "model")
        if not item["codex_version"].startswith("codex-cli ") or item["reasoning_effort"] not in {
                "none", "minimal", "low", "medium", "high", "xhigh", "max", "ultra"} or identity in runtimes:
            raise ReviewedReleaseError("invalid observed runtime")
        runtimes[identity] = item
    attempts = {}
    covered = set()
    for item in report["attempts"]:
        fields(item, {"id", "scenario", "areas", "runtime", "environment", "evidence_set", "evidence_sha256",
                      "task_sha256", "criteria", "outcome", "failure_kind", "resolved_by", "usage", "timeout_seconds"}, "attempt")
        integer(item["timeout_seconds"], minimum=1, maximum=600)
        identity = match(item["id"], IDENTIFIER, "attempt identifier")
        match(item["scenario"], IDENTIFIER, "scenario identifier")
        if identity in attempts or item["runtime"] not in runtimes or item["environment"] not in ENVIRONMENTS:
            raise ReviewedReleaseError("duplicate attempt or unsupported runtime/environment")
        if item["evidence_set"] not in sets or identity not in sets[item["evidence_set"]]:
            raise ReviewedReleaseError("attempt differs from its frozen evidence set")
        identifiers(item["areas"], allowed=AREAS)
        for key in ("evidence_sha256", "task_sha256"):
            match(item[key], controller.DIGEST, key)
        criteria = fields(item["criteria"], {"passed", "failed"}, "criteria counts")
        passed, failed = (integer(criteria[key], maximum=1000) for key in ("passed", "failed"))
        if passed + failed == 0:
            raise ReviewedReleaseError("attempt has no reviewed criteria")
        usage = fields(item["usage"], {"input_tokens", "cached_input_tokens", "output_tokens"}, "builder usage")
        for count in usage.values():
            integer(count)
        if usage["input_tokens"] == 0 or usage["cached_input_tokens"] > usage["input_tokens"]:
            raise ReviewedReleaseError("missing or inconsistent builder usage")
        if item["outcome"] == "passed":
            if failed or item["failure_kind"] != "none" or item["resolved_by"] is not None:
                raise ReviewedReleaseError("failed criteria cannot be relabeled as a pass")
            covered.update(item["areas"])
        elif item["outcome"] == "failed":
            if not failed or item["failure_kind"] != "environment":
                raise ReviewedReleaseError("unresolved behavioral failure requires new reviewed evidence")
            match(item["resolved_by"], IDENTIFIER, "failure resolution")
        else:
            raise ReviewedReleaseError("unsupported attempt outcome")
        attempts[identity] = item
    if set(declared) != set(attempts) or len(declared) != len(attempts):
        raise ReviewedReleaseError("frozen evidence set is missing attempts or duplicates them")
    if set(runtimes) != {item["runtime"] for item in attempts.values()}:
        raise ReviewedReleaseError("unused observed runtime")
    for index, item in enumerate(report["attempts"]):
        if item["outcome"] != "failed":
            continue
        resolution = attempts.get(item["resolved_by"], {})
        later = {attempt["id"] for attempt in report["attempts"][index + 1:]}
        if (resolution.get("id") not in later or resolution.get("outcome") != "passed"
                or any(resolution.get(key) != item[key] for key in ("scenario", "runtime", "task_sha256", "areas"))
                or item["environment"] != "workspace-write"
                or resolution.get("environment") != "scoped-skill-directory"
                or item["criteria"]["passed"] + item["criteria"]["failed"] != resolution["criteria"]["passed"]):
            raise ReviewedReleaseError("failed attempt lacks a matching authorized environment resolution")
    if any(item["environment"] == "scoped-skill-directory" for item in attempts.values()) and not EXTRA_LIMITATIONS <= set(report["limitations"]):
        raise ReviewedReleaseError("environment repeat limitations are missing")
    if covered != AREAS:
        raise ReviewedReleaseError("required workflow areas lack successful reviewed evidence")
    review = fields(report["review"], {"method", "reviewer_family", "evidence_sha256", "trace_audit_sha256",
                                      "unresolved_criteria"}, "independent review")
    if (review["method"] != "blind-output-plus-parent-trace" or review["reviewer_family"] != "same-family"
            or type(review["unresolved_criteria"]) is not int or review["unresolved_criteria"] != 0):
        raise ReviewedReleaseError("independent review or trace reconciliation is incomplete")
    for key in ("evidence_sha256", "trace_audit_sha256"):
        match(review[key], controller.DIGEST, key)
    return report


def review_summary(report: dict[str, Any]) -> dict[str, Any]:
    attempts = report["attempts"]
    return {"attempts": len(attempts),
            "outcomes": {outcome: sum(item["outcome"] == outcome for item in attempts) for outcome in ("passed", "failed")},
            "criteria": {outcome: sum(item["criteria"][outcome] for item in attempts) for outcome in ("passed", "failed")},
            "builder_usage": {counter: sum(item["usage"][counter] for item in attempts)
                              for counter in ("input_tokens", "cached_input_tokens", "output_tokens")},
            "observed_runtimes": report["runtimes"], "limitations": report["limitations"],
            "preserved_failures": [{key: item[key] for key in ("id", "scenario", "environment", "failure_kind", "resolved_by")}
                                   for item in attempts if item["outcome"] == "failed"]}


def authorize(env: dict[str, str]) -> dict[str, Any]:
    pin = env.get("CONTROLLER_SHA", "")
    tag = env.get("GITHUB_REF_NAME", "")
    if (env.get("GITHUB_REPOSITORY") != legacy.REPOSITORY or env.get("GITHUB_EVENT_NAME") != "workflow_dispatch"
            or env.get("GITHUB_RUN_ATTEMPT") != "1" or env.get("CERTIFICATION_ENABLED") != "true"
            or env.get("APPROVE_REVIEWED_EVIDENCE") != "true" or env.get("WORKFLOW_SHA") != pin
            or env.get("GITHUB_SHA") != pin or not controller.CONTROLLER_TAG.fullmatch(tag)
            or env.get("GITHUB_REF") != f"refs/tags/{tag}"
            or env.get("GITHUB_WORKFLOW_REF") != f"{legacy.REPOSITORY}/.github/workflows/certify-release.yml@refs/tags/{tag}"):
        raise ReviewedReleaseError("reviewed certification requires an enabled first-attempt dispatch from its approved controller tag")
    request = {"repository": legacy.REPOSITORY, "controller_sha": pin, "candidate_sha": env.get("CANDIDATE_SHA", ""),
               "baseline_sha": env.get("BASELINE_SHA", ""), "run_id": env.get("GITHUB_RUN_ID", ""),
               "run_attempt": 1, "review_sha256": env.get("REVIEW_SHA256", "")}
    validate_request(request)
    return request


def validate_request(request: Any) -> None:
    fields(request, REQUEST_KEYS, "reviewed certification request")
    if request["repository"] != legacy.REPOSITORY or type(request["run_attempt"]) is not int or request["run_attempt"] != 1:
        raise ReviewedReleaseError("invalid reviewed certification identity")
    for key in ("controller_sha", "candidate_sha", "baseline_sha"):
        match(request[key], controller.SHA, key)
    match(request["review_sha256"], controller.DIGEST, "reviewed report digest")
    match(request["run_id"], re.compile(r"[1-9][0-9]{0,19}"), "run identity")


def read_candidate_report(repository: Path, request: dict[str, Any], version: str) -> dict[str, Any]:
    name = f"evals/releases/v{version}/pstack-review.json"
    entry = controller.tree(repository, request["candidate_sha"]).get(name)
    if entry is None or entry[0] != "100644":
        raise ReviewedReleaseError("candidate lacks the fixed regular Pstack review report")
    size = int(controller.text_git(repository, "cat-file", "-s", entry[1]))
    if not 0 < size <= MAX_BYTES:
        raise ReviewedReleaseError("candidate review exceeds its byte limit")
    raw = controller.git(repository, "cat-file", "blob", entry[1])
    if hashlib.sha256(raw).hexdigest() != request["review_sha256"]:
        raise ReviewedReleaseError("candidate report differs from the approved review digest")
    with tempfile.TemporaryDirectory(prefix="tugling-review-data-") as directory:
        path = Path(directory) / "review.json"
        path.write_bytes(raw)
        return validate_report(read_json(path), gate.plugin_identity(repository))


def validate_sources(candidate: Path, report: dict[str, Any]) -> None:
    relative = Path("plugins/tugling/skills")
    inventory = relative / pstack_sources.MANIFEST
    if (candidate / inventory).read_bytes() != (ROOT / inventory).read_bytes():
        raise ReviewedReleaseError("source inventory differs from the independently reviewed controller")
    pstack_sources.validate(candidate / relative)
    if report["upstream_revision"] != gate.read_json(ROOT / inventory)["revision"]:
        raise ReviewedReleaseError("review names a different upstream source revision")


def assemble_certificate(request: dict[str, Any], report: dict[str, Any], install: dict[str, Any]) -> dict[str, Any]:
    validate_request(request)
    validate_report(report, report["plugin"])
    if (install.get("passed") is not True or install.get("mode") != "public-cli"
            or install.get("plugin") != report["plugin"] or install.get("live") != {"ran": False}
            or install.get("codex") != {"version": f"codex-cli {legacy.CODEX_VERSION}"}
            or install.get("source") != {"repository": legacy.REPOSITORY, "requested_revision": request["candidate_sha"],
                                        "resolved_revision": request["candidate_sha"], "expected_revision": request["candidate_sha"]}
            or set(install.get("checks", {})) != INSTALL_CHECKS
            or any(value is not True for value in install["checks"].values())):
        raise ReviewedReleaseError("fresh credential-free exact-candidate public installation did not pass")
    return {"schema_version": 2, "version": report["plugin"]["version"],
            "created_at": datetime.now(timezone.utc).isoformat(), "passed": True,
            "checks": {name: True for name in sorted(CHECKS)}, "plugin": report["plugin"],
            "policy_sha256": gate.file_digest(POLICY), "review_sha256": request["review_sha256"], "review": report,
            "behavioral": {"method": METHOD, "scope": SCOPE, "evaluated_revision": request["candidate_sha"],
                           "released_revision": request["baseline_sha"]},
            "clean_room": {"mode": "public-cli", "revision": request["candidate_sha"],
                           "codex_version": f"codex-cli {legacy.CODEX_VERSION}", "model_called": False}}


def verify_certificate(certificate: Any, *, package_source_root: Path | None = None) -> dict[str, Any]:
    fields(certificate, {"schema_version", "version", "created_at", "passed", "checks", "plugin", "policy_sha256",
                         "review_sha256", "review", "behavioral", "clean_room"}, "reviewed certificate")
    if (type(certificate["schema_version"]) is not int or certificate["schema_version"] != 2
            or certificate["passed"] is not True or certificate["policy_sha256"] != gate.file_digest(POLICY)
            or set(certificate["checks"]) != CHECKS or any(value is not True for value in certificate["checks"].values())):
        raise ReviewedReleaseError("certificate lacks current reviewed policy checks")
    match(certificate["review_sha256"], controller.DIGEST, "review digest")
    plugin = certificate["plugin"] if package_source_root is None else gate.plugin_identity(package_source_root)
    fields(plugin, {"name", "version", "content_sha256", "skills"}, "plugin identity")
    match(plugin["version"], controller.VERSION, "plugin version")
    match(plugin["content_sha256"], controller.DIGEST, "package digest")
    identifiers(plugin["skills"])
    if plugin["name"] != "tugling" or certificate["version"] != plugin["version"] or certificate["plugin"] != plugin:
        raise ReviewedReleaseError("certificate does not match current plugin content")
    validate_report(certificate["review"], plugin)
    behavior = fields(certificate["behavioral"], {"method", "scope", "evaluated_revision", "released_revision"}, "release scope")
    if behavior["method"] != METHOD or behavior["scope"] != SCOPE:
        raise ReviewedReleaseError("unsupported certificate claim")
    for key in ("evaluated_revision", "released_revision"):
        match(behavior[key], controller.SHA, key)
    if certificate["clean_room"] != {"mode": "public-cli", "revision": behavior["evaluated_revision"],
                                     "codex_version": f"codex-cli {legacy.CODEX_VERSION}", "model_called": False}:
        raise ReviewedReleaseError("certificate installation identity differs from its candidate")
    if not isinstance(certificate["created_at"], str) or not re.fullmatch(r"[0-9T:.+Z-]{20,40}", certificate["created_at"]):
        raise ReviewedReleaseError("invalid certificate timestamp")
    return certificate


def validate_artifact(output: Path, request: dict[str, Any], *, package_source_root: Path | None = None) -> dict[str, Any]:
    validate_request(request)
    if {path.name for path in output.iterdir()} != {"certificate.json", "certification.json"}:
        raise ReviewedReleaseError("unexpected certification artifact files")
    certificate = verify_certificate(read_json(output / "certificate.json"), package_source_root=package_source_root)
    envelope = fields(read_json(output / "certification.json"), REQUEST_KEYS | {"schema_version", "state", "created_at",
                                                                          "certificate_sha256"}, "reviewed envelope")
    if (type(envelope["schema_version"]) is not int or envelope["schema_version"] != 2
            or envelope["state"] != "CERTIFIED" or any(envelope[key] != value for key, value in request.items())
            or envelope["certificate_sha256"] != gate.file_digest(output / "certificate.json")
            or envelope["created_at"] != certificate["created_at"]
            or certificate["review_sha256"] != request["review_sha256"]
            or certificate["behavioral"]["evaluated_revision"] != request["candidate_sha"]
            or certificate["behavioral"]["released_revision"] != request["baseline_sha"]):
        raise ReviewedReleaseError("reviewed artifact does not bind the exact approved request")
    return certificate


def certify(candidate: Path, request: dict[str, Any], report: dict[str, Any], pattern_file: Path,
            output: Path, codex_bin: str | None = None) -> None:
    legacy.require_fresh_refs(candidate, request)
    legacy.check_public_policy(candidate, pattern_file)
    validate_sources(candidate, report)
    binary, version = clean_room.resolve_codex(codex_bin)
    if version != f"codex-cli {legacy.CODEX_VERSION}":
        raise ReviewedReleaseError("Codex CLI differs from the reviewed installation runtime")
    install = clean_room.public_install(source=legacy.REPOSITORY, ref=request["candidate_sha"], expected_root=candidate,
        codex_bin=binary, codex_version=version, auth_home=output.parent / "unused-no-auth", live=False,
        model="", reasoning_effort="", timeout=120)
    certificate = assemble_certificate(request, report, install)
    legacy.require_fresh_refs(candidate, request)
    output.mkdir()
    gate.write_json(output / "certificate.json", certificate)
    gate.write_json(output / "certification.json", {"schema_version": 2, "state": "CERTIFIED", **request,
        "created_at": certificate["created_at"], "certificate_sha256": gate.file_digest(output / "certificate.json")})
    validate_artifact(output, request, package_source_root=candidate)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("run", "validate-artifact"))
    parser.add_argument("--out", required=True)
    parser.add_argument("--policy-pattern-file")
    parser.add_argument("--codex-bin")
    args = parser.parse_args()
    try:
        request = authorize(dict(os.environ))
        if (controller.text_git(ROOT, "rev-parse", "HEAD") != request["controller_sha"]
                or controller.text_git(ROOT, "status", "--porcelain", "--untracked-files=all")):
            raise ReviewedReleaseError("controller checkout must be clean and match the independently approved pin")
        legacy.require_successful_verify(request["candidate_sha"])
        with tempfile.TemporaryDirectory(prefix="tugling-reviewed-certification-") as directory:
            candidate = Path(directory) / "candidate"
            plan = legacy.prepare_candidate(candidate, request)
            if plan["state"] != "CERTIFICATION_REQUIRED":
                raise ReviewedReleaseError("unchanged plugin content needs no new release certificate")
            controller.require_reviewed_package_modes(candidate, request["controller_sha"], request["candidate_sha"])
            report = read_candidate_report(candidate, request, plan["plugin"]["version"])
            validate_sources(candidate, report)
            output = Path(args.out).resolve()
            if args.command == "validate-artifact":
                certificate = validate_artifact(output, request, package_source_root=candidate)
                if certificate["review"] != report:
                    raise ReviewedReleaseError("signed review differs from the approved candidate report")
                legacy.require_fresh_refs(candidate, request)
            else:
                if not args.policy_pattern_file:
                    raise ReviewedReleaseError("configured public-policy patterns are required")
                certify(candidate, request, report, Path(args.policy_pattern_file), output, args.codex_bin)
        print("CERTIFIED: reviewed Pstack compatibility evidence; no model call")
        return 0
    except (gate.ReleaseGateError, legacy.CertificationError, controller.ControllerError, clean_room.CleanRoomError,
            OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired) as exc:
        detail = str(exc) if isinstance(exc, ReviewedReleaseError) else type(exc).__name__
        print(f"CERTIFICATION_FAILED: {detail}; no attested certificate", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
