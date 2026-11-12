"use strict";

const DrawPad = (() => {
  const SIZE = 256;
  const COLORS = ["#111111", "#ffffff", "#e63946", "#ff2e88", "#1d4ed8", "#ffd60a", "#2a9d3f", "#8b5a2b"];
  const SIZES = [2, 5, 10];
  const MAX_PNG = 42600;
  const ICONS = {
    pen: ["M4 20l4-1 11-11-3-3L5 16z", "M14 6l3 3"],
    fill: ["M4 11l7-7 8 8-7 7z", "M4 11h15", "M8 7L5 4", "M20 15c0 0-2 2.6-2 4a2 2 0 0 0 4 0c0-1.4-2-4-2-4z"],
    erase: ["M14.5 3.5l6 6-9.5 9.5H6l-3-3a1.5 1.5 0 0 1 0-2z", "M8.5 9.5l6 6", "M11 19h10"],
    undo: ["M9 14L4 9l5-5", "M4 9h10a6 6 0 0 1 0 12h-3"],
    redo: ["M15 14l5-5-5-5", "M20 9H10a6 6 0 0 0 0 12h3"],
  };

  function h(tag, cls, ...kids) {
    const el = document.createElement(tag);
    if (cls) el.className = cls;
    for (const c of kids.flat(Infinity)) if (c != null && c !== false) el.append(c);
    return el;
  }
  function icon(name) {
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("viewBox", "0 0 24 24");
    svg.setAttribute("aria-hidden", "true");
    for (const d of ICONS[name]) {
      const p = document.createElementNS("http://www.w3.org/2000/svg", "path");
      p.setAttribute("d", d);
      svg.append(p);
    }
    return svg;
  }
  function button(label, onClick, cls, k) {
    const b = h("button", cls);
    b.type = "button";
    b.append(label);
    b.dataset.k = k;
    b.addEventListener("click", onClick);
    return b;
  }
  const rgb = (c) => [1, 3, 5].map((i) => parseInt(c.slice(i, i + 2), 16));

  return (labels, aria, onInk = () => {}) => {
    const canvas = h("canvas", "im-canvas");
    canvas.width = canvas.height = SIZE;
    canvas.setAttribute("aria-label", aria);
    const g = canvas.getContext("2d", { willReadFrequently: true });
    g.fillStyle = "#ffffff";
    g.fillRect(0, 0, SIZE, SIZE);
    const state = { color: COLORS[0], size: SIZES[1], tool: "pen", undo: [], redo: [], down: false, last: null };
    const snap = () => {
      state.undo.push(g.getImageData(0, 0, SIZE, SIZE));
      if (state.undo.length > 30) state.undo.shift();
      state.redo = [];
    };
    const pos = (e) => {
      const r = canvas.getBoundingClientRect();
      return [Math.round(((e.clientX - r.left) * SIZE) / r.width), Math.round(((e.clientY - r.top) * SIZE) / r.height)];
    };
    const ink = () => {
      g.strokeStyle = g.fillStyle = state.tool === "erase" ? "#ffffff" : state.color;
      g.lineWidth = state.size * 2;
      g.lineCap = g.lineJoin = "round";
    };
    const dot = (p) => {
      ink();
      g.beginPath();
      g.arc(p[0], p[1], state.size, 0, 7);
      g.fill();
    };
    const flood = (x, y) => {
      if (x < 0 || y < 0 || x >= SIZE || y >= SIZE) return;
      const img = g.getImageData(0, 0, SIZE, SIZE);
      const d = img.data;
      const at = (y * SIZE + x) * 4;
      const from = [d[at], d[at + 1], d[at + 2]];
      const to = rgb(state.color);
      if (from.every((v, i) => v === to[i])) return;
      const same = (i) => Math.abs(d[i] - from[0]) < 48 && Math.abs(d[i + 1] - from[1]) < 48 && Math.abs(d[i + 2] - from[2]) < 48;
      const stack = [x + y * SIZE];
      const seen = new Uint8Array(SIZE * SIZE);
      while (stack.length) {
        const n = stack.pop();
        if (seen[n]) continue;
        seen[n] = 1;
        const i = n * 4;
        if (!same(i)) continue;
        d[i] = to[0]; d[i + 1] = to[1]; d[i + 2] = to[2]; d[i + 3] = 255;
        const px = n % SIZE;
        if (px > 0) stack.push(n - 1);
        if (px < SIZE - 1) stack.push(n + 1);
        if (n >= SIZE) stack.push(n - SIZE);
        if (n < SIZE * (SIZE - 1)) stack.push(n + SIZE);
      }
      g.putImageData(img, 0, 0);
    };
    canvas.addEventListener("pointerdown", (e) => {
      e.preventDefault();
      snap();
      const p = pos(e);
      if (state.tool === "fill") {
        flood(p[0], p[1]);
        return onInk();
      }
      state.down = true;
      state.last = p;
      canvas.setPointerCapture(e.pointerId);
      dot(p);
    });
    canvas.addEventListener("pointermove", (e) => {
      if (!state.down) return;
      const p = pos(e);
      ink();
      g.beginPath();
      g.moveTo(state.last[0], state.last[1]);
      g.lineTo(p[0], p[1]);
      g.stroke();
      state.last = p;
    });
    const stop = () => {
      if (!state.down) return;
      state.down = false;
      onInk();
    };
    canvas.addEventListener("pointerup", stop);
    canvas.addEventListener("pointercancel", stop);

    const toolButtons = {};
    const pick = (t) => {
      state.tool = t;
      for (const [k, b] of Object.entries(toolButtons)) b.setAttribute("aria-pressed", String(k === t));
    };
    const swatches = h("div", "im-tools im-colors", COLORS.map((c, i) => {
      const b = button("", () => {
        state.color = c;
        if (state.tool === "erase") pick("pen");
        swatches.querySelectorAll("button").forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
      }, "im-swatch", "color-" + i);
      b.style.setProperty("--swatch", c);
      b.setAttribute("aria-label", c);
      b.setAttribute("aria-pressed", String(i === 0));
      return b;
    }));
    for (const t of ["pen", "fill", "erase"]) {
      toolButtons[t] = button(icon(t), () => pick(t), "im-tool", "tool-" + t);
      toolButtons[t].setAttribute("aria-label", labels[t]);
    }
    pick("pen");
    const sizeButtons = SIZES.map((s, i) => {
      const b = button(h("i", "im-dot"), () => {
        state.size = s;
        sizeButtons.forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
      }, "im-tool im-size", "size-" + i);
      b.style.setProperty("--dot", 4 + i * 5 + "px");
      b.setAttribute("aria-label", labels.size(i + 1));
      b.setAttribute("aria-pressed", String(s === state.size));
      return b;
    });
    const history = (from, to) => () => {
      if (!from().length) return;
      to().push(g.getImageData(0, 0, SIZE, SIZE));
      g.putImageData(from().pop(), 0, 0);
      onInk();
    };
    const undo = button(icon("undo"), history(() => state.undo, () => state.redo), "im-tool", "undo");
    const redo = button(icon("redo"), history(() => state.redo, () => state.undo), "im-tool", "redo");
    undo.setAttribute("aria-label", labels.undo);
    redo.setAttribute("aria-label", labels.redo);

    const png = () => {
      const img = g.getImageData(0, 0, SIZE, SIZE);
      const d = img.data;
      const palette = COLORS.map(rgb);
      const greys = palette.slice(0, 2);
      for (let i = 0; i < d.length; i += 4) {
        let best = palette[0], score = Infinity;
        for (const c of Math.max(d[i], d[i + 1], d[i + 2]) - Math.min(d[i], d[i + 1], d[i + 2]) < 40 ? greys : palette) {
          const s = (d[i] - c[0]) ** 2 + (d[i + 1] - c[1]) ** 2 + (d[i + 2] - c[2]) ** 2;
          if (s < score) { score = s; best = c; }
        }
        d[i] = best[0]; d[i + 1] = best[1]; d[i + 2] = best[2]; d[i + 3] = 255;
      }
      const out = h("canvas");
      out.width = out.height = SIZE;
      out.getContext("2d").putImageData(img, 0, 0);
      const data = out.toDataURL("image/png").split(",")[1];
      return data.length > MAX_PNG ? null : data;
    };

    return {
      board: h("div", "im-board", canvas),
      swatches,
      tools: h("div", "im-tools", toolButtons.pen, toolButtons.fill, toolButtons.erase, sizeButtons, undo, redo),
      png,
    };
  };
})();
