import unittest

from src.app import render_label


class AppTest(unittest.TestCase):
    def test_label_is_normalized(self) -> None:
        self.assertEqual(render_label("  Ready "), "ready")


if __name__ == "__main__":
    unittest.main()
