import random
import unicodedata
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar, Protocol

if TYPE_CHECKING:
    from party.deck import Deck


class GameError(Exception):
    def __init__(self, message: str, status: int):
        super().__init__(message)
        self.status = status


def clean_line(value, limit: int) -> str:
    if not isinstance(value, str):
        raise GameError("Bad text", 400)
    kept = "".join(c for c in value if c == "‍" or not unicodedata.category(c).startswith("C") or c.isspace())
    return " ".join(unicodedata.normalize("NFKC", kept).split())[:limit].rstrip()


@dataclass
class Settings:
    lang: str = "en"
    spicy: bool = False


@dataclass(frozen=True)
class Seat:
    pid: str
    name: str


@dataclass
class Context:
    seats: list[Seat]
    settings: Settings
    rng: random.Random
    deck: "Deck"
    now: float


@dataclass(frozen=True)
class GameMeta:
    id: str
    names: dict[str, str]
    min_players: int
    max_players: int
    minutes: str


class Game(Protocol):
    meta: ClassVar[GameMeta]
    packs: ClassVar[dict]
    finished: bool

    def __init__(self, ctx: Context): ...

    def act(self, pid: str, body: dict, now: float, active: set[str]) -> None: ...

    def tick(self, now: float, active: set[str]) -> None: ...

    def hurry(self, now: float) -> None: ...

    def host_view(self, now: float) -> dict: ...

    def player_view(self, pid: str, now: float) -> dict: ...

    def scores(self) -> dict[str, int]: ...

