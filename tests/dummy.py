from party.common import GameMeta


class Dummy:
    meta = GameMeta("dummy", {"ro": "Proba", "en": "Test"}, 3, 16, "1")
    packs = {}

    def __init__(self, ctx):
        self.ctx = ctx
        self.points = {seat.pid: 0 for seat in ctx.seats}
        self.finished = False
        self.hurried = False

    def act(self, pid, body, now, active):
        if body["type"] == "point":
            self.points[pid] += 1
        elif body["type"] == "finish":
            self.finished = True

    def tick(self, now, active):
        pass

    def hurry(self, now):
        self.hurried = True

    def host_view(self, now):
        return {"seats": len(self.points)}

    def player_view(self, pid, now):
        return {"mine": self.points[pid]}

    def scores(self):
        return dict(self.points)


GAMES = {"dummy": Dummy}
