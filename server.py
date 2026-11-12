import hashlib
import ipaddress
import json
import os
import random
import re
import secrets
import socket
import sys
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from games import GAMES
from party.common import GameError
from party.room import Room

clock = time.time
ROOT = Path(__file__).resolve().parent
STATIC = ROOT / "static"
GAMES_DIR = ROOT / "games"
CODE_CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ23456789"
CODE_LEN = 6
BODY_MAX = 2048
MAX_CONNECTIONS = 64
REQUEST_DEADLINE = 20
MAX_ROOMS = 300
CREATE_LIMIT, CREATE_WINDOW = 5, 600
OPEN_PER_CLIENT, OPEN_PER_48 = 2, 10
MISS_LIMIT, MISS_LIMIT_48, MISS_WINDOW = 20, 100, 600
STATIC_ASSETS = ("app.js", "i18n.js", "sound.js", "draw.js", "poll.js", "style.css", "qrcode.js", "favicon.svg")
GAME_ASSETS = ("view.js", "view.css", "icon.svg")
TYPES = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8",
         ".svg": "image/svg+xml", ".woff2": "font/woff2", ".png": "image/png", ".json": "application/json"}
CSP = ("default-src 'self'; img-src 'self' data: blob:; style-src 'self'; script-src 'self'; font-src 'self'; "
       "connect-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'")
NO_STORE = {"Cache-Control": "no-store"}
CLOSED = "This room is closed"


def labels(game_id: str, mode: str = "") -> str:
    return '{game="%s",mode="%s"}' % (game_id, mode) if mode else '{game="%s"}' % game_id


class App:
    def __init__(self, games: dict):
        self.games = games
        self.rooms: dict[str, Room] = {}
        self.meta: dict[str, dict] = {}
        self.created: dict[str, list[float]] = {}
        self.misses: dict[str, list[float]] = {}
        self.lock = threading.Lock()
        self.swept = float("-inf")
        self.counts = dict.fromkeys(("visits", "parties", "players"), 0)
        self.started: dict[str, int] = {}
        self.finished: dict[str, int] = {}
        self.action_max = max([BODY_MAX] + [g.meta.upload_max for g in games.values()])

    def visit(self) -> None:
        with self.lock:
            self.counts["visits"] += 1

    def record(self, room: Room) -> None:
        for kind, game_id, label in room.drain_events():
            log = self.started if kind == "started" else self.finished
            key = labels(game_id, label)
            log[key] = log.get(key, 0) + 1
        if room.phase == "closed":
            self.rooms.pop(room.code, None)
            self.meta.pop(room.code, None)

    def janitor(self, now: float) -> None:
        if 0 <= now - self.swept < 1:
            return
        self.swept = now
        for room in list(self.rooms.values()):
            room.tick(now)
            self.record(room)
        for log, window in ((self.created, CREATE_WINDOW), (self.misses, MISS_WINDOW)):
            for k in [k for k, ts in log.items() if not ts or now - ts[-1] >= window]:
                del log[k]

    def room(self, code: str, now: float, pid: str) -> Room:
        self.janitor(now)
        room = self.rooms.get(code.strip().upper())
        if room is None or not room.is_member(pid):
            raise GameError(CLOSED, 404)
        return room

    def room_to_join(self, code: str, client: str, now: float, wide: str | None = None) -> Room:
        self.janitor(now)
        caps = {k: n for k, n in ((client, MISS_LIMIT), (wide, MISS_LIMIT_48)) if k}
        misses = {k: [t for t in self.misses.get(k, []) if now - t < MISS_WINDOW] for k in caps}
        if any(len(misses[k]) >= n for k, n in caps.items()):
            raise GameError("Too many wrong room codes, try again in a few minutes", 429)
        room = self.rooms.get(code.strip().upper())
        if room is None:
            for k, ts in misses.items():
                self.misses[k] = ts + [now]
            raise GameError(CLOSED, 404)
        return room

    def create(self, client: str, now: float, wide: str | None = None) -> dict:
        self.janitor(now)
        recent = [t for t in self.created.get(client, []) if now - t < CREATE_WINDOW]
        if len(recent) >= CREATE_LIMIT or \
                sum(m["owner"] == client for m in self.meta.values()) >= OPEN_PER_CLIENT or \
                wide and sum(m["wide"] == wide for m in self.meta.values()) >= OPEN_PER_48:
            raise GameError("Too many new parties, try again in a few minutes", 429)
        if len(self.rooms) >= MAX_ROOMS:
            raise GameError("Too many parties open right now, try again later", 503)
        code = "".join(secrets.choice(CODE_CHARS) for _ in range(CODE_LEN))
        while code in self.rooms:
            code = "".join(secrets.choice(CODE_CHARS) for _ in range(CODE_LEN))
        room = Room(code, now, self.games, random.Random(secrets.randbits(64)))
        self.created[client] = recent + [now]
        self.rooms[code] = room
        self.meta[code] = {"owner": client, "wide": wide}
        self.counts["parties"] += 1
        return {"code": code, "pid": room.host}

    def join(self, room: Room, name, now: float) -> dict:
        before = len(room.players)
        player = room.join(name, now)
        self.counts["players"] += len(room.players) > before
        return {"code": room.code, "pid": player.id}

    def metrics(self, now: float) -> str:
        with self.lock:
            c = dict(self.counts)
            started, finished = dict(self.started), dict(self.finished)
            open_rooms = len(self.rooms)
            online = sum(len(r.active(now)) for r in self.rooms.values())
        lines = [
            ("visits_total", "counter", "Page loads via Cloudflare", [("", c["visits"])]),
            ("parties_created_total", "counter", "Parties created", [("", c["parties"])]),
            ("players_joined_total", "counter", "Players who joined a party", [("", c["players"])]),
            ("games_started_total", "counter", "Games started", list(started.items())),
            ("games_finished_total", "counter", "Games played to the end", list(finished.items())),
            ("parties_open", "gauge", "Parties open right now", [("", open_rooms)]),
            ("players_online", "gauge", "Players active in the last minute", [("", online)]),
        ]
        out = []
        for name, kind, help_text, samples in lines:
            out += ["# HELP galagie_%s %s" % (name, help_text), "# TYPE galagie_%s %s" % (name, kind)]
            out += ["galagie_%s%s %d" % (name, labels, value) for labels, value in samples]
        return "\n".join(out) + "\n"


