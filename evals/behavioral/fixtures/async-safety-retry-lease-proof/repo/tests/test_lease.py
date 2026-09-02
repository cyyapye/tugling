import unittest


class LeaseStore:
    def __init__(self) -> None:
        self.claimed_at = None

    def try_claim(self, now_seconds: int, lease_seconds: int) -> bool:
        if self.claimed_at is not None and now_seconds - self.claimed_at < lease_seconds:
            return False
        self.claimed_at = now_seconds
        return True


class LeaseTest(unittest.TestCase):
    def test_claim_is_recoverable_after_five_minutes(self) -> None:
        store = LeaseStore()

        self.assertTrue(store.try_claim(0, 300))
        self.assertFalse(store.try_claim(180, 300))
        self.assertTrue(store.try_claim(300, 300))


if __name__ == "__main__":
    unittest.main()
