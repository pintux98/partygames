import base64
import json
import random
import struct
import unittest

from games import GAMES
from games.impostor.rules import CORRECT_VOTE, DRAW_MAX, GUESS_OPTIONS, MAX_ROUNDS, WIN_CREW, WIN_IMPOSTOR, Impostor
from party.common import Context, GameError, Seat, Settings
from party.deck import Deck

WORDS = [["bicycle", "motorcycle", "transport"], ["bus", "tram", "transport"], ["car", "van", "transport"], ["boat", "raft", "transport"],
         ["plane", "kite", "transport"], ["train", "metro", "transport"], ["cat", "dog", "animal"]]
PACKS = {"en": {"family": {"words": WORDS, "twists": ["t1", "t2", "t3"]}, "spicy": {"words": [], "twists": []}}}


def png(w=256, h=256, pad=20):
    return base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + struct.pack(">II", w, h) + b"\x00" * pad).decode()


def make(n, seed=1, **options):
    rng = random.Random(seed)
    settings = Settings(lang="en", options=options)
    seats = [Seat("p%d" % i, "N%d" % i) for i in range(n)]
    game = Impostor(Context(seats, settings, rng, Deck(PACKS, settings, rng, set()), 0))
    return game, {s.pid for s in seats}


def seat_of(game, impostor):
    return [i for i in range(len(game.pids)) if (i in game.impostors) == impostor]


def draw_all(game, everyone, now=1):
    for i in game.alive():
        game.act(game.pids[i], {"type": "draw", "png": png()}, now, everyone)


def vote_out(game, everyone, target, now=2):
    for i in game.alive():
        pick = target if i != target else next(j for j in game.alive() if j != target)
        game.act(game.pids[i], {"type": "vote", "target": pick}, now, everyone)


