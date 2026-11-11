import unittest

from party.common import GameError, clean_line


class CleanLineTests(unittest.TestCase):
    def test_clean_line_strips_controls_and_spaces(self):
        self.assertEqual(clean_line("  a\u200b\tb\n c\x00 ", 20), "a b c")

    def test_clean_line_cuts_to_limit(self):
        self.assertEqual(len(clean_line("x" * 100, 80)), 80)

    def test_clean_line_rejects_non_str(self):
        with self.assertRaises(GameError) as caught:
            clean_line(5, 20)
        self.assertEqual(caught.exception.status, 400)
