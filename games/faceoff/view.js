"use strict";

(() => {
  const MAX = 80;
  const CLAPS = 3;
  const TYPING = ["answer", "final_answer"];
  const WAITING = ["answer", "vote", "final_answer", "final_vote"];
  const S = {
    round: { ro: "Runda {n}", en: "Round {n}" },
    double: { ro: "Runda 2 · puncte duble", en: "Round 2 · double points" },
    final: { ro: "Finala", en: "Final" },
    hurry: { ro: "Hai, grabiti-va! Mai sunt {n} s", en: "Hurry up! {n} s left" },
    write: { ro: "Scrieti pe telefoane!", en: "Write on your phones!" },
    write_hint: { ro: "Fiecare primeste doua intrebari.", en: "Everyone gets two prompts." },
    final_write: { ro: "Toti raspund la aceeasi intrebare:", en: "Everyone answers the same prompt:" },
    voted: { ro: "{d} din {n} au votat", en: "{d} of {n} voted" },
    vote_hint: { ro: "Votati pe telefon, aveti cate 3 aplauze", en: "Vote on your phones, 3 claps each" },
    ran_away: { ro: "fugit de raspuns", en: "ran away" },
    walkover: { ro: "FARA ADVERSAR", en: "WALKOVER" },
    nobody: { ro: "Nimeni n-a raspuns. Mai departe!", en: "Nobody answered. Moving on!" },
    sweep: { ro: "SWEEP!", en: "SWEEP!" },
    standings: { ro: "Clasament", en: "Standings" },
    prompt_of: { ro: "Intrebarea {a} din {b}", en: "Prompt {a} of {b}" },
    placeholder: { ro: "Ceva amuzant...", en: "Something funny..." },
    your_answer: { ro: "Raspunsul tau", en: "Your answer" },
    send: { ro: "Trimite", en: "Send" },
    done: { ro: "Gata! Uita-te la TV", en: "Done, look at the TV" },
    look: { ro: "Uita-te la TV", en: "Look at the TV" },
    on_screen: { ro: "Raspunsul tau e pe ecran", en: "Your answer is on screen" },
    others_vote: { ro: "Ceilalti voteaza acum.", en: "The others are voting now." },
    pick: { ro: "Atinge ca sa aplauzi!", en: "Tap to clap!" },
    claps_left: { ro: "Aplauze ramase: {n}", en: "Claps left: {n}" },
    yours: { ro: "al tau", en: "yours" },
  };

  function h(tag, cls, ...kids) {
    const el = document.createElement(tag);
    if (cls) el.className = cls;
    for (const c of kids.flat(Infinity)) if (c != null && c !== false) el.append(c);
    return el;
  }
  const fill = (s, vars) => s.replace(/\{(\w+)\}/g, (_, k) => vars[k]);
  const say = (ctx, key, vars = {}) => fill(ctx.t(S[key]), vars);
  const sum = (a) => (a || []).reduce((x, y) => x + y, 0);
  const code = () => location.pathname.split("/").pop();
  const draftKey = (i) => "galagie.draft." + code() + "." + i;
  const draft = (i, text) => {
    try {
      if (text === undefined) return sessionStorage.getItem(draftKey(i)) || "";
      text ? sessionStorage.setItem(draftKey(i), text) : sessionStorage.removeItem(draftKey(i));
    } catch { return ""; }
  };
  function clearDrafts() {
    try {
      const prefix = "galagie.draft." + code() + ".";
      Object.keys(sessionStorage).filter((k) => k.startsWith(prefix)).forEach((k) => sessionStorage.removeItem(k));
    } catch {}
  }

  function paint(el, key, build) {
    if (el.foKey === key) return false;
    const active = document.activeElement;
    const k = active && el.contains(active) ? active.dataset.k : null;
    el.foKey = key;
    el.replaceChildren(h("div", "fo", build()));
    const again = k && el.querySelector('[data-k="' + k + '"]:not([disabled])');
    if (again) again.focus({ preventScroll: true });
    return true;
  }

  function fit(el) {
    for (const li of el.querySelectorAll(".fo-grid li")) {
      const t = li.querySelector(".fo-text");
      for (let size = 92; size >= 50 && li.scrollHeight > li.clientHeight + 1; size -= 8) t.style.fontSize = size + "%";
    }
  }

  function clock(el, game, ctx) {
    const live = WAITING.includes(game.phase) && game.left != null;
    const secs = live ? Math.ceil(game.left) : 0;
    const c = el.querySelector(".fo-clock");
    if (c) {
      c.textContent = live ? secs : "";
      c.classList.toggle("fo-low", live && secs <= 5);
    }
    const b = el.querySelector(".fo-hurry");
    if (b) {
      b.hidden = !(live && game.hurry);
      b.parentNode.classList.toggle("fo-rush", !b.hidden);
      b.textContent = say(ctx, "hurry", { n: secs });
    }
    return secs;
  }

  function head(ctx, game) {
    const label = game.round === "final" ? say(ctx, "final") : game.round === 2 ? say(ctx, "double") : say(ctx, "round", { n: game.round });
    const hurry = h("p", "fo-hurry");
    hurry.setAttribute("role", "status");
    return h("div", "fo-head", h("span", "fo-badge", label), hurry, h("span", "fo-clock"));
  }

  const text = (cls, s) => {
    const el = h("p", cls);
    el.textContent = s;
    return el;
  };

  function names(ctx, done) {
    return h("ul", "stickers fo-names", ctx.players.filter((p) => !p.waiting).map((p) => {
      const ok = done.includes(p.name);
      return h("li", "sticker" + (ok ? " fo-ok" : ""), text("", p.name), ok ? h("b", "tag", "OK") : null);
    }));
  }

  function card(ctx, game, side) {
    const answer = game.answers[side];
    const reveal = game.phase === "reveal";
    const box = h("div", "fo-side fo-" + "ab"[side]);
    const c = h("div", "fo-card" + (answer == null ? " fo-gone" : ""), text("", answer == null ? say(ctx, "ran_away") : answer));
    if (reveal && game.sweep === side) c.append(h("b", "fo-stamp", say(ctx, "sweep")));
    if (reveal && game.walkover && answer != null) c.append(h("b", "fo-stamp", say(ctx, "walkover")));
    box.append(c);
    if (game.voters) {
      const bar = h("i");
      bar.style.width = Math.min(100, (100 * game.claps[side]) / (game.voters * CLAPS)) + "%";
      box.append(h("div", "fo-meter", bar, h("b", "", String(game.claps[side]))));
    }
    if (reveal) box.append(h("div", "fo-by", text("", game.authors[side]), h("b", "", "+" + game.points[side])));
    return box;
  }

  function duel(ctx, game) {
    const both = game.answers.every((a) => a == null);
    let foot = null;
    if (game.phase === "vote") foot = say(ctx, "vote_hint") + " · " + say(ctx, "voted", { d: game.voters_done, n: game.voters });
    if (game.phase === "reveal" && both) foot = say(ctx, "nobody");
    return [
      text("fo-prompt", game.prompt),
      h("div", "fo-duel", card(ctx, game, 0), h("span", "fo-vs", "VS"), card(ctx, game, 1)),
      foot ? text("fo-foot", foot) : null,
    ];
  }

  function grid(game) {
    const reveal = game.phase === "final_reveal";
    const top = Math.max(1, ...game.claps);
    return h("ol", "fo-grid" + (game.answers.length > 8 ? " fo-two" : ""), game.answers.map((a, j) => {
      const by = reveal ? h("span", "fo-who", text("", game.authors[j]), h("b", "", "+" + game.points[j])) : null;
      return h("li", reveal && game.claps[j] === top ? "fo-best" : "", text("fo-text", a), by, h("b", "fo-claps", String(game.claps[j])));
    }));
  }

  function standings(ctx, game) {
    return [
      h("h1", "fo-title", say(ctx, "standings")),
      h("ol", "ranking", game.standings.map((s) => h("li", "", h("span", "", s.name), h("b", "", String(s.points))))),
    ];
  }

  function hostBody(ctx, game) {
    const p = game.phase;
    if (p === "answer") return [h("h1", "fo-title", say(ctx, "write")), text("fo-foot", say(ctx, "write_hint")), names(ctx, game.done)];
    if (p === "final_answer") return [text("fo-foot", say(ctx, "final_write")), text("fo-prompt", game.prompt), names(ctx, game.done)];
    if (p === "vote" || p === "reveal") return duel(ctx, game);
    if (p === "final_vote" || p === "final_reveal") return [text("fo-prompt fo-small", game.prompt), grid(game)];
    if (p === "scores") return standings(ctx, game);
    return [];
  }

  function host(el, game, ctx) {
    const moment = game.phase + "|" + (game.prompt || "") + "|" + JSON.stringify(game.answers || null);
    if (paint(el, JSON.stringify({ ...game, left: null }), () => [head(ctx, game), hostBody(ctx, game)])) fit(el);
    const seen = el.foSeen || {};
    const claps = sum(game.claps);
    if (seen.moment !== moment) {
      if (game.phase === "reveal") ctx.sound(game.sweep != null ? "sweep" : "reveal");
      if (game.phase === "final_reveal") ctx.sound("reveal");
    } else if (claps > seen.claps) ctx.sound("clap");
    const secs = clock(el, game, ctx);
    if (WAITING.includes(game.phase) && secs > 0 && secs <= 5 && secs !== seen.secs) ctx.sound("tick");
    el.foSeen = { moment, claps, secs };
  }

  function message(ctx, key, sub) {
    return h("div", "fo-msg", h("h1", "", say(ctx, key)), sub ? text("", say(ctx, sub)) : null);
  }

  function writer(ctx, game, prompt) {
    const area = document.createElement("textarea");
    area.className = "fo-area";
    area.rows = 3;
    area.placeholder = say(ctx, "placeholder");
    area.setAttribute("aria-label", say(ctx, "your_answer"));
    area.dataset.k = "answer";
    area.value = draft(prompt.i);
    const count = h("span", "fo-count");
    const sendBtn = h("button", "", say(ctx, "send"));
    sendBtn.type = "submit";
    sendBtn.dataset.k = "send";
    const update = () => {
      const chars = [...area.value];
      if (chars.length > MAX) area.value = chars.slice(0, MAX).join("");
      count.textContent = Math.min(chars.length, MAX) + "/" + MAX;
      sendBtn.disabled = !area.value.trim();
    };
    area.addEventListener("input", () => { update(); draft(prompt.i, area.value); });
    area.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); form.requestSubmit(); }
    });
    const form = h("form", "fo-write", area, h("div", "fo-row", count, sendBtn));
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      if (!area.value.trim() || sendBtn.disabled) return;
      sendBtn.disabled = true;
      if (await ctx.send({ type: "answer", i: prompt.i, text: area.value })) draft(prompt.i, "");
      else update();
    });
    update();
    const mine = game.prompts;
    const n = mine.indexOf(prompt) + 1;
    const ask = h("div", "fo-ask", mine.length > 1 ? h("small", "", say(ctx, "prompt_of", { a: n, b: mine.length })) : null, text("", prompt.text));
    return [ask, form];
  }

  function dots(ctx, left) {
    const row = h("div", "fo-dots", Array.from({ length: CLAPS }, (_, j) => h("i", j < left ? "on" : "")));
    row.setAttribute("aria-label", say(ctx, "claps_left", { n: left }));
    row.setAttribute("role", "img");
    return row;
  }

  function choice(label, cls, k, onclick, extra) {
    const b = h("button", "fo-pick " + cls, extra, text("", label));
    b.type = "button";
    b.dataset.k = k;
    b.addEventListener("click", onclick);
    return b;
  }

  function phoneBody(ctx, game) {
    const p = game.phase;
    if (TYPING.includes(p)) {
      const next = game.prompts.find((q) => !q.answered);
      return next ? writer(ctx, game, next) : message(ctx, "done");
    }
    if (p === "vote") {
      if (game.author) return message(ctx, "on_screen", "others_vote");
      if (!game.claps_left) return message(ctx, "done");
      return [
        h("div", "fo-row", text("fo-step", say(ctx, "pick")), dots(ctx, game.claps_left)),
        h("div", "fo-list fo-duo", game.answers.map((a, side) => choice(a, "fo-" + "ab"[side], "side-" + side, () => ctx.send({ type: "clap", side })))),
      ];
    }
    if (p === "final_vote") {
      if (!game.claps_left) return message(ctx, "done");
      const list = h("div", "fo-list", game.answers.map((a, j) => {
        const b = choice(a, "fo-" + "ab"[j % 2], "target-" + j, () => ctx.send({ type: "clap", target: j }), j === game.own ? h("small", "", say(ctx, "yours")) : null);
        b.disabled = j === game.own;
        return b;
      }));
      return [text("fo-ask fo-small", game.prompt), h("div", "fo-row", text("fo-step", say(ctx, "pick")), dots(ctx, game.claps_left)), list];
    }
    return message(ctx, "look");
  }

  function phone(el, game, ctx) {
    const typing = TYPING.includes(game.phase);
    const current = typing ? game.prompts.find((q) => !q.answered) : null;
    const key = typing
      ? game.phase + "|" + (current ? current.i + "|" + current.text : "done")
      : JSON.stringify({ phase: game.phase, prompt: game.prompt, answers: game.answers, claps: game.claps_left, author: game.author, own: game.own });
    if (el.foKey !== key && !typing) clearDrafts();
    paint(el, key, () => {
      const live = WAITING.includes(game.phase);
      return [live ? head(ctx, game) : null, h("div", "fo-phone", phoneBody(ctx, game))];
    });
    clock(el, game, ctx);
  }

  G.register("faceoff", { host, phone });
})();
