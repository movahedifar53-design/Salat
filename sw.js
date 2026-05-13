const CACHE_NAME = 'salat-v9';
const ASSETS = [
  './',
  './index.html',
  './data_birmingham.json',
  './data_london.json',
  './data_toronto.json',
  './manifest.json',
  './icon-192.png',
  './icon-512.png'
];

// Caches from releases that pre-date the in-app update banner.
// Clients running those releases can't react to a "waiting" SW, so when
// we see them we skipWaiting() and force-reload their windows.
const PRE_BANNER_CACHES = ['salat-v6', 'salat-v7'];

self.addEventListener('install', e => {
  e.waitUntil((async () => {
    const cache = await caches.open(CACHE_NAME);
    await cache.addAll(ASSETS);
    const keys = await caches.keys();
    if (keys.some(k => PRE_BANNER_CACHES.includes(k))) {
      // Old client has no banner -- take over immediately.
      await self.skipWaiting();
    }
    // Otherwise wait for SKIP_WAITING from the banner.
  })());
});

self.addEventListener('activate', e => {
  e.waitUntil((async () => {
    const keys = await caches.keys();
    const needsForceReload = keys.some(k => PRE_BANNER_CACHES.includes(k));
    await Promise.all(
      keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k))
    );
    await self.clients.claim();
    if (needsForceReload) {
      const clients = await self.clients.matchAll({ type: 'window' });
      clients.forEach(c => {
        try { c.navigate(c.url); } catch (_) {}
      });
    }
  })());
});

self.addEventListener('message', e => {
  if (e.data && e.data.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }
});

self.addEventListener('fetch', e => {
  e.respondWith(
    caches.match(e.request).then(r => r || fetch(e.request))
  );
});
