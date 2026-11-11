"use strict";

const Sound = (() => {
  let ac = null;
  const unlock = () => {
    if (!ac) {
      try { ac = new (window.AudioContext || window.webkitAudioContext)(); } catch { return; }
    }
    if (ac.state === "suspended") ac.resume();
  };
  addEventListener("pointerdown", unlock);
  addEventListener("keydown", unlock);

  const muted = () => { try { return localStorage.getItem("partygames.mute") === "1"; } catch { return false; } };
  const setMuted = (on) => { try { localStorage.setItem("partygames.mute", on ? "1" : "0"); } catch {} };

  function envelope(at, dur, peak) {
    const g = ac.createGain();
    g.gain.setValueAtTime(0.0001, at);
    g.gain.exponentialRampToValueAtTime(peak, at + 0.01);
    g.gain.exponentialRampToValueAtTime(0.0001, at + dur);
    g.connect(ac.destination);
    return g;
  }

  function tone(freq, start, dur, type = "square", peak = 0.12, to = freq) {
    const at = ac.currentTime + start;
    const o = ac.createOscillator();
    o.type = type;
    o.frequency.setValueAtTime(freq, at);
    o.frequency.exponentialRampToValueAtTime(to, at + dur);
    o.connect(envelope(at, dur, peak));
    o.start(at);
    o.stop(at + dur + 0.02);
  }

  function noise(start, dur, peak, freq) {
    const at = ac.currentTime + start;
    const buf = ac.createBuffer(1, Math.ceil(ac.sampleRate * dur), ac.sampleRate);
    const data = buf.getChannelData(0);
    for (let i = 0; i < data.length; i++) data[i] = Math.random() * 2 - 1;
    const src = ac.createBufferSource();
    src.buffer = buf;
    const band = ac.createBiquadFilter();
    band.type = "bandpass";
    band.frequency.value = freq;
    src.connect(band);
    band.connect(envelope(at, dur, peak));
    src.start(at);
  }

  const effects = {
    join: () => { tone(660, 0, 0.09); tone(990, 0.09, 0.16); },
    tick: () => tone(1400, 0, 0.04, "square", 0.06),
    reveal: () => { tone(220, 0, 0.35, "sawtooth", 0.08, 880); noise(0.3, 0.2, 0.2, 3000); },
    clap: () => { noise(0, 0.08, 0.5, 1500); noise(0.05, 0.12, 0.3, 1100); },
    sweep: () => { tone(300, 0, 0.6, "triangle", 0.15, 1800); [0.1, 0.25, 0.4].forEach((s) => noise(s, 0.1, 0.35, 1400)); },
    fanfare: () => [523, 659, 784, 1047].forEach((f, i) => tone(f, i * 0.14, i === 3 ? 0.6 : 0.14, "square", 0.1)),
  };

  return {
    muted,
    setMuted,
    play(name) {
      if (!ac || muted() || !effects[name]) return;
      try { effects[name](); } catch {}
    },
  };
})();
