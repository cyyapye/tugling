#!/usr/bin/env python3
"""Dependency-free integrity check for the synthetic React fixture."""

from pathlib import Path


root = Path(__file__).resolve().parents[1]
component = (root / "src" / "Holdings.tsx").read_text(encoding="utf-8")
styles = (root / "src" / "holdings.css").read_text(encoding="utf-8")
assert "holdingRow" in component
assert "min-width: 32.5rem" in styles
assert (root / "desktop.png").is_file()
assert (root / "mobile.png").is_file()
print("synthetic React fixture passed")
