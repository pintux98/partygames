import random
import unittest

from games import GAMES
from games.hotpotato.rules import BOOM_TIME, FUSES, READY_TIME, SURVIVE, HotPotato
from party.common import Context, GameError, Seat, Settings
from party.deck import Deck

PACKS = {"en": {"family": {"topics": ["t1", "t2", "t3"], "dares": ["d1", "d2"]},
                "spicy": {"topics": ["s1"], "dares": ["sd1"]}}}


def make(n, seed=1, **options):
    rng = random.Random(seed)
    settings = Settings(lang="en", options=options)
    seats = [Seat("p%d" % i, "N%d" % i) for i in range(n)]
    game = HotPotato(Context(seats, settings, rng, Deck(PACKS, settings, rng, set()), 0))
    return game, {s.pid for s in seats}


def live(game, everyone):
    game.tick(READY_TIME, everyone)
    return READY_TIME


def other(game, *skip):
    return next(i for i in range(len(game.pids)) if i not in skip)


class HotPotatoTests(unittest.TestCase):
    def fails(self, status, fn, *args):
        with self.assertRaises(GameError) as caught:
            fn(*args)
        self.assertEqual(caught.exception.status, status)

    def test_registry(self):
        self.assertIs(GAMES["hotpotato"], HotPotato)

    def test_starts_ready_then_live_with_hidden_fuse(self):
        game, everyone = make(4, fuse="short")
        self.assertEqual(game.phase, "ready")
        self.assertIn(game.topic, ("t1", "t2", "t3"))
        now = live(game, everyone)
        self.assertEqual(game.phase, "live")
        low, high = FUSES["short"]
        self.assertTrue(now + low <= game.deadline <= now + high)
        for view in [game.host_view(now)] + [game.player_view(p, now) for p in game.pids]:
            self.assertIsNone(view["left"])
            self.assertNotIn("deadline", view)

    def test_only_holder_passes_and_not_back(self):
        game, everyone = make(4)
        now = live(game, everyone)
        a = game.holder
        b = other(game, a)
        self.fails(409, game.act, game.pids[b], {"type": "pass", "target": a}, now, everyone)
        self.fails(400, game.act, game.pids[a], {"type": "pass", "target": a}, now, everyone)
        self.fails(400, game.act, game.pids[a], {"type": "pass", "target": 99}, now, everyone)
        self.fails(400, game.act, game.pids[a], {"type": "pass", "target": "1"}, now, everyone)
        game.act(game.pids[a], {"type": "pass", "target": b}, now, everyone)
        self.assertEqual((game.holder, game.giver), (b, a))
        self.fails(400, game.act, game.pids[b], {"type": "pass", "target": a}, now, everyone)
        c = other(game, a, b)
        game.act(game.pids[b], {"type": "pass", "target": c}, now, everyone)
        self.assertEqual(game.holder, c)

    def test_pass_back_allowed_when_only_two_here(self):
        game, everyone = make(3)
        now = live(game, everyone)
        a = game.holder
        b = other(game, a)
        c = other(game, a, b)
        here = everyone - {game.pids[c]}
        game.act(game.pids[a], {"type": "pass", "target": b}, now, here)
        game.act(game.pids[b], {"type": "pass", "target": a}, now, here)
        self.assertEqual(game.holder, a)

    def test_cannot_pass_to_away_player(self):
        game, everyone = make(4)
        now = live(game, everyone)
        a = game.holder
        b = other(game, a)
        self.fails(409, game.act, game.pids[a], {"type": "pass", "target": b}, now, everyone - {game.pids[b]})

    def test_boom_scores_and_next_round_starts_with_victim(self):
        game, everyone = make(4, rounds=5)
        now = live(game, everyone)
        victim = game.holder
        game.tick(game.deadline, everyone)
        self.assertEqual(game.phase, "boom")
        self.assertEqual(game.victim, victim)
        self.assertIn(game.dare, ("d1", "d2"))
        self.assertEqual(game.points[game.pids[victim]], 0)
        self.assertTrue(all(game.points[p] == SURVIVE for i, p in enumerate(game.pids) if i != victim))
        self.fails(409, game.act, game.pids[victim], {"type": "pass", "target": other(game, victim)}, game.deadline - 1, everyone)
        game.tick(game.deadline, everyone)
        self.assertEqual((game.phase, game.round, game.holder, game.giver), ("ready", 2, victim, None))

    def test_late_pass_loses_to_the_fuse(self):
        game, everyone = make(4)
        now = live(game, everyone)
        a = game.holder
        self.fails(409, game.act, game.pids[a], {"type": "pass", "target": other(game, a)}, game.deadline, everyone)
        self.assertEqual(game.victim, a)

    def test_game_ends_after_rounds(self):
        game, everyone = make(3, rounds=5)
        now = 0
        while game.phase != "over":
            now = game.deadline
            game.tick(now, everyone)
        self.assertEqual(game.round, 5)
        self.assertEqual(sum(game.booms), 5)
        self.assertEqual(sum(game.points.values()), 5 * 2 * SURVIVE)
        game.tick(game.deadline, everyone)
        self.assertTrue(game.finished)
        self.assertEqual(game.host_view(game.deadline)["over"]["booms"], [{"name": n, "booms": b} for n, b in zip(game.names, game.booms)])

    def test_away_holder_drops_the_bomb_on_someone_here(self):
        game, everyone = make(4)
        now = live(game, everyone)
        a = game.holder
        game.tick(now + 1, everyone - {game.pids[a]})
        self.assertNotEqual(game.holder, a)
        self.assertEqual(game.phase, "live")

    def test_hurry(self):
        game, everyone = make(4, fuse="long")
        game.hurry(1)
        game.tick(1, everyone)
        self.assertEqual(game.phase, "live")
        game.hurry(2)
        self.assertEqual(game.deadline, 5)
        game.tick(5, everyone)
        self.assertEqual(game.phase, "boom")

    def test_views(self):
        game, everyone = make(4)
        now = live(game, everyone)
        a = game.holder
        mine = game.player_view(game.pids[a], now)
        self.assertTrue(mine["holding"])
        self.assertEqual({t["seat"] for t in mine["targets"]}, set(range(4)) - {a})
        theirs = game.player_view(game.pids[other(game, a)], now)
        self.assertFalse(theirs["holding"])
        self.assertNotIn("targets", theirs)
        self.assertEqual(theirs["holder"], game.names[a])
        tv = game.host_view(now + 2)
        self.assertEqual((tv["holder"], tv["elapsed"]), (a, 2))
        self.assertEqual(len(tv["players"]), 4)

    def test_stop(self):
        game, everyone = make(4)
        game.stop(1)
        self.assertEqual(game.phase, "over")
        self.assertTrue(game.host_view(1)["over"]["stopped"])
        game.tick(game.deadline, everyone)
        self.assertTrue(game.finished)

    def test_unknown_action(self):
        game, everyone = make(4)
        self.fails(400, game.act, game.pids[0], {"type": "draw"}, 0, everyone)


if __name__ == "__main__":
    unittest.main()
