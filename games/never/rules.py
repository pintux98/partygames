from pathlib import Path

from party.common import GameError, GameMeta
from party.deck import load_packs
from party.poll import POINTS, Poll, rounds_option, time_option


class Never(Poll):
    meta = GameMeta("never", {"ro": "Eu niciodata", "en": "Never Have I Ever"}, 3, 16, "10-20",
                    blurb={"ro": "Raspunzi in secret daca ai facut-o. Ghicesti cati din camera au facut-o.",
                           "en": "Answer in secret if you have. Guess how many in the room have."},
                    options=(rounds_option(), time_option()))
    packs = load_packs(Path(__file__).parent / "content")
    tag = "statements"

    def read(self, body):
        have = body.get("have")
        if type(have) is not bool:
            raise GameError("Bad choice", 400)
        return {"have": have, "guess": self.pick(body, "guess", len(self.pids) + 1)}

    def score(self):
        count = sum(a["have"] for a in self.answers.values())
        best = min((abs(a["guess"] - count) for a in self.answers.values()), default=None)
        gains = {i: POINTS * (2 if best == 0 else 1) for i, a in self.answers.items() if abs(a["guess"] - count) == best}
        return {"count": count, "answered": len(self.answers), "exact": best == 0, "winners": [self.names[i] for i in gains]}, gains
