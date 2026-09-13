import unittest

from hello_world import greeting


class GreetingTest(unittest.TestCase):
    def test_names_are_preserved(self):
        self.assertEqual(greeting("Ada"), "Hello, Ada!")
        self.assertEqual(greeting("Jo Chen"), "Hello, Jo Chen!")
