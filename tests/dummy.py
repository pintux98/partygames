from party.common import GameMeta, GameOption


class Dummy:
    meta = GameMeta("dummy", {"ro": "Proba", "en": "Test"}, 3, 16, "1", upload_max=4000)
    packs = {}

    def __init__(self, ctx):
        self.ctx = ctx
        self.points = {seat.pid: 0 for seat in ctx.seats}
        self.finished = False
        self.hurried = False
        self.blob = None
        self.label = "m1"

    def act(self, pid, body, now, active):
        if body["type"] == "point":
            self.points[pid] += 1
        elif body["type"] == "finish":
            self.finished = True
        elif body["type"] == "blob":
            self.blob = body["data"].encode()

    def tick(self, now, active):
        pass

    def hurry(self, now):
        self.hurried = True

    def host_view(self, now):
        return {"seats": len(self.points)}

    def player_view(self, pid, now):
        return {"mine": self.points[pid]}

    def file(self, pid, name):
        return self.blob if name == "x.png" else None

    def scores(self):
        return dict(self.points)


class Optioned(Dummy):
    meta = GameMeta("opt", {"ro": "Optiuni", "en": "Options"}, 3, 16, "1",
                    options=(GameOption("x", {"ro": "X", "en": "X"}, ((1, {"ro": "1", "en": "1"}), (2, {"ro": "2", "en": "2"})), 1),))


GAMES = {"dummy": Dummy}
