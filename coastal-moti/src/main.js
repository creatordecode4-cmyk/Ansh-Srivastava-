// Entry point: detect the device, load settings, start the game.
import { createGame } from './game.js';
import { isMobile } from './engine/device.js';
import { loadSettings } from './save/settings.js';

const errorEl = document.getElementById('error');

try {
  const mobile = isMobile();
  const settings = loadSettings({ quality: mobile ? 'low' : 'medium', muted: false });
  const game = createGame({ canvas: document.getElementById('game'), mobile, settings });
  game.start();
  window.__moti = game; // handy for debugging and automated smoke tests
} catch (err) {
  console.error(err);
  errorEl.textContent = 'This device or browser could not start 3D graphics (WebGL).';
  errorEl.hidden = false;
}

// PWA: offline after the first visit. Service workers need https or localhost.
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('sw.js').catch((e) => console.warn('SW register failed', e));
  });
}
