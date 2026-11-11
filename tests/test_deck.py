import json
import random
import tempfile
import unittest
from pathlib import Path

from party.common import Settings
from party.deck import Deck, load_packs

PACKS = {"ro": {"family": {"t": ["a", "b"]}, "spicy": {"t": ["s"]}}}


class DeckTests(unittest.TestCase):
    def test_deck_family_only(self):
        for seed in range(50):
            deck = Deck(PACKS, Settings(), random.Random(seed), set())
            self.assertNotEqual(deck.draw("t"), "s")

    def test_deck_spicy_adds_pack(self):
        deck = Deck(PACKS, Settings(spicy=True), random.Random(1), set())
        self.assertEqual({deck.draw("t") for _ in range(3)}, {"a", "b", "s"})

    def test_deck_no_repeats_until_exhausted(self):
        used = set()
        settings = Settings(spicy=True)
        rng = random.Random(2)
        drawn = [Deck(PACKS, settings, rng, used).draw("t") for _ in range(3)]
        self.assertEqual(len(set(drawn)), 3)
        self.assertIn(Deck(PACKS, settings, rng, used).draw("t"), {"a", "b", "s"})

    def test_load_packs_reads_langs(self):
        with tempfile.TemporaryDirectory() as folder:
            for lang in ("en", "ro"):
                Path(folder, lang + ".json").write_text(json.dumps({"family": {}}))
            self.assertEqual(set(load_packs(Path(folder))), {"en", "ro"})
