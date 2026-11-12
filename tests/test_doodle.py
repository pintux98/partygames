import random
import unittest

from games import GAMES
from games.doodle.rules import DRAWER_BONUS, GUESS_MAX, GUESS_MIN, PICK_TIME, REVEAL_TIME, Doodle, same
from party.common import Context, GameError, Seat, Settings
from party.deck import Deck
from test_impostor import png

WORDS = [["ice cream", "cupcake", "food"], ["bus", "tram", "transport"], ["cat", "dog", "animals"], ["owl", "parrot", "animals"]]
PACKS = {"en": {"family": {"words": WORDS, "twists": []}, "spicy": {"words": [["beer", "wine", "drinks"]], "twists": []}}}


def make(n, seed=1, spicy=False, **options):
    rng = random.Random(seed)
    settings = Settings(lang="en", spicy=spicy, options=options)
    seats = [Seat("p%d" % i, "N%d" % i) for i in range(n)]
    game = Doodle(Context(seats, settings, rng, Deck(PACKS, settings, rng, set()), 0))
    return game, {s.pid for s in seats}


def drawing(game, everyone, now=1, pick=0):
    game.act(game.pids[game.drawer], {"type": "pick", "choice": pick}, now, everyone)
    return game.word


def guessers(game):
    return [i for i in range(len(game.pids)) if i != game.drawer]


