from games.bravo.rules import Bravo
from games.doodle.rules import Doodle
from games.hotpotato.rules import HotPotato
from games.impostor.rules import Impostor
from games.likely.rules import Likely
from games.never.rules import Never
from games.rather.rules import Rather

GAMES = {g.meta.id: g for g in (Bravo, Impostor, HotPotato, Doodle, Never, Likely, Rather)}
