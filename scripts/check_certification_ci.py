#!/usr/bin/env python3
"""Exercise installation and behavioral execution through the official proxy."""
from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
from pathlib import Path
import sys
import tempfile
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import certify_release as certification

FAKE_CREDENTIAL = "tugling-synthetic-credential-not-a-secret"


def write_state(path: Path, state: dict) -> None:
    temporary = path.with_suffix(".pending")
    temporary.write_text(json.dumps(state))
    temporary.replace(path)


def serve(path: Path) -> None:
    state = {"pid": os.getpid(), "requests": [], "port": 0, "tool_read_observed": False,
             "tool_read_count": 0}

    class FakeAPI(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_POST(self):
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 2 * 1024 * 1024:
                self.send_error(413)
                return
            body = json.loads(self.rfile.read(length))
            tool_read = any(
                item.get("type") in {"custom_tool_call_output", "function_call_output"}
                and "Synthetic fixture instructions" in json.dumps(item.get("output", ""))
                for item in body.get("input", []) if isinstance(item, dict))
            state["tool_read_observed"] = state["tool_read_observed"] or tool_read
            state["tool_read_count"] += int(tool_read)
            state["requests"].append({
                "path_matches": self.path == "/v1/responses",
                "model_matches": body.get("model") == certification.MODEL,
                "effort_matches": body.get("reasoning", {}).get("effort") == certification.EFFORT,
                "synthetic_auth": self.headers.get("Authorization") == "Bearer " + FAKE_CREDENTIAL,
            })
            write_state(path, state)
            answer = json.dumps({"selected_skill": "repo-verify", "canonical_verify": "make verify",
                                 "verification_order": "repository-native-first",
                                 "strongest_proven_state": "ADVISORY", "edited_files": False})
            schema = body.get("text", {}).get("format", {}).get("schema", {})
            case_ids = schema.get("properties", {}).get("case_id", {}).get("enum", [])
            if case_ids:
                # Valid structured output for the real behavioral CLI path.
                # Deliberately contains no correct decisions or behavioral proof.
                answer = json.dumps({"case_id": case_ids[0], "summary": "Synthetic runtime check",
                    "decisions": [], "commands_run": ["cat AGENTS.md"], "artifacts_inspected": ["AGENTS.md"],
                    "changes_made": [], "strongest_proven_state": "ADVISORY", "unverified": ["All behavior"]})
            item = {"id": "msg_synthetic", "type": "message", "role": "assistant", "status": "completed",
                    "content": [{"type": "output_text", "text": answer, "annotations": []}]}
            response = {"id": "resp_synthetic", "object": "response", "status": "completed",
                        "output": [item], "usage": {"input_tokens": 100, "output_tokens": 50,
                        "total_tokens": 150, "input_tokens_details": {"cached_tokens": 0},
                        "output_tokens_details": {"reasoning_tokens": 0}}}
            events = [
                {"type": "response.created", "response": {**response, "status": "in_progress", "output": []}},
                {"type": "response.output_item.added", "output_index": 0,
                 "item": {**item, "status": "in_progress", "content": []}},
                {"type": "response.output_text.delta", "item_id": item["id"], "output_index": 0,
                 "content_index": 0, "delta": answer},
                {"type": "response.output_text.done", "item_id": item["id"], "output_index": 0,
                 "content_index": 0, "text": answer},
                {"type": "response.output_item.done", "output_index": 0, "item": item},
                {"type": "response.completed", "response": response},
            ]
            if len(state["requests"]) % 2 == 1:
                tool = {"id": "ctc_synthetic", "type": "custom_tool_call", "call_id": "call_synthetic",
                        "name": "exec", "namespace": "functions",
                        "input": 'const result = await tools.exec_command({cmd: "cat AGENTS.md", max_output_tokens: 300}); text(result.output);'}
                response["output"] = [tool]
                events = [
                    {"type": "response.created", "response": {**response, "status": "in_progress", "output": []}},
                    {"type": "response.output_item.done", "output_index": 0, "item": tool},
                    {"type": "response.completed", "response": response},
                ]
            payload = "".join("event: " + event["type"] + "\ndata: " + json.dumps(
                {**event, "sequence_number": index}) + "\n\n" for index, event in enumerate(events)).encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

    with HTTPServer(("127.0.0.1", 0), FakeAPI) as server:
        state["port"] = server.server_port
        write_state(path, state)
        server.serve_forever()


def ready(path: Path) -> None:
    for _ in range(100):
        if path.is_file():
            state = json.loads(path.read_text())
            print(f"endpoint=http://127.0.0.1:{state['port']}/v1/responses")
            return
        time.sleep(0.1)
    raise RuntimeError("Synthetic provider did not start")


def resource_snapshot(proc: Path = Path("/proc")) -> dict:
    """Report numeric Linux resource data only, never process names or arguments."""
    def fields(path: Path) -> dict:
        if not path.is_file():
            return {}
        return {parts[0].rstrip(":"): int(parts[1]) for line in path.read_text().splitlines()
                if len(parts := line.split()) == 3 and parts[1].isdigit() and parts[2] == "kB"}

    memory, own = fields(proc / "meminfo"), fields(proc / "self/status")
    return {"memory_total_kib": memory.get("MemTotal"),
            "memory_available_kib": memory.get("MemAvailable"),
            "harness_rss_kib": own.get("VmRSS"),
            "process_count": sum(path.name.isdigit() for path in proc.iterdir()) if proc.is_dir() else None}


def check(args: argparse.Namespace) -> None:
    import certification_tasks as tasks
    import certification_worker as worker
    if not 1 <= args.tasks <= 91:
        raise RuntimeError("Synthetic task count must be between 1 and 91")
    initial = json.loads(args.state.read_text())
    info = json.loads(args.proxy_info.read_text())
    port = info.get("port")
    if type(port) is not int or not 1 <= port <= 65535 or port == initial["port"] or initial["requests"]:
        raise RuntimeError("Check requires a fresh synthetic provider behind the official proxy")
    allowed = {"PATH", "HOME", "TMPDIR", "TMP", "TEMP", "LANG", "LC_ALL", "RUNNER_TRACKING_ID"}
    env = {key: value for key, value in os.environ.items() if key in allowed}
    env["TUGLING_CODEX_PROXY_URL"] = f"http://127.0.0.1:{port}/v1"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    with patch.dict(os.environ, env, clear=True), tempfile.TemporaryDirectory(prefix="tugling-fake-certification-") as directory:
        binary, version = certification.clean_room.resolve_codex(args.codex_bin)
        if version != f"codex-cli {certification.CODEX_VERSION}":
            raise RuntimeError("CLI differs from the reviewed pin")
        report = {"synthetic_only": True, "passed": False, "requested_tasks": args.tasks,
                  "initial_resources": resource_snapshot(), "tasks": []}
        for task in range(1, args.tasks + 1):
            result = certification.clean_room.public_install(
                source=args.source, ref=args.ref, expected_root=ROOT, codex_bin=binary,
                codex_version=version, auth_home=Path(directory) / "no-auth", live=True,
                model=certification.MODEL, reasoning_effort=certification.EFFORT, timeout=45)
            state = json.loads(args.state.read_text())
            snapshot = {"task": task, "checks": result["checks"],
                        "fake_request_count": len(state["requests"]),
                        "tool_read_observed": state["tool_read_observed"],
                        "tool_read_count": state["tool_read_count"],
                        "resources": resource_snapshot()}
            report["tasks"].append(snapshot)
            print(json.dumps(snapshot, sort_keys=True), flush=True)
            if args.out:
                write_state(args.out, report)
            if (result["passed"] is not True or len(state["requests"]) != 2 * task
                    or not all(all(request.values()) for request in state["requests"])
                    or state["tool_read_count"] != task):
                raise RuntimeError("Installation or synthetic-provider contract failed")
            if result["live"]["usage"] != {"input_tokens": 200, "output_tokens": 100, "cached_input_tokens": 0}:
                raise RuntimeError("Synthetic completion usage did not reach the installation report")
        revision = certification.controller.text_git(ROOT, "rev-parse", "HEAD")
        plan = tasks.manifest({"repository": certification.REPOSITORY, "controller_sha": revision,
            "candidate_sha": revision, "baseline_sha": revision, "run_id": "1", "run_attempt": 1,
            "input_limit": 5_000_000, "output_limit": 500_000}, synthetic=True)
        report["behavioral_tasks"] = []
        for task in plan["tasks"][1:]:
            if task["trial"] != 1 or task["condition"] != "candidate":
                continue
            work = Path(directory) / task["id"]
            work.mkdir()
            receipt = worker.execute(plan, tasks.record(plan, task["id"], 0, "admission"), work, None)
            checks = (receipt.get("evidence") or {}).get("checks")
            snapshot = {"task": task["id"], "state": receipt["state"], "usage": receipt["usage"],
                        "checks": checks}
            report["behavioral_tasks"].append(snapshot)
            print(json.dumps(snapshot, sort_keys=True), flush=True)
            if args.out:
                write_state(args.out, report)
            if (receipt["state"] != "RESULT"
                    or receipt["usage"] != {"input_tokens": 200, "output_tokens": 100, "cached_input_tokens": 0}):
                raise RuntimeError("Behavioral CLI/parser/receipt contract failed")
            tasks.validate_behavioral_checks(task["case_id"], checks)
            if task["case_id"] == "tugling-bounded-noop" and checks["change_budget"] is not True:
                raise RuntimeError("Read-only synthetic tool execution dirtied the no-op fixture")
        state = json.loads(args.state.read_text())
        if (len(report["behavioral_tasks"]) != 10 or len(state["requests"]) != 2 * (args.tasks + 10)
                or not all(all(request.values()) for request in state["requests"])):
            raise RuntimeError("Behavioral requests escaped the exact synthetic proxy contract")
        report["passed"] = True
        if args.out:
            write_state(args.out, report)
    print("Installation and all ten behavioral execution paths passed through the official proxy and a local fake API; no provider calls or behavioral proof.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("serve", "ready", "check"))
    parser.add_argument("--state", required=True, type=Path)
    parser.add_argument("--proxy-info", type=Path)
    parser.add_argument("--codex-bin")
    parser.add_argument("--source")
    parser.add_argument("--ref")
    parser.add_argument("--tasks", type=int, default=1)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    if args.command == "serve":
        serve(args.state)
    elif args.command == "ready":
        ready(args.state)
    else:
        try:
            check(args)
        except Exception as exc:
            print("CERTIFICATION_RUNTIME_FAILED: " + certification.safe_failure_detail(exc), file=sys.stderr)
            raise SystemExit(1)
