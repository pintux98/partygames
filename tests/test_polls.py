import random
import unittest

from games import GAMES
from games.likely.rules import Likely
from games.never.rules import Never
from games.rather.rules import Rather
from party.common import Context, GameError, Seat, Settings
from party.deck import Deck
from party.poll import POINTS, REVEAL_TIME

PACKS = {"en": {"family": {"statements": ["f1", "f2"], "prompts": ["p1", "p2"], "dilemmas": [["a", "b"], ["c", "d"]]},
                "spicy": {"statements": ["s1"], "prompts": ["sp1"], "dilemmas": [["x", "y"]]}}}


def make(cls, n=4, spicy=False, **options):
    rng = random.Random(1)
    settings = Settings(lang="en", spicy=spicy, options=options)
    seats = [Seat("p%d" % i, "N%d" % i) for i in range(n)]
    game = cls(Context(seats, settings, rng, Deck(PACKS, settings, rng, set()), 0))
    return game, {s.pid for s in seats}


class PollTests(unittest.TestCase):
    def fails(self, status, fn, *args):
        with self.assertRaises(GameError) as caught:
            fn(*args)
        self.assertEqual(caught.exception.status, status)

    def test_registered(self):
        for cls in (Never, Likely, Rather):
            self.assertIs(GAMES[cls.meta.id], cls)

    def test_rounds_flow_and_finish(self):
        game, everyone = make(Rather, rounds=6, answer_time=15)
        self.assertEqual((game.phase, game.round), ("ask", 1))
        game.tick(15, everyone)
        self.assertEqual(game.phase, "reveal")
        self.assertEqual(game.gains, {})
        while not game.finished:
            game.tick(game.deadline, everyone)
        self.assertEqual(game.round, 6)

    def test_reveal_when_everyone_here_answered(self):
        game, everyone = make(Never)
        here = everyone - {"p3"}
        for i in range(3):
            self.assertEqual(game.phase, "ask")
            game.act("p%d" % i, {"type": "answer", "have": True, "guess": 3}, 1, here)
        self.assertEqual(game.phase, "reveal")
        self.assertAlmostEqual(game.deadline, 1 + REVEAL_TIME)
        self.fails(409, game.act, "p0", {"type": "answer", "have": True, "guess": 3}, 2, here)

    def test_bad_input(self):
        game, everyone = make(Never)
        for body in ({"type": "nope"}, {"type": "answer", "have": "yes", "guess": 1}, {"type": "answer", "have": True, "guess": 5},
                     {"type": "answer", "have": True, "guess": True}):
            self.fails(400, game.act, "p0", body, 1, everyone)
        self.fails(409, game.act, "stranger", {"type": "answer", "have": True, "guess": 1}, 1, everyone)

    def test_hurry(self):
        game, everyone = make(Likely, answer_time=30)
        game.hurry(1)
        self.assertEqual(game.deadline, 6)
        self.assertTrue(game.host_view(1)["hurry"])
        game.tick(6, everyone)
        self.assertEqual(game.phase, "reveal")
        game.hurry(7)
        game.tick(7, everyone)
        self.assertEqual((game.phase, game.round), ("ask", 2))

    def test_spicy_items_only(self):
        for cls, item in ((Never, "s1"), (Likely, "sp1"), (Rather, ["x", "y"])):
            game, _ = make(cls, spicy=True)
            self.assertEqual(game.item, item)
            self.assertTrue(game.host_view(0)["spicy"])

    def test_never_scoring(self):
        game, everyone = make(Never)
        answers = [(True, 2), (True, 3), (False, 1), (False, 0)]
        for i, (have, guess) in enumerate(answers):
            game.act("p%d" % i, {"type": "answer", "have": have, "guess": guess}, 1, everyone)
        self.assertEqual(game.result, {"count": 2, "answered": 4, "exact": True, "winners": ["N0"]})
        self.assertEqual(game.points, {"p0": 2 * POINTS, "p1": 0, "p2": 0, "p3": 0})
        self.assertNotIn("have", str(game.host_view(2)))
        self.assertEqual(game.player_view("p1", 2)["mine"], {"have": True, "guess": 3})

    def test_never_closest_not_exact(self):
        game, everyone = make(Never)
        for i, guess in enumerate((0, 4, 3, 4)):
            game.act("p%d" % i, {"type": "answer", "have": i == 0, "guess": guess}, 1, everyone)
        self.assertEqual((game.result["count"], game.result["exact"], game.result["winners"]), (1, False, ["N0"]))
        self.assertEqual(game.gains, {0: POINTS})

    def test_likely_votes_ties_and_recap(self):
        game, everyone = make(Likely, rounds=6)
        self.fails(400, game.act, "p0", {"type": "answer", "target": 4}, 1, everyone)
        for i, target in enumerate((1, 1, 2, 2)):
            game.act("p%d" % i, {"type": "answer", "target": target}, 1, everyone)
        self.assertEqual(game.result["top"], ["N1", "N2"])
        self.assertEqual(game.result["votes"], [{"name": "N1", "votes": 2, "top": True}, {"name": "N2", "votes": 2, "top": True}])
        self.assertEqual(game.gains, {0: POINTS, 1: POINTS, 2: POINTS, 3: POINTS})
        game.tick(game.deadline, everyone)
        for i in range(4):
            game.act("p%d" % i, {"type": "answer", "target": 3}, game.deadline - 1, everyone)
        self.assertEqual(game.gains, dict.fromkeys(range(4), POINTS))
        self.assertNotIn("most", game.host_view(0))
        while not game.finished:
            game.tick(game.deadline, everyone)
        self.assertEqual(game.host_view(0)["most"], {"names": ["N3"], "votes": 4})

    def test_likely_vote_can_change(self):
        game, everyone = make(Likely)
        game.act("p0", {"type": "answer", "target": 1}, 1, everyone)
        game.act("p0", {"type": "answer", "target": 2}, 1, everyone)
        self.assertEqual(game.answers[0], {"target": 2})

    def test_rather_majority_and_tie(self):
        game, everyone = make(Rather)
        self.fails(400, game.act, "p0", {"type": "answer", "pick": 2, "guess": 0}, 1, everyone)
        for i, (pick, guess) in enumerate(((0, 0), (0, 1), (1, 0), (0, 0))):
            game.act("p%d" % i, {"type": "answer", "pick": pick, "guess": guess}, 1, everyone)
        self.assertEqual(game.result, {"sides": [["N0", "N1", "N3"], ["N2"]], "majority": 0})
        self.assertEqual(game.gains, {0: POINTS, 2: POINTS, 3: POINTS})
        game.tick(game.deadline, everyone)
        for i, pick in enumerate((0, 1, 0, 1)):
            game.act("p%d" % i, {"type": "answer", "pick": pick, "guess": 0}, game.deadline - 1, everyone)
        self.assertIsNone(game.result["majority"])
        self.assertEqual(game.gains, {})


if __name__ == "__main__":
    unittest.main()
