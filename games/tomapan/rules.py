import unicodedata
from pathlib import Path

from party.common import HOLD, Context, GameError, GameMeta, GameOption, clean_line, left
from party.deck import load_packs

LETTERS = "ABCDEFGHIJLMNOPRSTUVZ"
WORD_MAX = 24
HURRY = 10
STOP_TIME = 5
UNIQUE_POINTS = 10
SHARED_POINTS = 5


def fold(text):
    return "".join(c for c in unicodedata.normalize("NFKD", text) if c.isalpha()).casefold()


def numbers(key, names, values, default):
    return GameOption(key, names, tuple((v, {"ro": str(v), "en": str(v)}) for v in values), default)


class Tomapan:
    meta = GameMeta("tomapan", {"ro": "Tomapan", "en": "Tomapan"}, 2, 16, "10-20",
                    blurb={"ro": "Tara, oras, munte, apa... scrie repede pe litera data", "en": "Name a word per category on the given letter, fast"},
                    options=(numbers("rounds", {"ro": "Runde", "en": "Rounds"}, (3, 5, 8), 5),
                             GameOption("answer_time", {"ro": "Timp de scris", "en": "Writing time"},
                                        tuple((v, {"ro": "%d s" % v, "en": "%d s" % v}) for v in (60, 90, 120)), 90),
                             numbers("categories", {"ro": "Categorii", "en": "Categories"}, (5, 8), 5)))
    packs = load_packs(Path(__file__).parent / "content")

    def __init__(self, ctx: Context):
        self.ctx = ctx
        options = {o.key: o.default for o in self.meta.options} | ctx.settings.options
        self.rounds, self.answer_time, self.count = options["rounds"], options["answer_time"], options["categories"]
        self.names = {s.pid: s.name for s in ctx.seats}
        self.ids = list(self.names)
        self.points = dict.fromkeys(self.ids, 0)
        self.letters = ctx.rng.sample(LETTERS, self.rounds)
        self.seen = set()
        self.finished = False
        self.round = 0
        self.start_round(ctx.now)

    def go(self, phase, now, seconds):
        self.phase, self.deadline, self.hurried = phase, now + seconds, False

    def start_round(self, now):
        self.round += 1
        self.letter = self.letters[self.round - 1]
        pool = self.ctx.deck.pool("categories")
        fresh = [c for c in pool if c not in self.seen]
        if len(fresh) < self.count:
            fresh, self.seen = pool, set()
        self.cats = self.ctx.rng.sample(fresh, self.count)
        self.seen.update(self.cats)
        self.answers = {pid: [""] * self.count for pid in self.ids}
        self.stopped = None
        self.vetoes = {}
        self.go("write", now, self.answer_time)

    def tick(self, now, active):
        while not self.finished and now >= self.deadline:
            if self.phase == "write":
                self.go("review", now, HOLD)
            else:
                for pid, gain in self.gains().items():
                    self.points[pid] += gain
                if self.round < self.rounds:
                    self.start_round(now)
                else:
                    self.finished = True

    def ok(self, pid, j):
        return fold(self.answers[pid][j]).startswith(self.letter.lower())

    def struck(self, pid, j):
        return 2 * len(self.vetoes.get((pid, j), ())) > len(self.ids) - 1

    def cell_points(self):
        out = {}
        for j in range(self.count):
            live = {pid: fold(self.answers[pid][j]) for pid in self.ids if self.ok(pid, j) and not self.struck(pid, j)}
            for pid, word in live.items():
                out[pid, j] = SHARED_POINTS if list(live.values()).count(word) > 1 else UNIQUE_POINTS
        return out

    def gains(self):
        gain = dict.fromkeys(self.ids, 0)
        for (pid, _), points in self.cell_points().items():
            gain[pid] += points
        return gain

    def act(self, pid, body, now, active):
        self.tick(now, active)
        kind = body.get("type")
        if kind == "answer":
            self.answer(pid, body)
        elif kind == "stop":
            self.stop(pid, now)
        elif kind == "veto":
            self.veto(pid, body)
        else:
            raise GameError("Unknown action", 400)
        self.tick(now, active)

    def answer(self, pid, body):
        if self.phase != "write":
            raise GameError("Not right now", 409)
        given = body.get("answers")
        if not isinstance(given, list) or len(given) != self.count:
            raise GameError("Bad answers", 400)
        self.answers[pid] = [clean_line(a, WORD_MAX) for a in given]

    def stop(self, pid, now):
        if self.phase != "write":
            raise GameError("Not right now", 409)
        if not all(self.answers[pid]):
            raise GameError("Fill every box first", 409)
        self.stopped = self.stopped or self.names[pid]
        self.deadline = min(self.deadline, now + STOP_TIME)

    def veto(self, pid, body):
        if self.phase != "review":
            raise GameError("Not right now", 409)
        i, j = body.get("player"), body.get("cat")
        if type(i) is not int or type(j) is not int or not 0 <= i < len(self.ids) or not 0 <= j < self.count:
            raise GameError("Bad choice", 400)
        target = self.ids[i]
        if target == pid:
            raise GameError("Not your own answer", 403)
        if not self.ok(target, j):
            raise GameError("Nothing to veto", 409)
        who = self.vetoes.setdefault((target, j), set())
        who.symmetric_difference_update({pid})

    def hurry(self, now):
        if self.phase == "write":
            self.deadline = min(self.deadline, now + HURRY)
            self.hurried = True
        else:
            self.deadline = now

    def common(self, now):
        return {"phase": self.phase, "round": self.round, "rounds": self.rounds, "letter": self.letter, "cats": self.cats,
                "left": None if self.finished else left(self.deadline, now), "hurry": self.hurried, "stopped": self.stopped}

    def review(self):
        points = self.cell_points()
        cells = [[{"a": self.answers[pid][j], "ok": self.ok(pid, j), "v": len(self.vetoes.get((pid, j), ())),
                   "x": self.struck(pid, j), "p": points.get((pid, j), 0)} for pid in self.ids] for j in range(self.count)]
        gain = self.gains()
        return {"players": list(self.names.values()), "cells": cells, "gain": [gain[p] for p in self.ids], "total": [self.points[p] + gain[p] for p in self.ids]}

    def host_view(self, now):
        view = self.common(now)
        if self.phase == "write":
            view["done"] = [self.names[pid] for pid in self.ids if all(self.answers[pid])]
        else:
            view["review"] = self.review()
        return view

    def player_view(self, pid, now):
        view = self.host_view(now)
        if self.phase == "write":
            view["mine"] = self.answers[pid]
        else:
            view["me"] = self.ids.index(pid)
            view["voted"] = [[self.ids.index(t), j] for (t, j), who in self.vetoes.items() if pid in who]
        return view

    def scores(self):
        return dict(self.points)
