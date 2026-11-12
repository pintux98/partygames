"use strict";

PollKit.register("likely", {
  who: { ro: "Pe cine votezi?", en: "Who gets your vote?" },
  you: { ro: "{name} (tu)", en: "{name} (you)" },
  votes: { ro: "{n} voturi", en: "{n} votes" },
  vote1: { ro: "1 vot", en: "1 vote" },
  winner_drinks: { ro: "{names}: bea!", en: "{names}: drink!" },
  nobody: { ro: "Niciun vot", en: "No votes" },
  you_top: { ro: "Asta esti tu!", en: "That's you!" },
  you_voted: { ro: "Ai votat: {name}", en: "You voted: {name}" },
  most: { ro: "Cel mai votat in seara asta", en: "Most picked tonight" },
}, {
  item: (k, game, big) => k.text("h1", "pl-item" + (big ? "" : " pl-small"), game.item),
  ask(k, game, ctx) {
    const list = k.h("div", "pl-list", game.names.map((n, i) => k.button(i === game.me ? k.say("you", { name: n }) : n, async () => {
      list.querySelectorAll("button").forEach((b) => (b.disabled = true));
      if (!(await ctx.send({ type: "answer", target: i }))) list.querySelectorAll("button").forEach((b) => (b.disabled = false));
    }, "pl-name", "t-" + i)));
    return [k.text("h2", "pl-ask", k.say("who")), list];
  },
  board(k, game) {
    const r = game.result;
    if (!r.votes.length) return k.text("p", "pl-label", k.say("nobody"));
    return k.h("div", "pl-board", k.h("ol", "pl-bars", r.votes.map((v) => k.h("li", v.top ? "pl-top" : "", k.text("span", "", v.name),
      k.text("b", "", k.say(v.votes === 1 ? "vote1" : "votes", { n: v.votes }))))),
      game.spicy ? k.text("p", "pl-drink", k.say("winner_drinks", { names: r.top.join(" & ") })) : null);
  },
  mine(k, game) {
    const out = game.mine ? [{ text: k.say("you_voted", { name: game.names[game.mine.target] }) }] : [];
    if (game.result.top.includes(game.names[game.me])) out.push({ text: k.say("you_top") + (game.spicy ? " " + k.say("drink") : ""), drink: game.spicy });
    return out;
  },
  results(k, el, game) {
    if (game.most) el.append(k.text("p", "", k.say("most") + ": " + game.most.names.join(" & ") + " (" + game.most.votes + ")"));
  },
});
