import http.client
import json
import socket
import threading
import time
import unittest

import server
from games import GAMES

CSP = ("default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; font-src 'self'; "
       "connect-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'")


class Api(unittest.TestCase):
    def setUp(self):
        server.clock = time.time
        self.srv = server.make_server("127.0.0.1", 0, GAMES)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.port = self.srv.server_address[1]
        self.app = self.srv.RequestHandlerClass.app

    def tearDown(self):
        self.srv.shutdown()
        self.srv.server_close()
        server.clock = time.time

    def raw(self, method, path, port=None, headers=None, body=None):
        c = http.client.HTTPConnection("127.0.0.1", port or self.port, timeout=5)
        c.request(method, path, body=body, headers=headers or {})
        r = c.getresponse()
        data = r.read()
        c.close()
        return r, data

    def call(self, method, path, body=None, pid=None, ip="9.9.9.9", raw=None):
        headers = {"CF-Connecting-IP": ip, "Content-Type": "application/json"}
        if pid:
            headers["X-Player"] = pid
        data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
        r, text = self.raw(method, path, headers=headers, body=data)
        try:
            return r.status, json.loads(text)
        except ValueError:
            return r.status, text.decode("utf-8", "replace")

    def create(self, ip="9.9.9.9"):
        s, d = self.call("POST", "/api/rooms", {}, ip=ip)
        self.assertEqual(s, 200, d)
        return d["code"], d["pid"]

    def join(self, code, name, ip="9.9.9.9"):
        return self.call("POST", "/api/rooms/%s/join" % code, {"name": name}, ip=ip)

    def party(self, n=3):
        code, host = self.create()
        pids = []
        for i in range(n):
            s, d = self.join(code, "P%d" % i)
            self.assertEqual(s, 200, d)
            pids.append(d["pid"])
        return code, host, pids

    def act(self, code, pid, **body):
        return self.call("POST", "/api/rooms/%s/action" % code, body, pid=pid)

    def state(self, code, pid):
        return self.call("GET", "/api/rooms/" + code, pid=pid)

    def answer_all(self, code, pids):
        for p in pids:
            for prompt in self.state(code, p)[1]["game"]["prompts"]:
                self.assertEqual(self.act(code, p, type="answer", i=prompt["i"], text="hi " + p[:4])[0], 200)

    def hurry_until(self, code, host, pids, t, done):
        for _ in range(60):
            d = self.state(code, host)[1]
            if done(d):
                return d
            self.assertEqual(self.act(code, pids[0], type="next")[0], 200)
            t[0] += 11
            for p in pids:
                self.state(code, p)
        self.fail("never got there: %r" % d)

    def test_full_flow_three_players(self):
        t = [1000.0]
        server.clock = lambda: t[0]
        code, host, pids = self.party()
        self.assertEqual(self.state(code, host)[1]["role"], "host")
        self.assertEqual(self.act(code, pids[0], type="start")[0], 200)
        self.answer_all(code, pids)
        self.assertEqual(self.state(code, host)[1]["game"]["phase"], "vote")
        self.hurry_until(code, host, pids, t, lambda d: d["game"]["phase"] == "final_answer")
        self.answer_all(code, pids)
        d = self.hurry_until(code, host, pids, t, lambda d: d["phase"] == "results")
        self.assertEqual(len(d["scores"]), 3)
        self.assertEqual(self.act(code, pids[0], type="end")[0], 200)
        self.assertEqual(self.state(code, pids[0]), (404, {"error": "This room is closed"}))
        self.assertIn('galagie_games_finished_total{game="faceoff"} 1\n', self.app.metrics(t[0]))

    def test_non_member_404_same_as_unknown(self):
        code, host = self.create()
        wrong = self.state(code, "nobody")
        self.assertEqual(wrong, (404, {"error": "This room is closed"}))
        self.assertEqual(self.state("ZZZZZZ", host), wrong)
        self.assertEqual(self.act(code, "nobody", type="start"), wrong)

    def test_rate_limit_parties(self):
        for _ in range(5):
            code, host = self.create(ip="1.1.1.1")
            self.assertEqual(self.act(code, host, type="end")[0], 200)
        self.assertEqual(self.call("POST", "/api/rooms", {}, ip="1.1.1.1")[0], 429)
        self.create(ip="2.2.2.2")
        self.create(ip="2.2.2.2")
        self.assertEqual(self.call("POST", "/api/rooms", {}, ip="2.2.2.2")[0], 429)
        self.create(ip="2001:db8:0:1::1")
        self.create(ip="2001:db8:0:1::2")
        self.assertEqual(self.call("POST", "/api/rooms", {}, ip="2001:db8:0:1::3")[0], 429)

    def test_ipv6_48_open_rooms_capped(self):
        for n in range(5):
            self.create(ip="2001:db8:1:%d::1" % n)
            self.create(ip="2001:db8:1:%d::2" % n)
        self.assertEqual(self.call("POST", "/api/rooms", {}, ip="2001:db8:1:5::1")[0], 429)
        self.create(ip="2001:db8:2::1")

    def test_ipv6_48_wrong_codes_capped(self):
        code, _ = self.create()
        for n in range(5):
            for _ in range(20):
                self.assertEqual(self.join("ZZZZZZ", "g", ip="2001:db8:1:%d::1" % n)[0], 404)
        self.assertEqual(self.join(code, "g", ip="2001:db8:1:5::1")[0], 429)
        self.assertEqual(self.join(code, "g", ip="2001:db8:2::1")[0], 200)

    def test_one_pending_screen_per_client(self):
        code, _ = self.create()
        screen = "/api/rooms/%s/screen" % code
        self.assertEqual(self.call("POST", screen, {}, ip="5.5.5.5")[0], 200)
        self.assertEqual(self.call("POST", screen, {}, ip="5.5.5.5")[0], 429)
        self.assertEqual(self.call("POST", screen, {}, ip="5.5.5.6")[0], 200)

    def test_bad_cf_header_uses_peer(self):
        self.create(ip="garbage1")
        self.create(ip="garbage2")
        self.assertEqual(self.call("POST", "/api/rooms", {}, ip="garbage3")[0], 429)

    def test_wrong_code_limit(self):
        code, host = self.create(ip="7.7.7.7")
        for i in range(10):
            self.assertEqual(self.join("ZZZZZ" + "ABCDEFGHJK"[i], "g", ip="6.6.6.6")[0], 404)
            self.assertEqual(self.call("POST", "/api/rooms/YYYYY%s/screen" % "ABCDEFGHJK"[i], {}, ip="6.6.6.6")[0], 404)
        self.assertEqual(self.join(code, "g", ip="6.6.6.6")[0], 429)
        self.assertEqual(self.call("POST", "/api/rooms/%s/screen" % code, {}, ip="6.6.6.6")[0], 429)
        self.assertEqual(self.join(code, "ok", ip="8.8.8.8")[0], 200)
        s, d = self.call("POST", "/api/rooms/%s/screen" % code, {}, ip="8.8.8.8")
        self.assertEqual(s, 200)
        self.assertEqual(self.state(code, d["pid"])[1]["role"], "screen_pending")

    def test_json_only_415(self):
        r, _ = self.raw("POST", "/api/rooms", headers={"Content-Type": "text/plain"}, body=b"{}")
        self.assertEqual(r.status, 415)

    def test_body_too_big_413(self):
        self.assertEqual(self.call("POST", "/api/rooms", raw=b"x" * 5000)[0], 413)

    def test_bad_content_length_400(self):
        for cl in ("-1", "abc"):
            c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
            c.putrequest("POST", "/api/rooms")
            c.putheader("Content-Type", "application/json")
            c.putheader("Content-Length", cl)
            c.endheaders()
            c.send(b"{}")
            self.assertEqual(c.getresponse().status, 400, cl)
            c.close()
        self.assertEqual(self.call("POST", "/api/rooms", raw=b"{nope")[0], 400)
        self.assertEqual(self.call("POST", "/api/rooms", raw=b"[]")[0], 400)

    def test_index_injects_games_versioned(self):
        for path in ("/r/K7XQ2P", "/r/k7xq2p", "/tv"):
            self.assertEqual(self.raw("GET", path)[0].status, 200, path)
        r, body = self.raw("GET", "/")
        html = body.decode()
        self.assertEqual(r.getheader("Cache-Control"), "no-store")
        self.assertEqual(r.getheader("Content-Security-Policy"), CSP)
        self.assertRegex(html, r'"/static/app\.js\?v=[0-9a-f]{10}"')
        self.assertRegex(html, r'"/static/style\.css\?v=[0-9a-f]{10}"')
        self.assertLess(html.index('<link rel="stylesheet" href="/games/faceoff/view.css?v='), html.index("</head>"))
        self.assertLess(html.index("</head>"), html.index('<script src="/games/faceoff/view.js?v='))
        self.assertLess(html.index("/games/faceoff/view.js?v="), html.index("</body>"))

    def test_game_assets_whitelisted(self):
        r, _ = self.raw("GET", "/games/faceoff/view.js?v=1")
        self.assertEqual(r.status, 200)
        self.assertIn("immutable", r.getheader("Cache-Control"))
        self.assertEqual(self.raw("GET", "/games/faceoff/view.css")[0].status, 200)
        for path in ("/games/faceoff/rules.py", "/games/nope/view.js", "/games/faceoff/../faceoff/view.js",
                     "/static/../server.py", "/static/%2e%2e/server.py", "/server.py"):
            self.assertEqual(self.raw("GET", path)[0].status, 404, path)

    def test_head_supported(self):
        for path in ("/", "/static/qrcode.js"):
            r, body = self.raw("HEAD", path)
            self.assertEqual((r.status, body), (200, b""), path)
            self.assertGreater(int(r.getheader("Content-Length")), 0)

    def test_visits_only_via_cloudflare(self):
        self.raw("GET", "/")
        self.raw("HEAD", "/", headers={"CF-Connecting-IP": "1.2.3.4"})
        self.raw("GET", "/tv", headers={"CF-Connecting-IP": "1.2.3.4"})
        self.raw("GET", "/static/style.css", headers={"CF-Connecting-IP": "1.2.3.4"})
        self.assertIn("galagie_visits_total 1\n", self.app.metrics(time.time()))

    def test_metrics_port_only(self):
        msrv = server.make_metrics_server("127.0.0.1", 0, self.app)
        threading.Thread(target=msrv.serve_forever, daemon=True).start()
        try:
            self.assertEqual(self.raw("GET", "/metrics")[0].status, 404)
            code, host, pids = self.party()
            self.assertEqual(self.act(code, pids[0], type="start")[0], 200)
            r, body = self.raw("GET", "/metrics", port=msrv.server_address[1])
            text = body.decode()
            self.assertEqual(r.status, 200)
            for line in ('galagie_games_started_total{game="faceoff"} 1', 'galagie_games_finished_total{game="faceoff"} 0',
                         "galagie_parties_created_total 1", "galagie_players_joined_total 3",
                         "galagie_parties_open 1", "galagie_players_online 3"):
                self.assertIn(line + "\n", text)
        finally:
            msrv.shutdown()
            msrv.server_close()

    def test_handler_has_socket_timeout(self):
        self.assertEqual(server.Handler.timeout, 15)


