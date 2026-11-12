# Party Games

Party games for a room full of friends. One screen (a TV or a laptop) shows the game, everyone else plays on their phone. No accounts, no app to install: scan the QR code, type a nickname and play.

Seven games so far:

- **Bravo!** (3 to 16 players): everyone answers silly prompts on their phone, answers meet head to head, and the room votes with claps.
- **Impostor** (4 to 16 players): everyone draws the same secret word on their phone, with a new twist each round, except the impostors, who have a different word (or, in the "Impostor knows" variant, only its category). All drawings show on the TV and the room votes someone out, round after round, until the impostors are caught or win.
- **Hot Potato** (3 to 16 players): the TV shows a topic and a ticking bomb. Whoever holds it says something from the topic out loud and passes it on from their phone. The fuse is secret; whoever holds the bomb when it blows gets a forfeit, everyone else scores.
- **Doodle** (3 to 16 players): one player picks a word and draws it on their phone while the TV shows the drawing as it grows. Everyone else types guesses; faster correct guesses score more and the drawer scores for every player who gets it. Wrong guesses scroll on the TV.
- **Never Have I Ever** (3 to 16 players): the TV shows a statement, everyone secretly taps "I have" or "I haven't" and guesses how many in the room have. The TV shows the count without names; the closest guesses score.
- **Most Likely To** (3 to 16 players): the TV asks who is most likely to do something, everyone secretly votes for a player, and whoever voted with the room scores.
- **Would You Rather** (3 to 16 players): the TV shows two options, everyone picks a side and guesses which side most people picked. The TV shows who picked what; right guesses score.

- The first player to join is the VIP and starts the games; the game and its options are picked in the lobby
- Bravo! options: answer time (45 to 120 s, default 75) and vote time (15 to 45 s, default 20)
- Impostor options: variant (Secret impostor or Impostor knows), impostors (1 to 3, capped at one per three players), draw time (20 to 60 s, default 30) and vote time (20 to 60 s, default 40)
- Hot Potato options: rounds (5, 8 or 12, default 8) and fuse (short, normal or long)
- Doodle options: draw time (60 to 100 s, default 80) and drawings each (1 or 2)
- Never Have I Ever, Most Likely To and Would You Rather options: rounds (6, 10 or 15, default 10) and answer time (15, 20 or 30 s, default 20)
- English by default, Romanian can be picked in the lobby; Family and Spicy modes. Spicy is adults only: it uses only the spicy content, and in Spicy the losing side of a round is told to drink
- Python standard library only, plain HTML, CSS and JS, no database, no build step

## How to play

1. On the big screen, open the site and tap **New party**. That device becomes the host screen. A TV browser works, and the TV can be driven with arrow keys and Enter.
2. Players join with the QR code, the 6-character room code or the share link, and pick a nickname.
3. The VIP chooses language, mode, game and the game's options, then starts. After a game, Play again returns to the lobby, where another game can be picked.

Rooms live in memory, so a restart closes any open rooms.

## Run with Coolify

1. **+ New → Public Repository** and paste this repo's URL, branch `main`.
2. Build pack: **Dockerfile**. Ports exposes: `8000`.
3. Set your domain.
4. Map the metrics port to `127.0.0.1` only (Ports Mappings `127.0.0.1:<host>:8001`) or not at all.
5. **Deploy**. Coolify uses the health check from the Dockerfile.

## Run with Docker

```sh
docker build -t partygames .
docker run -d --name partygames --restart unless-stopped \
  -p 127.0.0.1:8000:8000 -p 127.0.0.1:8001:8001 partygames
```

## Run without Docker

Python 3.12 or newer:

```sh
python server.py
```

Open http://localhost:8000.

In production, run it behind Cloudflare (proxy or tunnel) and never expose the origin port, because the rate limits and the connection cap trust the `CF-Connecting-IP` header.

## Settings

| Variable | Default |
|---|---|
| `PORT` | `8000` |
| `METRICS_PORT` | `8001` (Prometheus metrics, keep it private) |

The metrics port is not meant for the internet. Map it to `127.0.0.1` on the host, as above, and let Prometheus scrape it there.

