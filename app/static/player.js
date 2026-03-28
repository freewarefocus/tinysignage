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
    const PLAYER_VERSION = '0.2.0';

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
    let startTime = Date.now();
    let heartbeatTimer = null;

    // --- Startup ---
    async function init() {
        deviceId = await fetchDeviceId();
        loadCachedPlaylist();
        poll();                       // First poll immediately
        schedulePoll();
        scheduleHeartbeat();

        if (playlist.length > 0) {
            currentIndex = 0;
            playCurrentAsset();
        }
    }

    async function fetchDeviceId() {
        try {
            const resp = await fetch('/api/devices');
            if (resp.ok) {
                const devices = await resp.json();
                if (devices.length > 0) return devices[0].id;
            }
        } catch (e) { /* offline — will retry on next poll */ }
        // Fall back to cached device ID
        return localStorage.getItem('tinysignage_device_id') || '';
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
            if (deviceId) {
                localStorage.setItem('tinysignage_device_id', deviceId);
            }
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
            deviceId = await fetchDeviceId();
            if (!deviceId) {
                setOnlineStatus(false);
                return;
            }
        }

        try {
            const resp = await fetch(`/api/devices/${deviceId}/playlist`);
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
            element.src = `/media/${asset.uri}`;
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

            element.src = `/media/${asset.uri}`;
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
                img.src = `/media/${asset.uri}`;
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
            await fetch('/api/player/heartbeat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
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
