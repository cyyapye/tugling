"""Shared CI transport, process cleanup, and between-task usage accounting.

The official Codex Action owns the API credential. These helpers receive only
its loopback proxy address. Token thresholds are admission limits between tasks,
not a hard cap on tokens or dollars spent by an in-flight task.
"""

from __future__ import annotations

import os
import re
import signal
import subprocess
from dataclasses import dataclass
from typing import Any


class BudgetError(RuntimeError):
    pass


def proxy_arguments() -> list[str]:
    address = os.environ.get("TUGLING_CODEX_PROXY_URL")
    if address is None:
        return []
    match = re.fullmatch(r"http://127\.0\.0\.1:([0-9]{1,5})/v1", address)
    if match is None or not 1 <= int(match[1]) <= 65535:
        raise ValueError("CI requires the official action's loopback Responses proxy")
    values = {
        "model_provider": '"tugling-ci"',
        "model_providers.tugling-ci.name": '"Tugling CI"',
        "model_providers.tugling-ci.base_url": f'"{address}"',
        "model_providers.tugling-ci.wire_api": '"responses"',
        "model_providers.tugling-ci.requires_openai_auth": "false",
        "model_providers.tugling-ci.request_max_retries": "0",
        "model_providers.tugling-ci.stream_max_retries": "0",
        "model_providers.tugling-ci.supports_websockets": "false",
        "web_search": '"disabled"',
        "sandbox_workspace_write.exclude_slash_tmp": "true",
        "sandbox_workspace_write.exclude_tmpdir_env_var": "true",
    }
    return [part for key, value in values.items() for part in ("--config", f"{key}={value}")]


def child_environment(env: dict[str, str]) -> dict[str, str]:
    if not proxy_arguments():
        return env
    # Neither GitHub credentials nor policy patterns belong in fixture commands.
    allowed = {"PATH", "HOME", "TMPDIR", "TMP", "TEMP", "LANG", "LC_ALL", "CODEX_HOME",
               "NO_COLOR", "PYTHONDONTWRITEBYTECODE", "TUGLING_BEHAVIORAL_EVAL", "RUNNER_TRACKING_ID"}
    return {key: value for key, value in env.items() if key in allowed}


def run_process(argv: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
    """Stop background descendants before scratch cleanup on every POSIX exit."""
    timeout = kwargs.pop("timeout")
    kwargs.pop("check", None)
    capture = kwargs.pop("capture_output", False)
    if capture:
        kwargs.update(stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if os.name != "posix":
        return subprocess.run(argv, timeout=timeout, check=False, **kwargs)
    with subprocess.Popen(argv, start_new_session=True, **kwargs) as process:
        communicated = False
        try:
            stdout, stderr = process.communicate(timeout=timeout)
            communicated = True
        finally:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            if not communicated:
                process.communicate()
        return subprocess.CompletedProcess(argv, process.returncode, stdout, stderr)


@dataclass
class RunBudget:
    input_limit: int
    output_limit: int
    task_limit: int
    tasks: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cached_input_tokens: int = 0
    in_flight_or_unaccounted_task: bool = False

    def __post_init__(self) -> None:
        if any(type(value) is not int or value <= 0 for value in
               (self.input_limit, self.output_limit, self.task_limit)):
            raise BudgetError("usage limits must be positive integers")

    def begin(self) -> None:
        if (self.in_flight_or_unaccounted_task or self.tasks >= self.task_limit or self.input_tokens >= self.input_limit
                or self.output_tokens >= self.output_limit):
            raise BudgetError("usage threshold reached; no further model task admitted")
        self.in_flight_or_unaccounted_task = True

    def record(self, usage: dict[str, Any]) -> None:
        keys = ("input_tokens", "output_tokens", "cached_input_tokens")
        if (not isinstance(usage, dict) or any(type(usage.get(key)) is not int or usage[key] < 0
                                             for key in keys)
                or usage["input_tokens"] == 0
                or usage["cached_input_tokens"] > usage["input_tokens"]):
            raise BudgetError("model usage missing or invalid; certification stops")
        self.tasks += 1
        self.in_flight_or_unaccounted_task = False
        for key in keys:
            setattr(self, key, getattr(self, key) + usage[key])
        if self.input_tokens > self.input_limit or self.output_tokens > self.output_limit:
            raise BudgetError("completed task exceeded the observed-token threshold; certification stops")

    def report(self) -> dict[str, Any]:
        return {
            "accounting": "between-tasks-not-hard-billing-cap",
            "input_limit": self.input_limit, "output_limit": self.output_limit,
            "task_limit": self.task_limit, "completed_tasks": self.tasks,
            "input_tokens": self.input_tokens, "output_tokens": self.output_tokens,
            "cached_input_tokens": self.cached_input_tokens,
            "in_flight_or_unaccounted_task": self.in_flight_or_unaccounted_task,
        }
