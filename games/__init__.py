from games.bravo.rules import Bravo
from games.doodle.rules import Doodle
from games.hotpotato.rules import HotPotato
from games.impostor.rules import Impostor

GAMES = {g.meta.id: g for g in (Bravo, Impostor, HotPotato, Doodle)}
