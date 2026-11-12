from pathlib import Path

from party.common import Context, GameError, GameMeta, GameOption
from party.deck import load_packs

READY_TIME = 4
BOOM_TIME = 8
OVER_TIME = 8
HURRY = 3
SURVIVE = 100
FUSES = {"short": (10, 20), "normal": (15, 35), "long": (25, 50)}


class HotPotato:
    meta = GameMeta("hotpotato", {"ro": "Cartoful fierbinte", "en": "Hot Potato"}, 3, 16, "5-10",
                    blurb={"ro": "Spune un cuvant, da bomba mai departe. Nu o tine cand explodeaza.",
                           "en": "Say a word, pass the bomb. Don't be holding it when it blows."},
                    options=(GameOption("rounds", {"ro": "Runde", "en": "Rounds"},
                                        tuple((n, {"ro": str(n), "en": str(n)}) for n in (5, 8, 12)), 8),
                             GameOption("fuse", {"ro": "Fitil", "en": "Fuse"},
                                        (("short", {"ro": "Scurt", "en": "Short"}),
                                         ("normal", {"ro": "Normal", "en": "Normal"}),
                                         ("long", {"ro": "Lung", "en": "Long"})), "normal")))
    packs = load_packs(Path(__file__).parent / "content")

    def __init__(self, ctx: Context):
        self.ctx = ctx
        options = {o.key: o.default for o in self.meta.options} | ctx.settings.options
        self.rounds, self.fuse = options["rounds"], FUSES[options["fuse"]]
        self.pids = [s.pid for s in ctx.seats]
        self.names = [s.name for s in ctx.seats]
        self.points = dict.fromkeys(self.pids, 0)
        self.booms = [0] * len(self.pids)
        self.here = set(range(len(self.pids)))
        self.finished = False
        self.stopped = False
        self.round = 0
        self.victim = None
        self.next_round(ctx.rng.randrange(len(self.pids)), ctx.now)

    def go(self, phase, now, seconds):
        self.phase, self.deadline, self.started = phase, now + seconds, now

    def next_round(self, starter, now):
        self.round += 1
        self.topic = self.ctx.deck.draw("topics")
        self.holder, self.giver, self.passes = starter, None, 0
        self.victim = self.dare = None
        self.go("ready", now, READY_TIME)

    def tick(self, now, active):
        self.here = {i for i, p in enumerate(self.pids) if p in active}
        if self.phase == "live" and now < self.deadline and self.holder not in self.here:
            rest = sorted(self.here)
            if rest:
                self.holder, self.giver = self.ctx.rng.choice(rest), None
        while not self.finished and now >= self.deadline:
            self.advance(self.deadline if self.phase == "live" else now)

    def advance(self, now):
        if self.phase == "ready":
            self.go("live", now, self.ctx.rng.uniform(*self.fuse))
        elif self.phase == "live":
            self.victim = self.holder
            self.booms[self.victim] += 1
            for i, pid in enumerate(self.pids):
                if i != self.victim:
                    self.points[pid] += SURVIVE
            self.dare = self.ctx.deck.draw("dares")
            self.go("boom", now, BOOM_TIME)
        elif self.phase == "boom":
            if self.round >= self.rounds:
                self.go("over", now, OVER_TIME)
            else:
                self.next_round(self.victim, now)
        else:
            self.finished = True

    def stop(self, now):
        if self.phase != "over":
            self.stopped = True
            self.go("over", now, OVER_TIME)

    def act(self, pid, body, now, active):
        self.tick(now, active)
        if body.get("type") != "pass":
            raise GameError("Unknown action", 400)
        i = self.pids.index(pid) if pid in self.pids else None
        if self.phase != "live" or i != self.holder:
            raise GameError("Not right now", 409)
        target = body.get("target")
        if type(target) is not int or not 0 <= target < len(self.pids) or target == i:
            raise GameError("Bad pass", 400)
        if target not in self.here:
            raise GameError("They are away", 409)
        if target == self.giver and len(self.here - {i}) > 1:
            raise GameError("Pass it to someone else", 400)
        self.holder, self.giver = target, i
        self.passes += 1

    def hurry(self, now):
        self.deadline = min(self.deadline, now + HURRY) if self.phase == "live" else now

    def left(self, now):
        return None if self.finished or self.phase == "live" else max(0, self.deadline - now)

    def common(self, now):
        view = {"phase": self.phase, "round": self.round, "rounds": self.rounds, "topic": self.topic, "left": self.left(now),
                "holder": self.holder, "passes": self.passes}
        if self.phase == "live":
            view["elapsed"] = now - self.started
        if self.phase == "boom":
            view |= {"victim": self.victim, "dare": self.dare}
        if self.phase == "over":
            view["over"] = {"stopped": self.stopped, "booms": [{"name": n, "booms": b} for n, b in zip(self.names, self.booms)]}
        return view

    def host_view(self, now):
        return self.common(now) | {"players": [{"seat": i, "name": n, "booms": self.booms[i], "away": i not in self.here}
                                               for i, n in enumerate(self.names)]}

    def player_view(self, pid, now):
        i = self.pids.index(pid) if pid in self.pids else None
        view = self.common(now) | {"holder": self.names[self.holder], "holding": i == self.holder, "me": i,
                                   "names": self.names}
        if self.phase == "live" and i == self.holder:
            back = self.giver if len(self.here - {i}) > 1 else None
            view["targets"] = [{"seat": j, "name": self.names[j]} for j in sorted(self.here) if j not in (i, back)]
        return view

    def scores(self):
        return dict(self.points)
