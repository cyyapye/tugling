import unittest

from src.notes import normalize_note


class NotesTest(unittest.TestCase):
    def test_normalizes_spacing(self) -> None:
        self.assertEqual(normalize_note("one   two"), "one two")


if __name__ == "__main__":
    unittest.main()
