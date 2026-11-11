"use strict";

window.G = { games: {}, register(id, view) { this.games[id] = view; } };

const POLL_MS = 1000;
const CONFETTI = 24;
const DIRS = { ArrowUp: [0, -1], ArrowDown: [0, 1], ArrowLeft: [-1, 0], ArrowRight: [1, 0] };
let $app, $toast, timer, toastTimer, topEl, gameEl;
let session = load("galagie");
let view = null, roomLang = null, shellKey = "", pollGen = 0, busy = false, lastCount = -1, lastPhase = "";

function load(k) { try { return JSON.parse(localStorage.getItem(k)); } catch { return null; } }
function store(k, v) { try { v == null ? localStorage.removeItem(k) : localStorage.setItem(k, JSON.stringify(v)); } catch {} }
function setSession(s) { session = s; store("galagie", s); }

function lang() {
  if (roomLang) return roomLang;
  return (navigator.language || "").toLowerCase().startsWith("ro") ? "ro" : "en";
}
const t = (key, vars = {}) => I18N[lang()][key].replace(/\{(\w+)\}/g, (_, k) => vars[k]);
const errText = (msg) => I18N[lang()].errors[msg] || msg;

function h(tag, attrs = {}, ...kids) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v == null || v === false) continue;
    if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else if (k === "class") el.className = v;
    else el.setAttribute(k, v === true ? "" : v);
  }
  for (const c of kids.flat()) if (c != null && c !== false) el.append(c instanceof Node ? c : document.createTextNode(String(c)));
  return el;
}
const show = (...nodes) => $app.replaceChildren(...nodes.flat().filter(Boolean));

async function api(method, path, body) {
  const headers = { "Content-Type": "application/json" };
  if (session) headers["X-Player"] = session.pid;
  const r = await fetch(path, { method, headers, body: body ? JSON.stringify(body) : undefined });
  let d = {};
  try { d = await r.json(); } catch {}
  if (!r.ok) { const e = new Error(d.error || "Something went wrong"); e.status = r.status; throw e; }
  return d;
}

function toast(msg) {
  $toast.textContent = msg;
  $toast.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => ($toast.hidden = true), 3000);
}

async function poll() {
  clearTimeout(timer);
  const gen = ++pollGen;
  if (!session) return;
  try {
    const v = await api("GET", "/api/rooms/" + session.code);
    if (gen !== pollGen) return;
    render(v);
  } catch (e) {
    if (gen !== pollGen) return;
    if (e.status === 404) return closed();
    if (e.status === 429) toast(errText(e.message));
  }
  if (session && !document.hidden) timer = setTimeout(poll, POLL_MS);
}

async function send(body) {
  if (!session) return false;
  try {
    await api("POST", `/api/rooms/${session.code}/action`, body);
    return true;
  } catch (e) {
    if (e.status === 404) closed();
    else toast(errText(e.message));
    return false;
  } finally {
    poll();
  }
}

function reset() {
  view = null; shellKey = ""; topEl = gameEl = null; lastCount = -1; lastPhase = "";
  document.body.classList.remove("tv");
}

async function enter(make, role) {
  if (busy) return;
  busy = true;
  try {
    const d = await make();
    setSession({ code: d.code, pid: d.pid, role });
    reset();
    history.replaceState(null, "", "/r/" + d.code);
    poll();
  } catch (e) { toast(errText(e.message)); }
  busy = false;
}

async function newParty(endOld) {
  if (endOld && session) await api("POST", `/api/rooms/${session.code}/action`, { type: "end" }).catch(() => {});
  enter(() => api("POST", "/api/rooms", {}), "host");
}

function render(v) {
  view = v;
  roomLang = v.settings.lang;
  document.documentElement.lang = roomLang;
  if (v.role !== session.role) setSession({ ...session, role: v.role });
  if (v.role === "moved") return moved();
  const host = v.role === "host";
  document.body.classList.toggle("tv", host || v.role === "screen_pending");
  if (host && lastCount >= 0 && v.players.length > lastCount) Sound.play("join");
  if (host && v.phase === "results" && lastPhase && lastPhase !== "results") Sound.play("fanfare");
  const samePhase = lastPhase === v.phase;
  lastCount = v.players.length;
  lastPhase = v.phase;
  const playing = v.phase === "playing" && v.game;
  const key = JSON.stringify({ ...v, game: null });
  if (key !== shellKey) {
    shellKey = key;
    const focused = document.activeElement && document.activeElement.dataset ? document.activeElement.dataset.k : null;
    if (playing) {
      if (!gameEl || !gameEl.isConnected) {
        topEl = h("div", { class: "top" });
        gameEl = h("div", { class: "game" });
        show(topEl, gameEl);
      }
      topEl.replaceChildren(...[bar(v), allowDialog(v)].filter(Boolean));
    } else {
      topEl = gameEl = null;
      show(screen(v), allowDialog(v));
    }
    refocus(samePhase ? focused : null);
  }
  const game = playing && G.games[v.game_id];
  if (game) game[host ? "host" : "phone"](gameEl, v.game, ctx(v));
}

