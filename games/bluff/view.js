"use strict";

(() => {
  const MAX = 40;
  const S = {
    round: { ro: "Runda {a}/{b}", en: "Round {a}/{b}" },
    hurry: { ro: "Hai, grabiti-va! Mai sunt {n} s", en: "Hurry up! {n} s left" },
    write: { ro: "Scrieti pe telefoane o minciuna credibila!", en: "Write a believable fake on your phones!" },
    vote: { ro: "Care e adevarul? Votati pe telefoane", en: "Which one is true? Vote on your phones" },
    truth: { ro: "ADEVARUL", en: "THE TRUTH" },
    by: { ro: "Minciuna lui {who}", en: "Fake by {who}" },
    picked: { ro: "Au ales: {who}", en: "Picked by: {who}" },
    nobody: { ro: "Nimeni n-a ales asta", en: "Nobody picked this" },
    placeholder: { ro: "Raspunsul tau fals...", en: "Your fake answer..." },
    your_fake: { ro: "Minciuna ta", en: "Your fake" },
    send: { ro: "Trimite", en: "Send" },
    sent: { ro: "Minciuna ta: {text}", en: "Your fake: {text}" },
    done: { ro: "Gata! Uita-te la TV", en: "Done, look at the TV" },
    pick: { ro: "Atinge raspunsul adevarat!", en: "Tap the true answer!" },
    found: { ro: "Ai gasit adevarul!", en: "You found the truth!" },
    missed: { ro: "Te-ai lasat pacalit", en: "You got fooled" },
    no_vote: { ro: "N-ai votat", en: "You didn't vote" },
    fooled: { ro: "Jucatori pacaliti: {n}", en: "Players fooled: {n}" },
    gain: { ro: "Runda asta: +{n}", en: "This round: +{n}" },
  };

  function h(tag, cls, ...kids) {
    const el = document.createElement(tag);
    if (cls) el.className = cls;
    for (const c of kids.flat(Infinity)) if (c != null && c !== false) el.append(c);
    return el;
  }
  const say = (ctx, key, vars = {}) => ctx.t(S[key]).replace(/\{(\w+)\}/g, (_, k) => vars[k]);
  const text = (cls, s, tag = "p") => {
    const el = h(tag, cls);
    el.textContent = s;
    return el;
  };

  function paint(el, key, build) {
    if (el.blKey === key) return false;
    const active = document.activeElement;
    const k = active && el.contains(active) ? active.dataset.k : null;
    el.blKey = key;
    el.replaceChildren(h("div", "bl", build()));
    const again = k && el.querySelector('[data-k="' + k + '"]:not([disabled])');
    if (again) again.focus({ preventScroll: true });
    return true;
  }

  function head(ctx, game) {
    const note = h("p", "bl-note");
    note.setAttribute("role", "status");
    return h("div", "bl-head", text("bl-badge", say(ctx, "round", { a: game.round, b: game.rounds }), "span"), note, h("span", "bl-clock"));
  }

  function clock(el, game, ctx) {
    const live = game.phase !== "reveal" && game.left != null;
    const secs = live ? Math.ceil(game.left) : 0;
    const c = el.querySelector(".bl-clock");
    if (c) {
      c.textContent = live ? secs : "";
      c.classList.toggle("bl-low", live && secs <= 5);
    }
    const note = el.querySelector(".bl-note");
    if (note) {
      const words = live && game.hurry ? say(ctx, "hurry", { n: secs }) : "";
      note.hidden = !words;
      if (note.textContent !== words) note.textContent = words;
    }
    return secs;
  }

  function fact(game, cls) {
    const [before, ...rest] = game.fact.split("___");
    const blank = game.truth ? text("bl-blank bl-true", game.truth, "b") : text("bl-blank", " ? ", "b");
    return h("p", "bl-fact " + cls, before, blank, rest.join("___"));
  }

  function names(ctx, done) {
    return h("ul", "stickers bl-names", ctx.players.filter((p) => !p.waiting).map((p) => {
      const ok = done.includes(p.name);
      return h("li", "sticker" + (ok ? " bl-ok" : ""), text("", p.name), ok ? h("b", "tag", "OK") : null);
    }));
  }

  function reveal(ctx, game) {
    return [
      h("ul", "bl-opts", game.options.map((o) => h("li", "bl-opt" + (o.truth ? " bl-truth" : ""),
        text("bl-text", o.text),
        o.truth ? text("bl-stamp", say(ctx, "truth"), "b") : text("bl-by", say(ctx, "by", { who: o.authors.join(", ") }), "small"),
        text("bl-picked", o.picked.length ? say(ctx, "picked", { who: o.picked.join(", ") }) : say(ctx, "nobody"), "small")))),
      h("ol", "ranking bl-rank", game.standings.map((s) => h("li", "", h("span", "", s.name), text("bl-gain", "+" + s.gain, "i"), h("b", "", String(s.points))))),
    ];
  }

  function host(el, game, ctx) {
    const p = game.phase;
    paint(el, JSON.stringify({ ...game, left: null }), () => [
      head(ctx, game),
      p === "write" ? h("div", "bl-center", fact(game, ""), text("bl-foot", say(ctx, "write")), names(ctx, game.done))
        : p === "vote" ? [fact(game, "bl-small"), h("ul", "bl-opts", game.options.map((o) => h("li", "bl-opt", text("bl-text", o)))),
          text("bl-foot", say(ctx, "vote")), names(ctx, game.done)]
        : [fact(game, "bl-small"), reveal(ctx, game)],
    ]);
    const secs = clock(el, game, ctx);
    const seen = el.blSeen || {};
    if (p === "reveal" && seen.phase !== p) ctx.sound("reveal");
    if (p !== "reveal" && secs > 0 && secs <= 5 && secs !== seen.secs) ctx.sound("tick");
    el.blSeen = { phase: p, secs };
  }

  function writer(ctx, game) {
    if (game.mine) return h("div", "bl-msg", text("", say(ctx, "done"), "h1"), text("", say(ctx, "sent", { text: game.mine })));
    const input = document.createElement("input");
    input.type = "text";
    input.maxLength = MAX;
    input.autocomplete = "off";
    input.enterKeyHint = "send";
    input.placeholder = say(ctx, "placeholder");
    input.setAttribute("aria-label", say(ctx, "your_fake"));
    input.dataset.k = "fake";
    const send = h("button", "", say(ctx, "send"));
    send.type = "submit";
    send.dataset.k = "send";
    const update = () => (send.disabled = !input.value.trim());
    input.addEventListener("input", update);
    const form = h("form", "bl-write", input, send);
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      if (send.disabled) return;
      send.disabled = true;
      if (await ctx.send({ type: "fake", text: input.value })) ctx.sound("lock");
      else update();
    });
    update();
    return [fact(game, "bl-small"), form];
  }

  function voter(ctx, game) {
    if (game.voted) return h("div", "bl-msg", text("", say(ctx, "done"), "h1"));
    const list = h("div", "bl-list", game.picks.map((o) => {
      const b = h("button", "bl-pick", text("", o.text, "span"));
      b.type = "button";
      b.dataset.k = "pick-" + o.i;
      b.addEventListener("click", () => {
        list.querySelectorAll("button").forEach((x) => (x.disabled = true));
        b.classList.add("bl-on");
        ctx.send({ type: "vote", pick: o.i }).then((ok) => {
          if (ok) ctx.sound("lock");
          else list.querySelectorAll("button").forEach((x) => (x.disabled = false));
        });
      });
      return b;
    }));
    return [fact(game, "bl-small"), text("bl-foot", say(ctx, "pick")), list];
  }

  function result(ctx, game) {
    const me = game.me;
    return h("div", "bl-msg",
      text("", me.found ? say(ctx, "found") : me.voted ? say(ctx, "missed") : say(ctx, "no_vote"), "h1"),
      fact(game, "bl-small"),
      me.fooled ? text("", say(ctx, "fooled", { n: me.fooled })) : null,
      text("bl-total", say(ctx, "gain", { n: me.gain })));
  }

  function phone(el, game, ctx) {
    const p = game.phase;
    const key = p === "write" ? "w|" + game.round + "|" + (game.mine || "")
      : p === "vote" ? "v|" + game.round + "|" + game.voted : "r|" + game.round;
    paint(el, key, () => [p !== "reveal" ? head(ctx, game) : null,
      h("div", "bl-phone", p === "write" ? writer(ctx, game) : p === "vote" ? voter(ctx, game) : result(ctx, game))]);
    clock(el, game, ctx);
  }

  G.register("bluff", { host, phone });
})();
