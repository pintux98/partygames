import re
import unittest
from pathlib import Path

from party.deck import load_packs

ROOT = Path(__file__).resolve().parent.parent
PACKS = load_packs(ROOT / "games" / "bravo" / "content")
MINIMUMS = {("family", "round"): 120, ("family", "final"): 30, ("spicy", "round"): 80, ("spicy", "final"): 20}
DIACRITICS = re.compile("[ăâîșțşţĂÂÎȘȚŞŢ]")


def prompts(lang):
    return [p for mode in PACKS[lang].values() for tag in mode.values() for p in tag]


IMPOSTOR = load_packs(ROOT / "games" / "impostor" / "content")
IMPOSTOR_MINIMUMS = {("family", "words"): 100, ("spicy", "words"): 60, ("family", "twists"): 24, ("spicy", "twists"): 16}


class ImpostorContentTests(unittest.TestCase):
    def test_sizes(self):
        self.assertEqual(set(IMPOSTOR), {"en", "ro"})
        for lang, modes in IMPOSTOR.items():
            for (mode, tag), minimum in IMPOSTOR_MINIMUMS.items():
                self.assertGreaterEqual(len(modes[mode][tag]), minimum, (lang, mode, tag))

    def test_words_shape_and_uniqueness(self):
        for lang, modes in IMPOSTOR.items():
            words = modes["family"]["words"] + modes["spicy"]["words"]
            twists = modes["family"]["twists"] + modes["spicy"]["twists"]
            for entry in words:
                self.assertEqual(len(entry), 3, entry)
                self.assertNotEqual(entry[0].casefold(), entry[1].casefold(), entry)
            texts = [w for e in words for w in e[:2]] + twists
            for text in texts + [e[2] for e in words]:
                self.assertTrue(text.strip(), lang)
                self.assertLessEqual(len(text), 60, text)
                self.assertNotIn("{", text)
            folded = [w.casefold() for w in [e[0] for e in words] + twists]
            self.assertEqual(len(folded), len(set(folded)), [w for w in folded if folded.count(w) > 1])

    def test_nothing_childlike_mixes_with_spicy(self):
        for lang, modes in IMPOSTOR.items():
            texts = " ".join(modes["family"]["twists"] + [w for e in modes["family"]["words"] for w in e[:2]]).casefold()
            for word in ("baby", "bebelus", "teacher", "profesor", "school", "scoala"):
                self.assertNotIn(word, texts, (lang, word))

    def test_decoys_unique_and_not_words(self):
        for lang, modes in IMPOSTOR.items():
            words = modes["family"]["words"] + modes["spicy"]["words"]
            decoys = [e[1].casefold() for e in words]
            self.assertEqual(len(decoys), len(set(decoys)), [d for d in decoys if decoys.count(d) > 1])
            self.assertFalse(set(decoys) & {e[0].casefold() for e in words}, lang)

    def test_categories_have_six_words(self):
        for lang, modes in IMPOSTOR.items():
            for words in (modes["family"]["words"] + modes["spicy"]["words"], modes["spicy"]["words"]):
                for category in {e[2] for e in words}:
                    self.assertGreaterEqual(sum(e[2] == category for e in words), 6, (lang, category))


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


POTATO = load_packs(ROOT / "games" / "hotpotato" / "content")
POTATO_MINIMUMS = {("family", "topics"): 50, ("spicy", "topics"): 50, ("family", "dares"): 30, ("spicy", "dares"): 40}


class HotPotatoContentTests(unittest.TestCase):
    def test_sizes_unique_and_short(self):
        self.assertEqual(set(POTATO), {"en", "ro"})
        for lang, modes in POTATO.items():
            for (mode, tag), minimum in POTATO_MINIMUMS.items():
                self.assertGreaterEqual(len(modes[mode][tag]), minimum, (lang, mode, tag))
            for tag, limit in (("topics", 40), ("dares", 70)):
                items = modes["family"][tag] + modes["spicy"][tag]
                folded = [p.casefold() for p in items]
                self.assertEqual(len(folded), len(set(folded)), [p for p in folded if folded.count(p) > 1])
                for p in items:
                    self.assertTrue(p.strip(), lang)
                    self.assertLessEqual(len(p), limit, p)
                    self.assertNotIn("{", p)


def fold(text):
    return re.sub(r"[\W_]", "", text.casefold())


class NewContentTests(unittest.TestCase):
    def check(self, game, tag, minimums, limit, prefix=None):
        packs = load_packs(ROOT / "games" / game / "content")
        self.assertEqual(set(packs), {"en", "ro"})
        for lang, modes in packs.items():
            items = []
            for mode, minimum in minimums.items():
                self.assertGreaterEqual(len(modes[mode][tag]), minimum, (game, lang, mode))
                items += modes[mode][tag]
            texts = [t for item in items for t in ([item] if isinstance(item, str) else item)]
            for text in texts:
                self.assertTrue(text.strip(), (game, lang))
                self.assertLessEqual(len(text), limit, text)
                self.assertNotIn("{", text)
                if prefix:
                    self.assertTrue(text.startswith(prefix[lang]), text)
            folded = [fold(t) for t in texts]
            self.assertEqual(len(folded), len(set(folded)), [t for t in texts if folded.count(fold(t)) > 1])

    def test_never(self):
        self.check("never", "statements", {"family": 100, "spicy": 100}, 100, {"en": "Never have I ever ", "ro": "Eu niciodata nu "})

    def test_likely(self):
        self.check("likely", "prompts", {"family": 100, "spicy": 100}, 100, {"en": "Who is most likely to ", "ro": "Cine e cel mai probabil sa "})

    def test_rather(self):
        self.check("rather", "dilemmas", {"family": 80, "spicy": 80}, 60)
        for modes in load_packs(ROOT / "games" / "rather" / "content").values():
            for pair in modes["family"]["dilemmas"] + modes["spicy"]["dilemmas"]:
                self.assertEqual(len(pair), 2, pair)

    def test_doodle_own_words(self):
        self.check("doodle", "words", {"family": 150, "spicy": 80}, 24)
        for lang, modes in load_packs(ROOT / "games" / "doodle" / "content").items():
            family = " ".join(modes["family"]["words"]).casefold()
            for word in ("baby", "bebelus", "teacher", "profesor", "school", "scoala"):
                self.assertNotIn(word, family, (lang, word))
            self.assertFalse(any(c.isdigit() for w in modes["family"]["words"] + modes["spicy"]["words"] for c in w), lang)