class ImpostorTests(unittest.TestCase):
    def fails(self, status, fn, *args):
        with self.assertRaises(GameError) as caught:
            fn(*args)
        self.assertEqual(caught.exception.status, status)
        return str(caught.exception)

    def test_registry_has_impostor(self):
        self.assertIs(GAMES["impostor"], Impostor)

    def test_setup_counts_and_secret_words(self):
        game, _ = make(10, impostors=3)
        self.assertEqual(len(game.impostors), 3)
        for i, pid in enumerate(game.pids):
            view = game.player_view(pid, 0)
            self.assertNotIn("impostor", view)
            self.assertEqual(view["word"], game.decoy if i in game.impostors else game.word)
        host = json.dumps(game.host_view(0))
        self.assertNotIn(game.word, host)
        self.assertNotIn(game.decoy, host)

    def test_impostor_count_clamped(self):
        game, _ = make(4, impostors=3)
        self.assertEqual(len(game.impostors), 1)

    def test_knows_mode_views(self):
        game, _ = make(10, impostors=2, mode="knows")
        a, b = sorted(game.impostors)
        view = game.player_view(game.pids[a], 0)
        self.assertEqual((view["impostor"], view["category"], view["team"]), (True, game.category, [game.names[b]]))
        self.assertNotIn("word", view)
        self.assertEqual(game.label, "knows")

    def test_label_is_mode(self):
        self.assertEqual(make(4)[0].label, "secret")

    def test_draw_validation(self):
        game, everyone = make(4)
        act = lambda data: game.act("p0", {"type": "draw", "png": data}, 1, everyone)
        for bad in (png(128, 128), base64.b64encode(b"GIF89a" + b"\x00" * 30).decode(), "not base64!!", png(pad=DRAW_MAX), 5):
            self.assertEqual(self.fails(400, act, bad), "Bad drawing")
        act(png())
        self.assertIn(0, game.drawings)
        game.tick(100, everyone)
        self.fails(409, act, png())

    def test_draw_ends_when_all_active_drew(self):
        game, everyone = make(4)
        draw_all(game, everyone)
        self.assertEqual(game.phase, "vote")

    def test_away_player_does_not_block_draw_or_vote(self):
        game, everyone = make(5)
        active = everyone - {"p4"}
        for i in range(4):
            game.act(game.pids[i], {"type": "draw", "png": png()}, 1, active)
        self.assertEqual(game.phase, "vote")
        for i in range(4):
            game.act(game.pids[i], {"type": "vote", "target": (i + 1) % 4}, 2, active)
        self.assertEqual(game.phase, "reveal")

    def test_vote_rules(self):
        game, everyone = make(5)
        draw_all(game, everyone)
        self.fails(400, game.act, "p0", {"type": "vote", "target": 0}, 2, everyone)
        self.fails(400, game.act, "p0", {"type": "vote", "target": True}, 2, everyone)
        self.fails(400, game.act, "p0", {"type": "vote", "target": 9}, 2, everyone)
        game.act("p0", {"type": "vote", "target": 1}, 2, everyone)
        game.act("p0", {"type": "vote", "target": 2}, 2, everyone)
        game.act("p1", {"type": "vote", "target": 2}, 2, everyone)
        game.act("p2", {"type": "vote", "target": 3}, 2, everyone)
        game.act("p3", {"type": "vote", "target": 0}, 2, everyone)
        self.assertEqual(game.host_view(2)["votes"], [1, 0, 2, 1, 0])
        game.act("p4", {"type": "vote", "target": 3}, 2, everyone)
        self.assertEqual(game.result, {"out": None, "impostor": False})

    def test_spectator_cannot_act_or_be_voted(self):
        game, everyone = make(6)
        crew = seat_of(game, False)[0]
        draw_all(game, everyone)
        vote_out(game, everyone, crew)
        game.tick(100, everyone)
        self.assertEqual(game.phase, "draw")
        self.fails(409, game.act, game.pids[crew], {"type": "draw", "png": png()}, 101, everyone)
        draw_all(game, everyone, 101)
        other = next(i for i in game.alive())
        self.fails(400, game.act, game.pids[other], {"type": "vote", "target": crew}, 102, everyone)

    def test_spectator_view_has_no_secrets(self):
        game, everyone = make(6)
        crew = seat_of(game, False)[0]
        draw_all(game, everyone)
        vote_out(game, everyone, crew)
        view = game.player_view(game.pids[crew], 12)
        self.assertLessEqual(set(view), {"phase", "round", "left", "out", "hurry", "twist", "max_rounds"})
        for secret in (game.word, game.decoy, *(game.names[i] for i in game.impostors)):
            self.assertNotIn(secret, json.dumps(view))

    def test_crew_wins_when_impostors_out(self):
        game, everyone = make(6)
        imp = seat_of(game, True)[0]
        draw_all(game, everyone)
        vote_out(game, everyone, imp)
        game.tick(100, everyone)
        self.assertEqual((game.phase, game.winner), ("over", "crew"))
        crew = seat_of(game, False)
        self.assertEqual(game.scores()[game.pids[crew[0]]], WIN_CREW + CORRECT_VOTE)
        self.assertEqual(game.scores()[game.pids[imp]], 0)
        self.assertIn("over", game.host_view(100))
        game.tick(200, everyone)
        self.assertTrue(game.finished)

    def test_impostors_win_when_equal(self):
        game, everyone = make(4)
        crew = seat_of(game, False)
        draw_all(game, everyone, 1)
        vote_out(game, everyone, crew[0], 2)
        game.tick(100, everyone)
        self.assertEqual((game.phase, game.round), ("draw", 2))
        draw_all(game, everyone, 101)
        vote_out(game, everyone, crew[1], 102)
        game.tick(200, everyone)
        self.assertEqual((game.phase, game.winner), ("over", "impostors"))
        imp = seat_of(game, True)[0]
        self.assertEqual(game.scores()[game.pids[imp]], WIN_IMPOSTOR)

    def test_impostors_win_after_max_rounds(self):
        game, everyone = make(8)
        t = 1
        while game.phase != "over":
            game.tick(t + 1000, everyone)
            t += 1000
        self.assertEqual((game.winner, game.round), ("impostors", MAX_ROUNDS))

    def test_knows_mode_last_guess(self):
        for correct in (True, False):
            game, everyone = make(9, mode="knows")
            imp = seat_of(game, True)[0]
            draw_all(game, everyone)
            vote_out(game, everyone, imp)
            game.tick(20, everyone)
            self.assertEqual(game.phase, "guess")
            options = game.player_view(game.pids[imp], 20)["options"]
            self.assertEqual(len(options), GUESS_OPTIONS)
            self.assertIn(game.word, options)
            self.assertNotIn("options", game.player_view(game.pids[seat_of(game, False)[0]], 20))
            pick = game.word if correct else next(o for o in options if o != game.word)
            game.act(game.pids[imp], {"type": "guess", "word": pick}, 21, everyone)
            game.tick(22, everyone)
            if correct:
                self.assertEqual((game.phase, game.winner), ("over", "impostors"))
            else:
                self.assertNotEqual(game.winner, "impostors")

    def test_files_current_round_only(self):
        game, everyone = make(5)
        game.act("p0", {"type": "draw", "png": png()}, 1, everyone)
        name = "d%s-1-0.png" % game.tag
        self.assertIsNone(game.file("p1", name))
        game.tick(31, everyone)
        self.assertEqual(game.phase, "vote")
        self.assertEqual(game.file("p1", name), base64.b64decode(png()))
        self.assertEqual(game.host_view(31)["drawings"], [{"seat": 0, "file": name}])
        self.assertIsNone(game.file("p1", "d%s-1-1.png" % game.tag))
        self.assertIsNone(game.file("p1", "x.png"))
        for t in (100, 200, 300):
            game.tick(t, everyone)
        self.assertEqual(game.round, 2)
        self.assertIsNone(game.file("p1", name))

    def test_impostor_votes_earn_nothing(self):
        game, everyone = make(10, impostors=2)
        a, b = sorted(game.impostors)
        draw_all(game, everyone)
        for i in game.alive():
            game.act(game.pids[i], {"type": "vote", "target": b if i != b else a}, 2, everyone)
        self.assertEqual(game.points[game.pids[a]], 0)
        crew = seat_of(game, False)[0]
        self.assertEqual(game.points[game.pids[crew]], CORRECT_VOTE)

    def test_host_sees_impostor_count(self):
        self.assertEqual(make(6, impostors=3)[0].host_view(0)["impostors"], 1)

    def test_knows_mode_over_hides_decoy(self):
        game, everyone = make(6, mode="knows")
        game.end("crew", 0)
        self.assertEqual(game.host_view(0)["over"]["decoy"], None)
        self.assertEqual(game.host_view(0)["over"]["category"], game.category)

    def test_file_names_differ_between_games(self):
        self.assertNotEqual(make(5, seed=1)[0].tag, make(5, seed=2)[0].tag)

    def test_hurry(self):
        game, everyone = make(4)
        game.hurry(1)
        self.assertEqual((game.deadline, game.host_view(1)["hurry"]), (11, True))
        draw_all(game, everyone, 2)
        for i in range(4):
            game.act(game.pids[i], {"type": "vote", "target": (i + 1) % 4}, 3, everyone)
        self.assertEqual(game.phase, "reveal")
        game.hurry(4)
        game.tick(4, everyone)
        self.assertNotEqual(game.phase, "reveal")


if __name__ == "__main__":
    unittest.main()
