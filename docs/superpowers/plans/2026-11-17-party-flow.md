# Party Games Playtest Round Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** VIP-paced games, simpler voting, no end screens, Extreme mode, tighter sound, rewritten content, more options, 2-player play, two new games (Tomapan, Bluff).

**Architecture:** Read-screen phases get deadline `HOLD = float("inf")`; existing `hurry()` (VIP Next) already sets `deadline = now` outside answer phases. Room drops its `results` phase: a finished game returns to `lobby`, keeping `last_scores`, `seats`, `game` for a lobby strip. New games follow the `games/<id>/` folder pattern (README "Adding a game"). Content lives in `games/<id>/content/{en,ro}.json` with `family`/`spicy`/`extreme` sections.

**Tech Stack:** Python 3.12 stdlib, plain JS/CSS. Tests: `PYTHONUTF8=1 python -m unittest discover -s tests`.

**Spec:** `docs/superpowers/specs/2026-11-17-party-flow-design.md`

## Global Constraints
- No new dependencies, no build step, no inline scripts/styles (CSP). Build DOM with `textContent`.
- Plain letters only in JS/JSON: no diacritics (existing test `test_plain_letters_everywhere`).
- JSON views must never contain `Infinity`: `left` over a HOLD deadline is `null`.
- Answer/draw/vote/pick timers unchanged unless a task says so; Next in those phases still hurries.
- Content: nothing involving minors, non-consent, illegal acts, hate. Extreme = explicit, consenting adults. Bluff facts must be true and checkable.

## Review Focus
- VIP leaves during a held screen: VIP moves to another active player who can press Next. Test in Task 2.
- Last poll round reveal + Next finishes the game, not hang. Test in Task 2.
- Ending a game mid-play lands in lobby and keeps the stopped game's recap. Test in Task 1.
- Player who joined mid-game is seated in the next game. Test in Task 1.
- Tomapan answer with diacritics or different case still matches letter and duplicates (`Ăpa` vs `apa`). Test in Task 6.

---

### Task 1: Room returns to lobby; Extreme setting; hold helper

**Files:** `party/common.py`, `party/deck.py`, `party/room.py`; tests `tests/test_room.py`, `tests/test_deck.py`, `tests/test_server.py:97`

**Produces:** `party.common.HOLD = float("inf")`; `party.common.left(deadline, now) -> float | None`; `Settings.extreme: bool = False`; settings view `{"lang", "spicy", "extreme"}`; room view key `last` = `[{"name", "points"}]` sorted desc (empty before first game).

- [ ] Tests: end mid-game → phase `lobby`, `game.stopped`, host view `game` still `{"seats": 3}`; finish → `lobby`, `last[0] == {"name": "Ana", "points": 2}`; `test_finish_drops_away_and_seats_waiting` (replaces `test_again_...`): away players dropped, waiting cleared, next start seats them; `again` → 400; settings `extreme` validated like `spicy`, shown in view; deck: extreme → `extreme` list, missing → spicy, empty spicy → family. Server flow test waits for `phase == "lobby" and last`.
- [ ] Run → FAIL. Implement: `Deck.pool` cascade with `.get(mode, {}).get(tag)`; `Room.finish(now)` (scores, `finished` event only if `game.finished`, drop away players, clear waiting, `lobby`) called from `tick` and from `end` while playing (after `stop`); remove `again`; `view_for` builds `last`, includes `game` view in lobby when `self.game` exists.
- [ ] Run all → PASS. Commit `feat: games return to lobby, extreme mode setting`.

### Task 2: Hold read screens until Next

**Files:** `party/poll.py`, `games/{bravo,impostor,hotpotato,doodle}/rules.py`; their tests.

Held phases: poll `reveal`; bravo `reveal`, `scores`, `final_reveal`; impostor `reveal`, `over`; hotpotato `boom`, `over` (keep `ready`); doodle `reveal`. Every view `left` → `left(self.deadline, now)`. Delete now-unused time constants.

