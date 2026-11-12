"use strict";

PollKit.register("never", {
  have: { ro: "Am facut-o", en: "I have" },
  havent: { ro: "N-am facut-o", en: "I haven't" },
  how_many: { ro: "Cati dintre noi au facut-o?", en: "How many of us have?" },
  count: { ro: "{n} din {m}", en: "{n} of {m}" },
  have_it: { ro: "au facut-o", en: "have done it" },
  spot: { ro: "Fix! {names}", en: "Spot on: {names}" },
  closest: { ro: "Cel mai aproape: {names}", en: "Closest: {names}" },
  drink_all: { ro: "Cine a facut-o: bea!", en: "If you have: drink!" },
  you_have: { ro: "Ai facut-o. Bea!", en: "You have. Drink!" },
  guessed: { ro: "Ai zis {g}, au fost {n}", en: "You said {g}, it was {n}" },
}, {
  item: (k, game, big) => k.text("h1", "pl-item" + (big ? "" : " pl-small"), game.item),
  ask(k, game, ctx) {
    const box = k.h("div", "pl-steps");
    const lock = (on) => box.querySelectorAll("button").forEach((b) => (b.disabled = on));
    const guess = (have) => box.replaceChildren(k.text("h2", "pl-ask", k.say("how_many")),
      k.h("div", "pl-grid", Array.from({ length: game.names.length + 1 }, (_, n) => k.button(String(n), async () => {
        lock(true);
        if (!(await ctx.send({ type: "answer", have, guess: n }))) lock(false);
      }, "pl-num", "n-" + n))));
    box.append(k.h("div", "pl-duo", k.button(k.say("have"), () => guess(true), "pl-pick pl-a", "have"),
      k.button(k.say("havent"), () => guess(false), "pl-pick pl-b", "havent")));
    return box;
  },
  board(k, game) {
    const r = game.result;
    return k.h("div", "pl-board", k.text("p", "pl-big", k.say("count", { n: r.count, m: r.answered })), k.text("p", "pl-label", k.say("have_it")),
      r.winners.length ? k.text("p", "pl-winners", k.say(r.exact ? "spot" : "closest", { names: r.winners.join(", ") })) : null,
      game.spicy && r.count ? k.text("p", "pl-drink", k.say("drink_all")) : null);
  },
  mine(k, game) {
    if (!game.mine) return [];
    const out = [{ text: k.say("guessed", { g: game.mine.guess, n: game.result.count }) }];
    if (game.spicy && game.mine.have) out.push({ text: k.say("you_have"), drink: true });
    return out;
  },
});
