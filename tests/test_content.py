import re
import unittest
from pathlib import Path

from party.deck import load_packs

ROOT = Path(__file__).resolve().parent.parent
PACKS = load_packs(ROOT / "games" / "bravo" / "content")
MINIMUMS = {("family", "round"): 120, ("family", "final"): 30, ("spicy", "round"): 48, ("spicy", "final"): 12}
DIACRITICS = re.compile("[ăâîșțşţĂÂÎȘȚŞŢ]")


def prompts(lang):
    return [p for mode in PACKS[lang].values() for tag in mode.values() for p in tag]


class ContentTests(unittest.TestCase):
    def test_pack_sizes(self):
        self.assertEqual(set(PACKS), {"en", "ro"})
        for lang, modes in PACKS.items():
            for (mode, tag), minimum in MINIMUMS.items():
                self.assertGreaterEqual(len(modes[mode][tag]), minimum, (lang, mode, tag))

    def test_no_duplicates(self):
        for lang in PACKS:
            folded = [p.casefold() for p in prompts(lang)]
            self.assertEqual(len(folded), len(set(folded)), lang)

    def test_lengths_and_placeholders(self):
        for lang in PACKS:
            items = prompts(lang)
            for p in items:
                self.assertTrue(p.strip(), lang)
                self.assertLessEqual(len(p), 110, p)
                self.assertNotRegex(p.replace("{player}", ""), "[{}]", p)
            self.assertLessEqual(sum("{player}" in p for p in items) / len(items), 0.15, lang)

    def test_plain_letters_everywhere(self):
        files = [*ROOT.glob("games/*/content/*.json"), *ROOT.glob("games/*/view.js"), *ROOT.glob("static/*.js"), *ROOT.glob("static/index.html")]
        for f in files:
            if f.name != "qrcode.js":
                self.assertIsNone(DIACRITICS.search(f.read_text(encoding="utf-8")), f)