- [ ] Tests per game `test_read_screen_waits_for_next`: reach the phase, `tick(now + 3600)` keeps it, view `left is None`, `json.dumps(view, allow_nan=False)` ok, `hurry(now); tick(now)` moves on. Poll: last reveal + hurry → `finished`. Room: new VIP is `controller` during play. Fix loops that `tick(game.deadline)` in a read phase to `hurry(now); tick(now)` (`test_polls.py:41,103,109,125`, `test_doodle.py:139-192`, `test_hotpotato.py:111-177`, bravo full game).
- [ ] Run → FAIL. Implement. Run all → PASS. Commit `feat: read screens wait for the VIP's Next`.

### Task 3: Bravo one vote; Never without guess

**Files:** `games/bravo/rules.py` (`CLAPS = 1`), `games/bravo/view.js`, `games/never/{rules.py,view.js}`, `static/poll.js`; tests `test_bravo.py`, `test_polls.py`.

- [ ] Tests: Bravo second vote → 409 `"No claps left"`, `claps_left` 1 → 0; point expectations one vote each; final own-only case `claps_left == 1` for others. Never: `{"type": "answer", "have": True}` ok, non-bool 400, result `{"count", "answered"}`, gains `{}`.
- [ ] Implement. Never phone: one tap answers. PollKit option `points: false` hides the gain line. Bravo copy: "vote" not "clap", no dots row.
- [ ] Run all → PASS. Commit `feat: one vote in Bravo, no guess in Never Have I Ever`.

### Task 4: Options and 2-player rules

**Files:** `party/poll.py`, `games/*/rules.py` (7), their views where an option shows; tests per game; `static/i18n.js` (`"Need at least 2 players"` → ro `"Trebuie cel putin 2 jucatori"`).

Options (key: choices, default):
- Never/Likely/Rather: `rounds` (6,10,15,20) 10; `drinks` (True "On"/False "Off") True → view key `drinks = spicy and drinks`; views use `game.drinks` instead of `game.spicy`.
- Hot Potato: `rounds` (5,8,12,15) 8; `dares` (True/False) True → no `dare` drawn when off, view hides forfeit.
- Bravo: `rounds` (1,2) 2 = rounds before the final; round 2 double points only when `rounds == 2`.
- Impostor: `max_rounds` (4,6,8) 8 replaces `MAX_ROUNDS`.
- Doodle: `laps` (1,2,3) 1; `hints` (True/False) True → `hint()` reveals one random letter at 50% and another at 75% of draw time (positions fixed per turn via rng).
- `min_players = 2` for never, likely, rather, hotpotato, doodle.
- Likely: `tops` only if `top >= 2`. Rather with 2 seats: `gains` = guess equals the other player's pick; result adds `"duo": True`; view asks "What will {name} pick?".

- [ ] Tests: each option changes behavior (one assert each); Likely 1-1-1 → no gains, 2-of-3 → voters of top gain; 2-seat Likely agree → both gain, differ → none; 2-seat Rather partner-guess; 2-seat Hot Potato pass goes to the other; 2-seat Doodle reveal after one guess; hints count of revealed letters at 0/50/75%.
- [ ] Implement. Run all → PASS. Commit `feat: more game options and 2-player play`.

### Task 5: Front end: VIP lobby, lobby strip, no end screens, sound

**Files:** `static/{app.js,i18n.js,sound.js,style.css,poll.js}`, `games/{hotpotato,doodle,bravo,impostor}/view.js`.

- [ ] Lobby: `modeGroups(s)` (language + Family `{spicy:false,extreme:false}` / Spicy `{spicy:true,extreme:false}` / Extreme `{spicy:true,extreme:true}`) in `hostLobby` and the VIP card of `phoneLobby`. `lastGame(v)` strip when `v.last.length`: winner (top > 0), ranking, `gameRecap(v)`. Remove `results()` and `again` strings; host `fanfare` on `playing → lobby`.
- [ ] `closed()` → `stop()` then `homeScreen()` (or `tvScreen()` if body had `tv`). Drop `closed_*` strings.
- [ ] Poll every 300 ms when `view.phase === "playing"`, else 1000.
- [ ] Sounds: add `pass` (short noise sweep) and `lock` (soft blip) to `sound.js`. Hot Potato TV `pass` on holder change in `live`; phone `tick` when the bomb lands on you, `boom` when you blew up. `lock` after successful answer send (PollKit, Bravo, Impostor). Doodle phone `join` when `got` turns true.
- [ ] Verify: tests PASS; `python server.py` + Playwright (TV tab + 3 phone tabs): VIP phone shows language + 3 modes; Hot Potato boom waits for Next; game end → lobby strip; End party → phones on home. Commit `feat: VIP lobby settings, lobby results strip, faster sound`.

