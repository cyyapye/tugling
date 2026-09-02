#!/usr/bin/env python3
"""Dependency-free integrity check for the synthetic TypeScript fixture."""

import json
from pathlib import Path


root = Path(__file__).resolve().parents[1]
config = json.loads((root / "config" / "queue.json").read_text(encoding="utf-8"))
assert sum(config["retry_delays_seconds"]) < config["lease_ttl_seconds"]
assert config["max_receive_count"] == 3
assert (root / "src" / "worker.ts").is_file()
assert (root / "tests" / "worker.test.ts").is_file()
print("synthetic TypeScript fixture passed")
