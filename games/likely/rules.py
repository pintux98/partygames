from pathlib import Path

from party.common import GameMeta
from party.deck import load_packs
from party.poll import POINTS, Poll, rounds_option, time_option


class Likely(Poll):
    meta = GameMeta("likely", {"ro": "Cel mai probabil", "en": "Most Likely To"}, 3, 16, "10-20",
                    blurb={"ro": "Votezi in secret prietenul care se potriveste. Puncte daca votezi cu toata camera.",
                           "en": "Secretly vote for the friend who fits. Score by voting with the room."},
                    options=(rounds_option(), time_option()))
    packs = load_packs(Path(__file__).parent / "content")
    tag = "prompts"

    def __init__(self, ctx):
        self.picked = [0] * len(ctx.seats)
        super().__init__(ctx)

    def read(self, body):
        return {"target": self.pick(body, "target", len(self.pids))}

    def score(self):
        votes = [0] * len(self.pids)
        for a in self.answers.values():
            votes[a["target"]] += 1
        self.picked = [p + v for p, v in zip(self.picked, votes)]
        top = max(votes)
        tops = [i for i, v in enumerate(votes) if v == top and top]
        gains = {i: POINTS for i, a in self.answers.items() if a["target"] in tops}
        board = sorted(({"name": self.names[i], "votes": v, "top": i in tops} for i, v in enumerate(votes) if v), key=lambda r: -r["votes"])
        return {"votes": board, "top": [self.names[i] for i in tops]}, gains

    def common(self, now):
        view = super().common(now)
        top = max(self.picked)
        if self.finished and top:
            view["most"] = {"names": [n for n, p in zip(self.names, self.picked) if p == top], "votes": top}
        return view
