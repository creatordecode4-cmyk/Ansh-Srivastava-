// Simple offline-first service worker.
// Bump CACHE_VERSION on every release so players get the new files.
const CACHE_VERSION = 'coastal-moti-v0.1.0';

// App shell: everything needed to boot. Add new source files and assets here.
const PRECACHE = [
  './',
  'index.html',
  'manifest.json',
  'vendor/three.module.min.js',
  'src/main.js',
  'src/engine/engine.js',
  'src/engine/device.js',
  'src/engine/quality.js',
  'src/engine/sky.js',
  'src/engine/sea.js',
  'src/save/settings.js',
  'src/ui/base.css',
  'src/ui/controlsHint.js',
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

// Cache first, then network; anything fetched from our own origin is cached for next time.
self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET' || new URL(req.url).origin !== self.location.origin) return;
  event.respondWith(
    caches.match(req, { ignoreSearch: true }).then((hit) => hit || fetch(req).then((res) => {
      if (res.ok) {
        const copy = res.clone();
        caches.open(CACHE_VERSION).then((cache) => cache.put(req, copy));
      }
      return res;
    }))
  );
});
