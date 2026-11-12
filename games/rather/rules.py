from pathlib import Path

from party.common import GameMeta
from party.deck import load_packs
from party.poll import POINTS, Poll, rounds_option, time_option


class Rather(Poll):
    meta = GameMeta("rather", {"ro": "Ce ai prefera?", "en": "Would You Rather"}, 3, 16, "10-20",
                    blurb={"ro": "Alegi o parte si ghicesti ce alege majoritatea.",
                           "en": "Pick a side and guess what most of the room picks."},
                    options=(rounds_option(), time_option()))
    packs = load_packs(Path(__file__).parent / "content")
    tag = "dilemmas"

    def read(self, body):
        return {"pick": self.pick(body, "pick", 2), "guess": self.pick(body, "guess", 2)}

    def score(self):
        sides = [[self.names[i] for i, a in self.answers.items() if a["pick"] == s] for s in (0, 1)]
        majority = None if len(sides[0]) == len(sides[1]) else int(len(sides[1]) > len(sides[0]))
        gains = {i: POINTS for i, a in self.answers.items() if a["guess"] == majority}
        return {"sides": sides, "majority": majority}, gains