class Handler(BaseHTTPRequestHandler):
    server_version = "partygames"
    sys_version = ""
    timeout = 15
    app: App

    def log_message(self, *a):
        pass

    def _send(self, status: int, body: bytes, ctype: str, extra: dict | None = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", CSP)
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, status: int, data) -> None:
        self._send(status, json.dumps(data).encode(), "application/json", NO_STORE)

    def _body(self, limit: int = BODY_MAX) -> dict:
        if not (self.headers.get("Content-Type") or "").startswith("application/json"):
            raise GameError("Send JSON", 415)
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            raise GameError("Bad request", 400)
        if n < 0:
            raise GameError("Bad request", 400)
        if n > limit:
            raise GameError("Request too big", 413)
        try:
            raw = self.rfile.read(n)
            if raw.count(b"[") + raw.count(b"{") > 64:
                raise ValueError
            data = json.loads(raw or b"{}")
        except ValueError:
            raise GameError("Bad request", 400)
        if not isinstance(data, dict):
            raise GameError("Bad request", 400)
        return data

    def _client(self) -> tuple[str, str | None]:
        try:
            ip = ipaddress.ip_address((self.headers.get("CF-Connecting-IP") or "").strip())
        except ValueError:
            ip = ipaddress.ip_address(self.client_address[0])
        if ip.version == 4:
            return str(ip), None
        return str(ipaddress.ip_network("%s/64" % ip, strict=False)), str(ipaddress.ip_network("%s/48" % ip, strict=False))

    def _api(self, method: str) -> None:
        app, now = self.app, clock()
        path = urllib.parse.unquote(urllib.parse.urlsplit(self.path).path)
        pid = self.headers.get("X-Player", "")
        try:
            body = self._body(app.action_max if path.endswith("/action") else BODY_MAX) if method == "POST" else {}
            client, wide = self._client()
            with app.lock:
                if method == "POST" and path == "/api/rooms":
                    out = app.create(client, now, wide)
                else:
                    m = re.fullmatch(r"/api/rooms/([^/]+)(/join|/screen|/action|/files/[a-z0-9-]{1,40}\.png)?", path)
                    if not m:
                        raise GameError("Not found", 404)
                    route = m.group(2)
                    if route in ("/join", "/screen"):
                        room = app.room_to_join(m.group(1), client, now, wide)
                    else:
                        room = app.room(m.group(1), now, pid)
                    if method == "POST" and route == "/join":
                        out = app.join(room, body.get("name"), now)
                    elif method == "POST" and route == "/screen":
                        out = {"code": room.code, "pid": room.request_screen(now, client)}
                    elif method == "POST" and route == "/action":
                        room.action(pid, body, now)
                        out = {"ok": True}
                    elif method == "GET" and route and route.startswith("/files/"):
                        data = getattr(room.game, "file", lambda *_: None)(pid, route[7:])
                        if data is None:
                            raise GameError("Not found", 404)
                        app.record(room)
                        out = data
                    elif method == "GET" and route is None:
                        room.seen(pid, now)
                        room.tick(now)
                        room.check_open()
                        out = room.view_for(pid, now)
                    else:
                        raise GameError("Not found", 404)
                    app.record(room)
                if isinstance(out, bytes):
                    payload, kind, extra = out, "image/png", {"Cache-Control": "private, max-age=300"}
                else:
                    payload, kind, extra = json.dumps(out).encode(), "application/json", NO_STORE
            self._send(200, payload, kind, extra)
        except GameError as e:
            self._json(e.status, {"error": str(e)})
        except Exception as e:
            sys.stderr.write("error %s %r: %r\n" % (method, path, e))
            self._json(500, {"error": "Something went wrong"})

    def _static(self) -> None:
        parts = urllib.parse.urlsplit(self.path)
        path = urllib.parse.unquote(parts.path)
        if path in ("/", "/tv") or re.fullmatch(r"/r/[A-Za-z2-9]{6}", path):
            if self.command == "GET" and self.headers.get("CF-Connecting-IP"):
                self.app.visit()
            return self._send(200, index_page(self.app.games), TYPES[".html"], NO_STORE)
        f = None
        game = re.fullmatch(r"/games/([^/]+)/([^/]+)", path)
        if path.startswith("/static/"):
            f = (STATIC / path[len("/static/"):]).resolve()
            if STATIC not in f.parents:
                f = None
        elif game and game.group(1) in self.app.games and game.group(2) in GAME_ASSETS:
            f = GAMES_DIR / game.group(1) / game.group(2)
        if f is None or not f.is_file():
            return self._send(404, b"Not found", "text/plain; charset=utf-8")
        versioned = "v=" in parts.query
        self._send(200, f.read_bytes(), TYPES.get(f.suffix, "application/octet-stream"),
                   {"Cache-Control": "public, max-age=31536000, immutable" if versioned else "no-cache"})

    def do_GET(self):
        if self.path.startswith("/api/"):
            self._api("GET")
        else:
            self._static()

    do_HEAD = do_GET

    def do_POST(self):
        if self.path.startswith("/api/"):
            self._api("POST")
        else:
            self._send(404, b"Not found", "text/plain; charset=utf-8")


