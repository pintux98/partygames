import base64
import binascii
import re
import struct
from pathlib import Path

from party.common import Context, GameError, GameMeta, GameOption
from party.deck import load_packs

DRAW_SIZE = 256
DRAW_MAX = 32000
REVEAL_TIME = 5
GUESS_TIME = 15
OVER_TIME = 8
HURRY = 10
MAX_ROUNDS = 8
GUESS_OPTIONS = 6
WIN_CREW = 100
WIN_IMPOSTOR = 300
CORRECT_VOTE = 50
PNG = b"\x89PNG\r\n\x1a\n"
WAITING = ("draw", "vote", "guess")


def seconds(key, names, values, default):
    return GameOption(key, names, tuple((v, {"ro": "%d s" % v, "en": "%d s" % v}) for v in values), default)


def picture(data):
    try:
        raw = base64.b64decode(data, validate=True) if isinstance(data, str) else b""
    except (binascii.Error, ValueError):
        raw = b""
    if not (24 <= len(raw) <= DRAW_MAX and raw.startswith(PNG) and raw[12:16] == b"IHDR"
            and struct.unpack(">II", raw[16:24]) == (DRAW_SIZE, DRAW_SIZE)):
        raise GameError("Bad drawing", 400)
    return raw


class Impostor:
    meta = GameMeta("impostor", {"ro": "Impostor", "en": "Impostor"}, 4, 16, "5-10",
                    blurb={"ro": "Desenati acelasi cuvant. Unul dintre voi are altul.", "en": "Everyone draws the same word. One of you has another."},
                    options=(GameOption("mode", {"ro": "Mod", "en": "Mode"},
                                        (("secret", {"ro": "Impostor secret", "en": "Secret impostor"}),
                                         ("knows", {"ro": "Impostorul stie", "en": "Impostor knows"})), "secret"),
                             GameOption("impostors", {"ro": "Impostori", "en": "Impostors"},
                                        tuple((n, {"ro": str(n), "en": str(n)}) for n in (1, 2, 3)), 1),
                             seconds("draw_time", {"ro": "Timp de desen", "en": "Draw time"}, (20, 30, 45, 60), 30),
                             seconds("vote_time", {"ro": "Timp de vot", "en": "Vote time"}, (20, 30, 40, 60), 40)),
                    upload_max=48000)
    packs = load_packs(Path(__file__).parent / "content")

    def __init__(self, ctx: Context):
        self.ctx = ctx
        options = {o.key: o.default for o in self.meta.options} | ctx.settings.options
        self.label, self.draw_time, self.vote_time = options["mode"], options["draw_time"], options["vote_time"]
        self.pids = [s.pid for s in ctx.seats]
        self.names = [s.name for s in ctx.seats]
        count = min(options["impostors"], max(1, (len(self.pids) - 1) // 3))
        self.impostors = set(ctx.rng.sample(range(len(self.pids)), count))
        self.word, self.decoy, self.category = ctx.deck.draw("words")
        self.out: set[int] = set()
        self.points = dict.fromkeys(self.pids, 0)
        self.finished = False
        self.round = 0
        self.winner = None
        self.guesser = None
        self.options: list[str] = []
        self.next_round(ctx.now)

    def go(self, phase, now, seconds):
        self.phase, self.deadline, self.hurried = phase, now + seconds, False

    def next_round(self, now):
        self.round += 1
        self.twist = self.ctx.deck.draw("twists") if self.pool("twists") else ""
        self.drawings: dict[int, bytes] = {}
        self.votes: dict[int, int] = {}
        self.result = None
        self.go("draw", now, self.draw_time)

    def pool(self, tag):
        modes = self.ctx.deck.packs[self.ctx.settings.lang]
        return modes["family"][tag] + (modes["spicy"][tag] if self.ctx.settings.spicy else [])

    def alive(self):
        return [i for i in range(len(self.pids)) if i not in self.out]

    def seat(self, pid):
        return self.pids.index(pid) if pid in self.pids else None

    def complete(self, active):
        voters = [i for i in self.alive() if self.pids[i] in active]
        if self.phase == "draw":
            return all(i in self.drawings for i in voters)
        if self.phase == "vote":
            return all(i in self.votes for i in voters)
        return False

    def tick(self, now, active):
        while not self.finished and (now >= self.deadline or self.complete(active)):
            self.advance(now)

    def advance(self, now):
        if self.phase == "draw":
            self.go("vote", now, self.vote_time)
        elif self.phase == "vote":
            self.resolve(now)
        elif self.phase == "reveal":
            if self.result["impostor"] and self.label == "knows":
                self.start_guess(now)
            else:
                self.continue_or_end(now)
        elif self.phase == "guess":
            self.guesser = None
            self.continue_or_end(now)
        else:
            self.finished = True

    def resolve(self, now):
        counts = self.tally()
        top = max(counts)
        leaders = [i for i, n in enumerate(counts) if n == top]
        out = leaders[0] if top and len(leaders) == 1 else None
        if out is not None:
            self.out.add(out)
            for voter, target in self.votes.items():
                if target in self.impostors:
                    self.points[self.pids[voter]] += CORRECT_VOTE
        self.result = {"out": out, "impostor": out in self.impostors}
        self.go("reveal", now, REVEAL_TIME)

    def tally(self):
        counts = [0] * len(self.pids)
        for target in self.votes.values():
            counts[target] += 1
        return counts

    def start_guess(self, now):
        self.guesser = self.result["out"]
        words = self.pool("words")
        same = [w for w, _, c in words if c == self.category and w != self.word]
        rest = [w for w, _, c in words if c != self.category]
        rng = self.ctx.rng
        picks = rng.sample(same, min(len(same), GUESS_OPTIONS - 1))
        picks += rng.sample(rest, min(len(rest), GUESS_OPTIONS - 1 - len(picks)))
        self.options = picks + [self.word]
        rng.shuffle(self.options)
        self.go("guess", now, GUESS_TIME)

    def continue_or_end(self, now):
        impostors = self.impostors - self.out
        crew = [i for i in self.alive() if i not in self.impostors]
        if not impostors:
            self.end("crew", now)
        elif len(impostors) >= len(crew) or self.round >= MAX_ROUNDS:
            self.end("impostors", now)
        else:
            self.next_round(now)

    def end(self, winner, now):
        self.winner = winner
        for i, pid in enumerate(self.pids):
            if winner == "crew" and i not in self.impostors:
                self.points[pid] += WIN_CREW
            elif winner == "impostors" and i in self.impostors:
                self.points[pid] += WIN_IMPOSTOR
        self.go("over", now, OVER_TIME)

    def act(self, pid, body, now, active):
        self.tick(now, active)
        i = self.seat(pid)
        kind = body.get("type")
        if kind not in ("draw", "vote", "guess"):
            raise GameError("Unknown action", 400)
        if self.phase != kind or i is None or i in self.out and kind != "guess":
            raise GameError("Not right now", 409)
        if kind == "draw":
            self.drawings[i] = picture(body.get("png"))
        elif kind == "vote":
            target = body.get("target")
            if type(target) is not int or target == i or target not in self.alive():
                raise GameError("Bad vote", 400)
            self.votes[i] = target
        else:
            if i != self.guesser:
                raise GameError("Not right now", 409)
            if body.get("word") not in self.options:
                raise GameError("Bad guess", 400)
            if body["word"] == self.word:
                self.guesser = None
                self.end("impostors", now)
            else:
                self.deadline = now
        self.tick(now, active)

    def hurry(self, now):
        if self.phase in WAITING:
            self.deadline = min(self.deadline, now + HURRY)
            self.hurried = True
        else:
            self.deadline = now

    def file(self, pid, name):
        m = re.fullmatch(r"d(\d+)-(\d+)\.png", name)
        if m and int(m.group(1)) == self.round:
            return self.drawings.get(int(m.group(2)))
        return None

    def common(self, now):
        return {"phase": self.phase, "round": self.round, "max_rounds": MAX_ROUNDS, "twist": self.twist,
                "left": None if self.finished else max(0, self.deadline - now), "hurry": self.hurried}

    def over(self):
        return {"winner": self.winner, "word": self.word, "decoy": self.decoy, "impostors": [self.names[i] for i in sorted(self.impostors)]}

    def host_view(self, now):
        view = self.common(now) | {"mode": self.label, "players": [
            {"seat": i, "name": n, "out": i in self.out, "drew": i in self.drawings, "voted": i in self.votes} for i, n in enumerate(self.names)]}
        if self.phase in ("vote", "reveal", "guess"):
            view["drawings"] = [{"seat": i, "file": "d%d-%d.png" % (self.round, i)} for i in sorted(self.drawings)]
            view["votes"] = self.tally()
        if self.phase in ("reveal", "guess"):
            view["result"] = self.result
        if self.phase == "over":
            view["over"] = self.over()
        return view

    def player_view(self, pid, now):
        i = self.seat(pid)
        if i in self.out and self.phase != "over" and i != self.guesser:
            return {"phase": self.phase, "round": self.round, "left": self.common(now)["left"], "out": True}
        view = self.common(now) | {"out": i in self.out, "drew": i in self.drawings, "voted": self.votes.get(i)}
        if self.label == "knows" and i in self.impostors:
            view |= {"impostor": True, "category": self.category, "team": [self.names[j] for j in sorted(self.impostors) if j != i]}
        else:
            view["word"] = self.decoy if i in self.impostors else self.word
        if self.phase == "vote":
            view["targets"] = [{"seat": j, "name": self.names[j]} for j in self.alive() if j != i]
        if self.phase == "guess" and i == self.guesser:
            view["options"] = self.options
        if self.phase == "over":
            view["over"] = self.over()
        return view

    def scores(self):
        return dict(self.points)
