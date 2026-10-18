"""Synthetic reviewed evidence for disposable controller/provider tests."""
from scripts import pstack_release as reviewed


def report(plugin):
    attempts = []
    for index, area in enumerate(sorted(reviewed.AREAS)):
        attempts.append({"id": f"task-{index}", "scenario": f"scenario-{index}", "areas": [area],
            "runtime": "synthetic", "environment": "workspace-write", "evidence_set": "synthetic",
            "evidence_sha256": "1" * 64, "task_sha256": "2" * 64, "timeout_seconds": 240,
            "criteria": {"passed": 1, "failed": 0}, "outcome": "passed", "failure_kind": "none",
            "resolved_by": None, "usage": {"input_tokens": 100, "cached_input_tokens": 50, "output_tokens": 10}})
    return {"schema_version": 1, "method": "pstack-eval", "scope": "codex-port-compatibility", "plugin": plugin,
        "upstream_revision": "a" * 40,
        "evidence_sets": [{"id": "synthetic", "manifest_sha256": "3" * 64,
                           "attempt_ids": [item["id"] for item in attempts]}],
        "runtimes": [{"id": "synthetic", "codex_version": "codex-cli 0.153.4", "model": "synthetic-model",
                      "reasoning_effort": "medium"}], "attempts": attempts,
        "review": {"method": "blind-output-plus-parent-trace", "reviewer_family": "same-family",
                   "evidence_sha256": "4" * 64, "trace_audit_sha256": "5" * 64, "unresolved_criteria": 0},
        "limitations": sorted(reviewed.LIMITATIONS)}


def request(candidate="b" * 40, baseline="c" * 40, controller="a" * 40):
    return {"repository": "cyyapye/tugling", "controller_sha": controller, "candidate_sha": candidate,
            "baseline_sha": baseline, "run_id": "123", "run_attempt": 1, "review_sha256": "d" * 64}


def install(plugin, candidate):
    return {"passed": True, "mode": "public-cli", "plugin": plugin, "live": {"ran": False},
            "codex": {"version": "codex-cli 0.153.4"},
            "source": {"repository": "cyyapye/tugling", "requested_revision": candidate,
                       "resolved_revision": candidate, "expected_revision": candidate},
            "checks": {name: True for name in reviewed.INSTALL_CHECKS}}


def certificate(plugin, candidate="b" * 40, baseline="c" * 40, controller="a" * 40):
    return reviewed.assemble_certificate(request(candidate, baseline, controller), report(plugin), install(plugin, candidate))
