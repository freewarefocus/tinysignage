/**
 * TinySignage Player — Polling Architecture
 *
 * Polls the server for playlist updates, caches playlist JSON in localStorage,
 * relies on browser HTTP cache for media files. Owns its own playback timer.
 * Survives indefinitely without a network connection.
 */

(function () {
    'use strict';

    // --- Configuration ---
    const POLL_INTERVAL = 30000;      // 30s between polls
    const HEARTBEAT_INTERVAL = 60000; // 60s between heartbeats
    const MAX_VIDEO_DURATION = 300;   // 5 min cap for videos with duration=0
    const PRELOAD_AHEAD = 1;          // Number of assets to preload ahead
    const PLAYER_VERSION = '0.4.0';

    // Base URL for split deployment — read from <meta name="server-url">
    const serverMeta = document.querySelector('meta[name="server-url"]');
    const baseUrl = (serverMeta ? serverMeta.content : '').replace(/\/+$/, '');

    function apiUrl(path) {
        return baseUrl + path;
    }

    // --- State ---
    let currentLayer = 'a';
    let currentTransitionType = 'fade';
    let playlist = [];                // Active playlist items
    let playlistHash = '';
    let currentIndex = -1;
    let settings = {};
    let pollTimer = null;
    let playbackTimer = null;
    let online = false;
    let deviceId = '';
    let deviceToken = '';
    let startTime = Date.now();
    let heartbeatTimer = null;

    // --- Auth ---
    function authHeaders() {
        const headers = { 'Content-Type': 'application/json' };
        if (deviceToken) {
            headers['Authorization'] = 'Bearer ' + deviceToken;
        }
        return headers;
    }

    function authFetch(url, options = {}) {
        if (deviceToken) {
            options.headers = options.headers || {};
            options.headers['Authorization'] = 'Bearer ' + deviceToken;
        }
        return fetch(url, options);
    }

    function storeCredentials(id, token) {
        deviceId = id;
        deviceToken = token;
        localStorage.setItem('tinysignage_device_id', id);
        localStorage.setItem('tinysignage_device_token', token);
    }

    function cleanUrl() {
        const url = new URL(window.location);
        url.search = '';
        history.replaceState(null, '', url);
    }

    // --- Pairing ---
    async function pairWithCode(code) {
        const resp = await fetch(apiUrl('/api/devices/register'), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ code: code }),
        });
        if (!resp.ok) {
            const err = await resp.json().catch(() => ({}));
            throw new Error(err.detail || 'Pairing failed');
        }
        return await resp.json();
    }

    function showPairingOverlay() {
        const overlay = document.getElementById('pairing-overlay');
        overlay.classList.remove('hidden');

        const form = document.getElementById('pairing-form');
        const input = document.getElementById('pairing-code-input');
        const errorEl = document.getElementById('pairing-error');

        input.focus();

        // Force uppercase as user types
        input.addEventListener('input', () => {
            input.value = input.value.toUpperCase().replace(/[^A-Z0-9]/g, '');
        });

        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            const code = input.value.trim();
            if (!code) return;

            errorEl.classList.add('hidden');
            const btn = form.querySelector('button');
            btn.disabled = true;
            btn.textContent = 'Pairing...';

            try {
                const data = await pairWithCode(code);
                storeCredentials(data.device_id, data.token);
                cleanUrl();
                showPairingSuccess(data.device_name || 'Device');
            } catch (err) {
                errorEl.textContent = err.message;
                errorEl.classList.remove('hidden');
                btn.disabled = false;
                btn.textContent = 'Pair Display';
            }
        });
    }

    function showPairingSuccess(deviceName) {
        const overlay = document.getElementById('pairing-overlay');
        const inner = overlay.querySelector('.pairing-inner') || overlay;
        inner.innerHTML = '<div style="text-align:center;padding:2rem;">' +
            '<div style="font-size:2rem;margin-bottom:0.5rem;">&#10003;</div>' +
            '<div style="font-size:1.2rem;color:#fff;">Paired as ' +
            deviceName.replace(/</g, '&lt;').replace(/>/g, '&gt;') +
            '!</div></div>';
        overlay.classList.remove('hidden');
        setTimeout(function () {
            overlay.classList.add('hidden');
            startPlayer();
        }, 2000);
    }

    function hidePairingOverlay() {
        document.getElementById('pairing-overlay').classList.add('hidden');
    }

    // --- Startup ---
    async function init() {
        const params = new URLSearchParams(window.location.search);

        // Priority a: ?token=<token>&device=<id> — fully provisioned
        const urlToken = params.get('token');
        const urlDevice = params.get('device');
        if (urlToken && urlDevice) {
            storeCredentials(urlDevice, urlToken);
            cleanUrl();
            startPlayer();
            return;
        }

        // Priority b: ?pair=<CODE> — pairing mode
        const pairCode = params.get('pair');
        if (pairCode) {
            try {
                const data = await pairWithCode(pairCode);
                storeCredentials(data.device_id, data.token);
                cleanUrl();
                showPairingSuccess(data.device_name || 'Device');
            } catch (err) {
                // Show overlay with error pre-filled
                showPairingOverlay();
                const errorEl = document.getElementById('pairing-error');
                errorEl.textContent = err.message;
                errorEl.classList.remove('hidden');
                const input = document.getElementById('pairing-code-input');
                input.value = pairCode.toUpperCase();
            }
            return;
        }

        // Priority c: localStorage fallback
        const storedId = localStorage.getItem('tinysignage_device_id');
        const storedToken = localStorage.getItem('tinysignage_device_token');
        if (storedId && storedToken) {
            deviceId = storedId;
            deviceToken = storedToken;
            startPlayer();
            return;
        }

        // Priority d: No identity — show pairing prompt
        showPairingOverlay();
    }

    function startPlayer() {
        hidePairingOverlay();
        loadCachedPlaylist();
        poll();                       // First poll immediately
        schedulePoll();
        scheduleHeartbeat();

        if (playlist.length > 0) {
            currentIndex = 0;
            playCurrentAsset();
        }
    }

    // --- Cache ---
    function loadCachedPlaylist() {
        try {
            const cached = localStorage.getItem('tinysignage_playlist');
            if (cached) {
                const data = JSON.parse(cached);
                playlist = data.items || [];
                playlistHash = data.hash || '';
                settings = data.settings || {};
                applySettings(settings);
            }
        } catch (e) {
            console.warn('[TinySignage] Failed to load cached playlist:', e);
        }
    }

    function cachePlaylist(data) {
        try {
            localStorage.setItem('tinysignage_playlist', JSON.stringify(data));
        } catch (e) {
            console.warn('[TinySignage] Failed to cache playlist:', e);
        }
    }

    // --- Polling ---
    function schedulePoll() {
        if (pollTimer) clearTimeout(pollTimer);
        pollTimer = setTimeout(() => {
            poll();
            schedulePoll();
        }, POLL_INTERVAL);
    }

    async function poll() {
        if (!deviceId) {
            setOnlineStatus(false);
            return;
        }

        try {
            const resp = await authFetch(apiUrl(`/api/devices/${deviceId}/playlist`));
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            const data = await resp.json();
            setOnlineStatus(true);

            if (data.hash !== playlistHash) {
                console.log('[TinySignage] Playlist updated:', data.hash);
                const wasEmpty = playlist.length === 0;

                playlist = data.items || [];
                playlistHash = data.hash;
                settings = data.settings || {};
                applySettings(settings);
                cachePlaylist(data);

                // Preload new assets
                preloadAssets();

                if (wasEmpty && playlist.length > 0) {
                    currentIndex = 0;
                    playCurrentAsset();
                } else if (playlist.length === 0) {
                    showSplash();
                    cancelPlayback();
                }
            }
        } catch (e) {
            console.warn('[TinySignage] Poll failed:', e.message);
            setOnlineStatus(false);
        }
    }

    // --- Settings ---
    function applySettings(s) {
        if (s.transition_duration != null) {
            document.documentElement.style.setProperty(
                '--transition-duration', s.transition_duration + 's'
            );
        }
        if (s.transition_type) {
            currentTransitionType = s.transition_type;
        }
    }

    // --- Playback ---
    function playCurrentAsset() {
        if (playlist.length === 0) {
            showSplash();
            return;
        }

        // Wrap index
        if (currentIndex >= playlist.length) currentIndex = 0;
        if (currentIndex < 0) currentIndex = playlist.length - 1;

        const item = playlist[currentIndex];
        const asset = item.asset;
        if (!asset) {
            advance();
            return;
        }

        loadAsset(asset);

        // Schedule next advance based on duration
        const duration = getAssetDuration(asset);
        cancelPlayback();
        playbackTimer = setTimeout(() => advance(), duration * 1000);
        // For videos with duration=0, onended will fire first (before the 300s cap)
    }

    function getAssetDuration(asset) {
        if (asset.duration === 0 && asset.asset_type === 'video') {
            return MAX_VIDEO_DURATION;  // Safety cap; onended will fire first
        }
        return asset.duration || settings.default_duration || 10;
    }

    function advance() {
        cancelPlayback();
        currentIndex++;
        if (currentIndex >= playlist.length) currentIndex = 0;
        playCurrentAsset();
    }

    function cancelPlayback() {
        if (playbackTimer) {
            clearTimeout(playbackTimer);
            playbackTimer = null;
        }
    }

    // --- Asset Loading ---
    function loadAsset(asset) {
        const nextLayerId = currentLayer === 'a' ? 'b' : 'a';
        const nextLayer = document.getElementById(`layer-${nextLayerId}`);
        const currentLayerEl = document.getElementById(`layer-${currentLayer}`);

        cleanupLayer(nextLayer);

        let element;
        if (asset.asset_type === 'image') {
            element = document.createElement('img');
            element.onload = () => {
                setTimeout(() => doTransition(nextLayer, currentLayerEl, nextLayerId), 300);
            };
            element.onerror = () => {
                console.warn('[TinySignage] Image load failed:', asset.uri);
                setTimeout(() => doTransition(nextLayer, currentLayerEl, nextLayerId), 300);
            };
            element.src = `${baseUrl}/media/${asset.uri}`;
        } else if (asset.asset_type === 'video') {
            element = document.createElement('video');
            element.autoplay = true;
            element.muted = true;
            element.playsInline = true;
            element.loop = false;

            element.oncanplay = () => {
                setTimeout(() => doTransition(nextLayer, currentLayerEl, nextLayerId), 300);
            };

            element.onerror = () => {
                console.warn('[TinySignage] Video load failed:', asset.uri);
                advance();
            };

            element.onended = () => {
                advance();
            };

            element.src = `${baseUrl}/media/${asset.uri}`;
        } else if (asset.asset_type === 'url') {
            element = document.createElement('iframe');
            element.onload = () => {
                setTimeout(() => doTransition(nextLayer, currentLayerEl, nextLayerId), 500);
            };
            element.src = asset.uri;
            element.sandbox = 'allow-scripts allow-same-origin';
        }

        if (element) {
            nextLayer.appendChild(element);
        }
    }

    // --- Preloading ---
    function preloadAssets() {
        for (let i = 0; i < Math.min(PRELOAD_AHEAD, playlist.length); i++) {
            const idx = (currentIndex + 1 + i) % playlist.length;
            const asset = playlist[idx]?.asset;
            if (!asset) continue;

            if (asset.asset_type === 'image') {
                const img = new Image();
                img.src = `${baseUrl}/media/${asset.uri}`;
            }
            // Videos and iframes will be loaded on-demand
        }
    }

    // --- Transitions ---
    function doTransition(inLayer, outLayer, newCurrentId) {
        hideSplash();

        const inContent = inLayer.querySelector('video, img, iframe');
        const outContent = outLayer.querySelector('video, img, iframe');

        const isVideoToVideo = (
            inContent?.tagName === 'VIDEO' &&
            outContent?.tagName === 'VIDEO'
        );

        const useCut = currentTransitionType === 'cut' || isVideoToVideo;

        if (useCut) {
            inLayer.style.transition = 'none';
            outLayer.style.transition = 'none';
            inLayer.classList.add('active');
            outLayer.classList.remove('active');
            cleanupLayer(outLayer);
            requestAnimationFrame(() => {
                inLayer.style.transition = '';
                outLayer.style.transition = '';
            });
        } else {
            inLayer.classList.add('active');
            outLayer.classList.remove('active');
            const onTransitionEnd = () => {
                outLayer.removeEventListener('transitionend', onTransitionEnd);
                cleanupLayer(outLayer);
            };
            outLayer.addEventListener('transitionend', onTransitionEnd);
            const duration = parseFloat(
                getComputedStyle(document.documentElement)
                    .getPropertyValue('--transition-duration')
            ) || 1;
            setTimeout(() => {
                outLayer.removeEventListener('transitionend', onTransitionEnd);
                cleanupLayer(outLayer);
            }, (duration + 0.5) * 1000);
        }

        currentLayer = newCurrentId;
    }

    // --- Cleanup ---
    function cleanupLayer(layer) {
        const video = layer.querySelector('video');
        if (video) {
            video.onended = null;
            video.onerror = null;
            video.oncanplay = null;
            video.pause();
            video.removeAttribute('src');
            video.load();
        }
        const img = layer.querySelector('img');
        if (img) {
            img.onload = null;
            img.onerror = null;
        }
        const iframe = layer.querySelector('iframe');
        if (iframe) {
            iframe.onload = null;
        }
        layer.innerHTML = '';
    }

    // --- Status ---
    function setOnlineStatus(isOnline) {
        online = isOnline;
        const indicator = document.getElementById('status-indicator');
        if (indicator) {
            indicator.className = isOnline ? 'status-online' : 'status-offline';
            indicator.title = isOnline ? 'Connected' : 'Offline — playing from cache';
        }
    }

    function showSplash() {
        document.getElementById('splash').classList.remove('hidden');
    }

    function hideSplash() {
        document.getElementById('splash').classList.add('hidden');
    }

    // --- Heartbeat ---
    function scheduleHeartbeat() {
        if (heartbeatTimer) clearInterval(heartbeatTimer);
        sendHeartbeat();  // Send immediately
        heartbeatTimer = setInterval(sendHeartbeat, HEARTBEAT_INTERVAL);
    }

    async function sendHeartbeat() {
        if (!deviceId) return;
        try {
            await authFetch(apiUrl('/api/player/heartbeat'), {
                method: 'POST',
                headers: authHeaders(),
                body: JSON.stringify({
                    device_id: deviceId,
                    player_time: new Date().toISOString(),
                    player_timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
                    player_version: PLAYER_VERSION,
                    uptime_seconds: Math.round((Date.now() - startTime) / 1000),
                }),
            });
        } catch (e) {
            // Offline — silently skip
        }
    }

    // --- Go ---
    init();
})();