function refocus(k) {
  const all = [...$app.querySelectorAll("[data-k]")];
  const same = k && all.find((el) => el.dataset.k === k && !el.disabled);
  if (same) return same.focus({ preventScroll: true });
  const lost = !document.activeElement || document.activeElement === document.body;
  const auto = $app.querySelector("[data-auto]:not([disabled])");
  if (lost && auto && document.body.classList.contains("tv")) auto.focus({ preventScroll: true });
}

const ctx = (v) => ({
  lang: v.settings.lang,
  send,
  sound: Sound.play,
  t: (d) => (v.settings.lang in d ? d[v.settings.lang] : d.en),
  me: v.me,
  vip: v.vip,
  controller: v.controller,
  players: v.players,
});

const joinUrl = (code) => location.origin + "/r/" + code;
const ready = (v) => v.players.filter((p) => !p.away && !p.waiting).length;
const currentGame = (v) => v.games.find((g) => g.id === v.game_id);
const logo = (size = "") => h("div", { class: "logo " + size }, "GALAGIE!");
const ticket = (code) => h("div", { class: "ticket" }, h("span", { class: "label" }, t("code")), h("b", {}, code));
const button = (label, onclick, attrs = {}) => h("button", { type: "button", onclick, ...attrs }, label);
const message = (title, text, ...extra) => h("div", { class: "message" }, logo("big"), h("h1", {}, t(title)), h("p", {}, t(text)), ...extra);
const homeButton = () => button(t("home"), () => homeScreen(), { class: "ghost", "data-k": "home" });

function screen(v) {
  if (v.role === "screen_pending") return message("pending_title", "pending_text", ticket(v.code));
  if (v.phase === "lobby") return v.role === "host" ? hostLobby(v) : phoneLobby(v);
  if (v.phase === "results") return results(v);
  return message("waiting_title", "waiting_text");
}

function qr(code) {
  try {
    const q = qrcode(0, "M");
    q.addData(joinUrl(code));
    q.make();
    return h("img", { class: "qr", src: q.createDataURL(8, 0), alt: t("scan") + ": " + joinUrl(code) });
  } catch { return null; }
}

