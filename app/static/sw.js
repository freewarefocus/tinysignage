// TinySignage Service Worker — full offline support for the player
// Player page & assets: cache-first with background update (stale-while-revalidate)
// Media files: cache-first (immutable UUID filenames)

var CACHE_NAME = 'tinysignage-player-v4';

// Self-contained offline fallback player — served when the player page is not
// in cache AND the network is down. Reads playlist from localStorage and plays
// cached media via the SW media fetch handler. Graceful degradation: no zones,
// no triggers, no effects — just simple crossfade playback.
var OFFLINE_FALLBACK_HTML =
    '<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">' +
    '<meta name="viewport" content="width=device-width,initial-scale=1">' +
    '<title>TinySignage</title>' +
    '<style>' +
    '*{margin:0;padding:0;box-sizing:border-box}' +
    'body{background:#000;overflow:hidden;width:100vw;height:100vh}' +
    '#player{position:relative;width:100%;height:100%}' +
    '.layer{position:absolute;top:0;left:0;width:100%;height:100%;' +
    'opacity:0;transition:opacity 1s ease;display:flex;align-items:center;justify-content:center}' +
    '.layer.active{opacity:1}' +
    '.layer img,.layer video{max-width:100%;max-height:100%;object-fit:contain}' +
    '#splash{position:absolute;top:0;left:0;width:100%;height:100%;' +
    'display:flex;flex-direction:column;align-items:center;justify-content:center;' +
    'color:#888;font-family:sans-serif;text-align:center}' +
    '#splash h1{color:#aaa;font-weight:400;font-size:2em;margin-bottom:.5em}' +
    '#splash p{font-size:.9em}' +
    '#status-indicator{position:fixed;bottom:8px;right:8px;width:10px;height:10px;' +
    'border-radius:50%;background:#f44}' +
    '</style></head><body>' +
    '<div id="player">' +
    '<div id="layer-a" class="layer"></div>' +
    '<div id="layer-b" class="layer"></div>' +
    '<div id="splash"><h1>TinySignage</h1><p id="splash-status">Loading cached content\u2026</p></div>' +
    '<div id="status-indicator" title="Offline"></div>' +
    '</div>' +
    '<script>' +
    '(function(){' +
    'var splash=document.getElementById("splash");' +
    'var splashStatus=document.getElementById("splash-status");' +
    'var layerA=document.getElementById("layer-a");' +
    'var layerB=document.getElementById("layer-b");' +
    'var layers=[layerA,layerB];' +
    'var current=0;' +
    'var playlist,serverUrl,idx=0;' +
    'try{playlist=JSON.parse(localStorage.getItem("tinysignage_playlist"));}catch(e){}' +
    'try{serverUrl=localStorage.getItem("tinysignage_server_url")||"";}catch(e){}' +
    'if(!playlist||!playlist.items||playlist.items.length===0){' +
    'splashStatus.textContent="No cached content available.";' +
    'setTimeout(function(){location.reload()},30000);return;}' +
    'splash.style.display="none";' +
    'function mediaUrl(item){return serverUrl+"/media/"+item.uri;}' +
    'function showItem(item){' +
    'var next=1-current;var layer=layers[next];layer.innerHTML="";' +
    'var url=mediaUrl(item);' +
    'var dur=(item.duration||10)*1000;' +
    'if(item.type==="video"){' +
    'var v=document.createElement("video");' +
    'v.src=url;v.autoplay=true;v.playsInline=true;' +
    'v.addEventListener("ended",function(){advance();});' +
    'v.addEventListener("error",function(){setTimeout(advance,2000);});' +
    'layer.appendChild(v);' +
    '}else{' +
    'var img=document.createElement("img");' +
    'img.src=url;' +
    'img.addEventListener("error",function(){setTimeout(advance,2000);});' +
    'layer.appendChild(img);' +
    'setTimeout(advance,dur);' +
    '}' +
    'layers[current].classList.remove("active");' +
    'layer.classList.add("active");' +
    'current=next;' +
    '}' +
    'function advance(){idx=(idx+1)%playlist.items.length;showItem(playlist.items[idx]);}' +
    'showItem(playlist.items[0]);' +
    'setTimeout(function(){location.reload()},60000);' +
    '})();' +
    '</script></body></html>';

// --- Install: precache player page, then activate immediately ---
self.addEventListener('install', function (event) {
    event.waitUntil(
        caches.open(CACHE_NAME).then(function (cache) {
            return Promise.all([
                cache.add('/player').catch(function () {}),
                cache.add('/static/player.css').catch(function () {}),
                cache.add('/static/player.js').catch(function () {})
            ]);
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

// --- Fetch: cache-first for player (stale-while-revalidate), cache-first for media ---
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

    // Player page & assets: cache-first with background update (stale-while-revalidate)
    // Serves cached version instantly, then silently updates cache for next load.
    event.respondWith(
        caches.open(CACHE_NAME).then(function (cache) {
            return cache.match(event.request, { ignoreSearch: true }).then(function (cached) {
                // Always try to update cache in the background
                var networkUpdate = fetch(event.request).then(function (response) {
                    if (response.ok) cache.put(event.request, response.clone());
                    return response;
                });

                if (cached) {
                    // Serve stale immediately; background update is fire-and-forget
                    networkUpdate.catch(function () {});
                    return cached;
                }

                // No cache — race network against a short timeout
                return Promise.race([
                    networkUpdate.catch(function () { return null; }),
                    new Promise(function (resolve) {
                        setTimeout(function () { resolve(null); }, 3000);
                    })
                ]).then(function (response) {
                    if (response) return response;
                    // Network failed or timed out — serve functional offline fallback
                    if (isPlayerPage) {
                        return new Response(OFFLINE_FALLBACK_HTML, {
                            status: 200,
                            headers: { 'Content-Type': 'text/html; charset=utf-8' }
                        });
                    }
                    return new Response('', { status: 503, statusText: 'Offline' });
                });
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
