"use strict";

(() => {
  const S = {
    turn: { ro: "Desenul {n} din {m}", en: "Drawing {n} of {m}" },
    hurry: { ro: "Hai, grabiti-va! Mai sunt {n} s", en: "Hurry up! {n} s left" },
    picking: { ro: "{name} alege un cuvant...", en: "{name} is picking a word..." },
    drawing: { ro: "{name} deseneaza", en: "{name} is drawing" },
    pick: { ro: "Alege ce desenezi", en: "Pick what to draw" },
    draw_this: { ro: "Deseneaza: {w}", en: "Draw: {w}" },
    no_words: { ro: "Fara litere sau cifre. Ceilalti ghicesc.", en: "No letters or numbers. Everyone else guesses." },
    guess: { ro: "Ghiceste", en: "Guess" },
    type: { ro: "Ce e desenul?", en: "What is it?" },
    got: { ro: "Ai ghicit! +{n}", en: "You got it! +{n}" },
    word_is: { ro: "Era: {w}", en: "It was: {w}" },
    nobody: { ro: "Nimeni n-a ghicit", en: "Nobody got it" },
    it_was: { ro: "Cuvantul era", en: "The word was" },
    missed: { ro: "Nu l-ai ghicit", en: "You missed it" },
    drew_ok: { ro: "Desenul tau: +{n}", en: "Your drawing: +{n}" },
    drew_none: { ro: "Nimeni n-a ghicit desenul tau", en: "Nobody got your drawing" },
    look: { ro: "Uita-te la TV", en: "Look at the TV" },
    waiting: { ro: "Asteapta urmatorul desen", en: "Wait for the next drawing" },
    too_big: { ro: "Desenul e prea detaliat. Simplifica-l putin.", en: "That drawing is too detailed. Simplify it a little." },
    blank: { ro: "Inca nimic...", en: "Nothing yet..." },
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
  const fold = (s) => s.normalize("NFKD").replace(/\p{M}/gu, "").toLowerCase().replace(/[\W_]/g, "");
  const say = (ctx, key, vars = {}) => ctx.t(S[key]).replace(/\{(\w+)\}/g, (_, k) => vars[k]);
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
    if (el.ddKey === key) return false;
    const active = document.activeElement;
    const k = active && el.contains(active) ? active.dataset.k : null;
    el.ddKey = key;
    el.replaceChildren(h("div", "dd", build()));
    const again = k && el.querySelector('[data-k="' + k + '"]:not([disabled])');
    if (again) again.focus({ preventScroll: true });
    return true;
  }

  function head(ctx, game) {
    const hurry = h("p", "im-hurry");
    hurry.hidden = true;
    return h("div", "im-head", text("p", "im-badge", say(ctx, "turn", { n: game.turn, m: game.turns })), hurry, h("span", "im-clock"));
  }

  function clock(el, game, ctx) {
    const live = (game.phase === "draw" || game.phase === "pick") && game.left != null;
    const secs = live ? Math.ceil(game.left) : 0;
    const c = el.querySelector(".im-clock");
    if (c) {
      c.textContent = live ? secs : "";
      c.classList.toggle("im-low", live && secs <= 10);
    }
    const b = el.querySelector(".im-hurry");
    if (b) {
      const words = live && game.hurry ? say(ctx, "hurry", { n: secs }) : "";
      b.hidden = !words;
      if (b.textContent !== words) b.textContent = words;
    }
    return secs;
  }

  function art(el, ctx, game) {
    const box = el.querySelector(".dd-art");
    if (!box) return;
    let img = box.querySelector("img");
    if (!img) {
      img = h("img");
      img.alt = "";
      box.replaceChildren(img);
    }
    if (el.ddUrl && img.src !== el.ddUrl) img.src = el.ddUrl;
    if (!game.file) {
      if (!el.ddUrl) box.replaceChildren(text("p", "dd-blank", say(ctx, "blank")));
      return;
    }
    if (game.file === el.ddFile) return;
    el.ddFile = game.file;
    fetch("/api/rooms/" + ctx.code + "/files/" + game.file, { headers: { "X-Player": ctx.pid } })
      .then((r) => (r.ok ? r.blob() : null)).then((b) => {
        if (!b || el.ddFile !== game.file) return;
        const old = el.ddUrl;
        el.ddUrl = URL.createObjectURL(b);
        const now = el.querySelector(".dd-art img") || h("img");
        now.alt = "";
        now.src = el.ddUrl;
        if (!now.isConnected) { const at = el.querySelector(".dd-art"); if (at) at.replaceChildren(now); }
        if (old) setTimeout(() => URL.revokeObjectURL(old), 1000);
      }).catch(() => {});
  }

  function reset(el, game) {
    const turn = game.turn + "|" + game.phase;
    if (game.phase === "pick" && el.ddTurn !== turn) {
      if (el.ddUrl) URL.revokeObjectURL(el.ddUrl);
      el.ddUrl = el.ddFile = null;
    }
    el.ddTurn = turn;
  }

  const hint = (s) => text("p", "dd-hint", s);
  const feed = (game) => h("ul", "dd-feed", game.feed.map((f) => h("li", "", text("b", "", f.name), " " + f.text)));
  const gains = (ctx, game) => game.gains.length
    ? h("ul", "stickers dd-gains", game.gains.map((g) => text("li", "sticker", g.name + " +" + g.points)))
    : text("p", "dd-label", say(ctx, "nobody"));

  function hostBody(ctx, game) {
    if (game.phase === "pick") return [head(ctx, game), h("div", "im-center", text("h1", "im-title", say(ctx, "picking", { name: game.drawer })))];
    const side = game.phase === "draw"
      ? [hint(game.hint), text("p", "dd-label", say(ctx, "drawing", { name: game.drawer })), feed(game),
        h("ul", "stickers im-chips", game.players.filter((p) => !p.drawer).map((p) => text("li", "sticker" + (p.guessed ? " im-ok" : p.away ? " im-gone" : ""), p.name)))]
      : [text("h1", "dd-word", game.word), gains(ctx, game)];
    return [head(ctx, game), h("div", "dd-stage", h("div", "dd-art"), h("div", "dd-side", side))];
  }

  function host(el, game, ctx) {
    reset(el, game);
    paint(el, JSON.stringify({ ...game, left: null, file: null }), () => hostBody(ctx, game));
    art(el, ctx, game);
    const secs = clock(el, game, ctx);
    const seen = el.ddSeen || {};
    if (game.phase === "reveal" && seen.phase !== "reveal") ctx.sound("reveal");
    if (game.guessed.length > (seen.got || 0) && game.phase === "draw") ctx.sound("join");
    if (game.phase === "draw" && secs > 0 && secs <= 5 && secs !== seen.secs) ctx.sound("tick");
    el.ddSeen = { phase: game.phase, got: game.guessed.length, secs };
  }

  function drawer(ctx, game, el) {
    const labels = { pen: say(ctx, "pen"), fill: say(ctx, "fill"), erase: say(ctx, "erase"), undo: say(ctx, "undo"), redo: say(ctx, "redo"), size: (n) => say(ctx, "size", { n }) };
    const msg = h("div", "im-warn");
    let timer = null, busy = false, again = false;
    const push = async () => {
      if (busy) { again = true; return; }
      busy = true;
      do {
        again = false;
        const png = board.png();
        msg.replaceChildren(png ? "" : text("p", "im-small", say(ctx, "too_big")));
        if (png) await ctx.send({ type: "draw", png });
      } while (again && el.isConnected);
      busy = false;
    };
    const board = DrawPad(labels, say(ctx, "draw_this", { w: game.word }), () => {
      clearTimeout(timer);
      timer = setTimeout(push, 300);
    });
    return [h("div", "im-word-card", text("p", "", say(ctx, "draw_this", { w: game.word })), text("p", "im-small", say(ctx, "no_words"))),
      msg, board.board, board.swatches, board.tools];
  }

  function guesser(ctx, game) {
    if (game.got) return h("div", "im-msg", text("h1", "", say(ctx, "got", { n: game.gain })), text("p", "", say(ctx, "word_is", { w: game.word })));
    const input = h("input", "dd-input");
    Object.assign(input, { type: "text", maxLength: 40, autocomplete: "off", autocapitalize: "off", spellcheck: false, enterKeyHint: "send" });
    input.dataset.k = "guess-input";
    input.setAttribute("aria-label", say(ctx, "type"));
    input.placeholder = say(ctx, "type");
    const form = h("form", "dd-form", input, text("button", "", say(ctx, "guess")));
    const tried = h("ul", "stickers dd-tried");
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const value = input.value.trim();
      if (!value) return;
      input.value = "";
      const dup = [...tried.children].find((li) => fold(li.textContent) === fold(value));
      if (dup) {
        dup.classList.remove("dd-dup");
        void dup.offsetWidth;
        dup.classList.add("dd-dup");
        return input.focus({ preventScroll: true });
      }
      if (!(await ctx.send({ type: "guess", text: value }))) input.value = value;
      input.focus({ preventScroll: true });
    });
    return [hint(game.hint), text("p", "dd-label", say(ctx, "look")), tried, form];
  }

  function reveal(ctx, game) {
    const [mine, win] = game.drawing
      ? [say(ctx, game.gains.length ? "drew_ok" : "drew_none", { n: game.gain }), game.gains.length > 0]
      : game.got ? [say(ctx, "got", { n: game.gain }), true] : [say(ctx, "missed"), false];
    return h("div", "dd-reveal", text("p", "dd-mine" + (win ? " dd-win" : ""), mine), text("p", "dd-label", say(ctx, "it_was")),
      text("h1", "dd-word", game.word), h("div", "dd-art"), game.gains.length || !game.drawing ? gains(ctx, game) : null);
  }

  function phoneBody(ctx, game, el) {
    if (game.phase === "pick") {
      if (!game.choices) return h("div", "im-msg", text("h1", "", say(ctx, "picking", { name: game.drawer })));
      return [text("h2", "im-ask", say(ctx, "pick")), h("div", "dd-choices", game.choices.map((w, i) => button(w, () => ctx.send({ type: "pick", choice: i }), "im-target", "pick-" + i)))];
    }
    if (game.phase === "draw") return game.drawing ? drawer(ctx, game, el) : guesser(ctx, game);
    return reveal(ctx, game);
  }

  function phone(el, game, ctx) {
    reset(el, game);
    const key = JSON.stringify({ phase: game.phase, turn: game.turn, drawing: game.drawing, got: game.got, choices: game.choices, word: game.phase === "reveal" ? game.word : null });
    paint(el, key, () => [game.phase === "draw" || game.choices ? head(ctx, game) : null,
      h("div", "im-phone" + (game.phase === "draw" && game.drawing ? " im-drawing" : ""), phoneBody(ctx, game, el))]);
    clock(el, game, ctx);
    art(el, ctx, game);
    const list = el.querySelector(".dd-tried");
    const tried = (game.tried || []).join("|");
    if (list && list.ddKey !== tried) {
      list.ddKey = tried;
      list.replaceChildren(...game.tried.map((t) => text("li", "sticker", t)));
    }
  }

  G.register("doodle", { host, phone });
})();
