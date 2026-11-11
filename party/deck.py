import json
import random
from pathlib import Path

from party.common import Settings


def load_packs(folder: Path) -> dict:
    return {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in folder.glob("*.json")}


class Deck:
    def __init__(self, packs: dict, settings: Settings, rng: random.Random, used: set[str]):
        self.packs = packs
        self.settings = settings
        self.rng = rng
        self.used = used

    def draw(self, tag: str) -> str:
        modes = self.packs[self.settings.lang]
        pool = list(modes["family"][tag])
        if self.settings.spicy:
            pool += modes["spicy"][tag]
        key = lambda p: p if isinstance(p, str) else tuple(p)
        fresh = [p for p in pool if key(p) not in self.used]
        if not fresh:
            self.used.difference_update(map(key, pool))
            fresh = pool
        pick = self.rng.choice(fresh)
        self.used.add(key(pick))
        return pick
