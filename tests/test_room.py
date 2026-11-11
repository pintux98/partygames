import json
import random
import unittest

from party.common import GameError
from party.room import MAX_PLAYERS, Room
from dummy import GAMES, Dummy, Optioned
from games import GAMES as REAL

NAMES = ["Ana", "Bob", "Cara"] + ["P%d" % i for i in range(3, MAX_PLAYERS)]
START = {"type": "start"}


def room_with(n, now=0):
    room = Room("ABCDEF", 0, GAMES, random.Random(1))
    return room, [room.join(name, now) for name in NAMES[:n]]


class RoomTests(unittest.TestCase):
    def test_options_default_and_change(self):
        room = Room("ABCDEF", 0, REAL, random.Random(1))
        ana = room.join("Ana", 0)
        self.assertEqual(room.settings.options, {"answer_time": 75, "vote_time": 20})
        room.action(ana.id, {"type": "settings", "option": {"answer_time": 60}}, 0)
        self.assertEqual(room.settings.options["answer_time"], 60)
        opts = room.view_for(ana.id, 0)["options"]
        self.assertEqual((opts[0]["key"], opts[0]["value"]), ("answer_time", 60))
        self.assertIn({"value": 45, "names": {"ro": "45 s", "en": "45 s"}}, opts[0]["choices"])

    def test_option_validation(self):
        room = Room("ABCDEF", 0, REAL, random.Random(1))
        ana = room.join("Ana", 0)
        act = lambda option: room.action(ana.id, {"type": "settings", "option": option}, 0)
        self.assertEqual(self.fails(400, act, {"answer_time": 61}), "Bad option")
        self.assertEqual(self.fails(400, act, {"nope": 1}), "Unknown option")
        self.assertEqual(self.fails(400, act, {"answer_time": True}), "Bad option")
        self.fails(400, act, [1])
        room.join("Bob", 0)
        room.join("Cara", 0)
        room.action(ana.id, START, 0)
        self.fails(409, act, {"answer_time": 60})

    def test_game_change_resets_options(self):
        room = Room("ABCDEF", 0, {"opt": Optioned, "dummy": Dummy}, random.Random(1))
        ana = room.join("Ana", 0)
        self.assertEqual(room.settings.options, {"x": 1})
        room.action(ana.id, {"type": "settings", "option": {"x": 2}}, 0)
        room.action(ana.id, {"type": "settings", "game": "dummy"}, 0)
        self.assertEqual(room.settings.options, {})
        room.action(ana.id, {"type": "settings", "game": "opt"}, 0)
        self.assertEqual(room.settings.options, {"x": 1})
        self.assertEqual(room.view_for(ana.id, 0)["games"][0]["blurb"], {})

    def fails(self, status, fn, *args):
        with self.assertRaises(GameError) as caught:
            fn(*args)
        self.assertEqual(caught.exception.status, status)
        return str(caught.exception)

    def test_first_joiner_is_vip(self):
        room, (ana, bob) = room_with(2)
        self.assertEqual(room.vip, ana.id)
        self.assertTrue(room.view_for(ana.id, 0)["controller"])
        self.assertFalse(room.view_for(bob.id, 0)["controller"])

    def test_names_unique_case_insensitive(self):
        room, _ = room_with(1)
        self.assertEqual(self.fails(409, room.join, " ana ", 5), "That name is taken")
        self.assertEqual(self.fails(400, room.join, " \t ", 5), "Pick a nickname")

    def test_look_alike_names_taken(self):
        room, _ = room_with(1)
        room.join("x" * 19, 0)
        self.fails(409, room.join, "x" * 19 + " y", 0)
        self.fails(409, room.join, "\uff21\uff2e\uff21", 0)

    def test_name_never_reclaims_idle_seat(self):
        room, _ = room_with(1)
        self.assertEqual(self.fails(409, room.join, "ana", 500), "That name is taken")

    def test_room_full_at_16(self):
        room, _ = room_with(MAX_PLAYERS)
        self.assertEqual(self.fails(409, room.join, "Extra", 0), "Room is full")

    def test_start_needs_three(self):
        room, (ana, _) = room_with(2)
        self.assertIn("3", self.fails(409, room.action, ana.id, START, 0))

    def test_only_controller_starts(self):
        room, (_, bob, _) = room_with(3)
        self.assertEqual(self.fails(403, room.action, bob.id, START, 0), "Only the VIP can do that")
        room.action(room.host, START, 0)
        self.assertEqual(room.phase, "playing")

    def test_game_action_routed(self):
        room, (ana, bob, _) = room_with(3)
        room.action(ana.id, START, 0)
        room.action(ana.id, {"type": "point"}, 1)
        room.action(ana.id, {"type": "point"}, 2)
        self.assertEqual(room.view_for(ana.id, 2)["game"], {"mine": 2})
        self.assertEqual(room.view_for(room.host, 2)["game"], {"seats": 3})
        room.action(bob.id, {"type": "finish"}, 3)
        room.tick(3)
        self.assertEqual(room.phase, "results")
        self.assertEqual(room.last_scores[ana.id], 2)
        self.assertEqual(room.view_for(bob.id, 3)["scores"][0], {"name": "Ana", "points": 2})
        self.assertEqual(room.drain_events(), [("started", "dummy"), ("finished", "dummy")])
        self.assertEqual(room.drain_events(), [])

    def test_next_calls_hurry(self):
        room, (ana, bob, _) = room_with(3)
        room.action(ana.id, START, 0)
        self.fails(403, room.action, bob.id, {"type": "next"}, 1)
        room.action(ana.id, {"type": "next"}, 1)
        self.assertTrue(room.game.hurried)

    def test_mid_game_join_waits(self):
        room, (ana, _, _) = room_with(3)
        room.action(ana.id, START, 0)
        dan = room.join("Dan", 1)
        self.assertTrue(dan.waiting)
        self.assertIsNone(room.view_for(dan.id, 1)["game"])
        self.assertNotIn(dan.id, room.active(1))
        self.assertEqual(self.fails(400, room.action, dan.id, {"type": "point"}, 1), "Unknown action")
        for i in range(MAX_PLAYERS - 4):
            room.join("Late%d" % i, 1)
        self.fails(409, room.join, "Extra", 1)

    def test_again_drops_away_and_seats_waiting(self):
        room, (ana, bob, cara) = room_with(3)
        room.action(ana.id, START, 0)
        dan = room.join("Dan", 1)
        room.action(ana.id, {"type": "end"}, 30)
        self.assertEqual(room.phase, "results")
        for p in (ana, bob, dan):
            room.seen(p.id, 70)
        room.action(ana.id, {"type": "again"}, 70)
        self.assertEqual(room.phase, "lobby")
        self.assertIsNone(room.game)
        self.assertEqual(list(room.players), [ana.id, bob.id, dan.id])
        self.assertFalse(dan.waiting)
        room.action(ana.id, START, 70)
        self.assertEqual(set(room.game.points), {ana.id, bob.id, dan.id})

    def test_vip_moves_when_away(self):
        room, (ana, bob, cara) = room_with(3)
        room.seen(bob.id, 61)
        room.seen(cara.id, 61)
        room.tick(61)
        self.assertEqual(room.vip, bob.id)
        self.assertEqual(room.view_for(bob.id, 61)["players"][0], {"name": "Ana", "vip": False, "away": True, "waiting": False})

    def test_away_at_start_is_waiting(self):
        room, (ana, bob, cara, dan) = room_with(4)
        room.seen(ana.id, 61)
        room.seen(bob.id, 61)
        room.seen(cara.id, 61)
        room.action(ana.id, START, 61)
        self.assertTrue(dan.waiting)
        self.assertFalse(ana.waiting)
        room.tick(200)
        self.assertNotIn(room.vip, [dan.id])

    def test_screen_move_needs_vip(self):
        room, (ana, _, _) = room_with(3)
        old = room.host
        sid = room.request_screen(0, "tv")
        self.assertTrue(room.is_member(sid))
        self.assertEqual(room.view_for(sid, 0)["role"], "screen_pending")
        handle = room.view_for(ana.id, 0)["screen_requests"][0]
        self.fails(403, room.action, old, {"type": "allow_screen", "handle": handle}, 0)
        self.fails(404, room.action, ana.id, {"type": "allow_screen", "handle": sid}, 0)
        room.action(ana.id, {"type": "allow_screen", "handle": handle}, 0)
        self.assertEqual(room.host, sid)
        self.assertEqual(room.view_for(sid, 0)["role"], "host")
        self.assertEqual(room.view_for(old, 0)["role"], "moved")
        self.assertFalse(room.is_member("stranger"))

    def test_vip_never_sees_screen_token(self):
        room, players = room_with(3)
        ana = players[0]
        sid = room.request_screen(0, "tv")
        before = room.view_for(ana.id, 0)
        self.assertNotIn(sid, json.dumps(before))
        room.action(ana.id, {"type": "allow_screen", "handle": before["screen_requests"][0]}, 0)
        self.assertEqual(room.host, sid)
        for p in players:
            self.assertNotIn(room.host, json.dumps(room.view_for(p.id, 0)))
        room.request_screen(0, "tv")
        room.action(ana.id, {"type": "deny_screen", "handle": room.view_for(ana.id, 0)["screen_requests"][0]}, 0)
        self.assertEqual(room.screen_requests, {})

    def test_moved_tokens_bounded(self):
        room, (ana, _, _) = room_with(3)
        for _ in range(100):
            room.request_screen(0, "tv")
            room.action(ana.id, {"type": "allow_screen", "handle": room.view_for(ana.id, 0)["screen_requests"][0]}, 0)
        self.assertLessEqual(len(room.moved), 4)

    def test_screen_requests_capped_and_expire(self):
        room, _ = room_with(3)
        for i in range(3):
            room.request_screen(0, str(i))
        self.fails(429, room.request_screen, 0, "3")
        room.tick(121)
        self.assertEqual(room.screen_requests, {})
        room.request_screen(121, "0")

    def test_idle_close_after_900s(self):
        room, _ = room_with(3)
        room.tick(900)
        self.assertEqual(room.phase, "lobby")
        room.tick(901)
        self.assertEqual(room.phase, "closed")
        self.assertEqual(self.fails(404, room.join, "Dan", 901), "This room is closed")

    def test_joins_keep_room_alive(self):
        room = Room("ABCDEF", 0, GAMES, random.Random(1))
        room.join("Ana", 0)
        room.join("Bob", 800)
        room.tick(1000)
        self.assertEqual(room.phase, "lobby")

    def test_stale_screen_requests_do_not_block(self):
        room, _ = room_with(3)
        for i in range(3):
            room.request_screen(0, str(i))
        sid = room.request_screen(121, "0")
        self.assertEqual(list(room.screen_requests), [sid])

    def test_end_from_lobby_closes(self):
        room, (ana, _, _) = room_with(3)
        room.action(ana.id, {"type": "end"}, 0)
        self.assertEqual(room.phase, "closed")

    def test_settings_validation(self):
        room, (ana, bob, _) = room_with(3)
        self.fails(400, room.action, ana.id, {"type": "settings", "lang": "de"}, 0)
        self.fails(400, room.action, ana.id, {"type": "settings", "game": "nope"}, 0)
        self.fails(400, room.action, ana.id, {"type": "settings", "spicy": "yes"}, 0)
        self.assertEqual(room.view_for(ana.id, 0)["settings"], {"lang": "en", "spicy": False})
        self.fails(403, room.action, bob.id, {"type": "settings", "lang": "ro"}, 0)
        room.action(ana.id, {"type": "settings", "lang": "ro", "spicy": True, "game": "dummy"}, 0)
        self.assertEqual(room.view_for(ana.id, 0)["settings"], {"lang": "ro", "spicy": True})
        room.action(ana.id, START, 0)
        self.fails(409, room.action, ana.id, {"type": "settings", "lang": "en"}, 0)


if __name__ == "__main__":
    unittest.main()
