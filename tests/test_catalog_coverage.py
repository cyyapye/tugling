import json
import tempfile
import unittest
from pathlib import Path

from scripts import catalog_coverage


class CatalogCoverageTest(unittest.TestCase):
    def test_pending_declaration_must_match_missing_cases_exactly(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "coverage.json"
            cases = [{"skill": "how"}]
            for pending, valid in (({"why": "Needs a runtime case"}, True),
                                   ({}, False), ({"how": "Already covered"}, False),
                                   ({"why": ""}, False)):
                with self.subTest(pending=pending):
                    path.write_text(json.dumps({"schema_version": 1, "pending_skills": pending}))
                    self.assertEqual(not catalog_coverage.validate(cases, {"how", "why"}, path), valid)

    def test_release_requires_catalog_equality_not_a_subset_or_pending_waiver(self):
        self.assertFalse(catalog_coverage.release_covered({"how", "why"}, ["how"]))
        self.assertFalse(catalog_coverage.release_covered({"how"}, ["how", "why"]))
        self.assertFalse(catalog_coverage.release_covered(set(), []))
        self.assertTrue(catalog_coverage.release_covered({"how", "why"}, ["how", "why"]))
