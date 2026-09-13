"""Bounded synthetic provider reads and ownership-scoped report rendering."""

from pathlib import Path

POLL_SECONDS = 30


class FakeProvider:
    def __init__(self):
        self.calls = 0

    def sample(self):
        self.calls += 1
        return {"status": "ready"}


def collect_samples(tenants=3, duration_seconds=600):
    providers = [FakeProvider() for _ in range(tenants)]
    for second in range(duration_seconds):
        if second % POLL_SECONDS == 0:
            for provider in providers:
                provider.sample()
    return [provider.calls for provider in providers]


def render_report(directory, fail_after_write=False):
    owned = Path(directory) / "quota-report.tmp"
    # Exclusive creation establishes ownership before the cleanup scope starts.
    with owned.open("x") as stream:
        try:
            stream.write("synthetic report\n")
            stream.flush()
            if fail_after_write:
                raise RuntimeError("synthetic rendering failure")
            return "ready"
        finally:
            owned.unlink()