## Adding a game

A game is one folder under `games/` plus one line in the registry. Bravo! in `games/bravo/` is the example.

```
games/<id>/
  __init__.py
  rules.py
  view.js
  view.css
  content/en.json
  content/ro.json
```

**`rules.py`** holds a class that follows the `Game` protocol from `party/common.py`:

- `meta`: a `GameMeta(id, names, min_players, max_players, minutes)`, for example `GameMeta("bravo", {"ro": "Bravo!", "en": "Bravo!"}, 3, 16, "15-25")`. Optional: `blurb` (one line per language for the lobby card) and `options`, a tuple of `GameOption(key, names, choices, default)` where `choices` is a tuple of `(value, {"ro": label, "en": label})`. The VIP picks options in the lobby; the game reads them from `ctx.settings.options`.
- `packs`: the content, loaded with `load_packs(Path(__file__).parent / "content")`
- `finished`: set to `True` when the game is over
- `__init__(ctx)`: `ctx` is a `Context` with `seats`, `settings` (`lang`, `spicy`), `rng`, `deck` and `now`
- `act(pid, body, now, active)`: a player sent an action; raise `GameError(message, status)` to reject it
- `tick(now, active)`: called regularly to move timers forward
- `hurry(now)`: the VIP pressed Next, in any phase
- `host_view(now)` and `player_view(pid, now)`: JSON-serializable state for the host screen and for one phone
- `scores()`: points per player id

Use `ctx.deck.draw(tag)` to draw a prompt that was not used yet in the room. Use `clean_line(value, limit)` for any text players type.

**Content** is one JSON file per language. Each has a `family` and a `spicy` section, and each section maps a tag to a list of strings:

```json
{
  "family": { "round": ["..."], "final": ["..."] },
  "spicy": { "round": ["..."], "final": ["..."] }
}
```

`draw("round")` takes from `family`, or only from `spicy` when the room has Spicy on (falling back to `family` if that list is empty). Plain letters only, no diacritics.

**`view.js`** registers the screens. `host` draws the shared screen, `phone` draws a player's phone; both get the element, the view returned by the game and `ctx`:

```js
G.register("<id>", { host(el, game, ctx) {}, phone(el, game, ctx) {} });
```

`ctx` has `code`, `pid`, `lang`, `send(body)` (posts an action to `act`), `sound`, `t({ en, ro })`, `me`, `vip`, `controller`, `players`. Build the DOM with `textContent` only: the CSP forbids inline scripts and styles.

Optional extras a game can use:

- `GameMeta(..., upload_max=48000)` lets `/action` bodies grow to that size for this app (default limit 2048 bytes), for example to send a drawing.
- `file(pid, name)` returns bytes for `GET /api/rooms/<code>/files/<name>.png` (members only, PNG only, `name` matching `[a-z0-9-]{1,40}`), or `None` for 404. Fetch it with the `X-Player` header and show it through a blob URL.
- `stop(now)` is called when the VIP ends the game early, so the game can reveal its secrets in the results recap.
- `label`: a short string (for example the variant) added as `mode="..."` to the games started/finished metrics.

Content entries may also be lists (for example `["word", "decoy", "category"]`); `draw(tag)` returns them as they are.

**Registry**: add the class to the tuple in `games/__init__.py`:

```python
GAMES = {g.meta.id: g for g in (Bravo, Impostor, YourGame)}
```

A game needs `view.js`, `view.css` and `icon.svg` (shown on the lobby card) in its folder. `view.js` may also register `results(el, game, ctx)` to add a recap above the final ranking.

## Tests

```sh
PYTHONUTF8=1 python -m unittest discover -s tests
```

`PYTHONUTF8=1` is for Windows.

## Credits

Fonts: [Bowlby One](https://fonts.google.com/specimen/Bowlby+One) and [Space Grotesk](https://fonts.google.com/specimen/Space+Grotesk), both under the SIL Open Font License (`static/fonts/OFL.txt`). QR codes are made with [qrcode-generator](https://github.com/kazuhikoarase/qrcode-generator) by Kazuhiko Arase (MIT).

## License

MIT
