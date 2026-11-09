"""Keep synthetic release repositories independent of upstream test-corpus size."""

import json
import shutil
from pathlib import Path


def omit_statechart_corpus(repo: Path) -> None:
    # Release fixtures exercise Git identity and authority, not TLC replay data.
    # Source and clean-room tests separately validate the complete shipped bundle.
    bundle = repo / "plugins/tugling/skills"
    corpus = "statechart/scripts/test/"
    shutil.rmtree(bundle / corpus, ignore_errors=True)
    path = bundle / "poteto-mode/references/upstream/sources.json"
    manifest = json.loads(path.read_text())
    for group in ("files", "local_files"):
        manifest[group] = [item for item in manifest[group]
                           if not item["path"].startswith(corpus)]
    path.write_text(json.dumps(manifest, indent=2) + "\n")
