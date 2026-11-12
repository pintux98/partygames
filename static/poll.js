"use strict";

const PollKit = (() => {
  const BASE = {
    round: { ro: "Runda {n} din {m}", en: "Round {n} of {m}" },
    hurry: { ro: "Hai, grabiti-va! Mai sunt {n} s", en: "Hurry up! {n} s left" },
    locked: { ro: "Gata, ai raspuns!", en: "Locked in!" },
    look: { ro: "Uita-te la TV", en: "Look at the TV" },
    answer: { ro: "Raspundeti pe telefoane", en: "Answer on your phones" },
    nothing: { ro: "Niciun punct de data asta", en: "No points this time" },
    drink: { ro: "Bea!", en: "Drink!" },
  };

  function h(tag, cls, ...kids) {
    const el = document.createElement(tag);
    if (cls) el.className = cls;
    for (const c of kids.flat(Infinity)) if (c != null && c !== false) el.append(c);
    return el;
  }
  const text = (tag, cls, s) => {
    const el = h(tag, cls);
    el.textContent = s;
    return el;
  };
  function button(label, onClick, cls, k) {
    const b = text("button", cls, label);
    b.type = "button";
    b.dataset.k = k;
    b.addEventListener("click", onClick);
    return b;
  }

  function paint(el, key, build) {
    if (el.plKey === key) return;
    const active = document.activeElement;
    const k = active && el.contains(active) ? active.dataset.k : null;
    el.plKey = key;
    el.replaceChildren(h("div", "pl", build()));
    const again = k && el.querySelector('[data-k="' + k + '"]:not([disabled])');
    if (again) again.focus({ preventScroll: true });
  }

  function register(id, strings, parts) {
    const S = { ...BASE, ...strings };
    const kit = { h, text, button, say: null };

    function head(say, game) {
      const hurry = h("p", "im-hurry");
      hurry.hidden = true;
      return h("div", "im-head", text("p", "im-badge", say("round", { n: game.round, m: game.rounds })), hurry, h("span", "im-clock"));
    }

    function clock(el, game, say) {
      const live = game.phase === "ask" && game.left != null;
      const secs = live ? Math.ceil(game.left) : 0;
      const c = el.querySelector(".im-clock");
      if (c) {
        c.textContent = live ? secs : "";
        c.classList.toggle("im-low", live && secs <= 5);
      }
      const b = el.querySelector(".im-hurry");
      if (b) {
        const words = live && game.hurry ? say("hurry", { n: secs }) : "";
        b.hidden = !words;
        if (b.textContent !== words) b.textContent = words;
      }
      return secs;
    }

    const sayer = (ctx) => (key, vars = {}) => ctx.t(S[key]).replace(/\{(\w+)\}/g, (_, k) => vars[k]);

    function host(el, game, ctx) {
      const say = sayer(ctx);
      kit.say = say;
      paint(el, JSON.stringify({ ...game, left: null }), () => {
        if (game.phase === "ask") {
          return [head(say, game), h("div", "pl-stage", parts.item(kit, game, true), text("p", "pl-label", say("answer")),
            h("ul", "stickers im-chips", game.players.map((p) => text("li", "sticker" + (p.done ? " im-ok" : p.away ? " im-gone" : ""), p.name))))];
        }
        return [head(say, game), h("div", "pl-stage", parts.item(kit, game, false), parts.board(kit, game))];
      });
      const secs = clock(el, game, say);
      const seen = el.plSeen || {};
      const moment = game.phase + "|" + game.round;
      if (seen.moment !== moment && game.phase === "reveal") ctx.sound("reveal");
      const done = (game.players || []).filter((p) => p.done).length;
      if (game.phase === "ask" && done > (seen.done || 0)) ctx.sound("join");
      if (game.phase === "ask" && secs > 0 && secs <= 5 && secs !== seen.secs) ctx.sound("tick");
      el.plSeen = { moment, done, secs };
    }

    function phone(el, game, ctx) {
      const say = sayer(ctx);
      kit.say = say;
      const key = JSON.stringify({ phase: game.phase, round: game.round, mine: game.mine, gain: game.gain });
      paint(el, key, () => {
        if (game.phase === "ask" && !game.mine) return [head(say, game), h("div", "pl-phone", parts.item(kit, game, false), parts.ask(kit, game, ctx))];
        if (game.phase === "ask") return h("div", "im-msg", text("h1", "", say("locked")), text("p", "", say("look")));
        const mine = parts.mine(kit, game);
        return h("div", "pl-reveal", text("p", "pl-gain" + (game.gain ? " pl-win" : ""), game.gain ? "+" + game.gain : say("nothing")),
          mine.map((m) => text("p", "pl-note" + (m.drink ? " pl-drink" : ""), m.text)), text("p", "pl-label", say("look")));
      });
      clock(el, game, say);
    }

    G.register(id, { host, phone, results: parts.results && ((el, game, ctx) => { kit.say = sayer(ctx); parts.results(kit, el, game); }) });
  }

  return { register };
})();
