"use strict";

(() => {
  const S = {
    round: { ro: "Runda {n} din {m}", en: "Round {n} of {m}" },
    starts: { ro: "{name} incepe", en: "{name} starts" },
    you_start: { ro: "Tu incepi! Pregateste-te", en: "You start! Get ready" },
    has: { ro: "{name} are bomba", en: "{name} has the bomb" },
    yours: { ro: "AI BOMBA!", en: "YOU HAVE THE BOMB!" },
    say: { ro: "Spune ceva din categorie, apoi da-o mai departe", en: "Say one out loud, then pass it" },
    pass: { ro: "DA-O!", en: "PASS IT!" },
    rule: { ro: "Spuneti cate ceva din categorie si dati bomba mai departe", en: "Say something from the topic and pass the bomb" },
    boom: { ro: "BUM!", en: "BOOM!" },
    blew: { ro: "{name} a explodat", en: "{name} blew up" },
    you_blew: { ro: "Ai explodat!", en: "You blew up!" },
    forfeit: { ro: "Pedeapsa", en: "Forfeit" },
    passes: { ro: "{n} pase", en: "{n} passes" },
    pass1: { ro: "o pasa", en: "1 pass" },
    stopped: { ro: "Joc oprit inainte de final", en: "The game was ended early" },
    most: { ro: "Cele mai multe explozii", en: "Most explosions" },
    clean: { ro: "Nimeni n-a explodat", en: "Nobody blew up" },
    look: { ro: "Uita-te la TV", en: "Look at the TV" },
  };

  function h(tag, cls, ...kids) {
    const el = document.createElement(tag);
    if (cls) el.className = cls;
    for (const c of kids.flat(Infinity)) if (c != null && c !== false) el.append(c);
    return el;
  }
  const say = (ctx, key, vars = {}) => ctx.t(S[key]).replace(/\{(\w+)\}/g, (_, k) => vars[k]);
  const text = (tag, cls, s) => {
    const el = h(tag, cls);
    el.textContent = s;
    return el;
  };
  const calm = () => matchMedia("(prefers-reduced-motion: reduce)").matches;

  function paint(el, key, build) {
    if (el.hpKey === key) return false;
    const active = document.activeElement;
    const k = active && el.contains(active) ? active.dataset.k : null;
    el.hpKey = key;
    el.replaceChildren(h("div", "hp", build()));
    const again = k && el.querySelector('[data-k="' + k + '"]:not([disabled])');
    if (again) again.focus({ preventScroll: true });
    return true;
  }

  function bomb() {
    const wrap = h("div", "hp-bomb");
    wrap.setAttribute("aria-hidden", "true");
    wrap.innerHTML = '<svg viewBox="0 0 100 100"><path class="hp-fuse" d="M64 22c6-10 14-12 22-8"/><rect x="54" y="18" width="16" height="12" rx="2" transform="rotate(35 62 24)"/><circle cx="46" cy="58" r="34"/><ellipse class="hp-shine" cx="33" cy="45" rx="8" ry="5" transform="rotate(-35 33 45)"/><g class="hp-spark"><circle cx="87" cy="13" r="5"/><path d="M87 2v6M87 18v6M76 13h6M92 13h6"/></g></svg>';
    return wrap;
  }

  function worst(over) {
    const top = Math.max(...over.booms.map((b) => b.booms));
    return [top, over.booms.filter((b) => b.booms === top && top > 0).map((b) => b.name)];
  }

  function ending(ctx, over) {
    const [top, losers] = worst(over);
    return h("div", "hp-over", over.stopped ? text("p", "hp-label", say(ctx, "stopped")) : null,
      text("p", "hp-label", say(ctx, losers.length ? "most" : "clean")),
      losers.length ? text("h1", "hp-big", losers.join(" & ") + ": " + top) : null);
  }

  function head(ctx, game) {
    return h("div", "hp-head", text("p", "hp-badge", say(ctx, "round", { n: game.round, m: game.rounds })));
  }

  function hostBody(ctx, game) {
    if (game.phase === "over") return ending(ctx, game.over);
    const name = (seat) => game.players[seat].name;
    const topic = text("h1", "hp-topic", game.topic);
    if (game.phase === "ready") return [head(ctx, game), h("div", "hp-center", topic, text("p", "hp-label", say(ctx, "rule")), text("p", "hp-who", say(ctx, "starts", { name: name(game.holder) })))];
    if (game.phase === "boom") return [head(ctx, game), h("div", "hp-center hp-blast", text("h1", "hp-boom", say(ctx, "boom")),
      text("p", "hp-who", say(ctx, "blew", { name: name(game.victim) })), dare(ctx, game.dare), text("p", "hp-label", say(ctx, game.passes === 1 ? "pass1" : "passes", { n: game.passes })))];
    return [head(ctx, game), topic, h("div", "hp-center", bomb(), text("p", "hp-who", say(ctx, "has", { name: name(game.holder) }))),
      h("ul", "stickers hp-chips", game.players.map((p) => text("li", "sticker" + (p.seat === game.holder ? " hp-hot" : p.away ? " hp-away" : ""), p.name)))];
  }

  const dare = (ctx, s) => h("div", "hp-dare", text("p", "hp-label", say(ctx, "forfeit")), text("p", "", s));

  function fuse(el, game, ctx) {
    const loop = el.hpLoop;
    if (game.phase !== "live") {
      if (loop) clearTimeout(loop.timer);
      el.hpLoop = null;
      return;
    }
    if (loop && loop.round === game.round) return;
    if (loop) clearTimeout(loop.timer);
    const start = performance.now() - game.elapsed * 1000;
    const next = { round: game.round };
    const beat = () => {
      if (!el.isConnected || el.hpLoop !== next) return;
      const secs = (performance.now() - start) / 1000;
      el.style.setProperty("--heat", Math.min(1, secs / 40).toFixed(2));
      ctx.sound("tick");
      next.timer = setTimeout(beat, Math.max(140, 800 - secs * 22));
    };
    el.hpLoop = next;
    beat();
  }

  function host(el, game, ctx) {
    const moment = game.phase + "|" + game.round;
    paint(el, JSON.stringify({ ...game, elapsed: null, left: null }), () => hostBody(ctx, game));
    if (el.hpMoment !== moment && game.phase === "boom") ctx.sound("boom");
    el.hpMoment = moment;
    fuse(el, game, ctx);
  }

  function phoneBody(ctx, game) {
    if (game.phase === "over") return ending(ctx, game.over);
    if (game.phase === "boom") {
      const me = game.victim === game.me;
      return h("div", "hp-center" + (me ? " hp-blast" : ""), text("h1", "hp-boom", say(ctx, "boom")),
        text("p", "hp-who", me ? say(ctx, "you_blew") : say(ctx, "blew", { name: game.names[game.victim] })), dare(ctx, game.dare));
    }
    const topic = text("h1", "hp-topic", game.topic);
    if (game.phase === "ready") return h("div", "hp-center", topic, text("p", "hp-who", game.holding ? say(ctx, "you_start") : say(ctx, "starts", { name: game.holder })));
    if (!game.holding) return h("div", "hp-center", topic, text("p", "hp-who", say(ctx, "has", { name: game.holder })), text("p", "hp-label", say(ctx, "look")));
    const pass = text("button", "hp-pass", say(ctx, "pass"));
    pass.type = "button";
    pass.dataset.k = "pass";
    pass.addEventListener("click", async () => {
      pass.disabled = true;
      if (!(await ctx.send({ type: "pass" }))) pass.disabled = false;
    });
    return [text("h1", "hp-yours", say(ctx, "yours")), topic, text("p", "hp-label", say(ctx, "say")), pass];
  }

  function phone(el, game, ctx) {
    const hot = game.phase === "live" && game.holding;
    paint(el, JSON.stringify({ ...game, elapsed: null, left: null, passes: null }), () => h("div", "hp-phone" + (hot ? " hp-mine" : ""), phoneBody(ctx, game)));
    if (hot && !el.hpHot && navigator.vibrate && !calm()) navigator.vibrate(150);
    if (game.phase === "boom" && el.hpMoment !== game.round && game.victim === game.me && navigator.vibrate) navigator.vibrate([300, 80, 300]);
    if (game.phase === "boom") el.hpMoment = game.round;
    el.hpHot = hot;
  }

  function results(el, game, ctx) {
    if (!game.over) return;
    const [top, losers] = worst(game.over);
    el.replaceChildren(text("p", "", losers.length ? say(ctx, "most") + ": " + losers.join(" & ") + " (" + top + ")" : say(ctx, "clean")));
  }

  G.register("hotpotato", { host, phone, results });
})();
