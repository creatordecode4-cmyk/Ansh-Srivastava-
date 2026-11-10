// Sound hooks. Every game event calls audio.play('<name>').
// Right now each name is a tiny synthesized beep (original, generated in code, no files).
// To use a real sound later: audio.load('attack', 'assets/audio/attack.ogg') and it replaces the beep.
// Remember to list every sound file in licenses/ASSETS.md.

const SYNTH = {
  // Also available: 'thunder' and 'static' (filtered noise) and the looping 'storm' ambience.
  //            wave        start Hz  end Hz  seconds  volume
  step:        ['triangle',  90,       60,     0.05,    0.05],
  attack:      ['square',    260,      110,    0.11,    0.10],
  hit:         ['square',    180,      70,     0.09,    0.14],
  hurt:        ['sawtooth',  140,      60,     0.20,    0.16],
  dodge:       ['triangle',  320,      640,    0.14,    0.10],
  shoot:       ['square',    700,      200,    0.07,    0.07],
  shakti:      ['sine',      420,      980,    0.28,    0.16],
  burst:       ['sawtooth',  90,       420,    0.55,    0.20],
  burstReady:  ['sine',      660,      990,    0.25,    0.12],
  tool:        ['sine',      880,      880,    0.18,    0.10],
  denied:      ['square',    130,      110,    0.12,    0.08],
  ui:          ['sine',      600,      700,    0.06,    0.08],
  radio:       ['square',    1200,     1200,   0.04,    0.05],
  alert:       ['sawtooth',  500,      760,    0.18,    0.10],
  down:        ['triangle',  200,      50,     0.35,    0.14],
  objective:   ['sine',      520,      1040,   0.30,    0.14],
  unlock:      ['sine',      440,      1320,   0.50,    0.16],
  levelUp:     ['sine',      500,      1500,   0.60,    0.16],
  missionStart:    ['sine',  330,      660,    0.40,    0.14],
  missionComplete: ['sine',  440,      1100,   0.80,    0.16],
  flicker:     ['sawtooth',  60,       45,     0.22,    0.12],
  pickup:      ['sine',      700,      1400,   0.25,    0.14],
};

export function createAudio(settings) {
  let ctx = null;
  const samples = new Map();
  const pendingLoads = [];

  // Browsers only allow audio after a user gesture.
  function unlock() {
    if (!ctx) {
      const AC = window.AudioContext || window.webkitAudioContext;
      if (!AC) return;
      try { ctx = new AC(); } catch { return; }
      pendingLoads.splice(0).forEach(([name, url]) => load(name, url));
    }
    if (ctx.state === 'suspended') ctx.resume().catch(() => {});
    refresh();
  }
  window.addEventListener('pointerdown', unlock);
  window.addEventListener('keydown', unlock);

  async function load(name, url) {
    if (!ctx) { pendingLoads.push([name, url]); return; }
    try {
      const data = await (await fetch(url)).arrayBuffer();
      samples.set(name, await ctx.decodeAudioData(data));
    } catch (e) { console.warn(`Could not load sound "${name}"`, e); }
  }

  function play(name) {
    if (settings.muted || !ctx || ctx.state !== 'running') return;
    const t = ctx.currentTime;
    const gain = ctx.createGain();
    gain.connect(ctx.destination);
    const buffer = samples.get(name);
    if (buffer) {
      const src = ctx.createBufferSource();
      src.buffer = buffer;
      gain.gain.value = 0.8;
      src.connect(gain);
      src.start(t);
      return;
    }
    const s = SYNTH[name];
    if (!s) return;
    const [type, f0, f1, dur, vol] = s;
    const osc = ctx.createOscillator();
    osc.type = type;
    osc.frequency.setValueAtTime(f0, t);
    osc.frequency.exponentialRampToValueAtTime(Math.max(1, f1), t + dur);
    gain.gain.setValueAtTime(vol, t);
    gain.gain.exponentialRampToValueAtTime(0.0001, t + dur);
    osc.connect(gain);
    osc.start(t);
    osc.stop(t + dur + 0.02);
  }

  // ---- noise-based sounds: storm ambience, thunder, radio static (all synthesized) ----
  let noise = null, ambient = null, wantAmbient = null;
  function noiseBuffer() {
    if (noise) return noise;
    noise = ctx.createBuffer(1, ctx.sampleRate * 2, ctx.sampleRate);
    const d = noise.getChannelData(0);
    for (let i = 0; i < d.length; i++) d[i] = Math.random() * 2 - 1;
    return noise;
  }
  function noiseSource(filterType, freq, loop) {
    const src = ctx.createBufferSource();
    src.buffer = noiseBuffer(); src.loop = loop;
    const filter = ctx.createBiquadFilter();
    filter.type = filterType; filter.frequency.value = freq;
    const gain = ctx.createGain();
    src.connect(filter); filter.connect(gain); gain.connect(ctx.destination);
    return { src, gain, filter };
  }
  function stopAmbient() {
    if (!ambient) return;
    for (const n of ambient) { try { n.src.stop(); } catch { /* already stopped */ } n.gain.disconnect(); }
    ambient = null;
  }
  // Looping background sound for a level. name: 'storm' or null.
  function setAmbient(name) {
    wantAmbient = name;
    refresh();
  }
  // Call after the mute setting changes or audio unlocks.
  function refresh() {
    if (!ctx) return;
    const on = wantAmbient === 'storm' && !settings.muted;
    if (!on) { stopAmbient(); return; }
    if (ambient) return;
    const rain = noiseSource('highpass', 2200, true); rain.gain.gain.value = 0.035;
    const wind = noiseSource('lowpass', 320, true); wind.gain.gain.value = 0.22;
    const lfo = ctx.createOscillator(), depth = ctx.createGain();   // gusts
    lfo.frequency.value = 0.13; depth.gain.value = 0.12;
    lfo.connect(depth); depth.connect(wind.gain.gain);
    rain.src.start(); wind.src.start(); lfo.start();
    ambient = [rain, wind, { src: lfo, gain: depth }];
  }
  function burst(filterType, freq, volume, seconds) {
    if (settings.muted || !ctx || ctx.state !== 'running') return;
    const n = noiseSource(filterType, freq, true), t = ctx.currentTime;
    n.gain.gain.setValueAtTime(volume, t);
    n.gain.gain.exponentialRampToValueAtTime(0.0001, t + seconds);
    n.src.start(t); n.src.stop(t + seconds + 0.05);
  }
  SYNTH.thunder = SYNTH.static = null; // noise sounds: listed as hooks, handled below
  const synthPlay = play;
  function playAny(name) {
    if (name === 'thunder') return burst('lowpass', 160, 0.9, 2.6);
    if (name === 'static') return burst('highpass', 1800, 0.12, 0.45);
    synthPlay(name);
  }

  return { play: playAny, load, setAmbient, refresh, names: Object.keys(SYNTH) };
}
