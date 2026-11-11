from pathlib import Path

from party.common import Context, GameError, GameMeta, clean_line
from party.deck import load_packs

ANSWER_TIME = 75
VOTE_TIME = 20
REVEAL_TIME = 6
EMPTY_TIME = 3
SCORES_TIME = 8
FINAL_REVEAL_TIME = 10
HURRY = 10
CLAPS = 3
CLAP_POINTS = 100
SWEEP_BONUS = 200
WALKOVER_POINTS = 100
FINAL_CLAP_POINTS = 150
ANSWER_MAX = 80
TYPING = ("answer", "final_answer")
WAITING = ("answer", "vote", "final_answer", "final_vote")


class Bravo:
    meta = GameMeta("bravo", {"ro": "Bravo!", "en": "Bravo!"}, 3, 16, "15-25")
    packs = load_packs(Path(__file__).parent / "content")

    def __init__(self, ctx: Context):
        self.ctx = ctx
        self.names = {s.pid: s.name for s in ctx.seats}
        self.points = dict.fromkeys(self.names, 0)
        self.finished = False
        self.round = 0
        self.start_round(ctx.now)

    def go(self, phase, now, seconds):
        self.phase, self.deadline, self.hurried = phase, now + seconds, False

    def fill(self, tag, authors):
        others = [name for pid, name in self.names.items() if pid not in authors]
        return self.ctx.deck.draw(tag).replace("{player}", self.ctx.rng.choice(others))

    def start_round(self, now):
        self.round += 1
        ring = self.ctx.rng.sample(list(self.names), len(self.names))
        pairs = [self.ctx.rng.sample([ring[i], ring[(i + 1) % len(ring)]], 2) for i in range(len(ring))]
        self.ctx.rng.shuffle(pairs)
        self.prompts = [{"text": self.fill("round", pair), "authors": pair, "answers": [None, None]} for pair in pairs]
        self.idx = -1
        self.go("answer", now, ANSWER_TIME)

    def start_final(self, now):
        self.round = "final"
        authors = list(self.names)
        self.prompts = [{"text": self.fill("final", []), "authors": authors, "answers": [None] * len(authors)}]
        self.idx = 0
        self.go("final_answer", now, ANSWER_TIME)

    def answered(self, pid):
        return all(p["answers"][p["authors"].index(pid)] is not None for p in self.prompts if pid in p["authors"])

    def complete(self, active):
        here = [pid for pid in self.names if pid in active]
        if self.phase in TYPING:
            return all(self.answered(pid) for pid in here)
        if self.phase == "vote":
            return all(self.spent.get(pid, 0) >= CLAPS for pid in self.voters & active)
        if self.phase == "final_vote":
            return all(self.spent.get(pid, 0) >= CLAPS or self.stuck(pid) for pid in here)
        return False

    def stuck(self, pid):
        return self.order in ([], [pid])

    def tick(self, now, active):
        while not self.finished and (now >= self.deadline or self.complete(active)):
            self.advance(now, active)

    def advance(self, now, active):
        if self.phase in ("answer", "reveal"):
            self.showdown(now, active)
        elif self.phase == "vote":
            self.reveal(now)
        elif self.phase == "scores":
            if self.round == 1:
                self.start_round(now)
            else:
                self.start_final(now)
        elif self.phase == "final_answer":
            answers = self.prompts[0]["answers"]
            self.order = [pid for pid, text in zip(self.prompts[0]["authors"], answers) if text is not None]
            self.ctx.rng.shuffle(self.order)
            self.claps, self.spent = [0] * len(self.order), {}
            self.go("final_vote", now, VOTE_TIME)
        elif self.phase == "final_vote":
            self.gained = [n * FINAL_CLAP_POINTS for n in self.claps]
            for pid, gain in zip(self.order, self.gained):
                self.points[pid] += gain
            self.go("final_reveal", now, FINAL_REVEAL_TIME)
        else:
            self.finished = True

    def showdown(self, now, active):
        self.idx += 1
        if self.idx == len(self.prompts):
            return self.go("scores", now, SCORES_TIME)
        prompt = self.prompts[self.idx]
        self.claps, self.spent, self.voters, self.sweep = [0, 0], {}, set(), None
        given = [a is not None for a in prompt["answers"]]
        self.walkover = any(given) and not all(given)
        if all(given):
            self.voters = set(active) & set(self.names) - set(prompt["authors"])
            return self.go("vote", now, VOTE_TIME)
        self.award([WALKOVER_POINTS * self.round * g for g in given], now, REVEAL_TIME if self.walkover else EMPTY_TIME)

    def reveal(self, now):
        gained = [n * CLAP_POINTS * self.round for n in self.claps]
        if sum(self.claps) and 0 in self.claps:
            self.sweep = 1 - self.claps.index(0)
            gained[self.sweep] += SWEEP_BONUS * self.round
        self.award(gained, now, REVEAL_TIME)

    def award(self, gained, now, seconds):
        self.gained = gained
        for pid, gain in zip(self.prompts[self.idx]["authors"], gained):
            self.points[pid] += gain
        self.go("reveal", now, seconds)

    def act(self, pid, body, now, active):
        self.tick(now, active)
        kind = body.get("type")
        if kind == "answer":
            self.answer(pid, body)
        elif kind == "clap":
            self.clap(pid, body)
        else:
            raise GameError("Unknown action", 400)
        self.tick(now, active)

    def index(self, value, size):
        if type(value) is not int or not 0 <= value < size:
            raise GameError("Bad choice", 400)
        return value

    def answer(self, pid, body):
        if self.phase not in TYPING:
            raise GameError("Not right now", 409)
        prompt = self.prompts[self.index(body.get("i"), len(self.prompts))]
        if pid not in prompt["authors"]:
            raise GameError("Not your prompt", 403)
        side = prompt["authors"].index(pid)
        if prompt["answers"][side] is not None:
            raise GameError("Already answered", 409)
        text = clean_line(body.get("text"), ANSWER_MAX)
        if not text:
            raise GameError("Write something", 400)
        prompt["answers"][side] = text

    def clap(self, pid, body):
        if self.phase == "vote":
            pick = self.index(body.get("side"), 2)
            if pid not in self.voters:
                raise GameError("Not your vote", 403)
        elif self.phase == "final_vote":
            pick = self.index(body.get("target"), len(self.order))
            if self.order[pick] == pid:
                raise GameError("Not your own answer", 403)
        else:
            raise GameError("Not right now", 409)
        if self.spent.get(pid, 0) >= CLAPS:
            raise GameError("No claps left", 409)
        self.spent[pid] = self.spent.get(pid, 0) + 1
        self.claps[pick] += 1

    def hurry(self, now):
        if self.phase in WAITING:
            self.deadline = min(self.deadline, now + HURRY)
            self.hurried = True
        else:
            self.deadline = now

    def common(self, now):
        return {"phase": self.phase, "round": self.round, "left": None if self.finished else max(0, self.deadline - now), "hurry": self.hurried}

    def final_answers(self):
        answers = dict(zip(self.prompts[0]["authors"], self.prompts[0]["answers"]))
        return [answers[pid] for pid in self.order]

    def host_view(self, now):
        view = self.common(now)
        prompt = self.prompts[self.idx] if self.idx >= 0 and self.phase != "scores" else None
        if self.phase in TYPING:
            view["done"] = [name for pid, name in self.names.items() if self.answered(pid)]
        if self.phase == "final_answer":
            view["prompt"] = prompt["text"]
        if self.phase in ("vote", "reveal"):
            done = sum(self.spent.get(pid, 0) >= CLAPS for pid in self.voters)
            view.update(prompt=prompt["text"], answers=prompt["answers"], claps=self.claps, voters_done=done, voters=len(self.voters))
        if self.phase == "reveal":
            view.update(authors=[self.names[pid] for pid in prompt["authors"]], points=self.gained, sweep=self.sweep, walkover=self.walkover)
        if self.phase in ("final_vote", "final_reveal"):
            view.update(prompt=prompt["text"], answers=self.final_answers(), claps=self.claps)
        if self.phase == "final_reveal":
            view.update(authors=[self.names[pid] for pid in self.order], points=self.gained)
        if self.phase == "scores":
            view["standings"] = sorted(({"name": name, "points": self.points[pid]} for pid, name in self.names.items()), key=lambda row: -row["points"])
        return view

    def player_view(self, pid, now):
        if self.phase == "vote":
            prompt = self.prompts[self.idx]
            left = CLAPS - self.spent.get(pid, 0) if pid in self.voters else 0
            return self.common(now) | {"prompt": prompt["text"], "answers": prompt["answers"], "author": pid in prompt["authors"], "claps_left": left}
        if self.phase == "final_vote":
            own = self.order.index(pid) if pid in self.order else None
            return self.common(now) | {"prompt": self.prompts[0]["text"], "answers": self.final_answers(), "own": own, "claps_left": 0 if self.stuck(pid) else CLAPS - self.spent.get(pid, 0)}
        view = self.common(now) if self.phase == "answer" else self.host_view(now)
        if self.phase in TYPING:
            view["prompts"] = [{"i": i, "text": p["text"], "answered": p["answers"][p["authors"].index(pid)] is not None} for i, p in enumerate(self.prompts) if pid in p["authors"]]
        return view

    def scores(self):
        return dict(self.points)
