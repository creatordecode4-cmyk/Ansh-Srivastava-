// Entry point. Skeleton only: sky + sea + quality toggle. No gameplay yet.
import { createEngine } from './engine/engine.js';
import { isMobile } from './engine/device.js';
import { QUALITY_ORDER } from './engine/quality.js';
import { loadSettings, saveSettings } from './save/settings.js';
import { showControlsHint } from './ui/controlsHint.js';

const canvas = document.getElementById('game');
const qualityBtn = document.getElementById('quality-btn');
const fpsEl = document.getElementById('fps');
const errorEl = document.getElementById('error');

function fail(message) {
  errorEl.textContent = message;
  errorEl.hidden = false;
}

try {
  const mobile = isMobile();
  const settings = loadSettings({ quality: mobile ? 'low' : 'medium' });

  const engine = createEngine(canvas, settings.quality);
  showControlsHint(document.getElementById('controls-hint'), mobile);

  const label = (q) => `Quality: ${q[0].toUpperCase()}${q.slice(1)}`;
  qualityBtn.textContent = label(settings.quality);
  qualityBtn.addEventListener('click', () => {
    const next = QUALITY_ORDER[(QUALITY_ORDER.indexOf(settings.quality) + 1) % QUALITY_ORDER.length];
    settings.quality = next;
    engine.setQuality(next);
    saveSettings(settings);
    qualityBtn.textContent = label(next);
  });

  engine.onFps((fps) => { fpsEl.textContent = `${fps} FPS`; });
  engine.start();

  // Handy for debugging and automated smoke tests.
  window.__moti = engine;
} catch (err) {
  console.error(err);
  fail('This device or browser could not start 3D graphics (WebGL).');
}

// PWA: offline after first visit. Service workers need https or localhost.
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('sw.js').catch((e) => console.warn('SW register failed', e));
  });
}
