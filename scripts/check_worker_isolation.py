#!/usr/bin/env python3
"""Free Linux integration proof: memory, PID, timeout, UID and filesystem faults.

Every destructive operation is confined to the task's disposable cgroup and
tmpfs. This script uses no model, provider, credentials, or repository mutation.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

import certification_sandbox as sandbox


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    subprocess.run(["sudo", "-n", "python3", "-I", str(Path(sandbox.__file__)),
                    "setup", "--work", str(args.work)], check=True)
    checks = {}
    try:
        # The supervisor's process is a sentinel outside the worker UID/cgroup.
        identity = f'''
import os,json,errno
from pathlib import Path
assert os.getuid() != {os.getuid()}
try:
    os.kill({os.getpid()}, 0)
except PermissionError:
    pass
else:
    raise AssertionError("worker could signal supervisor")
try:
    Path({str(Path(__file__).resolve().parent / "forbidden-worker-write")!r}).write_text("forbidden")
except OSError as exc:
    assert exc.errno in (errno.EACCES, errno.EPERM, errno.EROFS)
else:
    raise AssertionError("controller checkout writable")
Path("identity-ok").write_text("ok")
'''
        probes = {
            "identity_and_readonly_controller": (identity, {}, True),
            "memory_exhaustion": ("x=bytearray(512*1024*1024)", {"MemoryMax": "64M"}, False),
            "timeout": ("import time; time.sleep(15)", {"RuntimeMaxSec": "1", "TimeoutStopSec": "1"}, False),
            "process_limit": ('''import subprocess,sys,errno
children=[]
try:
    for i in range(40):
        children.append(subprocess.Popen([sys.executable,"-c","import time; time.sleep(30)"]))
except OSError as exc:
    assert exc.errno == errno.EAGAIN
else:
    raise AssertionError("process limit not enforced")
''', {"TasksMax": "16"}, True),
        }
        for name, (program, overrides, success) in probes.items():
            script = args.out / "probe.py"
            script.write_text(program)
            code = sandbox.execute(args.work, ["python3", str(script)], env=dict(os.environ),
                out=args.out / (name + ".json"), properties={**sandbox.PROPERTIES, **overrides})
            checks[name] = (code == 0) == success
            telemetry = json.loads((args.out / (name + ".json")).read_text())
            if name in {"memory_exhaustion", "timeout"}:
                expected = "oom-kill" if name == "memory_exhaustion" else "timeout"
                checks[name] = checks[name] and telemetry["service_result"] == expected
            if not checks[name]:
                raise RuntimeError("worker isolation check failed: " + name)
        # Re-run after all faults, proving the supervisor can still launch work.
        script = args.out / "after.py"
        script.write_text('print("worker-recovered")')
        checks["supervisor_survives_and_restarts_worker"] = sandbox.execute(args.work,
            ["python3", str(script)], env=dict(os.environ), out=args.out / "after.json") == 0
    finally:
        subprocess.run(["sudo", "-n", "python3", "-I", str(Path(sandbox.__file__)),
                        "cleanup", "--work", str(args.work)], check=True)
        (args.out / "isolation-proof.json").write_text(json.dumps({"synthetic_only": True,
            "checks": checks, "passed": len(checks) == 5 and all(checks.values())}, sort_keys=True) + "\n")
    return 0 if len(checks) == 5 and all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
