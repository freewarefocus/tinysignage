/**
 * TinySignage Player — Polling Architecture with Multi-Zone Support
 *
 * Polls the server for playlist updates, caches playlist JSON in localStorage,
 * relies on browser HTTP cache for media files. Owns its own playback timer.
 * Survives indefinitely without a network connection.
 *
 * When a layout with zones is assigned, each zone runs its own independent
 * playback loop with its own dual-layer crossfade engine.
 */

(function () {
    'use strict';

    // --- Configuration ---
    const POLL_INTERVAL = 30000;      // 30s between polls
    const HEARTBEAT_INTERVAL = 60000; // 60s between heartbeats
    const MAX_VIDEO_DURATION = 300;   // 5 min cap for videos with duration=0
    const PRELOAD_AHEAD = 1;          // Number of assets to preload ahead
    const PLAYER_VERSION = '0.7.0';
    const CAPABILITY_REPORT_INTERVAL = 3600000; // 60 min

    // Base URL for split deployment — read from <meta name="server-url">
    const serverMeta = document.querySelector('meta[name="server-url"]');
    const baseUrl = (serverMeta ? serverMeta.content : '').replace(/\/+$/, '');

    function apiUrl(path) {
        return baseUrl + path;
    }

    // --- State ---
    let currentLayer = 'a';
    let currentTransitionType = 'fade';
    let playlist = [];                // Active playlist items (main/fallback)
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
    let activeOverride = null;
    let overrideExpiryTimer = null;
    let pairingBound = false;

    // --- Transition playlist state ---
    let transitionPlaylist = null;    // Bumper content between schedule changes
    let playingTransition = false;    // Whether we're currently playing a transition playlist
    let transitionIndex = -1;
    let pendingPlaylist = null;       // Main playlist to switch to after transition
    let pendingHash = '';
    let pendingSettings = {};

    // --- Multi-zone state ---
    let activeZones = [];             // Array of zone playback controllers
    let zonesActive = false;          // Whether we're in multi-zone mode

    // --- Trigger engine state ---
    let triggerFlow = null;           // Current trigger flow data from server
    let currentSourcePlaylistId = ''; // Which playlist is currently active in the flow
    let loopCount = 0;               // How many times the current playlist has looped
    let triggerTimeoutTimer = null;   // Timeout trigger timer
    let triggerListenersActive = false; // Whether keyboard listener is registered
    let triggerKeydownHandler = null; // Reference to keydown handler for cleanup

    // --- GPIO bridge state ---
    let gpioWebSocket = null;         // WebSocket connection to GPIO bridge
    let gpioReconnectTimer = null;    // Auto-reconnect timer
    const GPIO_BRIDGE_URL = 'ws://localhost:8765';

    // --- Webhook trigger state ---
    let lastSeenWebhookFires = {};    // { branchId: isoTimestamp } — tracks last processed webhook fire

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

        if (pairingBound) return;
        pairingBound = true;

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
        const inner = overlay.querySelector('.pairing-card') || overlay;
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

        const urlToken = params.get('token');
        const urlDevice = params.get('device');
        if (urlToken && urlDevice) {
            storeCredentials(urlDevice, urlToken);
            cleanUrl();
            startPlayer();
            return;
        }

        const pairCode = params.get('pair');
        if (pairCode) {
            try {
                const data = await pairWithCode(pairCode);
                storeCredentials(data.device_id, data.token);
                cleanUrl();
                showPairingSuccess(data.device_name || 'Device');
            } catch (err) {
                showPairingOverlay();
                const errorEl = document.getElementById('pairing-error');
                errorEl.textContent = err.message;
                errorEl.classList.remove('hidden');
                const input = document.getElementById('pairing-code-input');
                input.value = pairCode.toUpperCase();
            }
            return;
        }

        const storedId = localStorage.getItem('tinysignage_device_id');
        const storedToken = localStorage.getItem('tinysignage_device_token');
        if (storedId && storedToken) {
            deviceId = storedId;
            deviceToken = storedToken;
            startPlayer();
            return;
        }

        showPairingOverlay();
    }

    function startPlayer() {
        hidePairingOverlay();
        loadCachedPlaylist();
        poll();
        schedulePoll();
        scheduleHeartbeat();
        scheduleCapabilityReport();

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

                // Restore trigger flow from cache
                if (data.trigger_flow) {
                    let sourceId = data.trigger_flow.source_playlist_id;
                    const savedState = loadTriggerState();
                    if (savedState && savedState.flowId === data.trigger_flow.id && savedState.sourcePlaylistId) {
                        const savedBranch = data.trigger_flow.branches.find(
                            b => b.target_playlist_id === savedState.sourcePlaylistId
                        );
                        if (savedBranch && savedBranch.target_playlist) {
                            sourceId = savedState.sourcePlaylistId;
                            playlist = savedBranch.target_playlist.items || [];
                            settings = savedBranch.target_playlist.settings || {};
                            applySettings(settings);
                            loopCount = savedState.loopCount || 0;
                        }
                    }
                    initTriggerEngine(data.trigger_flow, sourceId);
                }
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
            if (resp.status === 401) {
                console.warn('[TinySignage] Token rejected (401), clearing credentials');
                localStorage.removeItem('tinysignage_device_id');
                localStorage.removeItem('tinysignage_device_token');
                deviceId = '';
                deviceToken = '';
                cancelPlayback();
                teardownZones();
                teardownTriggerEngine();
                showPairingOverlay();
                return;
            }
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            const data = await resp.json();
            setOnlineStatus(true);

            // --- Emergency override handling ---
            if (data.override) {
                if (data.override.type === 'message') {
                    showEmergencyMessage(data.override);
                    activeOverride = data.override;
                    scheduleOverrideExpiry(data.override);
                    playlistHash = data.hash;
                    cachePlaylist(data);
                    teardownZones();
                    return;
                }
                activeOverride = data.override;
                scheduleOverrideExpiry(data.override);
            } else if (activeOverride) {
                console.log('[TinySignage] Override ended, resuming normal playback');
                activeOverride = null;
                if (overrideExpiryTimer) { clearTimeout(overrideExpiryTimer); overrideExpiryTimer = null; }
                hideEmergencyMessage();
                if (playlist.length > 0) {
                    playCurrentAsset();
                } else {
                    showSplash();
                }
            }

            if (data.hash !== playlistHash) {
                console.log('[TinySignage] Playlist updated:', data.hash);
                const wasEmpty = playlist.length === 0;
                const hadContent = playlist.length > 0;

                hideEmergencyMessage();

                // --- Transition playlist: play bumper before switching ---
                if (hadContent && !playingTransition && data.transition_playlist
                    && data.transition_playlist.items && data.transition_playlist.items.length > 0) {
                    console.log('[TinySignage] Playing transition playlist before switch');
                    pendingPlaylist = data.items || [];
                    pendingHash = data.hash;
                    pendingSettings = data.settings || {};
                    transitionPlaylist = data.transition_playlist.items;
                    playingTransition = true;
                    transitionIndex = 0;
                    cancelPlayback();
                    teardownZones();
                    cachePlaylist(data);
                    playTransitionAsset();
                    return;
                }

                playlist = data.items || [];
                playlistHash = data.hash;
                settings = data.settings || {};
                applySettings(settings);
                cachePlaylist(data);

                // --- Multi-zone handling ---
                if (data.zones && data.zones.length > 0) {
                    setupZones(data.zones, data.items);
                    return;
                } else {
                    teardownZones();
                }

                // --- Trigger engine integration ---
                if (data.trigger_flow) {
                    // Restore source playlist from saved state if resuming same flow
                    let sourceId = data.trigger_flow.source_playlist_id;
                    const savedState = loadTriggerState();
                    if (savedState && savedState.flowId === data.trigger_flow.id && savedState.sourcePlaylistId) {
                        // Find the saved source in the flow's branches as a target
                        const savedBranch = data.trigger_flow.branches.find(
                            b => b.target_playlist_id === savedState.sourcePlaylistId
                        );
                        if (savedBranch && savedBranch.target_playlist) {
                            // Resume on the previously active playlist
                            sourceId = savedState.sourcePlaylistId;
                            playlist = savedBranch.target_playlist.items || [];
                            settings = savedBranch.target_playlist.settings || {};
                            applySettings(settings);
                            loopCount = savedState.loopCount || 0;
                        }
                    }
                    initTriggerEngine(data.trigger_flow, sourceId);
                    checkWebhookTriggers();
                } else if (triggerFlow) {
                    teardownTriggerEngine();
                }

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

    // ===================================================================
    // MULTI-ZONE ENGINE
    // Each zone gets its own dual-layer container and independent playback
    // ===================================================================

    function setupZones(zonesData, mainItems) {
        teardownZones();
        zonesActive = true;

        // Hide single-mode layers
        const layerA = document.getElementById('layer-a');
        const layerB = document.getElementById('layer-b');
        layerA.classList.remove('active');
        layerB.classList.remove('active');
        layerA.style.display = 'none';
        layerB.style.display = 'none';
        cancelPlayback();
        hideSplash();

        const container = document.getElementById('zones-container');
        container.classList.remove('hidden');
        container.innerHTML = '';

        zonesData.forEach(zone => {
            const items = zone.items && zone.items.length > 0 ? zone.items : [];
            const zoneSettings = zone.settings || settings;

            const zoneEl = document.createElement('div');
            zoneEl.className = 'zone';
            zoneEl.style.left = zone.x_percent + '%';
            zoneEl.style.top = zone.y_percent + '%';
            zoneEl.style.width = zone.width_percent + '%';
            zoneEl.style.height = zone.height_percent + '%';
            zoneEl.style.zIndex = zone.z_index || 0;
            zoneEl.dataset.zoneId = zone.id;
            zoneEl.dataset.zoneName = zone.name;

            // Dual-layer crossfade per zone
            const layerAEl = document.createElement('div');
            layerAEl.className = 'zone-layer';
            const layerBEl = document.createElement('div');
            layerBEl.className = 'zone-layer';

            zoneEl.appendChild(layerAEl);
            zoneEl.appendChild(layerBEl);
            container.appendChild(zoneEl);

            // Zone controller
            const ctrl = {
                id: zone.id,
                name: zone.name,
                el: zoneEl,
                layerA: layerAEl,
                layerB: layerBEl,
                currentLayer: 'a',
                items: items,
                currentIndex: -1,
                settings: zoneSettings,
                timer: null,
                transitionType: zoneSettings.transition_type || 'fade',
            };

            activeZones.push(ctrl);

            if (items.length > 0) {
                ctrl.currentIndex = 0;
                zonePlayAsset(ctrl);
            }
        });

        console.log('[TinySignage] Multi-zone mode active with', activeZones.length, 'zones');
    }

    function teardownZones() {
        if (!zonesActive) return;

        activeZones.forEach(ctrl => {
            if (ctrl.timer) clearTimeout(ctrl.timer);
            zoneCleanupLayer(ctrl.layerA);
            zoneCleanupLayer(ctrl.layerB);
        });
        activeZones = [];
        zonesActive = false;

        const container = document.getElementById('zones-container');
        container.classList.add('hidden');
        container.innerHTML = '';

        // Restore single-mode layers
        const layerA = document.getElementById('layer-a');
        const layerB = document.getElementById('layer-b');
        layerA.style.display = '';
        layerB.style.display = '';
    }

    function zonePlayAsset(ctrl) {
        if (ctrl.items.length === 0) return;

        if (ctrl.currentIndex >= ctrl.items.length) ctrl.currentIndex = 0;
        if (ctrl.currentIndex < 0) ctrl.currentIndex = ctrl.items.length - 1;

        const item = ctrl.items[ctrl.currentIndex];
        const asset = item.asset;
        if (!asset) {
            zoneAdvance(ctrl);
            return;
        }

        zoneLoadAsset(ctrl, asset);

        const duration = zoneGetDuration(ctrl, asset);
        if (ctrl.timer) clearTimeout(ctrl.timer);
        ctrl.timer = setTimeout(() => zoneAdvance(ctrl), duration * 1000);
    }

    function zoneGetDuration(ctrl, asset) {
        if (asset.duration === 0 && asset.asset_type === 'video') {
            return MAX_VIDEO_DURATION;
        }
        return asset.duration || ctrl.settings.default_duration || settings.default_duration || 10;
    }

    function zoneAdvance(ctrl) {
        if (ctrl.timer) { clearTimeout(ctrl.timer); ctrl.timer = null; }
        if (ctrl.settings.shuffle && ctrl.items.length > 1) {
            let next;
            do { next = Math.floor(Math.random() * ctrl.items.length); } while (next === ctrl.currentIndex);
            ctrl.currentIndex = next;
        } else {
            ctrl.currentIndex++;
            if (ctrl.currentIndex >= ctrl.items.length) ctrl.currentIndex = 0;
        }
        zonePlayAsset(ctrl);
    }

    function zoneLoadAsset(ctrl, asset) {
        const isLayerA = ctrl.currentLayer === 'a';
        const nextLayer = isLayerA ? ctrl.layerB : ctrl.layerA;
        const outLayer = isLayerA ? ctrl.layerA : ctrl.layerB;

        zoneCleanupLayer(nextLayer);

        const transition = getEffectiveTransition(asset);
        const doTx = () => zoneDoTransition(ctrl, nextLayer, outLayer, isLayerA ? 'b' : 'a', transition);

        let element;
        if (asset.asset_type === 'image') {
            element = document.createElement('img');
            element.onload = () => { setTimeout(doTx, 300); };
            element.onerror = () => { setTimeout(doTx, 300); };
            element.src = `${baseUrl}/media/${asset.uri}`;
        } else if (asset.asset_type === 'video') {
            element = document.createElement('video');
            element.autoplay = true;
            element.muted = true;
            element.playsInline = true;
            element.loop = false;
            const videoLoadTimeout = setTimeout(() => {
                if (element.readyState < 2) {
                    console.warn('[TinySignage] Video load timeout (zone):', asset.uri);
                    element.oncanplay = null;
                    element.onerror = null;
                    element.onended = null;
                    zoneAdvance(ctrl);
                }
            }, 10000);
            element.oncanplay = () => { clearTimeout(videoLoadTimeout); setTimeout(doTx, 300); };
            element.onerror = () => { clearTimeout(videoLoadTimeout); zoneAdvance(ctrl); };
            element.onended = () => { zoneAdvance(ctrl); };
            element.src = `${baseUrl}/media/${asset.uri}`;
        } else if (asset.asset_type === 'html') {
            element = document.createElement('iframe');
            element.onload = () => { setTimeout(doTx, 300); };
            element.src = `${baseUrl}/media/${asset.uri}`;
            element.sandbox = 'allow-scripts allow-same-origin';
        } else if (asset.asset_type === 'url') {
            element = document.createElement('iframe');
            element.onload = () => { setTimeout(doTx, 500); };
            element.src = asset.uri;
            element.sandbox = 'allow-scripts allow-same-origin';
        }

        if (element) {
            nextLayer.appendChild(element);
        }
    }

    function zoneDoTransition(ctrl, inLayer, outLayer, newCurrentId, transition) {
        const inContent = inLayer.querySelector('video, img, iframe');
        const outContent = outLayer.querySelector('video, img, iframe');
        const isVideoToVideo = inContent?.tagName === 'VIDEO' && outContent?.tagName === 'VIDEO';

        const txType = transition ? transition.type : ctrl.transitionType;
        const txDuration = transition ? transition.duration : null;
        const useCut = txType === 'cut' || isVideoToVideo;

        if (useCut) {
            inLayer.style.transition = 'none';
            outLayer.style.transition = 'none';
            inLayer.classList.add('active');
            outLayer.classList.remove('active');
            zoneCleanupLayer(outLayer);
            requestAnimationFrame(() => {
                inLayer.style.transition = '';
                outLayer.style.transition = '';
            });
        } else {
            if (txDuration != null) {
                inLayer.style.transitionDuration = txDuration + 's';
                outLayer.style.transitionDuration = txDuration + 's';
            }
            inLayer.classList.add('active');
            outLayer.classList.remove('active');
            const onEnd = () => {
                outLayer.removeEventListener('transitionend', onEnd);
                zoneCleanupLayer(outLayer);
                inLayer.style.transitionDuration = '';
                outLayer.style.transitionDuration = '';
            };
            outLayer.addEventListener('transitionend', onEnd);
            const dur = txDuration != null ? txDuration : 1;
            setTimeout(() => {
                outLayer.removeEventListener('transitionend', onEnd);
                zoneCleanupLayer(outLayer);
                inLayer.style.transitionDuration = '';
                outLayer.style.transitionDuration = '';
            }, (dur + 0.5) * 1000);
        }

        ctrl.currentLayer = newCurrentId;
    }

    function zoneCleanupLayer(layer) {
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

    // ===================================================================
    // SINGLE-MODE PLAYBACK (original dual-layer engine)
    // ===================================================================

    function playCurrentAsset() {
        if (playlist.length === 0) {
            showSplash();
            return;
        }

        if (currentIndex >= playlist.length) currentIndex = 0;
        if (currentIndex < 0) currentIndex = playlist.length - 1;

        const item = playlist[currentIndex];
        const asset = item.asset;
        if (!asset) {
            advance();
            return;
        }

        loadAsset(asset);

        const duration = getAssetDuration(asset);
        cancelPlayback();
        playbackTimer = setTimeout(() => advance(), duration * 1000);
    }

    function getAssetDuration(asset) {
        if (asset.duration === 0 && asset.asset_type === 'video') {
            return MAX_VIDEO_DURATION;
        }
        return asset.duration || settings.default_duration || 10;
    }

    function advance() {
        cancelPlayback();
        if (settings.shuffle && playlist.length > 1) {
            let next;
            do { next = Math.floor(Math.random() * playlist.length); } while (next === currentIndex);
            currentIndex = next;
        } else {
            currentIndex++;
            if (currentIndex >= playlist.length) {
                currentIndex = 0;
                // Playlist wrapped — check loop count triggers
                if (triggerFlow) checkLoopCount();
            }
        }
        playCurrentAsset();
    }

    function cancelPlayback() {
        if (playbackTimer) {
            clearTimeout(playbackTimer);
            playbackTimer = null;
        }
    }

    // --- Per-asset transition overrides ---
    function getEffectiveTransition(asset) {
        const type = asset.transition_type || currentTransitionType;
        const duration = (asset.transition_duration != null)
            ? asset.transition_duration
            : (settings.transition_duration != null ? settings.transition_duration : 1);
        return { type, duration };
    }

    // --- Asset Loading ---
    function loadAsset(asset) {
        const nextLayerId = currentLayer === 'a' ? 'b' : 'a';
        const nextLayer = document.getElementById(`layer-${nextLayerId}`);
        const currentLayerEl = document.getElementById(`layer-${currentLayer}`);

        cleanupLayer(nextLayer);

        const transition = getEffectiveTransition(asset);
        const doTx = () => doTransition(nextLayer, currentLayerEl, nextLayerId, transition);

        let element;
        if (asset.asset_type === 'image') {
            element = document.createElement('img');
            element.onload = () => { setTimeout(doTx, 300); };
            element.onerror = () => {
                console.warn('[TinySignage] Image load failed:', asset.uri);
                setTimeout(doTx, 300);
            };
            element.src = `${baseUrl}/media/${asset.uri}`;
        } else if (asset.asset_type === 'video') {
            element = document.createElement('video');
            element.autoplay = true;
            element.muted = true;
            element.playsInline = true;
            element.loop = false;

            const videoLoadTimeout = setTimeout(() => {
                if (element.readyState < 2) {
                    console.warn('[TinySignage] Video load timeout:', asset.uri);
                    element.oncanplay = null;
                    element.onerror = null;
                    element.onended = null;
                    advance();
                }
            }, 10000);

            element.oncanplay = () => { clearTimeout(videoLoadTimeout); setTimeout(doTx, 300); };

            element.onerror = () => {
                clearTimeout(videoLoadTimeout);
                console.warn('[TinySignage] Video load failed:', asset.uri);
                advance();
            };

            element.onended = () => {
                advance();
            };

            element.src = `${baseUrl}/media/${asset.uri}`;
        } else if (asset.asset_type === 'html') {
            element = document.createElement('iframe');
            element.onload = () => { setTimeout(doTx, 300); };
            element.src = `${baseUrl}/media/${asset.uri}`;
            element.sandbox = 'allow-scripts allow-same-origin';
        } else if (asset.asset_type === 'url') {
            element = document.createElement('iframe');
            element.onload = () => { setTimeout(doTx, 500); };
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
        }
    }

    // --- Transitions ---
    function doTransition(inLayer, outLayer, newCurrentId, transition) {
        hideSplash();

        const inContent = inLayer.querySelector('video, img, iframe');
        const outContent = outLayer.querySelector('video, img, iframe');

        const isVideoToVideo = (
            inContent?.tagName === 'VIDEO' &&
            outContent?.tagName === 'VIDEO'
        );

        const txType = transition ? transition.type : currentTransitionType;
        const txDuration = transition ? transition.duration : null;
        const useCut = txType === 'cut' || isVideoToVideo;

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
            if (txDuration != null) {
                inLayer.style.transitionDuration = txDuration + 's';
                outLayer.style.transitionDuration = txDuration + 's';
            }

            inLayer.classList.add('active');
            outLayer.classList.remove('active');
            const onTransitionEnd = () => {
                outLayer.removeEventListener('transitionend', onTransitionEnd);
                cleanupLayer(outLayer);
                inLayer.style.transitionDuration = '';
                outLayer.style.transitionDuration = '';
            };
            outLayer.addEventListener('transitionend', onTransitionEnd);
            const duration = txDuration != null
                ? txDuration
                : (parseFloat(
                    getComputedStyle(document.documentElement)
                        .getPropertyValue('--transition-duration')
                ) || 1);
            setTimeout(() => {
                outLayer.removeEventListener('transitionend', onTransitionEnd);
                cleanupLayer(outLayer);
                inLayer.style.transitionDuration = '';
                outLayer.style.transitionDuration = '';
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
        sendHeartbeat();
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

    // --- Emergency Override ---
    function showEmergencyMessage(override) {
        const overlay = document.getElementById('emergency-overlay');
        const messageEl = document.getElementById('emergency-message');
        const nameEl = document.getElementById('emergency-name');

        const escaped = override.message
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;');
        messageEl.innerHTML = escaped;
        nameEl.textContent = override.name || '';

        overlay.classList.remove('hidden');
        hideSplash();
        cancelPlayback();
    }

    function hideEmergencyMessage() {
        const overlay = document.getElementById('emergency-overlay');
        overlay.classList.add('hidden');
    }

    function scheduleOverrideExpiry(override) {
        if (overrideExpiryTimer) {
            clearTimeout(overrideExpiryTimer);
            overrideExpiryTimer = null;
        }
        if (!override || !override.expires_at) return;
        const expiresAt = new Date(override.expires_at.endsWith('Z') ? override.expires_at : override.expires_at + 'Z');
        const msUntilExpiry = expiresAt.getTime() - Date.now();
        if (msUntilExpiry <= 0) {
            console.log('[TinySignage] Override already expired client-side, clearing');
            activeOverride = null;
            hideEmergencyMessage();
            if (playlist.length > 0) { playCurrentAsset(); } else { showSplash(); }
            return;
        }
        overrideExpiryTimer = setTimeout(() => {
            console.log('[TinySignage] Override expired client-side, clearing');
            activeOverride = null;
            hideEmergencyMessage();
            overrideExpiryTimer = null;
            if (playlist.length > 0) { playCurrentAsset(); } else { showSplash(); }
        }, msUntilExpiry);
    }

    // ===================================================================
    // TRANSITION PLAYLIST PLAYBACK
    // Plays bumper/transition content once, then switches to the pending
    // scheduled playlist.
    // ===================================================================

    function playTransitionAsset() {
        if (!playingTransition || !transitionPlaylist || transitionPlaylist.length === 0) {
            finishTransition();
            return;
        }

        if (transitionIndex >= transitionPlaylist.length) {
            finishTransition();
            return;
        }

        const item = transitionPlaylist[transitionIndex];
        const asset = item.asset;
        if (!asset) {
            transitionIndex++;
            playTransitionAsset();
            return;
        }

        loadAsset(asset);

        const duration = getAssetDuration(asset);
        cancelPlayback();
        playbackTimer = setTimeout(() => {
            transitionIndex++;
            playTransitionAsset();
        }, duration * 1000);
    }

    function finishTransition() {
        console.log('[TinySignage] Transition playlist complete, switching to new content');
        playingTransition = false;
        transitionPlaylist = null;
        transitionIndex = -1;

        playlist = pendingPlaylist || [];
        playlistHash = pendingHash;
        settings = pendingSettings || {};
        applySettings(settings);
        pendingPlaylist = null;
        pendingHash = '';
        pendingSettings = {};

        if (playlist.length > 0) {
            currentIndex = 0;
            preloadAssets();
            playCurrentAsset();
        } else {
            showSplash();
        }
    }

    // --- Capability Reporting ---
    let capabilityTimer = null;

    async function gatherCapabilities() {
        const payload = {
            protocol_version: 1,
            reported_at: new Date().toISOString(),
            software: {
                player_version: PLAYER_VERSION,
                player_type: 'browser',
                user_agent: navigator.userAgent,
            },
            display: {
                resolution_detected: screen.width + 'x' + screen.height,
                pixel_ratio: window.devicePixelRatio || 1,
                color_depth: screen.colorDepth,
            },
            hardware: {
                cpu_cores: navigator.hardwareConcurrency || null,
                ram_mb: navigator.deviceMemory ? navigator.deviceMemory * 1024 : null,
                os: navigator.platform || null,
            },
            capabilities: {
                touch: 'ontouchstart' in window || navigator.maxTouchPoints > 0,
                audio: typeof AudioContext !== 'undefined' || typeof webkitAudioContext !== 'undefined',
            },
        };

        // Browser storage quota (not promoted to device columns)
        if (navigator.storage && navigator.storage.estimate) {
            try {
                const est = await navigator.storage.estimate();
                payload.hardware.browser_storage_quota_mb = Math.round((est.quota || 0) / (1024 * 1024));
                payload.hardware.browser_storage_usage_mb = Math.round((est.usage || 0) / (1024 * 1024));
            } catch (e) { /* ignore */ }
        }

        return payload;
    }

    async function sendCapabilities() {
        if (!deviceId) return;
        try {
            const payload = await gatherCapabilities();
            await authFetch(apiUrl(`/api/devices/${deviceId}/capabilities`), {
                method: 'POST',
                headers: authHeaders(),
                body: JSON.stringify(payload),
            });
            console.log('[TinySignage] Capabilities reported');
        } catch (e) {
            console.warn('[TinySignage] Capability report failed:', e.message);
        }
    }

    function scheduleCapabilityReport() {
        sendCapabilities();
        if (capabilityTimer) clearInterval(capabilityTimer);
        capabilityTimer = setInterval(sendCapabilities, CAPABILITY_REPORT_INTERVAL);
    }

    // ===================================================================
    // TRIGGER ENGINE
    // Listens for keyboard, touch, timeout, and loop_count triggers
    // and swaps the active playlist when a trigger fires.
    // ===================================================================

    function initTriggerEngine(flowData, sourcePlaylistId) {
        teardownTriggerEngine();
        triggerFlow = flowData;
        currentSourcePlaylistId = sourcePlaylistId;
        loopCount = 0;

        console.log('[TinySignage] TriggerEngine init — flow:', flowData.id, 'source:', sourcePlaylistId);

        const branches = findBranchesForSource(sourcePlaylistId);
        if (branches.length === 0) {
            console.log('[TinySignage] No trigger branches for source playlist');
            return;
        }

        registerKeyboardTriggers(branches);
        createTouchZoneOverlays(branches);
        startTimeoutTriggers(branches);
        connectGpioBridge(branches);
        initWebhookTracking(branches);

        saveTriggerState();
    }

    function teardownTriggerEngine() {
        // Remove keyboard listener
        if (triggerKeydownHandler) {
            document.removeEventListener('keydown', triggerKeydownHandler);
            triggerKeydownHandler = null;
        }
        triggerListenersActive = false;

        // Remove touch zones
        const container = document.getElementById('touch-zones-container');
        if (container) container.innerHTML = '';

        // Clear timeout timer
        if (triggerTimeoutTimer) {
            clearTimeout(triggerTimeoutTimer);
            triggerTimeoutTimer = null;
        }

        // Disconnect GPIO bridge
        disconnectGpioBridge();

        triggerFlow = null;
        currentSourcePlaylistId = '';
        loopCount = 0;
        lastSeenWebhookFires = {};
    }

    function findBranchesForSource(sourceId) {
        if (!triggerFlow || !triggerFlow.branches) return [];
        return triggerFlow.branches
            .filter(b => b.source_playlist_id === sourceId)
            .sort((a, b) => (b.priority || 0) - (a.priority || 0));
    }

    function registerKeyboardTriggers(branches) {
        const keyBranches = branches.filter(b => b.trigger_type === 'keyboard');
        if (keyBranches.length === 0) return;

        triggerKeydownHandler = function (e) {
            // Skip if override is active or pairing form is visible
            if (activeOverride) return;
            const pairingOverlay = document.getElementById('pairing-overlay');
            if (pairingOverlay && !pairingOverlay.classList.contains('hidden')) return;

            for (const branch of keyBranches) {
                const config = branch.trigger_config || {};
                if (!config.key) continue;

                if (e.key !== config.key) continue;

                const modifiers = config.modifiers || [];
                if (modifiers.includes('Shift') !== e.shiftKey) continue;
                if (modifiers.includes('Ctrl') !== e.ctrlKey) continue;
                if (modifiers.includes('Alt') !== e.altKey) continue;
                if (modifiers.includes('Meta') !== e.metaKey) continue;

                e.preventDefault();
                console.log('[TinySignage] Keyboard trigger fired:', config.key);
                fireTrigger(branch);
                return;
            }
        };

        document.addEventListener('keydown', triggerKeydownHandler);
        triggerListenersActive = true;
        console.log('[TinySignage] Registered', keyBranches.length, 'keyboard trigger(s)');
    }

    function createTouchZoneOverlays(branches) {
        const touchBranches = branches.filter(b => b.trigger_type === 'touch_zone');
        if (touchBranches.length === 0) return;

        const container = document.getElementById('touch-zones-container');
        if (!container) return;
        container.innerHTML = '';

        touchBranches.forEach(branch => {
            const config = branch.trigger_config || {};
            const zone = document.createElement('div');
            zone.className = 'touch-zone';
            zone.style.left = (config.x_percent || 0) + '%';
            zone.style.top = (config.y_percent || 0) + '%';
            zone.style.width = (config.width_percent || 20) + '%';
            zone.style.height = (config.height_percent || 20) + '%';

            const handler = function (e) {
                if (activeOverride) return;
                e.preventDefault();
                console.log('[TinySignage] Touch zone trigger fired');
                fireTrigger(branch);
            };
            zone.addEventListener('click', handler);
            zone.addEventListener('touchstart', handler, { passive: false });

            container.appendChild(zone);
        });

        console.log('[TinySignage] Created', touchBranches.length, 'touch zone overlay(s)');
    }

    function startTimeoutTriggers(branches) {
        const timeoutBranch = branches.find(b => b.trigger_type === 'timeout');
        if (!timeoutBranch) return;

        const config = timeoutBranch.trigger_config || {};
        const seconds = config.seconds || 30;

        if (triggerTimeoutTimer) clearTimeout(triggerTimeoutTimer);
        triggerTimeoutTimer = setTimeout(() => {
            if (activeOverride) return;
            console.log('[TinySignage] Timeout trigger fired after', seconds, 's');
            fireTrigger(timeoutBranch);
        }, seconds * 1000);

        console.log('[TinySignage] Timeout trigger set for', seconds, 's');
    }

    function checkLoopCount() {
        if (!triggerFlow) return;
        loopCount++;

        const branches = findBranchesForSource(currentSourcePlaylistId);
        const loopBranch = branches.find(b => b.trigger_type === 'loop_count');
        if (!loopBranch) return;

        const config = loopBranch.trigger_config || {};
        const targetCount = config.count || 3;

        if (loopCount >= targetCount) {
            console.log('[TinySignage] Loop count trigger fired after', loopCount, 'loops');
            fireTrigger(loopBranch);
        }
    }

    function fireTrigger(branch) {
        if (!branch.target_playlist) {
            console.warn('[TinySignage] Trigger branch has no target_playlist data');
            return;
        }

        const target = branch.target_playlist;
        console.log('[TinySignage] Firing trigger → target playlist:', target.name || target.id);

        // Teardown current triggers before swapping
        if (triggerKeydownHandler) {
            document.removeEventListener('keydown', triggerKeydownHandler);
            triggerKeydownHandler = null;
        }
        triggerListenersActive = false;
        const touchContainer = document.getElementById('touch-zones-container');
        if (touchContainer) touchContainer.innerHTML = '';
        if (triggerTimeoutTimer) {
            clearTimeout(triggerTimeoutTimer);
            triggerTimeoutTimer = null;
        }

        // Swap playlist and settings
        playlist = target.items || [];
        settings = target.settings || {};
        playlistHash = playlistHash + '-trig' + Date.now();
        currentSourcePlaylistId = branch.target_playlist_id;
        currentIndex = 0;
        loopCount = 0;

        applySettings(settings);
        cancelPlayback();

        if (playlist.length > 0) {
            playCurrentAsset();
            preloadAssets();
        } else {
            showSplash();
        }

        // Re-register triggers for the new source playlist
        const newBranches = findBranchesForSource(currentSourcePlaylistId);
        if (newBranches.length > 0) {
            registerKeyboardTriggers(newBranches);
            createTouchZoneOverlays(newBranches);
            startTimeoutTriggers(newBranches);
            connectGpioBridge(newBranches);
        } else {
            disconnectGpioBridge();
        }

        saveTriggerState();
    }

    // --- Webhook trigger tracking ---
    function initWebhookTracking(branches) {
        const webhookBranches = branches.filter(b => b.trigger_type === 'webhook');
        webhookBranches.forEach(b => {
            if (b.last_webhook_fire && !lastSeenWebhookFires[b.id]) {
                // On first init, record current fire time so we don't immediately trigger
                lastSeenWebhookFires[b.id] = b.last_webhook_fire;
            }
        });
    }

    function checkWebhookTriggers() {
        if (!triggerFlow || !triggerFlow.branches || activeOverride) return;
        const branches = findBranchesForSource(currentSourcePlaylistId);
        const webhookBranches = branches.filter(b => b.trigger_type === 'webhook');

        for (const branch of webhookBranches) {
            if (!branch.last_webhook_fire) continue;
            const lastSeen = lastSeenWebhookFires[branch.id];
            if (!lastSeen || branch.last_webhook_fire !== lastSeen) {
                lastSeenWebhookFires[branch.id] = branch.last_webhook_fire;
                console.log('[TinySignage] Webhook trigger fired for branch:', branch.id);
                fireTrigger(branch);
                return;
            }
        }
    }

    // --- GPIO WebSocket client ---
    function connectGpioBridge(branches) {
        const gpioBranches = branches.filter(b => b.trigger_type === 'gpio');
        if (gpioBranches.length === 0) {
            disconnectGpioBridge();
            return;
        }

        // Already connected
        if (gpioWebSocket && gpioWebSocket.readyState === WebSocket.OPEN) return;

        disconnectGpioBridge();

        try {
            gpioWebSocket = new WebSocket(GPIO_BRIDGE_URL);

            gpioWebSocket.onopen = function () {
                console.log('[TinySignage] GPIO bridge connected');
            };

            gpioWebSocket.onmessage = function (event) {
                try {
                    const data = JSON.parse(event.data);
                    handleGpioEvent(data, gpioBranches);
                } catch (e) {
                    console.warn('[TinySignage] GPIO message parse error:', e.message);
                }
            };

            gpioWebSocket.onclose = function () {
                console.log('[TinySignage] GPIO bridge disconnected');
                gpioWebSocket = null;
                // Auto-reconnect after 5s if GPIO branches still exist
                if (triggerFlow) {
                    gpioReconnectTimer = setTimeout(() => {
                        const currentBranches = findBranchesForSource(currentSourcePlaylistId);
                        connectGpioBridge(currentBranches);
                    }, 5000);
                }
            };

            gpioWebSocket.onerror = function () {
                // onclose will fire after this, handling reconnect
            };
        } catch (e) {
            console.warn('[TinySignage] GPIO bridge connect failed:', e.message);
        }
    }

    function disconnectGpioBridge() {
        if (gpioReconnectTimer) {
            clearTimeout(gpioReconnectTimer);
            gpioReconnectTimer = null;
        }
        if (gpioWebSocket) {
            gpioWebSocket.onclose = null; // Prevent reconnect on intentional close
            gpioWebSocket.close();
            gpioWebSocket = null;
        }
    }

    function handleGpioEvent(data, gpioBranches) {
        if (activeOverride) return;
        if (data.type !== 'gpio') return;

        // Match pin and edge against GPIO branches (sorted by priority)
        for (const branch of gpioBranches) {
            const config = branch.trigger_config || {};
            if (config.pin === data.pin) {
                const expectedEdge = config.edge || 'falling';
                if (data.edge === expectedEdge) {
                    console.log('[TinySignage] GPIO trigger fired: pin', data.pin);
                    fireTrigger(branch);
                    return;
                }
            }
        }
    }

    // --- Trigger state persistence ---
    function saveTriggerState() {
        try {
            if (triggerFlow) {
                localStorage.setItem('tinysignage_trigger_state', JSON.stringify({
                    flowId: triggerFlow.id,
                    sourcePlaylistId: currentSourcePlaylistId,
                    loopCount: loopCount,
                }));
            } else {
                localStorage.removeItem('tinysignage_trigger_state');
            }
        } catch (e) { /* ignore */ }
    }

    function loadTriggerState() {
        try {
            const raw = localStorage.getItem('tinysignage_trigger_state');
            if (raw) return JSON.parse(raw);
        } catch (e) { /* ignore */ }
        return null;
    }

    // --- Go ---
    init();
})();
