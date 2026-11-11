from games.bravo.rules import Bravo
from games.impostor.rules import Impostor

GAMES = {g.meta.id: g for g in (Bravo, Impostor)}
