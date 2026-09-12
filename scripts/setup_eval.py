#!/usr/bin/env python3
"""Run bounded project-setup diagnostics using Tugling's existing evaluator."""

from __future__ import annotations

import argparse
import copy
from pathlib import Path
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts import behavioral_eval as harness
from scripts.codex_runtime import BudgetError, RunBudget


CASES = harness.ROOT / "evals" / "setup" / "cases.json"
VERIFIER = harness.ROOT / "evals" / "setup" / "verify_bootstrap.py"


def load_suite() -> dict:
    value = harness.read_json(CASES)
    if not isinstance(value, dict) or value.get("schema_version") != 1:
        raise harness.EvalError("setup cases must use schema_version 1")
    cases = value.get("cases")
    if not isinstance(cases, list) or not cases:
        raise harness.EvalError("setup cases must be a nonempty array")
    errors = [error for case in cases for error in harness.validate_case(case)]
    if errors:
        raise harness.EvalError("; ".join(errors))
    ids = [case.get("id") for case in cases if isinstance(case, dict)]
    if len(ids) != len(set(ids)):
        errors.append("setup case ids must be unique")
    if errors:
        raise harness.EvalError("; ".join(errors))
    # The frozen release matrix and its thresholds are not modified by this suite.
    suite = copy.deepcopy(value)
    suite["gates"] = harness.read_json(harness.DEFAULT_SUITE)["gates"]
    for case in suite["cases"]:
        for command in case.get("post_run_commands", []):
            command[:] = [str(VERIFIER) if part == "{setup_verifier}" else part for part in command]
    return suite


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("validate", help="validate synthetic cases without a model")
    run = commands.add_parser("run", help="run local diagnostics, not release certification")
    harness.add_run_arguments(run)
    run.set_defaults(timeout=300)
    run.add_argument("--case", action="append", default=[])
    run.add_argument("--max-input-tokens", type=int, required=True)
    run.add_argument("--max-output-tokens", type=int, required=True)
    args = parser.parse_args(argv)
    budget = None
    try:
        suite = load_suite()
        if args.command == "validate":
            print(f"Setup diagnostics valid: {len(suite['cases'])} synthetic cases; no model called.")
            return 0
        if args.require_gate == "promotion" or args.condition in ("released", "all") or args.baseline_ref:
            raise harness.EvalError("setup diagnostics do not certify a release; use control/candidate conditions")
        if args.jobs != 1 or not 1 <= args.attempts <= 3 or not 30 <= args.timeout <= 600:
            raise harness.EvalError("setup diagnostics require jobs=1, attempts=1..3, timeout=30..600")
        cases = harness.select_cases(suite, args.case)
        total = len(cases) * len(harness.conditions_for(args.condition)) * args.attempts
        if total > 24:
            raise harness.EvalError("setup diagnostics are limited to 24 model tasks per invocation")
        budget = RunBudget(args.max_input_tokens, args.max_output_tokens, total)
        _, exit_code = harness.run_evaluation(suite=suite, cases=cases, args=args, budget=budget)
        return exit_code
    except (harness.EvalError, BudgetError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    finally:
        if budget is not None:
            print(f"Observed usage (between tasks, not a hard billing cap): {budget.report()}", file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
