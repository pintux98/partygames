"use strict";

(() => {
  const WAITING = ["draw", "vote", "guess"];
  const S = {
    round: { ro: "Runda {n} din {m}", en: "Round {n} of {m}" },
    hurry: { ro: "Hai, grabiti-va! Mai sunt {n} s", en: "Hurry up! {n} s left" },
    draw_tv: { ro: "Desenati pe telefoane!", en: "Draw on your phones!" },
    vote_tv: { ro: "Cine e impostorul? Votati pe telefon", en: "Who is the impostor? Vote on your phones" },
    nothing: { ro: "fara desen", en: "no drawing" },
    out_imp: { ro: "{name} a iesit. ERA IMPOSTOR!", en: "{name} is out. IMPOSTOR!" },
    out_crew: { ro: "{name} a iesit. Nu era impostor...", en: "{name} is out. Not the impostor..." },
    tie: { ro: "Egalitate. Nu iese nimeni.", en: "It's a tie. Nobody is out." },
    guessing: { ro: "{name} are o sansa sa ghiceasca cuvantul", en: "{name} gets one guess at the word" },
    crew_won: { ro: "Echipa a castigat!", en: "The crew wins!" },
    stopped: { ro: "Joc oprit inainte de final", en: "The game was ended early" },
    too_big: { ro: "Desenul e prea detaliat. Simplifica-l putin.", en: "That drawing is too detailed. Simplify it a little." },
    imps_won: { ro: "Impostorii au castigat!", en: "The impostors win!" },
    word_was: { ro: "Cuvantul: {w} · al impostorului: {d}", en: "The word: {w} · the impostor's: {d}" },
    word_cat: { ro: "Cuvantul: {w} · categoria: {c}", en: "The word: {w} · category: {c}" },
    count: { ro: "Impostori: {n}", en: "Impostors: {n}" },
    impostors_were: { ro: "Impostori: {names}", en: "Impostors: {names}" },
    your_word: { ro: "Cuvantul tau: {w}", en: "Your word: {w}" },
    word_hint: { ro: "Toti deseneaza acelasi cuvant. Unul are altul.", en: "Everyone draws the same word. Someone has another." },
    you_imp: { ro: "Esti IMPOSTORUL. Categoria: {c}", en: "You are the IMPOSTOR. Category: {c}" },
    team: { ro: "Echipa ta: {names}", en: "Your team: {names}" },
    done: { ro: "Gata", en: "Done" },
    sent: { ro: "Trimis! Uita-te la TV", en: "Sent! Look at the TV" },
    look: { ro: "Uita-te la TV", en: "Look at the TV" },
    pick: { ro: "Cine e impostorul?", en: "Who is the impostor?" },
    change: { ro: "Poti schimba votul pana se termina timpul.", en: "You can change your vote until time runs out." },
    out: { ro: "Ai iesit din joc", en: "You're out" },
    out_hint: { ro: "Uita-te la TV pana se termina jocul.", en: "Watch the TV until the game ends." },
    guess: { ro: "Ghiceste cuvantul!", en: "Guess the word!" },
    pen: { ro: "Creion", en: "Pen" },
    fill: { ro: "Galeata", en: "Fill" },
    erase: { ro: "Radiera", en: "Eraser" },
    undo: { ro: "Inapoi", en: "Undo" },
    redo: { ro: "Refa", en: "Redo" },
    size: { ro: "Grosime {n}", en: "Size {n}" },
  };
  function h(tag, cls, ...kids) {
    const el = document.createElement(tag);
    if (cls) el.className = cls;
    for (const c of kids.flat(Infinity)) if (c != null && c !== false) el.append(c);
    return el;
  }
  const fill = (s, vars) => s.replace(/\{(\w+)\}/g, (_, k) => vars[k]);
  const say = (ctx, key, vars = {}) => fill(ctx.t(S[key]), vars);
  const text = (cls, s) => {
    const el = h("p", cls);
    el.textContent = s;
    return el;
  };
  function button(label, onClick, cls, k) {
    const b = h("button", cls);
    b.type = "button";
    if (typeof label === "string") b.textContent = label;
    else b.append(label);
    b.dataset.k = k;
    b.addEventListener("click", onClick);
    return b;
  }

  function paint(el, key, build) {
    if (el.imKey === key) return false;
    const active = document.activeElement;
    const k = active && el.contains(active) ? active.dataset.k : null;
    el.imKey = key;
    el.replaceChildren(h("div", "im", build()));
    const again = k && el.querySelector('[data-k="' + k + '"]:not([disabled])');
    if (again) again.focus({ preventScroll: true });
    return true;
  }

  function head(ctx, game) {
    const hurry = h("p", "im-hurry");
    hurry.hidden = true;
    const label = say(ctx, "round", { n: game.round, m: game.max_rounds }) + (game.impostors ? " · " + say(ctx, "count", { n: game.impostors }) : "");
    return h("div", "im-head", text("im-badge", label), hurry, h("span", "im-clock"));
  }

  function clock(el, game, ctx) {
    const live = WAITING.includes(game.phase) && game.left != null;
    const secs = live ? Math.ceil(game.left) : 0;
    const c = el.querySelector(".im-clock");
    if (c) {
      c.textContent = live ? secs : "";
      c.classList.toggle("im-low", live && secs <= 5);
    }
    const b = el.querySelector(".im-hurry");
    if (b) {
      const words = live && game.hurry ? say(ctx, "hurry", { n: secs }) : "";
      b.hidden = !words;
      if (b.textContent !== words) b.textContent = words;
    }
    return secs;
  }

  const images = new Map();
  let imageRound = 0;
  function picture(ctx, game, file) {
    if (game.round !== imageRound) {
      images.forEach((p) => p.then((u) => u && URL.revokeObjectURL(u)));
      images.clear();
      imageRound = game.round;
    }
    if (!images.has(file)) {
      images.set(file, fetch("/api/rooms/" + ctx.code + "/files/" + file, { headers: { "X-Player": ctx.pid } })
        .then((r) => (r.ok ? r.blob() : null)).then((b) => (b ? URL.createObjectURL(b) : null)).catch(() => null));
    }
    const img = h("img");
    img.alt = "";
    images.get(file).then((u) => { if (u) img.src = u; });
    return img;
  }

  function chips(game) {
    return h("ul", "stickers im-chips", game.players.map((p) => {
      const li = h("li", "sticker" + (p.out ? " im-gone" : p.drew ? " im-ok" : ""), text("", p.name));
      return li;
    }));
  }

  function grid(ctx, game) {
    const files = new Map((game.drawings || []).map((d) => [d.seat, d.file]));
    const shown = game.players.filter((p) => !p.out || files.has(p.seat));
    const cols = shown.length <= 4 ? shown.length : shown.length <= 8 ? 4 : shown.length <= 12 ? 6 : 8;
    const list = h("ul", "im-grid");
    list.style.setProperty("--cols", cols);
    list.style.setProperty("--rows", Math.ceil(shown.length / cols));
    for (const p of shown) {
      const tile = h("li", "im-tile" + (game.result && game.result.out === p.seat ? " im-picked" : ""));
      tile.append(files.has(p.seat) ? picture(ctx, game, files.get(p.seat)) : text("im-none", say(ctx, "nothing")));
      tile.append(text("im-name", p.name));
      const n = game.votes ? game.votes[p.seat] : 0;
      if (n) tile.append(h("b", "im-votes", String(n)));
      list.append(tile);
    }
    return list;
  }

  function verdict(ctx, game) {
    const r = game.result;
    if (!r) return null;
    const name = r.out == null ? "" : game.players[r.out].name;
    if (game.phase === "guess") return text("im-verdict im-imp", say(ctx, "guessing", { name }));
    if (r.out == null) return text("im-verdict", say(ctx, "tie"));
    return text("im-verdict" + (r.impostor ? " im-imp" : ""), say(ctx, r.impostor ? "out_imp" : "out_crew", { name }));
  }

  function ending(ctx, over) {
    return h("div", "im-over",
      h("h1", "im-winner", say(ctx, over.winner === "crew" ? "crew_won" : over.winner ? "imps_won" : "stopped")),
      text("im-word", over.decoy ? say(ctx, "word_was", { w: over.word, d: over.decoy }) : say(ctx, "word_cat", { w: over.word, c: over.category })),
      text("im-foot", say(ctx, "impostors_were", { names: over.impostors.join(", ") })));
  }

  function hostBody(ctx, game) {
    if (game.phase === "over") return ending(ctx, game.over);
    const twist = text("im-twist", game.twist);
    if (game.phase === "draw") return [head(ctx, game), h("div", "im-center", twist, h("h1", "im-title", say(ctx, "draw_tv")), chips(game))];
    return [head(ctx, game), twist, verdict(ctx, game) || text("im-foot", say(ctx, "vote_tv")), grid(ctx, game)];
  }

  function host(el, game, ctx) {
    paint(el, JSON.stringify({ ...game, left: null }), () => hostBody(ctx, game));
    const seen = el.imSeen || {};
    const moment = game.phase + "|" + game.round;
    if (seen.moment !== moment && game.phase === "reveal" && game.result) ctx.sound(game.result.impostor ? "sweep" : "reveal");
    const secs = clock(el, game, ctx);
    if (WAITING.includes(game.phase) && secs > 0 && secs <= 5 && secs !== seen.secs) ctx.sound("tick");
    el.imSeen = { moment, secs };
  }

  function message(ctx, key, sub) {
    return h("div", "im-msg", h("h1", "", say(ctx, key)), sub ? text("", say(ctx, sub)) : null);
  }

  function wordCard(ctx, game) {
    if (game.impostor) {
      return h("div", "im-word-card im-imp-card", text("", say(ctx, "you_imp", { c: game.category })),
        game.team.length ? text("im-small", say(ctx, "team", { names: game.team.join(", ") })) : null);
    }
    return h("div", "im-word-card", text("", say(ctx, "your_word", { w: game.word })), text("im-small", say(ctx, "word_hint")));
  }

  function pad(ctx, game, el) {
    const labels = { pen: say(ctx, "pen"), fill: say(ctx, "fill"), erase: say(ctx, "erase"), undo: say(ctx, "undo"), redo: say(ctx, "redo"), size: (n) => say(ctx, "size", { n }) };
    const board = DrawPad(labels, say(ctx, "your_word", { w: game.word || game.category || "" }));
    let sent = false;
    const submit = async () => {
      if (sent) return;
      const png = board.png();
      if (!png) return msg.replaceChildren(text("im-small", say(ctx, "too_big")));
      sent = true;
      if (!(await ctx.send({ type: "draw", png }))) sent = false;
    };
    const msg = h("div", "im-warn");
    el.imSubmit = submit;
    const done = button(say(ctx, "done"), submit, "im-done", "done");
    return [wordCard(ctx, game), msg, board.board, board.swatches, board.tools, done];
  }

  function voter(ctx, game) {
    const list = h("div", "im-targets", game.targets.map((t) => {
      const b = button(t.name, () => ctx.send({ type: "vote", target: t.seat }), "im-target", "target-" + t.seat);
      b.setAttribute("aria-pressed", String(game.voted === t.seat));
      return b;
    }));
    return [wordCard(ctx, game), h("h2", "im-ask", say(ctx, "pick")), list, text("im-small", say(ctx, "change"))];
  }

  function guesser(ctx, game) {
    return [h("h2", "im-ask", say(ctx, "guess")), h("div", "im-targets", game.options.map((w, i) =>
      button(w, () => ctx.send({ type: "guess", word: w }), "im-target", "guess-" + i)))];
  }

  function phoneBody(ctx, game, el) {
    if (game.phase === "guess" && game.options) return guesser(ctx, game);
    if (game.out && game.phase !== "over") return message(ctx, "out", "out_hint");
    if (game.phase === "over") return ending(ctx, game.over);
    if (game.phase === "draw") return game.drew ? message(ctx, "sent") : pad(ctx, game, el);
    if (game.phase === "vote") return voter(ctx, game);
    return message(ctx, "look");
  }

  function phone(el, game, ctx) {
    const key = JSON.stringify({ phase: game.phase, round: game.round, drew: game.drew, voted: game.voted, out: game.out, options: game.options, targets: game.targets, over: !!game.over });
    if (paint(el, key, () => {
      el.imSubmit = null;
      const live = WAITING.includes(game.phase) && (!game.out || game.options);
      return [live ? head(ctx, game) : null, h("div", "im-phone" + (game.phase === "draw" && !game.drew ? " im-drawing" : ""), phoneBody(ctx, game, el))];
    }) && game.phase === "draw") {
      const t = el.querySelector(".im-head .im-badge");
      if (t) t.textContent = game.twist;
    }
    const secs = clock(el, game, ctx);
    if (game.phase === "draw" && el.imSubmit && game.left != null && game.left <= 3 && secs >= 0) el.imSubmit();
  }

  function results(el, game, ctx) {
    if (game.over) el.replaceChildren(text("", say(ctx, game.over.winner ? (game.over.winner === "crew" ? "crew_won" : "imps_won") : "stopped")),
      text("", game.over.decoy ? say(ctx, "word_was", { w: game.over.word, d: game.over.decoy }) : say(ctx, "word_cat", { w: game.over.word, c: game.over.category })),
      text("", say(ctx, "impostors_were", { names: game.over.impostors.join(", ") })));
  }

  G.register("impostor", { host, phone, results });
})();
