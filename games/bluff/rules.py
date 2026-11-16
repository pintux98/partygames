import unicodedata
from pathlib import Path

from party.common import HOLD, Context, GameError, GameMeta, GameOption, clean_line, left
from party.deck import load_packs

FAKE_MAX = 40
HURRY = 10
TRUTH_POINTS = 100
FOOL_POINTS = 50


def fold(text):
    return "".join(c for c in unicodedata.normalize("NFKD", text) if c.isalnum()).casefold()


def choices(key, names, values, default, unit=""):
    return GameOption(key, names, tuple((v, {"ro": str(v) + unit, "en": str(v) + unit}) for v in values), default)


class Bluff:
    meta = GameMeta("bluff", {"ro": "Minciuna", "en": "Bluff"}, 3, 16, "10-20",
                    blurb={"ro": "Inventeaza o minciuna credibila si ghiceste adevarul", "en": "Fake a believable answer, then spot the truth"},
                    options=(choices("rounds", {"ro": "Runde", "en": "Rounds"}, (5, 8, 10), 8),
                             choices("answer_time", {"ro": "Timp de scris", "en": "Writing time"}, (45, 60, 90), 60, " s"),
                             choices("vote_time", {"ro": "Timp de vot", "en": "Vote time"}, (20, 30), 30, " s")))
    packs = load_packs(Path(__file__).parent / "content")

    def __init__(self, ctx: Context):
        self.ctx = ctx
        options = {o.key: o.default for o in self.meta.options} | ctx.settings.options
        self.rounds, self.answer_time, self.vote_time = options["rounds"], options["answer_time"], options["vote_time"]
        self.names = {s.pid: s.name for s in ctx.seats}
        self.ids = list(self.names)
        self.points = dict.fromkeys(self.ids, 0)
        self.finished = False
        self.round = 0
        self.start_round(ctx.now)

    def go(self, phase, now, seconds):
        self.phase, self.deadline, self.hurried = phase, now + seconds, False

    def start_round(self, now):
        self.round += 1
        self.fact, self.truth = self.ctx.deck.draw("facts")
        self.fakes, self.votes, self.options, self.gained = {}, {}, [], {}
        self.go("write", now, self.answer_time)

    def start_vote(self, now):
        merged = {}
        for pid, text in self.fakes.items():
            merged.setdefault(fold(text), {"text": text, "authors": [], "truth": False})["authors"].append(pid)
        self.options = [*merged.values(), {"text": self.truth, "authors": [], "truth": True}]
        self.ctx.rng.shuffle(self.options)
        self.go("vote", now, self.vote_time)

    def reveal(self, now):
        self.gained = dict.fromkeys(self.ids, 0)
        for pid, i in self.votes.items():
            if self.options[i]["truth"]:
                self.gained[pid] += TRUTH_POINTS
            for author in self.options[i]["authors"]:
                self.gained[author] += FOOL_POINTS
        for pid, gain in self.gained.items():
            self.points[pid] += gain
        self.go("reveal", now, HOLD)

    def complete(self, active):
        here = [pid for pid in self.ids if pid in active]
        if self.phase == "write":
            return all(pid in self.fakes for pid in here)
        if self.phase == "vote":
            return all(pid in self.votes for pid in here)
        return False

    def tick(self, now, active):
        while not self.finished and (now >= self.deadline or self.complete(active)):
            if self.phase == "write":
                self.start_vote(now)
            elif self.phase == "vote":
                self.reveal(now)
            elif self.round < self.rounds:
                self.start_round(now)
            else:
                self.finished = True

    def act(self, pid, body, now, active):
        self.tick(now, active)
        kind = body.get("type")
        if kind == "fake":
            self.fake(pid, body)
        elif kind == "vote":
            self.vote(pid, body)
        else:
            raise GameError("Unknown action", 400)
        self.tick(now, active)

    def fake(self, pid, body):
        if self.phase != "write":
            raise GameError("Not right now", 409)
        if pid in self.fakes:
            raise GameError("Already answered", 409)
        text = clean_line(body.get("text"), FAKE_MAX)
        if not fold(text):
            raise GameError("Write something", 400)
        if fold(text) == fold(self.truth):
            raise GameError("Too close to the truth", 409)
        self.fakes[pid] = text

    def vote(self, pid, body):
        if self.phase != "vote":
            raise GameError("Not right now", 409)
        i = body.get("pick")
        if type(i) is not int or not 0 <= i < len(self.options):
            raise GameError("Bad choice", 400)
        if pid in self.options[i]["authors"]:
            raise GameError("Not your own answer", 403)
        if pid in self.votes:
            raise GameError("Already voted", 409)
        self.votes[pid] = i

    def hurry(self, now):
        if self.phase == "reveal":
            self.deadline = now
        else:
            self.deadline = min(self.deadline, now + HURRY)
            self.hurried = True

    def common(self, now):
        return {"phase": self.phase, "round": self.round, "rounds": self.rounds, "fact": self.fact,
                "left": None if self.finished else left(self.deadline, now), "hurry": self.hurried}

    def host_view(self, now):
        view = self.common(now)
        if self.phase == "write":
            view["done"] = [self.names[pid] for pid in self.ids if pid in self.fakes]
        elif self.phase == "vote":
            view["done"] = [self.names[pid] for pid in self.ids if pid in self.votes]
            view["options"] = [o["text"] for o in self.options]
        else:
            view["truth"] = self.truth
            view["options"] = [{"text": o["text"], "truth": o["truth"], "authors": [self.names[p] for p in o["authors"]],
                                "picked": [self.names[p] for p, i in self.votes.items() if i == j]} for j, o in enumerate(self.options)]
            view["standings"] = sorted(({"name": self.names[p], "gain": self.gained[p], "points": self.points[p]} for p in self.ids),
                                       key=lambda row: -row["points"])
        return view

    def player_view(self, pid, now):
        if self.phase == "write":
            return self.common(now) | {"mine": self.fakes.get(pid)}
        if self.phase == "vote":
            picks = [{"i": i, "text": o["text"]} for i, o in enumerate(self.options) if pid not in o["authors"]]
            return self.common(now) | {"picks": picks, "voted": pid in self.votes}
        view = self.host_view(now)
        mine = self.votes.get(pid)
        view["me"] = {"found": mine is not None and self.options[mine]["truth"], "voted": mine is not None,
                      "fooled": sum(pid in self.options[i]["authors"] for i in self.votes.values()), "gain": self.gained[pid]}
        return view

    def scores(self):
        return dict(self.points)
