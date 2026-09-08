#!/usr/bin/env python3
"""Run one disposable Linux worker outside the GitHub runner's user/cgroup.

The trusted caller keeps sudo; the worker gets no capabilities, sudo, writable
controller files, or host control sockets. The official API proxy stays outside
the worker. All writable filesystems and process output are bounded.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import pwd
import subprocess
import sys
import tempfile
import time

WORKER_USER = "tugling-worker"
PROPERTIES = {
    "User": WORKER_USER, "Group": WORKER_USER,
    "NoNewPrivileges": "yes", "CapabilityBoundingSet": "",
    "AmbientCapabilities": "", "ProtectSystem": "strict",
    "ProtectHome": "read-only", "ProtectKernelTunables": "yes",
    "ProtectKernelModules": "yes", "ProtectControlGroups": "yes",
    "RestrictSUIDSGID": "yes", "RestrictRealtime": "yes",
    "PrivateDevices": "yes", "MemoryMax": "4G", "MemorySwapMax": "0",
    "CPUQuota": "200%", "TasksMax": "256", "RuntimeMaxSec": "300",
    "TimeoutStopSec": "5", "KillMode": "control-group", "LimitFSIZE": "16M",
    "TemporaryFileSystem": "/tmp:rw,nosuid,nodev,size=512M /var/tmp:rw,nosuid,nodev,size=128M",
    "InaccessiblePaths": "-/run/docker.sock -/run/containerd -/run/dbus -/run/systemd/private",
}
MAX_OUTPUT_BYTES = 16 * 1024 * 1024


def setup(work: Path) -> None:
    if sys.platform != "linux" or os.geteuid() != 0:
        raise RuntimeError("worker setup requires root on an ephemeral Linux CI runner")
    try:
        account = pwd.getpwnam(WORKER_USER)
    except KeyError:
        subprocess.run(["useradd", "--system", "--user-group", "--no-create-home",
                        "--shell", "/usr/sbin/nologin", WORKER_USER], check=True)
        account = pwd.getpwnam(WORKER_USER)
    work.mkdir(mode=0o755, parents=True, exist_ok=False)
    subprocess.run(["mount", "-t", "tmpfs", "-o", "size=1G,nosuid,nodev,mode=0755",
                    "tmpfs", str(work)], check=True)
    os.chown(work, account.pw_uid, account.pw_gid)
    # Hosted runners keep their temporary directory non-traversable. Permit
    # reaching this explicitly shared mount without granting directory listings
    # or read access to any other user's private files.
    for parent in work.parents:
        parent.chmod(parent.stat().st_mode | 0o001)


def command(unit: str, work: Path, argv: list[str], environment: Path,
            properties: dict | None = None) -> list[str]:
    return ["sudo", "-n", "systemd-run", "--quiet", "--wait", "--pipe", f"--unit={unit}",
            *[f"--property={key}={value}" for key, value in (properties or PROPERTIES).items()],
            f"--property=ReadWritePaths={work}", f"--property=WorkingDirectory={work}",
            f"--property=EnvironmentFile={environment}", "--", *argv]


def execute(work: Path, argv: list[str], *, env: dict[str, str], out: Path,
            properties: dict | None = None) -> int:
    if sys.platform != "linux" or os.geteuid() == 0:
        raise RuntimeError("trusted supervisor must be a non-root Linux runner")
    account = pwd.getpwnam(WORKER_USER)
    if account.pw_uid == os.getuid() or not os.path.ismount(work):
        raise RuntimeError("separate worker user and bounded filesystem are required")
    unit = "tugling-task-" + str(os.getpid())
    # Only deliberate public settings reach the unit. API keys and GitHub
    # credentials never enter either this file or the worker environment.
    allowed = {"PATH", "LANG", "LC_ALL", "PYTHONDONTWRITEBYTECODE", "TUGLING_CODEX_PROXY_URL",
               "PUBLIC_REPOSITORY", "PUBLIC_REVISION"}
    selected = {key: value for key, value in env.items() if key in allowed}
    selected.update(HOME=str(work), TMPDIR=str(work), PYTHONDONTWRITEBYTECODE="1")
    with tempfile.TemporaryDirectory(prefix="tugling-supervisor-") as directory:
        private = Path(directory)
        environment = private / "environment"
        environment.write_text("".join(key + "=" + json.dumps(value) + "\n" for key, value in selected.items()))
        environment.chmod(0o600)
        log = private / "unit.log"
        telemetry = {"worker_uid_distinct": True, "bounded_filesystem": True,
                     "memory_peak_bytes": 0, "tasks_peak": 0, "output_limit_hit": False,
                     "supervisor_timeout": False, "exit_code": None, "service_result": None}
        started = time.monotonic()
        with log.open("wb") as stream:
            process = subprocess.Popen(command(unit, work, argv, environment, properties),
                                       stdout=stream, stderr=stream)
            try:
                while process.poll() is None:
                    state = subprocess.run(["systemctl", "show", unit, "--property=MemoryPeak,TasksCurrent"],
                                           capture_output=True, text=True, timeout=5)
                    for line in state.stdout.splitlines():
                        key, _, value = line.partition("=")
                        target = {"MemoryPeak": "memory_peak_bytes", "TasksCurrent": "tasks_peak"}.get(key)
                        if target and value.isdigit() and int(value) < 2**63:
                            telemetry[target] = max(telemetry[target], int(value))
                    if log.stat().st_size > MAX_OUTPUT_BYTES or time.monotonic() - started > 330:
                        telemetry["output_limit_hit"] = log.stat().st_size > MAX_OUTPUT_BYTES
                        telemetry["supervisor_timeout"] = time.monotonic() - started > 330
                        subprocess.run(["sudo", "-n", "systemctl", "kill", "--signal=KILL", unit],
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
                        break
                    time.sleep(0.2)
                telemetry["exit_code"] = process.wait(timeout=15)
            finally:
                status = subprocess.run(["systemctl", "show", unit, "--property=Result", "--value"],
                                        capture_output=True, text=True, timeout=5).stdout.strip()
                if status in {"success", "exit-code", "signal", "core-dump", "watchdog", "timeout",
                              "oom-kill", "resources", "protocol"}:
                    telemetry["service_result"] = status
                subprocess.run(["sudo", "-n", "systemctl", "stop", unit],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)
                subprocess.run(["sudo", "-n", "systemctl", "reset-failed", unit],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
                if process.poll() is None:
                    process.kill()
                    process.wait(timeout=5)
        out.write_text(json.dumps(telemetry, sort_keys=True) + "\n")
        # The private log is never published. Exit categories and numeric
        # telemetry are enough for public diagnostics.
        return telemetry["exit_code"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("setup", "run", "cleanup"))
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--out", type=Path)
    raw = sys.argv[1:]
    split = raw.index("--") if "--" in raw else len(raw)
    args = parser.parse_args(raw[:split])
    if args.mode == "setup":
        setup(args.work.resolve())
        return 0
    if args.mode == "cleanup":
        if os.path.ismount(args.work):
            subprocess.run(["umount", str(args.work)], check=True)
        args.work.rmdir()
        return 0
    argv = raw[split + 1:]
    return execute(args.work.resolve(), argv, env=dict(os.environ), out=args.out)


if __name__ == "__main__":
    raise SystemExit(main())
