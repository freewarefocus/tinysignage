// TinySignage Service Worker — offline page caching for the player
// Network-first: always prefer live server, fall back to cache when offline.

var CACHE_NAME = 'tinysignage-player-v1';

// --- Install: activate immediately, no precaching ---
self.addEventListener('install', function (event) {
    self.skipWaiting();
});

// --- Activate: clean old caches, take control of all clients ---
self.addEventListener('activate', function (event) {
    event.waitUntil(
        caches.keys().then(function (names) {
            return Promise.all(
                names.filter(function (name) {
                    return name.startsWith('tinysignage-player-') && name !== CACHE_NAME;
                }).map(function (name) {
                    return caches.delete(name);
                })
            );
        }).then(function () {
            return self.clients.claim();
        })
    );
});

// --- Fetch: network-first for player files, passthrough for everything else ---
self.addEventListener('fetch', function (event) {
    var url = new URL(event.request.url);

    // Only intercept player page and its static assets
    var isPlayerPage = url.pathname === '/player';
    var isPlayerAsset = url.pathname.match(/^\/static\/player\./);

    if (!isPlayerPage && !isPlayerAsset) {
        return; // passthrough — let browser handle normally
    }

    event.respondWith(
        fetch(event.request).then(function (response) {
            // Got a response from the network — cache it and return
            if (response.ok) {
                var responseClone = response.clone();
                caches.open(CACHE_NAME).then(function (cache) {
                    cache.put(event.request, responseClone);
                });
            }
            return response;
        }).catch(function () {
            // Network failed — try the cache
            return caches.match(event.request).then(function (cached) {
                if (cached) {
                    return cached;
                }
                // Nothing in cache for /player — return a minimal offline page
                if (isPlayerPage) {
                    return new Response(
                        '<!DOCTYPE html><html><head><meta charset="utf-8">' +
                        '<meta name="viewport" content="width=device-width,initial-scale=1">' +
                        '<title>TinySignage</title>' +
                        '<style>' +
                        'body{margin:0;background:#111;color:#888;font-family:sans-serif;' +
                        'display:flex;align-items:center;justify-content:center;height:100vh}' +
                        'div{text-align:center}' +
                        'h2{color:#aaa;font-weight:400;margin-bottom:.5em}' +
                        'p{font-size:.9em}' +
                        '</style></head><body>' +
                        '<div><h2>Connecting to server\u2026</h2>' +
                        '<p>Waiting for the CMS to become reachable.</p>' +
                        '<script>setTimeout(function(){location.reload()},10000)</script>' +
                        '</div></body></html>',
                        {
                            status: 200,
                            headers: { 'Content-Type': 'text/html; charset=utf-8' }
                        }
                    );
                }
                // For uncached player assets, return a network error
                return new Response('', { status: 503, statusText: 'Offline' });
            });
        })
    );
});