function shareBox(code) {
  const url = joinUrl(code);
  const link = h("p", { class: "link" }, url.replace(/^https?:\/\//, ""));
  const btn = button(t("share"), async () => {
    try {
      if (navigator.share) return await navigator.share({ title: "GALAGIE!", text: t("invite"), url });
      await navigator.clipboard.writeText(url);
      btn.textContent = t("copied");
      setTimeout(() => (btn.textContent = t("share")), 2000);
    } catch (e) {
      if (e && e.name === "AbortError") return;
      getSelection().selectAllChildren(link);
    }
  }, { class: "ghost", "data-k": "share" });
  return h("div", { class: "share" }, link, btn);
}

function stickers(players) {
  return h("ul", { class: "stickers" }, players.map((p) =>
    h("li", { class: "sticker" + (p.vip ? " vip" : "") + (p.away ? " away" : "") },
      h("span", {}, p.name),
      p.vip ? h("b", { class: "tag" }, t("vip")) : null,
      p.away ? h("i", { class: "tag" }, t("away")) : null)));
}

function muteButton() {
  const b = button("", () => { Sound.setMuted(!Sound.muted()); label(); }, { class: "ghost mute", "data-k": "mute" });
  const label = () => (b.textContent = t(Sound.muted() ? "sound_off" : "sound_on"));
  label();
  return b;
}

function choice(k, label, on, body) {
  return button(label, () => send({ type: "settings", ...body }), { class: "pill" + (on ? " on" : ""), "aria-pressed": String(on), "data-k": k });
}
const group = (label, ...buttons) => h("div", { class: "group", role: "group", "aria-label": label }, h("span", { class: "label" }, label), ...buttons);

function startBlock(v) {
  const g = currentGame(v);
  const can = ready(v) >= g.min;
  return [
    button(t("start"), () => send({ type: "start" }), { class: "big", disabled: !can, "data-k": "start", "data-auto": true }),
    can ? null : h("p", { class: "hint" }, t("need", { n: g.min })),
  ];
}

function hostLobby(v) {
  const s = v.settings;
  return h("div", { class: "lobby" },
    h("section", { class: "join-side" },
      logo(),
      h("div", { class: "qr-card" }, qr(v.code), h("p", {}, t("scan"))),
      ticket(v.code),
      shareBox(v.code)),
    h("section", { class: "room-side" },
      h("div", { class: "head" }, h("h2", {}, t("players")), h("span", { class: "count" }, t("count", { n: v.players.length }))),
      stickers(v.players),
      h("div", { class: "settings" },
        group(t("language"), choice("lang-ro", "RO", s.lang === "ro", { lang: "ro" }), choice("lang-en", "EN", s.lang === "en", { lang: "en" })),
        group(t("mode"), choice("family", t("family"), !s.spicy, { spicy: false }), choice("spicy", t("spicy"), s.spicy, { spicy: true })),
        group(t("game"), v.games.map((g) => choice("game-" + g.id,
          [h("span", {}, g.names[s.lang] || g.id), h("small", {}, t("game_info", g))], g.id === v.game_id, { game: g.id })))),
      h("div", { class: "go" }, startBlock(v), muteButton())));
}

function phoneLobby(v) {
  return h("div", { class: "phone-lobby" },
    logo(),
    ticket(v.code),
    stickers(v.players),
    v.vip
      ? h("div", { class: "card vip-card" }, h("h2", {}, t("vip_you")), h("p", {}, t("vip_hint")), startBlock(v),
          button(t("end"), () => send({ type: "end" }), { class: "ghost", "data-k": "end" }))
      : h("p", { class: "wait" }, t("wait_vip")),
    shareBox(v.code));
}

function bar(v) {
  const host = v.role === "host";
  if (!host && !v.vip) return null;
  return h("div", { class: "bar" },
    host ? logo() : null,
    host ? ticket(v.code) : null,
    h("span", { class: "grow" }),
    button(t("next"), () => send({ type: "next" }), { "data-k": "next", "data-auto": true }),
    button(t("end"), () => send({ type: "end" }), { class: "ghost", "data-k": "end" }),
    host ? muteButton() : null);
}

function allowDialog(v) {
  const sid = v.screen_requests[0];
  if (!sid) return null;
  return h("div", { class: "backdrop" },
    h("div", { class: "card dialog", role: "alertdialog", "aria-modal": "true", "aria-labelledby": "allow-q" },
      h("h2", { id: "allow-q" }, t("allow_q")),
      h("p", {}, t("allow_text")),
      h("div", { class: "actions" },
        button(t("allow"), () => send({ type: "allow_screen", sid }), { "data-k": "allow" }),
        button(t("deny"), () => send({ type: "deny_screen", sid }), { class: "ghost", "data-k": "deny" }))));
}

function confetti() {
  return h("div", { class: "confetti", "aria-hidden": "true" }, Array.from({ length: CONFETTI }, (_, i) => {
    const piece = h("i");
    piece.style.setProperty("--i", i);
    return piece;
  }));
}

function results(v) {
  const top = v.scores.length ? v.scores[0].points : 0;
  const winners = top > 0 ? v.scores.filter((s) => s.points === top).map((s) => s.name) : [];
  return h("div", { class: "results" },
    winners.length ? confetti() : null,
    h("h1", {}, t("results")),
    winners.length ? h("div", { class: "card winner" },
      h("span", { class: "label" }, t("winner")),
      h("strong", {}, winners.join(" & ")),
      h("span", { class: "points" }, t("points", { n: top }))) : null,
    h("ol", { class: "ranking" }, v.scores.map((s) => h("li", {}, h("span", {}, s.name), h("b", {}, s.points)))),
    v.controller ? h("div", { class: "actions" },
      button(t("again"), () => send({ type: "again" }), { "data-k": "again", "data-auto": true }),
      button(t("end"), () => send({ type: "end" }), { class: "ghost", "data-k": "end" }),
      v.role === "host" ? button(t("new_party"), () => newParty(true), { class: "alt", "data-k": "new" }) : null) : null);
}

function stop() {
  clearTimeout(timer);
  pollGen++;
  setSession(null);
}

function closed() {
  stop();
  history.replaceState(null, "", "/");
  const tv = document.body.classList.contains("tv");
  reset();
  document.body.classList.toggle("tv", tv);
  show(message("closed_title", "closed_text",
    button(t("new_party"), () => newParty(false), { "data-k": "new", "data-auto": true }), homeButton()));
  refocus(null);
}

function moved() {
  stop();
  history.replaceState(null, "", "/");
  show(message("moved_title", "moved_text", homeButton()));
}

function codeInput(code) {
  return h("input", { id: "code", class: "code-in", maxlength: 8, autocomplete: "off", autocapitalize: "characters",
    autocorrect: "off", spellcheck: "false", value: code, "data-k": "code" });
}

function readCode(input) {
  const c = input.value.replace(/\s+/g, "").toUpperCase();
  if (/^[A-Z2-9]{6}$/.test(c)) return c;
  toast(t("bad_code"));
  return null;
}

function homeScreen(code = "") {
  reset();
  roomLang = null;
  document.documentElement.lang = lang();
  if (!code) history.replaceState(null, "", "/");
  const codeIn = codeInput(code);
  const nameIn = h("input", { id: "name", maxlength: 20, autocomplete: "nickname", "data-k": "name" });
  const join = (e) => {
    e.preventDefault();
    const c = readCode(codeIn);
    const n = nameIn.value.trim();
    if (!c) return;
    if (!n) return toast(errText("Pick a nickname"));
    enter(() => api("POST", `/api/rooms/${c}/join`, { name: n }), "player");
  };
  show(h("div", { class: "home" },
    logo("big"),
    h("p", { class: "tagline" }, t("tagline")),
    h("form", { class: "card join", onsubmit: join },
      h("label", { for: "code" }, t("code")), codeIn,
      h("label", { for: "name" }, t("nickname")), nameIn,
      h("button", { type: "submit", "data-k": "join" }, t("join"))),
    h("div", { class: "tv-actions" },
      button(t("new_party"), () => newParty(false), { class: "alt", "data-k": "new" }),
      h("p", { class: "hint" }, t("new_party_hint")),
      button(t("use_tv"), tvScreen, { class: "ghost", "data-k": "tv" }))));
  if (code) nameIn.focus();
}

function tvScreen() {
  reset();
  document.body.classList.add("tv");
  history.replaceState(null, "", "/tv");
  const codeIn = codeInput("");
  const connect = (e) => {
    e.preventDefault();
    const c = readCode(codeIn);
    if (c) enter(() => api("POST", `/api/rooms/${c}/screen`, {}), "screen_pending");
  };
  show(h("div", { class: "home" },
    logo("big"),
    h("h1", {}, t("tv_title")),
    h("p", { class: "tagline" }, t("tv_hint")),
    button(t("new_party"), () => newParty(false), { class: "big", "data-k": "new", "data-auto": true }),
    h("form", { class: "card join", onsubmit: connect },
      h("label", { for: "code" }, t("code")), codeIn,
      h("button", { type: "submit", class: "alt", "data-k": "connect" }, t("connect"))),
    button(t("back"), () => homeScreen(), { class: "ghost", "data-k": "back" })));
  refocus(null);
}

function center(el) {
  const r = el.getBoundingClientRect();
  return { x: r.left + r.width / 2, y: r.top + r.height / 2 };
}

function arrows(e) {
  const d = DIRS[e.key];
  if (!d || e.altKey || e.ctrlKey || e.metaKey || e.shiftKey) return;
  const cur = document.activeElement;
  if (d[0] && cur && cur.matches("input, textarea") && cur.value) return;
  const scope = document.querySelector(".backdrop") || document;
  const all = [...scope.querySelectorAll("button:not([disabled]), input:not([disabled]), textarea:not([disabled]), a[href], [tabindex='0']")]
    .filter((el) => el.getClientRects().length);
  if (!all.length) return;
  e.preventDefault();
  if (!all.includes(cur)) return all[0].focus();
  const a = center(cur);
  let best = null, bestScore = Infinity;
  for (const el of all) {
    const b = center(el);
    const dx = b.x - a.x, dy = b.y - a.y;
    const along = dx * d[0] + dy * d[1];
    if (el === cur || along <= 1) continue;
    const score = along + Math.abs(dx * d[1] + dy * d[0]);
    if (score < bestScore) { bestScore = score; best = el; }
  }
  if (best) best.focus();
}

document.addEventListener("DOMContentLoaded", () => {
  $app = document.getElementById("app");
  $toast = document.getElementById("toast");
  document.addEventListener("keydown", arrows);
  document.addEventListener("visibilitychange", () => { if (!document.hidden) poll(); });
  const m = location.pathname.match(/^\/r\/([A-Za-z2-9]{6})$/);
  const code = m ? m[1].toUpperCase() : "";
  if (session && session.code && (!code || code === session.code)) return poll();
  if (location.pathname === "/tv") return tvScreen();
  homeScreen(code);
});
