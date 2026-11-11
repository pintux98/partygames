import random
import secrets
from collections import deque
from dataclasses import dataclass

from party.common import Context, Game, GameError, Seat, Settings, clean_line
from party.deck import Deck

MAX_PLAYERS = 16
AWAY = 60
IDLE_CLOSE = 900
EMPTY_CLOSE = 300
SCREEN_TTL = 120
MAX_SCREEN_REQUESTS = 3
NAME_MAX = 20
LANGS = ("ro", "en")
CONTROLLER_ACTIONS = ("settings", "start", "next", "end", "again")


@dataclass
class Player:
    id: str
    name: str
    joined: float
    seen: float
    waiting: bool = False

    def here(self, now: float) -> bool:
        return now - self.seen <= AWAY


class Room:
    def __init__(self, code: str, now: float, games: dict[str, type[Game]], rng: random.Random):
        self.code = code
        self.games = games
        self.rng = rng
        self.host = secrets.token_urlsafe(16)
        self.phase = "lobby"
        self.players: dict[str, Player] = {}
        self.vip: str | None = None
        self.game_id = next(iter(games))
        self.settings = Settings(options=self.defaults(self.game_id))
        self.game: Game | None = None
        self.seats: list[Seat] = []
        self.last_scores: dict[str, int] = {}
        self.used: set[str] = set()
        self.screen_requests: dict[str, tuple[float, str, str]] = {}
        self.moved: deque[str] = deque(maxlen=4)
        self.last_action = now
        self.events: list[tuple[str, str]] = []

    def defaults(self, game_id: str) -> dict:
        return {o.key: o.default for o in self.games[game_id].meta.options}

    def check_open(self):
        if self.phase == "closed":
            raise GameError("This room is closed", 404)

    def join(self, name, now: float) -> Player:
        self.check_open()
        self.last_action = now
        name = clean_line(name, NAME_MAX)
        if not name:
            raise GameError("Pick a nickname", 400)
        if any(p.name.casefold() == name.casefold() for p in self.players.values()):
            raise GameError("That name is taken", 409)
        if len(self.players) >= MAX_PLAYERS:
            raise GameError("Room is full", 409)
        player = Player(secrets.token_urlsafe(16), name, now, now, self.phase == "playing")
        self.players[player.id] = player
        if self.vip is None:
            self.vip = player.id
        return player

    def request_screen(self, now: float, client: str) -> str:
        self.check_open()
        self.last_action = now
        self.prune_screens(now)
        if len(self.screen_requests) >= MAX_SCREEN_REQUESTS or any(r[1] == client for r in self.screen_requests.values()):
            raise GameError("Too many screen requests", 429)
        sid = secrets.token_urlsafe(16)
        self.screen_requests[sid] = (now, client, secrets.token_urlsafe(8))
        return sid

    def prune_screens(self, now: float):
        self.screen_requests = {sid: r for sid, r in self.screen_requests.items() if now - r[0] <= SCREEN_TTL}

    def is_member(self, pid: str) -> bool:
        return pid == self.host or pid in self.players or pid in self.screen_requests or pid in self.moved

    def seen(self, pid: str, now: float) -> None:
        if pid in self.players:
            self.players[pid].seen = now

    def active(self, now: float) -> set[str]:
        return {pid for pid, p in self.players.items() if not p.waiting and p.here(now)}

    def seated(self, pid: str) -> bool:
        return any(seat.pid == pid for seat in self.seats)

    def action(self, pid: str, body: dict, now: float) -> None:
        self.check_open()
        self.last_action = now
        kind = body.get("type")
        if kind in CONTROLLER_ACTIONS and pid not in (self.host, self.vip):
            raise GameError("Only the VIP can do that", 403)
        if kind == "settings":
            self.change_settings(body)
        elif kind == "start":
            self.start(now)
        elif kind == "next":
            self.need("playing")
            self.game.hurry(now)
        elif kind == "end":
            if self.phase == "playing":
                self.phase = "results"
                self.last_scores = self.game.scores()
            else:
                self.phase = "closed"
        elif kind == "again":
            self.need("results")
            self.players = {pid: p for pid, p in self.players.items() if p.here(now)}
            for player in self.players.values():
                player.waiting = False
            self.game = None
            self.phase = "lobby"
        elif kind in ("allow_screen", "deny_screen"):
            if pid != self.vip:
                raise GameError("Only the VIP can do that", 403)
            sid = next((s for s, r in self.screen_requests.items() if r[2] == body.get("handle")), None)
            if sid is None:
                raise GameError("That screen request expired", 404)
            del self.screen_requests[sid]
            if kind == "allow_screen":
                self.moved.append(self.host)
                self.host = sid
        elif self.phase == "playing" and self.seated(pid):
            self.game.act(pid, body, now, self.active(now))
        else:
            raise GameError("Unknown action", 400)
        self.tick(now)

    def need(self, phase: str):
        if self.phase != phase:
            raise GameError("Not right now", 409)

    def change_settings(self, body: dict):
        self.need("lobby")
        lang = body.get("lang", self.settings.lang)
        game_id = body.get("game", self.game_id)
        spicy = body.get("spicy", self.settings.spicy)
        if lang not in LANGS:
            raise GameError("Unknown language", 400)
        if not isinstance(spicy, bool):
            raise GameError("Bad spicy setting", 400)
        if not isinstance(game_id, str) or game_id not in self.games:
            raise GameError("Unknown game", 400)
        options = self.defaults(game_id) if game_id != self.game_id else dict(self.settings.options)
        changes = body.get("option", {})
        if not isinstance(changes, dict):
            raise GameError("Bad option", 400)
        allowed = {o.key: [v for v, _ in o.choices] for o in self.games[game_id].meta.options}
        for key, value in changes.items():
            if key not in allowed:
                raise GameError("Unknown option", 400)
            if not any(type(value) is type(v) and value == v for v in allowed[key]):
                raise GameError("Bad option", 400)
            options[key] = value
        self.settings.lang = lang
        self.settings.spicy = spicy
        self.game_id = game_id
        self.settings.options = options

    def start(self, now: float):
        self.need("lobby")
        game_cls = self.games[self.game_id]
        active = self.active(now)
        seats = [Seat(pid, p.name) for pid, p in self.players.items() if pid in active]
        if len(seats) < game_cls.meta.min_players:
            raise GameError(f"Need at least {game_cls.meta.min_players} players", 409)
        if len(seats) > game_cls.meta.max_players:
            raise GameError(f"At most {game_cls.meta.max_players} players", 409)
        for pid, p in self.players.items():
            p.waiting = pid not in active
        deck = Deck(game_cls.packs, self.settings, self.rng, self.used)
        self.game = game_cls(Context(seats, self.settings, self.rng, deck, now))
        self.seats = seats
        self.phase = "playing"
        self.events.append(("started", self.game_id))

    def tick(self, now: float) -> None:
        if self.phase == "closed":
            return
        active = self.active(now)
        if self.phase == "playing":
            self.game.tick(now, active)
            if self.game.finished:
                self.phase = "results"
                self.last_scores = self.game.scores()
                self.events.append(("finished", self.game_id))
        if self.vip not in active:
            fallback = self.vip if self.vip in self.players else None
            self.vip = next((pid for pid in self.players if pid in active), fallback)
        self.prune_screens(now)
        if now - self.last_action > (IDLE_CLOSE if self.players else EMPTY_CLOSE):
            self.phase = "closed"

    def view_for(self, pid: str, now: float) -> dict:
        if pid == self.host:
            role = "host"
        elif pid in self.players:
            role = "player"
        elif pid in self.screen_requests:
            role = "screen_pending"
        elif pid in self.moved:
            role = "moved"
        else:
            raise GameError("Room not found", 404)
        me = self.players.get(pid)
        game = None
        if self.game and role == "host":
            game = self.game.host_view(now)
        elif self.game and role == "player" and self.seated(pid):
            game = self.game.player_view(pid, now)
        scores = []
        if self.phase == "results":
            scores = sorted(({"name": s.name, "points": self.last_scores.get(s.pid, 0)} for s in self.seats), key=lambda row: -row["points"])
        return {
            "code": self.code,
            "phase": self.phase,
            "role": role,
            "me": me.name if me else None,
            "vip": pid == self.vip,
            "controller": pid in (self.host, self.vip),
            "game_id": self.game_id,
            "games": [{"id": gid, "names": g.meta.names, "blurb": g.meta.blurb, "min": g.meta.min_players, "max": g.meta.max_players, "minutes": g.meta.minutes} for gid, g in self.games.items()],
            "options": [{"key": o.key, "names": o.names, "value": self.settings.options.get(o.key, o.default),
                         "choices": [{"value": v, "names": n} for v, n in o.choices]} for o in self.games[self.game_id].meta.options],
            "settings": {"lang": self.settings.lang, "spicy": self.settings.spicy},
            "players": [{"name": p.name, "vip": p.id == self.vip, "away": not p.here(now), "waiting": p.waiting} for p in self.players.values()],
            "screen_requests": [r[2] for r in self.screen_requests.values()] if pid == self.vip else [],
            "scores": scores,
            "game": game,
        }

    def drain_events(self) -> list[tuple[str, str]]:
        events, self.events = self.events, []
        return events
