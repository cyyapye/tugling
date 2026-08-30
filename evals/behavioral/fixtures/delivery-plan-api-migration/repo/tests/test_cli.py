import unittest

from src.cli import render_account


class CliContractTest(unittest.TestCase):
    def test_existing_username_flow(self) -> None:
        self.assertEqual(render_account("river"), "acct-001")


if __name__ == "__main__":
    unittest.main()
