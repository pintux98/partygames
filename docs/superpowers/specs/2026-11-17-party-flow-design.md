# Party Games: playtest round (flow, content, new games)

## Intent
Playtest feedback on mimi's party games. The VIP sets the pace, not timers. Fewer taps, no dead-end screens, sound that matches the screen. Spicy should feel adult, Extreme explicit, and every line should read naturally in RO and EN. Couples can play the games that work with 2. Two new games: Tomapan and Bluff.

## Anti-goals
- Diacritics in Romanian (user wants plain letters; existing test stays).
- Any content involving minors, non-consent, illegal acts, or hate. Extreme is explicit between consenting adults only.
- Invented "true" facts in Bluff: every fact must be checkable.
- Server push / new dependencies.

## A. Flow and sound
1. **VIP phone lobby** shows Language (RO/EN) and Mode (Family/Spicy/Extreme) on the VIP card.
2. **No auto-advance on read screens.** Reveals, dares/forfeits, Bravo scores, game-over screens hold until the VIP (phone or TV) presses Next. Answer/draw/vote timers still run; Next there still means "hurry". Hot Potato keeps its 4 s "get ready" countdown.
3. **Bravo**: one vote per voter (was 3 claps), wording says vote. **Never Have I Ever**: no "how many" guess, no points; tap I have / I haven't, TV shows the count.
4. **Game end** (finished or ended) goes straight to the lobby, which shows a strip with the last winner, ranking and the game's recap. No Results screen, no "Play again". **Party end**: everyone goes straight to the home page.
5. **Sound**: poll every 300 ms during a game (1 s otherwise). TV: bomb passed. Phones: bomb lands on you, you blew up, answer locked in, doodle guessed.

## B. Content, options, 2 players
6. **Extreme mode**: third mode. Packs get an `extreme` section; draw falls back extreme → spicy → family.
7. **Rewrite all content** (7 games + new ones, RO and EN): natural phrasing, no literal translations. Spicy = bold adult (frank sex questions, kiss/lap-dance dares, nothing graphic). Extreme = explicit (kinks, positions, body parts named, touching dares).
8. **Options** (my proposal, not objected):
   - Never / Likely / Rather: rounds 6/10/15/20; Drinks on/off (drink lines only show in Spicy/Extreme).
   - Hot Potato: rounds 5/8/12/15; Dares on/off.
   - Bravo: rounds before the final 1/2.
   - Impostor: max rounds 4/6/8.
   - Doodle: drawings each 1/2/3; letter hints on/off (letters appear in the hint as time runs out).
9. **2 players** (min players 2): Never, Likely, Rather, Hot Potato, Doodle, Tomapan.
   - Likely: you score only when the top pick has at least 2 votes (2 players: you agreed). Also stops 1-1-1 ties scoring everyone.
   - Rather with 2: you guess your partner's pick, not the majority.

## C. New games
10. **Tomapan** (2-16): TV shows a letter and N categories. Everyone types one word per category starting with that letter. The first player with every box filled can press STOP: everyone else gets 5 s. Review (held): TV shows answers per category; players tap to veto others' answers; an answer is struck when more than half of the other players veto it. Scoring: 10 unique valid, 5 shared (same word folded), 0 empty/wrong letter/struck. Options: rounds 3/5/8, time 60/90/120 s, categories 5/8. Categories come from packs per mode (Spicy/Extreme have adult categories). Letters exclude Q, W, X, Y, K.
11. **Bluff** (3-16): TV shows a true but strange fact with a blank. Everyone writes a fake answer (rejected if it matches the truth). Vote: each phone lists all fakes + truth minus their own; pick the truth. Reveal (held): +100 for finding the truth, +50 to an author per player fooled. Options: rounds 5/8/10, write time 45/60/90 s, vote time 20/30 s. Packs: `facts` = `[question_with____, answer]`.

## Approaches
- Faster polling for sound (picked). SSE ruled out: 64-connection cap and 20 s request reaper.
- Tomapan veto: majority veto of other players (picked) vs VIP-only strike (VIP bias) vs none (anyone types junk).

## Builder notes (my calls)
- Hold = deadline `float("inf")`; views report `left: null` (JSON has no Infinity).
- Extreme = `extreme` bool beside `spicy` (extreme implies spicy); existing `spicy` checks keep working.
- Keep `room.game` after it ends for the lobby recap; `start` replaces it.
- Would You Rather keeps its majority guess with 3+.
- `moved` screen (party moved to another TV) stays.
- Content minimums per mode for new `extreme` sections: about 60% of the spicy minimum.
