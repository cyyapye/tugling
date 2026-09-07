#!/usr/bin/env python3
"""Exercise the pinned real CLI against a local fake API; never call a provider."""

from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import certify_release as certification
import codex_runtime as runtime


def check(binary: str) -> None:
    observed = []

    class FakeAPI(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))))
            observed.append((self.path, body, self.headers.get("Authorization")))
            payload = json.dumps({"error": {"message": "synthetic-private-error-message",
                                           "type": "invalid_request_error", "code": "unsupported_value"}}).encode()
            self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

    with tempfile.TemporaryDirectory(prefix="tugling-cli-contract-") as directory:
        scratch = Path(directory)
        fixture = scratch / "fixture"
        fixture.mkdir()
        subprocess.run(["git", "init", "--quiet", "--template=", str(fixture)], check=True)
        codex_home = scratch / "codex-home"
        codex_home.mkdir(mode=0o700)
        server = HTTPServer(("127.0.0.1", 0), FakeAPI)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            with patch.dict(os.environ, {"TUGLING_CODEX_PROXY_URL": f"http://127.0.0.1:{server.server_port}/v1"}):
                env = runtime.child_environment({**os.environ, "CODEX_HOME": str(codex_home)})
                version = subprocess.run([binary, "--version"], env=env, text=True,
                                         capture_output=True, check=True, timeout=15).stdout.strip()
                if version != f"codex-cli {certification.CODEX_VERSION}":
                    raise RuntimeError("runtime differs from the reviewed pin")
                # Probe the actual public installation interface without installing
                # anything or using account authentication.
                for command in (("plugin", "marketplace", "add"), ("plugin", "add")):
                    subprocess.run([binary, *command, "--help"], env=env,
                                   capture_output=True, check=True, timeout=15)
                schema = scratch / "output.schema.json"
                schema.write_text(json.dumps({"type": "object", "properties": {
                    "ok": {"type": "boolean"}}, "required": ["ok"], "additionalProperties": False}))
                argv = [binary, "exec", "--ephemeral", "--ignore-user-config", "--ignore-rules",
                        "--json", "--color", "never", "--sandbox", "read-only", "--cd", str(fixture),
                        "--model", certification.MODEL, "--config", 'model_reasoning_effort="medium"',
                        "--output-schema", str(schema), "--output-last-message", str(scratch / "final.json"),
                        *runtime.proxy_arguments(), "This is a synthetic transport test. Return ok=true."]
                result = runtime.run_process(argv, env=env, cwd=fixture, stdin=subprocess.DEVNULL,
                                             capture_output=True, text=True, timeout=45)
                if result.returncode == 0 or len(observed) != 1:
                    raise RuntimeError("CLI did not make exactly one request to the local fake API")
                path, body, auth = observed[0]
                if (path != "/v1/responses" or body.get("model") != certification.MODEL
                        or body.get("reasoning", {}).get("effort") != certification.EFFORT or auth):
                    raise RuntimeError("CLI did not use the explicit credential-free proxy contract")
                diagnostics = runtime.failure_diagnostics(result.stdout)
                # The pinned CLI can retain the API code while omitting HTTP status.
                if (diagnostics["http_statuses"] not in ([], [400])
                        or diagnostics["api_error_codes"] != ["unsupported_value"]
                        or diagnostics["error_event_observed"] is not True
                        or diagnostics["turn_failed"] is not True
                        or "synthetic-private-error-message" in json.dumps(diagnostics)):
                    raise RuntimeError("CLI rejection did not preserve safe failure categories")
        finally:
            server.shutdown()
            server.server_close()
            worker.join()
    print("Codex CI transport contract passed against a local fake API; no provider calls.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--codex-bin", required=True)
    check(parser.parse_args().codex_bin)
