import random
import unittest

from games import GAMES
from games.faceoff.rules import FaceOff
from party.common import Context, GameError, Seat, Settings
from party.deck import Deck
from party.room import Room

PACKS = {"en": {"family": {"round": ["r1", "r2", "r3", "r4"], "final": ["f1"]}, "spicy": {"round": ["s1"], "final": ["sf"]}}}


def make(n, seed=1, packs=PACKS):
    rng = random.Random(seed)
    settings = Settings(lang="en")
    seats = [Seat("p%d" % i, chr(65 + i)) for i in range(n)]
    game = FaceOff(Context(seats, settings, rng, Deck(packs, settings, rng, set()), 0))
    return game, {s.pid for s in seats}


def answer_all(game, everyone, now, skip=()):
    for pid in sorted(everyone - set(skip)):
        for prompt in game.player_view(pid, now)["prompts"]:
            game.act(pid, {"type": "answer", "i": prompt["i"], "text": "x" + pid}, now, everyone)


def pairs(game):
    return {frozenset(p["authors"]) for p in game.prompts}


class FaceOffTests(unittest.TestCase):
    def fails(self, status, game, pid, body, now, active):
        with self.assertRaises(GameError) as caught:
            game.act(pid, body, now, active)
        self.assertEqual(caught.exception.status, status)
        return str(caught.exception)

    def skip_until(self, game, everyone, now, phase, round_):
        while (game.phase, game.round) != (phase, round_):
            game.hurry(now)
            now += 10
            game.tick(now, everyone)
        return now

    def to_vote(self, n, round_=1):
        game, everyone = make(n)
        now = self.skip_until(game, everyone, 0, "answer", round_)
        answer_all(game, everyone, now)
        self.assertEqual(game.phase, "vote")
        authors = set(game.prompts[0]["authors"])
        return game, everyone, now, authors, sorted(everyone - authors)

    def test_each_player_two_prompts_each_prompt_two_authors(self):
        for n in (3, 8, 16):
            game, everyone = make(n)
            self.assertEqual(len(game.prompts), n)
            for pid in everyone:
                self.assertEqual(len(game.player_view(pid, 0)["prompts"]), 2)
            for prompt in game.prompts:
                self.assertEqual(len(set(prompt["authors"])), 2)

    def test_round_two_reshuffles_ring(self):
        game, everyone = make(6)
        first = pairs(game)
        self.skip_until(game, everyone, 0, "answer", 2)
        self.assertNotEqual(pairs(game), first)

    def test_answer_phase_ends_when_all_answered(self):
        game, everyone = make(4)
        answer_all(game, everyone, 1)
        self.assertNotEqual(game.host_view(1)["phase"], "answer")

    def test_away_player_does_not_block(self):
        game, everyone = make(4)
        active = everyone - {"p2"}
        for pid in sorted(active):
            for prompt in game.player_view(pid, 1)["prompts"]:
                game.act(pid, {"type": "answer", "i": prompt["i"], "text": "hi"}, 1, active)
        self.assertNotEqual(game.phase, "answer")
        for prompt in game.prompts:
            if "p2" in prompt["authors"]:
                self.assertIsNone(prompt["answers"][prompt["authors"].index("p2")])

    def test_claps_and_points_round1(self):
        game, everyone, now, authors, (voter,) = self.to_vote(3)
        for side in (0, 0, 1):
            game.act(voter, {"type": "clap", "side": side}, now, everyone)
        view = game.host_view(now)
        self.assertEqual(view["phase"], "reveal")
        self.assertEqual(view["points"], [200, 100])
        self.assertIsNone(view["sweep"])
        self.assertFalse(view["walkover"])
        first, second = game.prompts[0]["authors"]
        self.assertEqual(game.scores()[first], 200)
        self.assertEqual(game.scores()[second], 100)

    def test_sweep_bonus_doubled_round2(self):
        game, everyone, now, authors, voters = self.to_vote(5, 2)
        self.assertEqual(len(voters), 3)
        for voter in voters:
            game.act(voter, {"type": "clap", "side": 0}, now, everyone)
        self.assertEqual(game.host_view(now)["voters_done"], 0)
        game.hurry(now)
        game.tick(now + 10, everyone)
        view = game.host_view(now + 10)
        self.assertEqual(view["points"], [3 * 100 * 2 + 200 * 2, 0])
        self.assertEqual(view["sweep"], 0)

    def test_walkover_no_vote(self):
        game, everyone = make(3)
        first = game.prompts[0]["authors"][0]
        game.act(first, {"type": "answer", "i": 0, "text": "solo"}, 1, everyone)
        game.hurry(1)
        game.tick(11, everyone)
        view = game.host_view(11)
        self.assertEqual(view["phase"], "reveal")
        self.assertTrue(view["walkover"])
        self.assertEqual(view["points"], [100, 0])
        self.assertEqual(view["answers"], ["solo", None])

    def test_both_missing_skipped(self):
        game, everyone = make(3)
        game.tick(75, everyone)
        view = game.host_view(75)
        self.assertEqual((view["phase"], view["left"], view["points"]), ("reveal", 3, [0, 0]))
        game.tick(78, everyone)
        self.assertEqual(game.host_view(78)["answers"], [None, None])
        self.assertEqual(game.idx, 1)

    def test_author_cannot_clap(self):
        game, everyone, now, authors, _ = self.to_vote(4)
        self.fails(403, game, min(authors), {"type": "clap", "side": 1}, now, everyone)
        self.assertTrue(game.player_view(min(authors), now)["author"])

    def test_fourth_clap_rejected(self):
        game, everyone, now, authors, voters = self.to_vote(4)
        for _ in range(3):
            game.act(voters[0], {"type": "clap", "side": 1}, now, everyone)
        self.assertEqual(game.player_view(voters[0], now)["claps_left"], 0)
        self.assertEqual(self.fails(409, game, voters[0], {"type": "clap", "side": 1}, now, everyone), "No claps left")
        self.assertEqual(game.host_view(now)["voters_done"], 1)
        self.fails(400, game, voters[1], {"type": "clap", "side": 2}, now, everyone)

    def test_answer_limits(self):
        game, everyone = make(3)
        mine = game.player_view("p0", 0)["prompts"]
        other = next(i for i, p in enumerate(game.prompts) if "p0" not in p["authors"])
        self.assertEqual(self.fails(403, game, "p0", {"type": "answer", "i": other, "text": "hi"}, 0, everyone), "Not your prompt")
        self.assertEqual(self.fails(400, game, "p0", {"type": "answer", "i": mine[0]["i"], "text": "   "}, 0, everyone), "Write something")
        game.act("p0", {"type": "answer", "i": mine[0]["i"], "text": "y" * 200}, 0, everyone)
        self.assertEqual(self.fails(409, game, "p0", {"type": "answer", "i": mine[0]["i"], "text": "again"}, 0, everyone), "Already answered")
        prompt = game.prompts[mine[0]["i"]]
        self.assertEqual(prompt["answers"][prompt["authors"].index("p0")], "y" * 80)
        self.assertTrue(game.player_view("p0", 0)["prompts"][0]["answered"])
        self.fails(400, game, "p0", {"type": "answer", "i": 99, "text": "hi"}, 0, everyone)
        self.fails(409, game, "p0", {"type": "clap", "side": 0}, 0, everyone)

    def test_hurry_answer_gives_ten_seconds(self):
        game, everyone = make(3)
        game.hurry(5)
        view = game.host_view(5)
        self.assertEqual((view["left"], view["hurry"]), (10, True))
        game.tick(15, everyone)
        self.assertEqual(game.host_view(15)["answers"], [None, None])
        self.assertFalse(game.host_view(15)["hurry"])

    def test_hurry_reveal_skips(self):
        game, everyone = make(3)
        game.tick(75, everyone)
        game.hurry(76)
        game.tick(76, everyone)
        self.assertEqual(game.idx, 1)

    def test_final_round_no_self_clap_and_150_points(self):
        game, everyone = make(4)
        now = self.skip_until(game, everyone, 0, "final_answer", "final")
        self.assertEqual(game.player_view("p0", now)["prompts"], [{"i": 0, "text": "f1", "answered": False}])
        answer_all(game, everyone, now, skip=["p3"])
        game.hurry(now)
        now += 10
        game.tick(now, everyone)
        view = game.player_view("p0", now)
        self.assertEqual(view["phase"], "final_vote")
        self.assertEqual(len(view["answers"]), 3)
        own = view["own"]
        other = (own + 1) % 3
        self.assertEqual(self.fails(403, game, "p0", {"type": "clap", "target": own}, now, everyone), "Not your own answer")
        self.assertIsNone(game.player_view("p3", now)["own"])
        target = game.order[other]
        for pid in ("p0", "p3"):
            for _ in range(3):
                game.act(pid, {"type": "clap", "target": other}, now, everyone)
        self.assertEqual(game.phase, "final_vote")
        game.hurry(now)
        game.tick(now + 10, everyone)
        view = game.host_view(now + 10)
        self.assertEqual(view["phase"], "final_reveal")
        self.assertEqual(view["points"][other], 900)
        self.assertEqual(view["authors"][other], chr(65 + int(target[1:])))
        self.assertEqual(game.scores()[target], 900)

    def test_full_game_finishes(self):
        game, everyone = make(3)
        now = 0
        seen = set()
        while not game.finished:
            seen.add(game.phase)
            if game.phase in ("answer", "final_answer"):
                answer_all(game, everyone, now)
            elif game.phase == "vote":
                voter = next(pid for pid in sorted(everyone) if game.player_view(pid, now)["claps_left"])
                game.act(voter, {"type": "clap", "side": 0}, now, everyone)
            else:
                game.hurry(now)
                now += 10
                game.tick(now, everyone)
            self.assertLess(now, 2000)
        self.assertEqual(seen, {"answer", "vote", "reveal", "scores", "final_answer", "final_vote", "final_reveal"})
        self.assertEqual(set(game.scores()), everyone)
        self.assertGreater(sum(game.scores().values()), 0)
        self.assertIsNone(game.host_view(now)["left"])

    def test_player_placeholder_never_names_author(self):
        packs = {"en": {"family": {"round": ["{player} ate it"], "final": ["f"]}, "spicy": {"round": [], "final": []}}}
        for seed in range(20):
            game, _ = make(3, seed, packs)
            for prompt in game.prompts:
                name = prompt["text"][: -len(" ate it")]
                self.assertIn(name, "ABC")
                self.assertNotIn("p%d" % (ord(name) - 65), prompt["authors"])

    def test_showdown_order_hides_authors(self):
        broken = False
        for seed in range(5):
            game, _ = make(6, seed)
            prompts = game.prompts
            broken |= any(prompts[k + 1]["authors"][0] != prompts[k]["authors"][1] for k in range(5))
        self.assertTrue(broken)

    def test_late_answer_rejected_without_tick(self):
        game, everyone = make(3)
        mine = game.player_view("p0", 0)["prompts"][0]["i"]
        self.fails(409, game, "p0", {"type": "answer", "i": mine, "text": "late"}, 76, everyone)

    def test_walkover_round2_doubled(self):
        game, everyone = make(3)
        now = self.skip_until(game, everyone, 0, "answer", 2)
        first = game.prompts[0]["authors"][0]
        game.act(first, {"type": "answer", "i": 0, "text": "solo"}, now, everyone)
        game.hurry(now)
        game.tick(now + 10, everyone)
        view = game.host_view(now + 10)
        self.assertEqual((view["phase"], view["walkover"], view["points"]), ("reveal", True, [200, 0]))

    def test_only_own_final_answer_means_no_claps(self):
        game, everyone = make(3)
        now = self.skip_until(game, everyone, 0, "final_answer", "final")
        game.act("p0", {"type": "answer", "i": 0, "text": "mine"}, now, everyone)
        game.hurry(now)
        game.tick(now + 10, everyone)
        self.assertEqual(game.player_view("p0", now + 10)["claps_left"], 0)
        self.assertEqual(game.player_view("p1", now + 10)["claps_left"], 3)

    def test_registry_has_faceoff(self):
        self.assertIs(GAMES["faceoff"], FaceOff)

    def test_platform_runs_faceoff(self):
        room = Room("ABCDEF", 0, GAMES, random.Random(1))
        ana = room.join("Ana", 0)
        room.join("Bob", 0)
        room.join("Cara", 0)
        room.action(ana.id, {"type": "start"}, 0)
        self.assertEqual(room.view_for(room.host, 0)["game"]["phase"], "answer")
        prompts = room.view_for(ana.id, 0)["game"]["prompts"]
        room.action(ana.id, {"type": "answer", "i": prompts[0]["i"], "text": "hi"}, 1)
        self.assertTrue(room.view_for(ana.id, 1)["game"]["prompts"][0]["answered"])


if __name__ == "__main__":
    unittest.main()