class DoodleTests(unittest.TestCase):
    def fails(self, status, fn, *args):
        with self.assertRaises(GameError) as caught:
            fn(*args)
        self.assertEqual(caught.exception.status, status)

    def test_registry_and_shared_words(self):
        self.assertIs(GAMES["doodle"], Doodle)
        self.assertIs(Doodle.packs, GAMES["impostor"].packs)

    def test_same(self):
        self.assertTrue(same("  Ice-Cream ", "ice cream"))
        self.assertTrue(same("Inghețată", "inghetata"))
        self.assertFalse(same("ice", "ice cream"))
        self.assertFalse(same("", "cat"))

    def test_order_covers_everyone_per_lap(self):
        game, _ = make(4, laps=2)
        self.assertEqual(len(game.order), 8)
        self.assertEqual(sorted(game.order[:4]), [0, 1, 2, 3])
        self.assertEqual(sorted(game.order[4:]), [0, 1, 2, 3])

    def test_pick_only_drawer_and_choices_hidden(self):
        game, everyone = make(4)
        self.assertEqual(game.phase, "pick")
        mine = game.player_view(game.pids[game.drawer], 0)
        self.assertEqual(len(mine["choices"]), 3)
        self.assertTrue(set(mine["choices"]) <= {w for e in WORDS for w in e[:2]})
        other = game.player_view(game.pids[guessers(game)[0]], 0)
        self.assertNotIn("choices", other)
        self.assertNotIn("word", other)
        self.assertNotIn("choices", game.host_view(0))
        self.fails(409, game.act, game.pids[guessers(game)[0]], {"type": "pick", "choice": 0}, 0, everyone)
        self.fails(400, game.act, game.pids[game.drawer], {"type": "pick", "choice": 3}, 0, everyone)
        word = drawing(game, everyone)
        self.assertEqual(word, mine["choices"][0])
        self.assertEqual(game.phase, "draw")

    def test_pick_times_out_to_first_choice(self):
        game, everyone = make(4)
        first = game.choices[0]
        game.tick(PICK_TIME, everyone)
        self.assertEqual((game.phase, game.word), ("draw", first))

    def test_guess_scoring_and_hint(self):
        game, everyone = make(4, draw_time=80)
        word = drawing(game, everyone, now=0)
        a, b, c = guessers(game)
        hint = game.player_view(game.pids[a], 0)["hint"]
        self.assertEqual(len(hint), len(word))
        self.assertNotIn(word, str(game.player_view(game.pids[a], 0)))
        self.assertNotIn(word, str(game.host_view(0)))
        game.act(game.pids[a], {"type": "guess", "text": "nope"}, 10, everyone)
        self.assertEqual(game.points[game.pids[a]], 0)
        self.assertEqual(game.host_view(10)["feed"], [{"name": "N%d" % a, "text": "nope"}])
        game.act(game.pids[a], {"type": "guess", "text": word.upper()}, 0, everyone)
        self.assertEqual(game.points[game.pids[a]], GUESS_MAX)
        self.assertEqual(game.points[game.pids[game.drawer]], DRAWER_BONUS)
        self.assertEqual(game.player_view(game.pids[a], 0)["word"], word)
        self.assertEqual(game.player_view(game.pids[a], 0)["gain"], GUESS_MAX)
        self.fails(409, game.act, game.pids[a], {"type": "guess", "text": word}, 1, everyone)
        self.fails(409, game.act, game.pids[game.drawer], {"type": "guess", "text": word}, 1, everyone)
        game.act(game.pids[b], {"type": "guess", "text": word}, 79, everyone)
        self.assertEqual(game.points[game.pids[b]], GUESS_MIN)
        self.assertEqual(game.phase, "draw")
        game.act(game.pids[c], {"type": "guess", "text": word}, 40, everyone)
        self.assertEqual(game.phase, "reveal")
        self.assertEqual(game.points[game.pids[game.drawer]], 3 * DRAWER_BONUS)

    def test_feed_keeps_last_eight(self):
        game, everyone = make(3)
        drawing(game, everyone)
        a = guessers(game)[0]
        for i in range(12):
            game.act(game.pids[a], {"type": "guess", "text": "x%d" % i}, 1, everyone)
        feed = game.host_view(1)["feed"]
        self.assertEqual(len(feed), 8)
        self.assertEqual(feed[-1]["text"], "x11")

    def test_drawing_upload_and_file(self):
        game, everyone = make(3)
        self.fails(409, game.act, game.pids[game.drawer], {"type": "draw", "png": png()}, 0, everyone)
        drawing(game, everyone)
        g = guessers(game)[0]
        self.fails(409, game.act, game.pids[g], {"type": "draw", "png": png()}, 1, everyone)
        self.fails(400, game.act, game.pids[game.drawer], {"type": "draw", "png": "junk"}, 1, everyone)
        game.act(game.pids[game.drawer], {"type": "draw", "png": png()}, 1, everyone)
        first = game.host_view(1)["file"]
        self.assertIsNotNone(game.file(game.pids[g], first))
        game.act(game.pids[game.drawer], {"type": "draw", "png": png(pad=30)}, 2, everyone)
        second = game.player_view(game.pids[g], 2)["file"]
        self.assertNotEqual(first, second)
        self.assertEqual(len(game.file(game.pids[g], second)), 24 + 30)
        self.assertEqual(game.file(game.pids[g], first), game.png)
        self.assertIsNone(game.file(game.pids[g], "nope.png"))
        self.assertIsNone(game.file(game.pids[g], first.replace("-%d-" % game.turn, "-%d-" % (game.turn + 1))))

    def test_turns_advance_and_finish(self):
        game, everyone = make(3)
        drawers = []
        now = 0
        while not game.finished:
            if game.phase == "pick":
                drawers.append(game.drawer)
            now = game.deadline
            game.tick(now, everyone)
        self.assertEqual(sorted(drawers), [0, 1, 2])
        self.assertEqual(len(game.words), 3)

    def test_no_one_guesses_drawer_gets_nothing(self):
        game, everyone = make(3)
        drawing(game, everyone)
        game.tick(game.deadline, everyone)
        self.assertEqual(game.phase, "reveal")
        self.assertEqual(sum(game.points.values()), 0)
        self.assertEqual(game.host_view(game.deadline - 1)["word"], game.word)

    def test_away_drawer_skipped(self):
        game, everyone = make(4)
        nxt = game.order[1]
        gone = game.pids[game.drawer]
        game.tick(1, everyone - {gone})
        self.assertEqual((game.phase, game.drawer), ("pick", nxt))

    def test_words_not_repeated(self):
        game, everyone = make(4, laps=2)
        seen = []
        while not game.finished:
            if game.phase == "pick":
                seen += game.choices
            game.tick(game.deadline, everyone)
        self.assertGreaterEqual(len(seen), 8)
        self.assertEqual(len(set(seen[:8])), 8)

    def test_spicy_adds_words(self):
        game, _ = make(3, spicy=True)
        self.assertIn("beer", game.pool())

    def test_hurry(self):
        game, everyone = make(3, draw_time=80)
        game.hurry(1)
        game.tick(1, everyone)
        self.assertEqual(game.phase, "draw")
        game.hurry(2)
        self.assertEqual(game.deadline, 12)
        self.assertTrue(game.host_view(2)["hurry"])
        game.tick(12, everyone)
        self.assertEqual(game.phase, "reveal")
        game.hurry(13)
        game.tick(13, everyone)
        self.assertEqual(game.phase, "pick")

    def test_reveal_time(self):
        game, everyone = make(3)
        drawing(game, everyone)
        game.tick(game.deadline, everyone)
        self.assertAlmostEqual(game.deadline - game.started, REVEAL_TIME)


if __name__ == "__main__":
    unittest.main()