class Limits(unittest.TestCase):
    def setUp(self):
        self.saved = server.MAX_CONNECTIONS, server.REQUEST_DEADLINE
        self.socks = []
        self.srv = None

    def tearDown(self):
        for s in self.socks:
            s.close()
        if self.srv:
            self.srv.shutdown()
            self.srv.server_close()
        server.MAX_CONNECTIONS, server.REQUEST_DEADLINE = self.saved

    def start(self):
        self.srv = server.make_server("127.0.0.1", 0, GAMES)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def connect(self):
        s = socket.create_connection(self.srv.server_address, timeout=5)
        self.socks.append(s)
        return s

    def get(self):
        c = http.client.HTTPConnection(*self.srv.server_address, timeout=5)
        try:
            c.request("GET", "/")
            return c.getresponse().status
        except ConnectionError:
            return None
        finally:
            c.close()

    def test_slow_request_cut_at_deadline(self):
        server.REQUEST_DEADLINE = 1
        self.start()
        s = self.connect()
        s.settimeout(0.3)
        began, gone = time.monotonic(), False
        while not gone and time.monotonic() - began < 5:
            try:
                s.sendall(b"G")
                gone = s.recv(1) == b""
            except TimeoutError:
                pass
            except ConnectionError:
                gone = True
        self.assertTrue(gone)
        self.assertLess(time.monotonic() - began, 4)
        self.assertEqual(self.get(), 200)

    def test_connections_capped(self):
        server.MAX_CONNECTIONS = 2
        self.start()
        busy = [self.connect(), self.connect()]
        self.assertEqual(self.connect().recv(1), b"")
        for s in busy:
            s.close()
        began, status = time.monotonic(), None
        while status != 200 and time.monotonic() - began < 5:
            status = self.get()
        self.assertEqual(status, 200)


class AppTests(unittest.TestCase):
    def test_janitor_sweeps_once_per_second(self):
        app = server.App(GAMES)
        room = app.rooms[app.create("1.1.1.1", 1000)["code"]]
        ticks = []
        room.tick = ticks.append
        app.janitor(1002)
        app.janitor(1002.5)
        self.assertEqual(ticks, [1002])

    def test_never_joined_room_closes(self):
        app = server.App(GAMES)
        code = app.create("1.1.1.1", 1000)["code"]
        app.janitor(1300)
        self.assertIn(code, app.rooms)
        app.janitor(1302)
        self.assertNotIn(code, app.rooms)


if __name__ == "__main__":
    unittest.main()
