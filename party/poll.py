from party.common import Context, GameError, GameOption

REVEAL_TIME = 9
HURRY = 5
POINTS = 100


def rounds_option(default=10):
    return GameOption("rounds", {"ro": "Runde", "en": "Rounds"}, tuple((n, {"ro": str(n), "en": str(n)}) for n in (6, 10, 15)), default)


def time_option(default=20):
    return GameOption("answer_time", {"ro": "Timp de raspuns", "en": "Answer time"},
                      tuple((n, {"ro": "%d s" % n, "en": "%d s" % n}) for n in (15, 20, 30)), default)


class Poll:
    tag = ""

    def __init__(self, ctx: Context):
        self.ctx = ctx
        options = {o.key: o.default for o in self.meta.options} | ctx.settings.options
        self.rounds, self.answer_time = options["rounds"], options["answer_time"]
        self.pids = [s.pid for s in ctx.seats]
        self.names = [s.name for s in ctx.seats]
        self.points = dict.fromkeys(self.pids, 0)
        self.here = set(range(len(self.pids)))
        self.finished = False
        self.round = 0
        self.next_round(ctx.now)

    def go(self, phase, now, seconds):
        self.phase, self.deadline, self.hurried = phase, now + seconds, False

    def next_round(self, now):
        if self.round >= self.rounds:
            self.finished = True
            return
        self.round += 1
        self.item = self.ctx.deck.draw(self.tag)
        self.answers: dict[int, dict] = {}
        self.gains: dict[int, int] = {}
        self.result = None
        self.go("ask", now, self.answer_time)

    def tick(self, now, active):
        self.here = {i for i, p in enumerate(self.pids) if p in active}
        while not self.finished:
            if self.phase == "ask" and self.here and self.here <= set(self.answers):
                self.reveal(now)
            elif now >= self.deadline:
                self.reveal(now) if self.phase == "ask" else self.next_round(now)
            else:
                break

    def reveal(self, now):
        self.result, self.gains = self.score()
        for i, gain in self.gains.items():
            self.points[self.pids[i]] += gain
        self.go("reveal", now, REVEAL_TIME)

    def act(self, pid, body, now, active):
        self.tick(now, active)
        i = self.pids.index(pid) if pid in self.pids else None
        if body.get("type") != "answer":
            raise GameError("Unknown action", 400)
        if self.finished or self.phase != "ask" or i is None:
            raise GameError("Not right now", 409)
        self.answers[i] = self.read(body)
        self.tick(now, active)

    def pick(self, body, key, count):
        value = body.get(key)
        if type(value) is not int or not 0 <= value < count:
            raise GameError("Bad choice", 400)
        return value

    def hurry(self, now):
        if self.phase == "ask":
            self.deadline, self.hurried = min(self.deadline, now + HURRY), True
        else:
            self.deadline = now

    def common(self, now):
        view = {"phase": self.phase, "round": self.round, "rounds": self.rounds, "item": self.item, "spicy": self.ctx.settings.spicy,
                "left": None if self.finished else max(0, self.deadline - now), "hurry": self.hurried}
        if self.phase == "reveal":
            view["result"] = self.result
        return view

    def host_view(self, now):
        return self.common(now) | {"players": [{"name": n, "done": i in self.answers, "away": i not in self.here}
                                               for i, n in enumerate(self.names)]}

    def player_view(self, pid, now):
        i = self.pids.index(pid) if pid in self.pids else None
        return self.common(now) | {"mine": self.answers.get(i), "gain": self.gains.get(i, 0), "names": self.names, "me": i}

    def scores(self):
        return dict(self.points)
