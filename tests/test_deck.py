import json
import random
import tempfile
import unittest
from pathlib import Path

from party.common import Settings
from party.deck import Deck, load_packs

PACKS = {"en": {"family": {"t": ["a", "b"]}, "spicy": {"t": ["s"]}}}


class DeckTests(unittest.TestCase):
    def test_deck_family_only(self):
        for seed in range(50):
            deck = Deck(PACKS, Settings(), random.Random(seed), set())
            self.assertNotEqual(deck.draw("t"), "s")

    def test_deck_spicy_is_spicy_only(self):
        deck = Deck(PACKS, Settings(spicy=True), random.Random(1), set())
        self.assertEqual({deck.draw("t") for _ in range(3)}, {"s"})

    def test_deck_spicy_falls_back_to_family_when_empty(self):
        deck = Deck({"en": {"family": {"t": ["a"]}, "spicy": {"t": []}}}, Settings(spicy=True), random.Random(1), set())
        self.assertEqual(deck.draw("t"), "a")

    def test_deck_no_repeats_until_exhausted(self):
        used = set()
        rng = random.Random(2)
        drawn = [Deck(PACKS, Settings(), rng, used).draw("t") for _ in range(2)]
        self.assertEqual(len(set(drawn)), 2)
        self.assertIn(Deck(PACKS, Settings(), rng, used).draw("t"), {"a", "b"})

    def test_load_packs_reads_langs(self):
        with tempfile.TemporaryDirectory() as folder:
            for lang in ("en", "ro"):
                Path(folder, lang + ".json").write_text(json.dumps({"family": {}}))
            self.assertEqual(set(load_packs(Path(folder))), {"en", "ro"})


class ListItems(unittest.TestCase):
    def test_list_items(self):
        packs = {"en": {"family": {"words": [["a", "b", "c"], ["d", "e", "f"]]}, "spicy": {"words": []}}}
        deck = Deck(packs, Settings(lang="en"), random.Random(1), set())
        self.assertEqual(sorted([deck.draw("words"), deck.draw("words")]), [["a", "b", "c"], ["d", "e", "f"]])
