import re
import unicodedata

from games.impostor.rules import Impostor, picture, seconds
from party.common import Context, GameError, GameMeta, GameOption, clean_line

PICK_TIME = 12
REVEAL_TIME = 6
HURRY = 10
CHOICES = 3
GUESS_MAX = 300
GUESS_MIN = 50
DRAWER_BONUS = 50
FEED = 8
GUESS_LIMIT = 40


def same(guess, word):
    fold = lambda s: re.sub(r"[\W_]", "", "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c)).casefold())
    return bool(fold(guess)) and fold(guess) == fold(word)


class Doodle:
    meta = GameMeta("doodle", {"ro": "Doodle", "en": "Doodle"}, 3, 16, "10-20",
                    blurb={"ro": "Unul deseneaza, ceilalti ghicesc. Cine ghiceste mai repede ia mai multe puncte.",
                           "en": "One draws, everyone else guesses. Faster guesses score more."},
                    options=(seconds("draw_time", {"ro": "Timp de desen", "en": "Draw time"}, (60, 80, 100), 80),
                             GameOption("laps", {"ro": "Desene de fiecare", "en": "Drawings each"},
                                        tuple((n, {"ro": str(n), "en": str(n)}) for n in (1, 2)), 1)),
                    upload_max=Impostor.meta.upload_max)
    packs = Impostor.packs

    def __init__(self, ctx: Context):
        self.ctx = ctx
        options = {o.key: o.default for o in self.meta.options} | ctx.settings.options
        self.draw_time = options["draw_time"]
        self.pids = [s.pid for s in ctx.seats]
        self.names = [s.name for s in ctx.seats]
        self.order = [i for _ in range(options["laps"]) for i in ctx.rng.sample(range(len(self.pids)), len(self.pids))]
        self.points = dict.fromkeys(self.pids, 0)
        self.here = set(range(len(self.pids)))
        self.tag = "%08x" % ctx.rng.getrandbits(32)
        self.used: set[str] = set()
        self.words: list[str] = []
        self.finished = False
        self.turn = -1
        self.next_turn(ctx.now)

    def pool(self):
        modes = self.ctx.deck.packs[self.ctx.settings.lang]
        entries = modes["family"]["words"] + (modes["spicy"]["words"] if self.ctx.settings.spicy else [])
        return list(dict.fromkeys(w for e in entries for w in e[:2]))

    def go(self, phase, now, seconds):
        self.phase, self.deadline, self.started, self.hurried = phase, now + seconds, now, False

    def next_turn(self, now):
        self.turn += 1
        if self.turn >= len(self.order):
            self.finished = True
            return
        self.drawer = self.order[self.turn]
        pool = self.pool()
        fresh = [w for w in pool if w not in self.used]
        rng = self.ctx.rng
        self.choices = rng.sample(fresh, min(CHOICES, len(fresh)))
        self.choices += rng.sample([w for w in pool if w not in self.choices], CHOICES - len(self.choices))
        self.used.update(self.choices)
        self.word = None
        self.png, self.version = None, 0
        self.guessed: dict[int, int] = {}
        self.feed: list[dict] = []
        self.go("pick", now, PICK_TIME)

    def start_drawing(self, word, now):
        self.word = word
        self.words.append(word)
        self.go("draw", now, self.draw_time)

    def tick(self, now, active):
        self.here = {i for i, p in enumerate(self.pids) if p in active}
        while not self.finished:
            if self.phase in ("pick", "draw") and self.drawer not in self.here and self.here:
                self.next_turn(now)
            elif self.phase == "draw" and self.here - {self.drawer} and self.here - {self.drawer} <= set(self.guessed):
                self.go("reveal", now, REVEAL_TIME)
            elif now >= self.deadline:
                self.advance(now)
            else:
                break

    def advance(self, now):
        if self.phase == "pick":
            self.start_drawing(self.choices[0], now)
        elif self.phase == "draw":
            self.go("reveal", now, REVEAL_TIME)
        else:
            self.next_turn(now)

    def act(self, pid, body, now, active):
        self.tick(now, active)
        i = self.pids.index(pid) if pid in self.pids else None
        kind = body.get("type")
        if kind not in ("pick", "draw", "guess"):
            raise GameError("Unknown action", 400)
        drawer = i == self.drawer
        if self.finished or self.phase != ("pick" if kind == "pick" else "draw") or drawer != (kind != "guess") or i in self.guessed:
            raise GameError("Not right now", 409)
        if kind == "pick":
            choice = body.get("choice")
            if type(choice) is not int or not 0 <= choice < len(self.choices):
                raise GameError("Bad choice", 400)
            self.start_drawing(self.choices[choice], now)
        elif kind == "draw":
            self.png = picture(body.get("png"))
            self.version += 1
        else:
            text = clean_line(body.get("text"), GUESS_LIMIT)
            if not text:
                raise GameError("Type a guess", 400)
            if same(text, self.word):
                self.guessed[i] = max(GUESS_MIN, round(GUESS_MAX * (self.deadline - now) / self.draw_time))
                self.points[pid] += self.guessed[i]
                self.points[self.pids[self.drawer]] += DRAWER_BONUS
            else:
                self.feed = (self.feed + [{"name": self.names[i], "text": text}])[-FEED:]
        self.tick(now, active)

    def hurry(self, now):
        if self.phase == "draw":
            self.deadline = min(self.deadline, now + HURRY)
            self.hurried = True
        else:
            self.deadline = now

    def file(self, pid, name):
        m = re.fullmatch(r"s([0-9a-f]{8})-(\d+)-\d+\.png", name)
        return self.png if m and m.group(1) == self.tag and int(m.group(2)) == self.turn else None

    def file_name(self):
        return "s%s-%d-%d.png" % (self.tag, self.turn, self.version)

    def hint(self):
        return re.sub(r"\w", "_", self.word)

    def common(self, now):
        view = {"phase": self.phase, "turn": self.turn + 1, "turns": len(self.order), "drawer": self.names[self.drawer],
                "left": None if self.finished else max(0, self.deadline - now), "hurry": self.hurried,
                "feed": self.feed, "guessed": [self.names[i] for i in self.guessed]}
        if self.png and self.phase in ("draw", "reveal"):
            view["file"] = self.file_name()
        if self.phase == "draw":
            view["hint"] = self.hint()
        if self.phase == "reveal":
            view |= {"word": self.word, "gains": [{"name": self.names[i], "points": p} for i, p in self.guessed.items()]}
        return view

    def host_view(self, now):
        return self.common(now) | {"players": [{"name": n, "drawer": i == self.drawer, "guessed": i in self.guessed, "away": i not in self.here}
                                               for i, n in enumerate(self.names)]}

    def player_view(self, pid, now):
        i = self.pids.index(pid) if pid in self.pids else None
        view = self.common(now) | {"drawing": i == self.drawer, "got": i in self.guessed, "gain": self.guessed.get(i)}
        if i == self.drawer and self.phase == "pick":
            view["choices"] = self.choices
        if self.word and (i == self.drawer or i in self.guessed):
            view["word"] = self.word
        return view

    def scores(self):
        return dict(self.points)
