// TinySignage Service Worker — full offline support for the player
// Player page & assets: network-first with precaching on install
// Media files: cache-first (immutable UUID filenames)

var CACHE_NAME = 'tinysignage-player-v2';

// --- Install: precache player page, then activate immediately ---
self.addEventListener('install', function (event) {
    event.waitUntil(
        caches.open(CACHE_NAME).then(function (cache) {
            return cache.add('/player').catch(function () {
                // Precache may fail on very first install — that's OK,
                // player.js will populate the cache from the page side.
            });
        }).then(function () {
            return self.skipWaiting();
        })
    );
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

// --- Fetch: network-first for player, cache-first for media ---
self.addEventListener('fetch', function (event) {
    var url = new URL(event.request.url);

    var isPlayerPage = url.pathname === '/player';
    var isPlayerAsset = url.pathname.match(/^\/static\/player\./);
    var isMedia = url.pathname.match(/^\/media\//);

    if (!isPlayerPage && !isPlayerAsset && !isMedia) {
        return; // passthrough — let browser handle normally
    }

    // Media files: cache-first (immutable content-addressed filenames)
    if (isMedia) {
        event.respondWith(
            caches.match(event.request).then(function (cached) {
                if (cached) {
                    return cached;
                }
                return fetch(event.request).then(function (response) {
                    if (response.ok) {
                        var responseClone = response.clone();
                        caches.open(CACHE_NAME).then(function (cache) {
                            cache.put(event.request, responseClone);
                        });
                    }
                    return response;
                });
            })
        );
        return;
    }

    // Player page & assets: network-first
    event.respondWith(
        fetch(event.request).then(function (response) {
            if (response.ok) {
                var responseClone = response.clone();
                caches.open(CACHE_NAME).then(function (cache) {
                    cache.put(event.request, responseClone);
                });
            }
            return response;
        }).catch(function () {
            // Network failed — try the cache
            return caches.match(event.request, { ignoreSearch: true }).then(function (cached) {
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
                return new Response('', { status: 503, statusText: 'Offline' });
            });
        })
    );
});

// --- Message handler: receive media URLs from player.js ---
self.addEventListener('message', function (event) {
    var data = event.data;
    if (!data || !data.type) return;

    if (data.type === 'CACHE_MEDIA') {
        var urls = data.urls || [];
        if (urls.length === 0) return;
        event.waitUntil(
            caches.open(CACHE_NAME).then(function (cache) {
                return Promise.all(urls.map(function (url) {
                    return cache.match(url).then(function (existing) {
                        if (existing) return; // already cached
                        return cache.add(url).catch(function () {
                            // Individual media fetch may fail — skip it
                        });
                    });
                }));
            })
        );
    }

    if (data.type === 'CLEANUP_MEDIA') {
        var activeUrls = data.urls || [];
        var activeSet = {};
        activeUrls.forEach(function (u) { activeSet[u] = true; });
        event.waitUntil(
            caches.open(CACHE_NAME).then(function (cache) {
                return cache.keys().then(function (requests) {
                    return Promise.all(requests.filter(function (req) {
                        var path = new URL(req.url).pathname;
                        return path.match(/^\/media\//) && !activeSet[path];
                    }).map(function (req) {
                        return cache.delete(req);
                    }));
                });
            })
        );
    }
});
