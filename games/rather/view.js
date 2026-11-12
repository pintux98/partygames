"use strict";

PollKit.register("rather", {
  rather: { ro: "Ai prefera sa...", en: "Would you rather..." },
  or: { ro: "SAU", en: "OR" },
  pick: { ro: "Tu ce alegi?", en: "What would you pick?" },
  guess: { ro: "Ce alege majoritatea?", en: "What will most people pick?" },
  tie: { ro: "Egalitate!", en: "It's a tie!" },
  tie_drink: { ro: "Egalitate! Toata lumea bea!", en: "Tie! Everyone drinks!" },
  minority: { ro: "{names}: bea!", en: "{names}: drink!" },
  you_picked: { ro: "Ai ales: {o}", en: "You picked: {o}" },
}, {
  item(k, game, big) {
    if (!big) return k.text("p", "pl-label", k.say("rather"));
    return k.h("div", "pl-rather", k.text("p", "pl-label", k.say("rather")),
      k.h("div", "pl-duel", k.text("div", "pl-opt pl-a", game.item[0]), k.text("span", "pl-or", k.say("or")), k.text("div", "pl-opt pl-b", game.item[1])));
  },
  ask(k, game, ctx) {
    const box = k.h("div", "pl-steps");
    const lock = (on) => box.querySelectorAll("button").forEach((b) => (b.disabled = on));
    const two = (onPick, k1) => k.h("div", "pl-duo", [0, 1].map((s) => k.button(game.item[s], () => onPick(s), "pl-pick pl-" + "ab"[s], k1 + s)));
    const guess = (pick) => box.replaceChildren(k.text("h2", "pl-ask", k.say("guess")), two(async (g) => {
      lock(true);
      if (!(await ctx.send({ type: "answer", pick, guess: g }))) lock(false);
    }, "guess-"));
    box.append(k.text("h2", "pl-ask", k.say("pick")), two(guess, "pick-"));
    return box;
  },
  board(k, game) {
    const r = game.result;
    const sides = k.h("div", "pl-sides", [0, 1].map((s) => k.h("div", "pl-side" + (r.majority === s ? " pl-major" : ""),
      k.text("p", "pl-opt-text", game.item[s]), k.text("p", "pl-count", String(r.sides[s].length)),
      k.h("ul", "stickers", r.sides[s].map((n) => k.text("li", "sticker", n))))));
    let line = null;
    if (r.majority === null && r.sides[0].length) line = k.text("p", game.spicy ? "pl-drink" : "pl-label", k.say(game.spicy ? "tie_drink" : "tie"));
    else if (r.majority !== null && game.spicy && r.sides[1 - r.majority].length) line = k.text("p", "pl-drink", k.say("minority", { names: r.sides[1 - r.majority].join(", ") }));
    return k.h("div", "pl-board", sides, line);
  },
  mine(k, game) {
    if (!game.mine) return [];
    const out = [{ text: k.say("you_picked", { o: game.item[game.mine.pick] }) }];
    const r = game.result;
    if (game.spicy && (r.majority === null || game.mine.pick !== r.majority)) out.push({ text: k.say("drink"), drink: true });
    return out;
  },
});
