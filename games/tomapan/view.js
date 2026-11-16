"use strict";

(() => {
  const MAX = 24;
  const S = {
    round: { ro: "Runda {a}/{b}", en: "Round {a}/{b}" },
    hurry: { ro: "Hai, grabiti-va! Mai sunt {n} s", en: "Hurry up! {n} s left" },
    stop: { ro: "STOP! {name} a terminat. Mai sunt {n} s", en: "STOP! {name} is done. {n} s left" },
    write: { ro: "Scrieti pe telefoane! Litera:", en: "Write on your phones! Letter:" },
    review: { ro: "Verificati raspunsurile", en: "Check the answers" },
    review_hint: { ro: "Atingeti pe telefon un raspuns gresit ca sa-l taiati", en: "Tap a wrong answer on your phone to veto it" },
    total: { ro: "Runda asta", en: "This round" },
    all: { ro: "Total", en: "Total" },
    placeholder: { ro: "cu {l}...", en: "with {l}..." },
    send: { ro: "Trimite", en: "Send" },
    sent: { ro: "Trimis", en: "Sent" },
    stop_btn: { ro: "STOP", en: "STOP" },
    yours: { ro: "al tau", en: "yours" },
    tap: { ro: "Atinge un raspuns gresit ca sa-l votezi la taiat.", en: "Tap a wrong answer to vote it out." },
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
    if (el.tpKey === key) return false;
    const active = document.activeElement;
    const k = active && el.contains(active) ? active.dataset.k : null;
    el.tpKey = key;
    el.replaceChildren(h("div", "tp", build()));
    const again = k && el.querySelector('[data-k="' + k + '"]:not([disabled])');
    if (again) again.focus({ preventScroll: true });
    return true;
  }

  function head(ctx, game) {
    const note = h("p", "tp-note");
    note.setAttribute("role", "status");
    return h("div", "tp-head", text("tp-badge", say(ctx, "round", { a: game.round, b: game.rounds }), "span"), note, h("span", "tp-clock"));
  }

  function clock(el, game, ctx) {
    const live = game.phase === "write" && game.left != null;
    const secs = live ? Math.ceil(game.left) : 0;
    const c = el.querySelector(".tp-clock");
    if (c) {
      c.textContent = live ? secs : "";
      c.classList.toggle("tp-low", live && secs <= 5);
    }
    const note = el.querySelector(".tp-note");
    if (note) {
      const words = !live ? "" : game.stopped ? say(ctx, "stop", { name: game.stopped, n: secs }) : game.hurry ? say(ctx, "hurry", { n: secs }) : "";
      note.hidden = !words;
      if (note.textContent !== words) note.textContent = words;
    }
    return secs;
  }

  function cats(game) {
    return h("ul", "tp-cats", game.cats.map((c) => text("", c, "li")));
  }

  function names(ctx, done) {
    return h("ul", "stickers tp-names", ctx.players.filter((p) => !p.waiting).map((p) => {
      const ok = done.includes(p.name);
      return h("li", "sticker" + (ok ? " tp-ok" : ""), text("", p.name), ok ? h("b", "tag", "OK") : null);
    }));
  }

  function grid(ctx, game) {
    const r = game.review;
    const cols = r.players.length;
    const el = h("div", "tp-grid");
    el.style.gridTemplateColumns = "minmax(0, 1.1fr) repeat(" + cols + ", minmax(0, 1fr))";
    el.style.fontSize = Math.max(0.55, Math.min(1, 7 / cols)) + "em";
    el.append(h("span"), r.players.map((p) => text("tp-pl", p, "b")));
    game.cats.forEach((c, j) => {
      el.append(text("tp-cat", c, "b"));
      r.cells[j].forEach((x) => {
        const cell = h("span", "tp-cell" + (x.x ? " tp-x" : !x.a ? " tp-none" : !x.ok ? " tp-bad" : ""), text("tp-a", x.a || "-"));
        if (x.v) cell.append(text("tp-v", "x" + x.v, "i"));
        if (x.p) cell.append(text("tp-p", "+" + x.p, "i"));
        el.append(cell);
      });
    });
    el.append(text("tp-cat", say(ctx, "total"), "b"), r.gain.map((g) => text("tp-sum", "+" + g, "b")));
    el.append(text("tp-cat", say(ctx, "all"), "b"), r.total.map((g) => text("tp-sum", String(g), "b")));
    return el;
  }

  function host(el, game, ctx) {
    const write = game.phase === "write";
    paint(el, JSON.stringify({ ...game, left: null }), () => [
      head(ctx, game),
      write
        ? h("div", "tp-center", text("tp-foot", say(ctx, "write")), text("tp-letter", game.letter, "h1"), cats(game), names(ctx, game.done))
        : [text("tp-foot", say(ctx, "review") + " · " + game.letter + " · " + say(ctx, "review_hint")), grid(ctx, game)],
    ]);
    const secs = clock(el, game, ctx);
    const seen = el.tpSeen || {};
    if (!write && game.phase !== seen.phase) ctx.sound("reveal");
    if (write && secs > 0 && secs <= 5 && secs !== seen.secs) ctx.sound("tick");
    el.tpSeen = { phase: game.phase, secs };
  }

  function writer(ctx, game) {
    const inputs = game.cats.map((c, j) => {
      const input = document.createElement("input");
      input.type = "text";
      input.maxLength = MAX;
      input.autocomplete = "off";
      input.value = game.mine[j] || "";
      input.placeholder = say(ctx, "placeholder", { l: game.letter });
      input.setAttribute("aria-label", c);
      input.dataset.k = "c" + j;
      input.enterKeyHint = j < game.cats.length - 1 ? "next" : "done";
      return input;
    });
    const send = h("button", "", say(ctx, "send"));
    const stop = h("button", "tp-stop", say(ctx, "stop_btn"));
    send.type = stop.type = "button";
    send.dataset.k = "send";
    stop.dataset.k = "stop";
    const update = () => {
      stop.disabled = !inputs.every((i) => i.value.trim());
      send.textContent = say(ctx, "send");
    };
    inputs.forEach((i) => i.addEventListener("input", update));
    const push = async () => {
      const ok = await ctx.send({ type: "answer", answers: inputs.map((i) => i.value) });
      if (ok) {
        ctx.sound("lock");
        send.textContent = say(ctx, "sent");
      }
      return ok;
    };
    send.addEventListener("click", push);
    stop.addEventListener("click", async () => {
      stop.disabled = true;
      if (await push()) await ctx.send({ type: "stop" });
      update();
    });
    update();
    return [
      h("div", "tp-me", text("tp-letter", game.letter, "h1")),
      h("div", "tp-fields", game.cats.map((c, j) => h("label", "tp-field", text("", c, "span"), inputs[j]))),
      h("div", "tp-bar", send, stop),
    ];
  }

  function voter(ctx, game) {
    const mine = new Set(game.voted.map(([i, j]) => i + "|" + j));
    return [
      text("tp-foot", say(ctx, "tap")),
      h("div", "tp-list", game.cats.map((c, j) => h("section", "tp-sec", text("tp-cat", c, "h2"),
        game.review.cells[j].map((x, i) => {
          const own = i === game.me;
          const b = h("button", "tp-pick" + (x.x ? " tp-x" : "") + (mine.has(i + "|" + j) ? " tp-on" : ""),
            text("", (own ? say(ctx, "yours") : game.review.players[i]) + ": " + (x.a || "-"), "span"),
            x.v ? text("tp-v", "x" + x.v, "i") : null, x.p ? text("tp-p", "+" + x.p, "i") : null);
          b.type = "button";
          b.dataset.k = "v" + i + "-" + j;
          b.disabled = own || !x.ok;
          b.addEventListener("click", () => ctx.send({ type: "veto", player: i, cat: j }).then((ok) => ok && ctx.sound("lock")));
          return b;
        })))),
    ];
  }

  function phone(el, game, ctx) {
    const write = game.phase === "write";
    const key = write ? "w|" + game.round : JSON.stringify({ ...game, left: null });
    paint(el, key, () => [write ? head(ctx, game) : null, h("div", "tp-phone", write ? writer(ctx, game) : voter(ctx, game))]);
    clock(el, game, ctx);
  }

  G.register("tomapan", { host, phone });
})();
