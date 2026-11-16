"use strict";

PollKit.register("never", {
  have: { ro: "Am facut-o", en: "I have" },
  havent: { ro: "N-am facut-o", en: "I haven't" },
  count: { ro: "{n} din {m}", en: "{n} of {m}" },
  have_it: { ro: "au facut-o", en: "have done it" },
  drink_all: { ro: "Cine a facut-o: bea!", en: "If you have: drink!" },
  you_have: { ro: "Ai facut-o. Bea!", en: "You have. Drink!" },
}, {
  points: false,
  item: (k, game, big) => k.text("h1", "pl-item" + (big ? "" : " pl-small"), game.item),
  ask(k, game, ctx) {
    const box = k.h("div", "pl-steps");
    const send = async (have) => {
      box.querySelectorAll("button").forEach((b) => (b.disabled = true));
      if (!(await ctx.send({ type: "answer", have }))) box.querySelectorAll("button").forEach((b) => (b.disabled = false));
    };
    box.append(k.h("div", "pl-duo", k.button(k.say("have"), () => send(true), "pl-pick pl-a", "have"),
      k.button(k.say("havent"), () => send(false), "pl-pick pl-b", "havent")));
    return box;
  },
  board(k, game) {
    const r = game.result;
    return k.h("div", "pl-board", k.text("p", "pl-big", k.say("count", { n: r.count, m: r.answered })), k.text("p", "pl-label", k.say("have_it")),
      game.drinks && r.count ? k.text("p", "pl-drink", k.say("drink_all")) : null);
  },
  mine(k, game) {
    if (!game.mine) return [];
    const out = [];
    if (game.drinks && game.mine.have) out.push({ text: k.say("you_have"), drink: true });
    return out;
  },
});