### Task 6: Tomapan

**Files:** create `games/tomapan/{__init__.py,rules.py,view.js,view.css,icon.svg,content/en.json,content/ro.json}`; modify `games/__init__.py`; test `tests/test_tomapan.py`.

Rules per spec §10. Phases: `write` (option time) → `review` (HOLD) → next round / finished. Actions: `answer {"answers": [str] * N}` (each `clean_line(.., 24)`, may resend until STOP window ends), `stop` (only if all N filled; sets `deadline = min(deadline, now + 5)`), `veto {"player": seat, "cat": j}` toggles in `review`. Fold = NFKD, strip marks, casefold, drop non-letters. Letters: `ABCDEFGHIJLMNOPRSTUVZ`. Content `{"family": {"categories": [...]}, "spicy": {...}, "extreme": {...}}`; draw N distinct categories per round from `deck.pool("categories")`. Meta: names ro/en "Tomapan", 2-16 players, options `rounds` (3,5,8) 5, `answer_time` (60,90,120) 90, `categories` (5,8) 5.

- [ ] Tests: wrong letter → 0; `Ăpa`/`apa` with letter A → shared 5 each; unique → 10; veto by > half of others strikes; STOP needs all filled and sets 5 s; review waits for Next; 2 players works.
- [ ] Implement rules, view (phone: N inputs + Send + STOP; TV: letter + categories + who is done; review: grid category × player, struck answers crossed, phone tap to veto), content (family ≥ 20 categories, spicy ≥ 12, extreme ≥ 10, each ≤ 24 chars, RO + EN).
- [ ] Run all → PASS. Commit `feat: Tomapan`.

### Task 7: Bluff

**Files:** create `games/bluff/{__init__.py,rules.py,view.js,view.css,icon.svg,content/en.json,content/ro.json}`; modify `games/__init__.py`; test `tests/test_bluff.py`.

Rules per spec §11. Phases: `write` → `vote` → `reveal` (HOLD) → next / finished. Fake rejected (`"Too close to the truth"` 409, add to i18n ro) when folded equal to answer; identical fakes merge (all authors credited). Vote options shuffled once per round, each phone excludes own fake. Points: truth +100, author +50 per fooled voter. Meta: "Bluff" / ro "Minciuna", 3-16, options `rounds` (5,8,10) 8, `answer_time` (45,60,90) 60, `vote_time` (20,30) 30. Content `facts`: `[text with "___", answer]`, family ≥ 60, spicy ≥ 30, extreme ≥ 20 per language, all true.

- [ ] Tests: fake equal to truth rejected; own fake not in own options; points for truth and for fooling; merged fakes credit both; reveal waits for Next.
- [ ] Implement rules, view, content. Run all → PASS. Commit `feat: Bluff`.

### Tasks 8-14: Content rewrite (one task per game: bravo, impostor, hotpotato, doodle, never, likely, rather)

**Files:** `games/<id>/content/{en,ro}.json`; `tests/test_content.py` (add `extreme` minimums).

Per game, both languages:
- Rewrite any line that reads as a literal translation or is clumsy (RO and EN). RO: natural spoken Romanian, plain letters, no diacritics.
- Spicy: replace mild lines so the section is bold adult (frank sex, kissing/lap-dance dares, nothing graphic).
- Add `extreme` with the same tags: explicit (kinks, positions, body parts, touching dares).
- Extreme minimums: never/likely 60, rather 50, bravo round 50 / final 12, hotpotato topics 30 / dares 25, impostor words 36 (≥ 6 per category) / twists 10, doodle words 50.
- Keep every existing structural test (prefixes, lengths, uniqueness, placeholder ratio).

- [ ] Rewrite + extend content; add extreme minimums to `test_content.py`. Run all → PASS. Commit `content: rewrite <id>, add extreme`.

### Task 15: Docs and final check

- [ ] README: new games, modes, options, 2 players, Next holds, no results screen, `extreme` section in content format.
- [ ] Full tests PASS; Playwright smoke of Tomapan and Bluff with 3 tabs. Commit `docs: playtest round`.