def _version(f: Path) -> str:
    return hashlib.sha256(f.read_bytes()).hexdigest()[:10]


def index_page(games: dict) -> bytes:
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    for name in STATIC_ASSETS:
        html = html.replace('"/static/%s"' % name, '"/static/%s?v=%s"' % (name, _version(STATIC / name)))
    links = "".join('<link rel="stylesheet" href="/games/%s/view.css?v=%s">\n' % (g, _version(GAMES_DIR / g / "view.css")) for g in games)
    scripts = "".join('<script src="/games/%s/view.js?v=%s"></script>\n' % (g, _version(GAMES_DIR / g / "view.js")) for g in games)
    return html.replace("</head>", links + "</head>", 1).replace("</body>", scripts + "</body>", 1).encode()


class MetricsHandler(BaseHTTPRequestHandler):
    server_version = "partygames"
    sys_version = ""
    timeout = 15
    app: App

    def log_message(self, *a):
        pass

    def do_GET(self):
        if self.path != "/metrics":
            self.send_error(404)
            return
        body = self.app.metrics(clock()).encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; version=0.0.4")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class Server(ThreadingHTTPServer):
    def __init__(self, address, handler):
        super().__init__(address, handler)
        self.slots = threading.BoundedSemaphore(MAX_CONNECTIONS)
        self.born: dict[socket.socket, float] = {}
        self.closed = threading.Event()
        threading.Thread(target=self.reap, daemon=True).start()

    def process_request(self, request, client_address):
        if not self.slots.acquire(blocking=False):
            return self.shutdown_request(request)
        self.born[request] = time.monotonic()
        try:
            super().process_request(request, client_address)
        except BaseException:
            self.done(request)
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self.done(request)

    def done(self, request):
        self.born.pop(request, None)
        self.slots.release()

    def reap(self):
        while not self.closed.wait(REQUEST_DEADLINE / 4):
            cutoff = time.monotonic() - REQUEST_DEADLINE
            for request, born in self.born.copy().items():
                if born < cutoff:
                    try:
                        request.shutdown(socket.SHUT_RDWR)
                    except OSError:
                        pass

    def handle_error(self, request, client_address):
        if not isinstance(sys.exc_info()[1], OSError):
            super().handle_error(request, client_address)

    def server_close(self):
        self.closed.set()
        super().server_close()


def make_metrics_server(host: str, port: int, app: App) -> Server:
    return Server((host, port), type("BoundMetrics", (MetricsHandler,), {"app": app}))


def make_server(host: str, port: int, games: dict) -> Server:
    return Server((host, port), type("BoundHandler", (Handler,), {"app": App(games)}))


def main() -> None:
    port = int(os.environ.get("PORT", "8000"))
    metrics_port = int(os.environ.get("METRICS_PORT", "8001"))
    print("partygames on :%d" % port, flush=True)
    srv = make_server("0.0.0.0", port, GAMES)
    threading.Thread(target=make_metrics_server("0.0.0.0", metrics_port, srv.RequestHandlerClass.app).serve_forever,
                     daemon=True).start()
    srv.serve_forever()


if __name__ == "__main__":
    main()
