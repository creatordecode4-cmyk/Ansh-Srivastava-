// Simple service worker: precache the app shell, then network-first with an offline fallback.
// Bump CACHE_VERSION on every release so players get the new files.
const CACHE_VERSION = 'coastal-moti-v0.2.0';

// App shell: everything needed to boot. Add new source files and assets here.
const PRECACHE = [
  './',
  'index.html',
  'manifest.json',
  'vendor/three.module.min.js',
  'src/ai/bot.js',
  'src/audio/audio.js',
  'src/engine/cameraRig.js',
  'src/engine/combat.js',
  'src/engine/device.js',
  'src/engine/engine.js',
  'src/engine/events.js',
  'src/engine/health.js',
  'src/engine/input.js',
  'src/engine/mathx.js',
  'src/engine/player.js',
  'src/engine/quality.js',
  'src/engine/sea.js',
  'src/engine/shaktis.js',
  'src/engine/sky.js',
  'src/engine/world.js',
  'src/game.js',
  'src/main.js',
  'src/missions/missionManager.js',
  'src/missions/systemsCheck.js',
  'src/save/save.js',
  'src/save/settings.js',
  'src/ui/base.css',
  'src/ui/controlsHint.js',
  'src/ui/hud.css',
  'src/ui/hud.js',
  'src/ui/missionCard.js',
  'src/ui/pauseMenu.js',
  'src/ui/radio.js',
  'src/ui/touchControls.js',
  'assets/icons/icon.svg',
  'assets/icons/icon-192.png',
  'assets/icons/icon-512.png',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_VERSION).then((cache) => cache.addAll(PRECACHE)).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE_VERSION).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

// Network first, cache as the offline fallback. Online players always get the newest files;
// offline players get the last version they loaded.
self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET' || new URL(req.url).origin !== self.location.origin) return;
  event.respondWith(
    fetch(req).then((res) => {
      if (res.ok) {
        const copy = res.clone();
        caches.open(CACHE_VERSION).then((cache) => cache.put(req, copy));
      }
      return res;
    }).catch(() => caches.match(req, { ignoreSearch: true }).then((hit) => hit || Response.error()))
  );
});
