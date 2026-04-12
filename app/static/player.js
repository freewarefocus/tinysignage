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
    const PLAYER_VERSION = '0.9.0';
    const CAPABILITY_REPORT_INTERVAL = 3600000; // 60 min
    const HEALTH_CHECK_INTERVAL = 30000;        // 30s between health checks
    const RAF_STALE_THRESHOLD = 10000;           // 10s = DOM frozen
    const MEMORY_GRACE_PERIOD = 300000;          // 5 min after reload, skip memory checks
    const MIN_UPTIME_FOR_SCHEDULED_RESTART = 3600000; // 1hr
    const WPE_MAX_UPTIME = 86400000; // 24 hours — safety-net restart on WPE

    // --- Persistent Player Log (ring buffer in localStorage) ---
    const LOG_STORAGE_KEY = 'tinysignage_player_log';
    const LOG_MAX_ENTRIES = 200;

    const PlayerLog = {
        _buffer: null,

        _load() {
            if (this._buffer !== null) return this._buffer;
            try {
                const raw = localStorage.getItem(LOG_STORAGE_KEY);
                this._buffer = raw ? JSON.parse(raw) : [];
            } catch {
                this._buffer = [];
            }
            return this._buffer;
        },

        _save() {
            try {
                localStorage.setItem(LOG_STORAGE_KEY, JSON.stringify(this._buffer));
            } catch {
                // Storage full — drop oldest half and retry
                if (this._buffer && this._buffer.length > 10) {
                    this._buffer = this._buffer.slice(Math.floor(this._buffer.length / 2));
                    try { localStorage.setItem(LOG_STORAGE_KEY, JSON.stringify(this._buffer)); } catch { /* give up */ }
                }
            }
        },

        _append(level, message) {
            const buf = this._load();
            buf.push({
                t: new Date().toISOString(),
                l: level,
                m: message,
            });
            // Trim to ring buffer size
            while (buf.length > LOG_MAX_ENTRIES) buf.shift();
            this._save();
        },

        info(msg) {
            console.log('[Player]', msg);
            this._append('info', msg);
        },

        warn(msg) {
            console.warn('[Player]', msg);
            this._append('warn', msg);
        },

        error(msg) {
            console.error('[Player]', msg);
            this._append('error', msg);
        },

        /** Return all entries (newest last) */
        getAll() {
            return this._load().slice();
        },

        /** Return entries as formatted text for the debug overlay */
        toText() {
            const entries = this._load();
            return entries.map(e => {
                const lvl = e.l.toUpperCase().padEnd(5);
                return `${e.t} [${lvl}] ${e.m}`;
            }).join('\n');
        },

        /** Clear the log */
        clear() {
            this._buffer = [];
            try { localStorage.removeItem(LOG_STORAGE_KEY); } catch { /* ok */ }
        },
    };

    // Base URL for split deployment — read from <meta name="server-url"> or localStorage
    const serverMeta = document.querySelector('meta[name="server-url"]');
    const metaUrl = (serverMeta ? serverMeta.content : '').replace(/\/+$/, '');
    const baseUrl = metaUrl || (localStorage.getItem('tinysignage_server_url') || '').replace(/\/+$/, '');

    function apiUrl(path) {
        return baseUrl + path;
    }

    // --- State ---
    let currentLayer = 'a';
    let currentTransitionType = 'fade';
    // Per-layer in-flight transition cleanup state — lets cleanupLayer()
    // cancel a pending transitionend listener + fallback timer when a new
    // loadAsset() is called on a layer that is still mid-fade (e.g. because
    // a trigger fired mid-transition). Keys are layer element ids.
    const layerTxCleanup = {};  // { 'layer-a': { el, listener, fallbackTimer }, ... }
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
    let registrationBound = false;

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
    let shuffleAdvanceCount = 0;     // Track advances in shuffle mode for loop detection
    let triggerTimeoutTimer = null;   // Timeout trigger timer
    let triggerKeydownHandler = null; // Reference to keydown handler for cleanup

    // --- GPIO / Joystick bridge state ---
    let gpioWebSocket = null;         // WebSocket connection to GPIO bridge
    let gpioReconnectTimer = null;    // Auto-reconnect timer
    let activeGpioBranches = [];      // Current GPIO branches for onmessage matching
    let activeJoystickBranches = [];  // Current joystick branches for onmessage matching
    const GPIO_BRIDGE_URL = (location.protocol === 'https:' ? 'wss' : 'ws') + '://localhost:8765';

    // --- Health monitor state ---
    let healthCheckTimer = null;
    let lastRafTime = Date.now();
    let rafResponsive = true;
    let serverRestartHour = null;
    let serverMemoryLimitMb = 200;
    let preloadImg = null;
    const isWPE = /WPE/i.test(navigator.userAgent);

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

    // --- Registration ---
    function getStoredServerUrl() {
        return (localStorage.getItem('tinysignage_server_url') || '').replace(/\/+$/, '');
    }

    function storeServerUrl(url) {
        localStorage.setItem('tinysignage_server_url', url.replace(/\/+$/, ''));
    }

    function registrationApiUrl(serverUrl, path) {
        return serverUrl.replace(/\/+$/, '') + path;
    }

    function showRegistrationOverlay() {
        const overlay = document.getElementById('registration-overlay');
        overlay.classList.remove('hidden');

        const form = document.getElementById('registration-form');
        const serverInput = document.getElementById('reg-server-url');
        const nameInput = document.getElementById('reg-display-name');
        const errorEl = document.getElementById('registration-error');

        // Pre-fill server URL: stored > meta tag > current origin
        const storedUrl = getStoredServerUrl();
        serverInput.value = storedUrl || baseUrl || window.location.origin;
        nameInput.focus();

        if (registrationBound) return;
        registrationBound = true;

        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            const serverUrl = serverInput.value.trim().replace(/\/+$/, '');
            const name = nameInput.value.trim() || 'New Display';

            if (!serverUrl) {
                errorEl.textContent = 'Server URL is required';
                errorEl.classList.remove('hidden');
                return;
            }

            errorEl.classList.add('hidden');
            const btn = form.querySelector('button');
            btn.disabled = true;
            btn.textContent = 'Registering...';

            try {
                const resp = await fetch(registrationApiUrl(serverUrl, '/api/devices/register'), {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ name: name }),
                });
                if (!resp.ok) {
                    const err = await resp.json().catch(() => ({}));
                    throw new Error(err.detail || 'Registration failed');
                }
                const data = await resp.json();
                storeServerUrl(serverUrl);
                storeCredentials(data.device_id, data.token);
                cleanUrl();
                if (data.status === 'pending') {
                    hideRegistrationOverlay();
                    showPendingOverlay(data.device_name || name);
                    startPlayer();
                } else {
                    showRegistrationSuccess(data.device_name || name);
                }
            } catch (err) {
                PlayerLog.error('Registration failed: ' + err.message);
                errorEl.textContent = err.message;
                errorEl.classList.remove('hidden');
                btn.disabled = false;
                btn.textContent = 'Register Display';
            }
        });
    }

    function showRegistrationSuccess(deviceName) {
        const overlay = document.getElementById('registration-overlay');
        const inner = overlay.querySelector('.registration-card') || overlay;
        inner.innerHTML = '<div style="text-align:center;padding:2rem;">' +
            '<div style="font-size:2rem;margin-bottom:0.5rem;">&#10003;</div>' +
            '<div style="font-size:1.2rem;color:#fff;">Registered as ' +
            deviceName.replace(/</g, '&lt;').replace(/>/g, '&gt;') +
            '!</div></div>';
        overlay.classList.remove('hidden');
        setTimeout(function () {
            overlay.classList.add('hidden');
            startPlayer();
        }, 2000);
    }

    function hideRegistrationOverlay() {
        document.getElementById('registration-overlay').classList.add('hidden');
    }

    // --- Pending Overlay ---
    function showPendingOverlay(deviceName) {
        const overlay = document.getElementById('pending-overlay');
        const nameEl = document.getElementById('pending-device-name');
        if (nameEl && deviceName) {
            nameEl.textContent = deviceName;
        }
        overlay.classList.remove('hidden');
    }

    function hidePendingOverlay() {
        document.getElementById('pending-overlay').classList.add('hidden');
    }

    // --- Local bootstrap ---
    async function tryLocalBootstrap() {
        // Ask the local server for credentials for the default device (seeded
        // from config.yaml during install). Always targets localhost to satisfy
        // the server's localhost-only security check, regardless of what
        // server_url is configured (which may resolve to a network IP via mDNS).
        try {
            const localOrigin = window.location.origin;  // e.g. http://localhost:8080
            const resp = await fetch(localOrigin + '/api/player/bootstrap', { method: 'POST' });
            if (!resp.ok) return false;
            const data = await resp.json();
            if (data.device_id && data.token) {
                PlayerLog.info('Local bootstrap: paired as ' + (data.device_name || data.device_id));
                storeCredentials(data.device_id, data.token);
                return true;
            }
        } catch (e) {
            PlayerLog.warn('Local bootstrap unavailable: ' + e.message);
        }
        return false;
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

        // Headless auto-registration: ?name= param (used by BrightSign autorun)
        const autoName = params.get('name');
        if (autoName) {
            const serverUrl = baseUrl || window.location.origin;
            try {
                const resp = await fetch(registrationApiUrl(serverUrl, '/api/devices/register'), {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ name: autoName }),
                });
                if (resp.ok) {
                    const data = await resp.json();
                    storeServerUrl(serverUrl);
                    storeCredentials(data.device_id, data.token);
                    cleanUrl();
                    startPlayer();
                    return;
                }
            } catch (e) {
                PlayerLog.warn('Auto-registration failed: ' + e.message);
            }
            // Fall through to existing flow on failure
        }

        const storedId = localStorage.getItem('tinysignage_device_id');
        const storedToken = localStorage.getItem('tinysignage_device_token');
        if (storedId && storedToken) {
            deviceId = storedId;
            deviceToken = storedToken;
            startPlayer();
            return;
        }

        // Try local bootstrap before showing registration overlay
        if (await tryLocalBootstrap()) {
            startPlayer();
            return;
        }

        showRegistrationOverlay();
    }

    function startPlayer() {
        hideRegistrationOverlay();
        // One-time cleanup: remove stale trigger-state key from older builds
        localStorage.removeItem('tinysignage_trigger_state');
        loadCachedPlaylist();
        poll();
        schedulePoll();
        scheduleHeartbeat();
        scheduleCapabilityReport();
        startHealthMonitor();

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

                if (data.trigger_flow) {
                    initTriggerEngine(data.trigger_flow, data.trigger_flow.source_playlist_id, 0);
                }
            }
        } catch (e) {
            PlayerLog.warn('Failed to load cached playlist: ' + e);
        }
    }

    function cachePlaylist(data) {
        try {
            localStorage.setItem('tinysignage_playlist', JSON.stringify(data));
        } catch (e) {
            PlayerLog.warn('Failed to cache playlist: ' + e);
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
                PlayerLog.warn('Token rejected (401), attempting re-bootstrap');
                if (await tryLocalBootstrap()) {
                    PlayerLog.info('Re-bootstrap succeeded, retrying poll');
                    return;  // Next scheduled poll will use the new token
                }
                localStorage.removeItem('tinysignage_device_id');
                localStorage.removeItem('tinysignage_device_token');
                deviceId = '';
                deviceToken = '';
                cancelPlayback();
                teardownZones();
                teardownTriggerEngine();
                showRegistrationOverlay();
                return;
            }
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            const data = await resp.json();
            setOnlineStatus(true);

            // --- Pending approval gate ---
            if (data.status === 'pending') {
                showPendingOverlay();
                return;
            }
            // Device was approved — hide pending overlay if it was showing
            hidePendingOverlay();

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
                PlayerLog.info('Override ended, resuming normal playback');
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
                PlayerLog.info('Playlist updated: ' + data.hash);
                const wasEmpty = playlist.length === 0;
                const hadContent = playlist.length > 0;

                hideEmergencyMessage();

                // --- Transition playlist: play bumper before switching ---
                if (hadContent && !playingTransition && data.transition_playlist
                    && data.transition_playlist.items && data.transition_playlist.items.length > 0) {
                    PlayerLog.info('Playing transition playlist before switch');
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
                    initTriggerEngine(data.trigger_flow, data.trigger_flow.source_playlist_id, 0);
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
            PlayerLog.warn('Poll failed: ' + e.message);
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

        PlayerLog.info('Multi-zone mode active with ' + activeZones.length + ' zones');
    }

    function teardownZones() {
        if (!zonesActive) return;

        activeZones.forEach(ctrl => {
            if (ctrl.timer) clearTimeout(ctrl.timer);
            if (ctrl.txFallbackTimer) clearTimeout(ctrl.txFallbackTimer);
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

        zoneLoadAsset(ctrl, item);

        const duration = zoneGetDuration(ctrl, item);
        if (ctrl.timer) clearTimeout(ctrl.timer);
        ctrl.timer = setTimeout(() => zoneAdvance(ctrl), duration * 1000);
    }

    function zoneGetDuration(ctrl, item) {
        const asset = item.asset || item;
        if (item.duration != null && item.duration > 0) {
            return item.duration;
        }
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

    function zoneLoadAsset(ctrl, item) {
        const asset = item.asset || item;
        const isLayerA = ctrl.currentLayer === 'a';
        const nextLayer = isLayerA ? ctrl.layerB : ctrl.layerA;
        const outLayer = isLayerA ? ctrl.layerA : ctrl.layerB;

        zoneCleanupLayer(nextLayer);

        const transition = getEffectiveTransition(item);
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
                    PlayerLog.warn('Video load timeout (zone): ' + asset.uri);
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
            if (element.tagName === 'IMG' || element.tagName === 'VIDEO') {
                element.style.objectFit = getEffectiveObjectFit(item, ctrl.settings);
            }
            nextLayer.appendChild(element);
            applyZoneEffect(nextLayer, item, ctrl);
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
        } else if (txType === 'slide') {
            const dur = txDuration != null ? txDuration : 1;
            inLayer.classList.add('slide-transition', 'slide-ready');
            outLayer.classList.add('slide-transition');
            if (txDuration != null) {
                inLayer.style.setProperty('--transition-duration', txDuration + 's');
                outLayer.style.setProperty('--transition-duration', txDuration + 's');
            }
            void inLayer.offsetWidth;
            inLayer.classList.remove('slide-ready');
            inLayer.classList.add('slide-in');
            outLayer.classList.add('slide-out');
            const cleanSlide = () => {
                outLayer.removeEventListener('transitionend', cleanSlide);
                inLayer.classList.remove('slide-transition', 'slide-in');
                outLayer.classList.remove('slide-transition', 'slide-out');
                inLayer.style.removeProperty('--transition-duration');
                outLayer.style.removeProperty('--transition-duration');
                inLayer.classList.add('active');
                outLayer.classList.remove('active');
                zoneCleanupLayer(outLayer);
            };
            outLayer.addEventListener('transitionend', cleanSlide);
            if (ctrl.txFallbackTimer) clearTimeout(ctrl.txFallbackTimer);
            ctrl.txFallbackTimer = setTimeout(cleanSlide, (dur + 0.5) * 1000);
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
            if (ctrl.txFallbackTimer) clearTimeout(ctrl.txFallbackTimer);
            ctrl.txFallbackTimer = setTimeout(() => {
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
            img.classList.remove('has-effect');
            img.style.animationName = '';
            img.removeAttribute('src');
            img.src = '';
        }
        const iframe = layer.querySelector('iframe');
        if (iframe) {
            iframe.onload = null;
            iframe.removeAttribute('src');
            iframe.srcdoc = '';   // synchronously clear document without navigation
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

        loadAsset(item);

        const duration = getAssetDuration(item);
        cancelPlayback();
        playbackTimer = setTimeout(() => advance(), duration * 1000);
    }

    function getAssetDuration(item) {
        const asset = item.asset || item;
        // Item-level duration override takes precedence
        if (item.duration != null && item.duration > 0) {
            return item.duration;
        }
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
            // Track shuffle advances to detect logical loop completion
            if (triggerFlow && playlist.length > 0) {
                shuffleAdvanceCount++;
                if (shuffleAdvanceCount >= playlist.length) {
                    shuffleAdvanceCount = 0;
                    checkLoopCount();
                }
            }
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

    // --- Per-item → per-playlist → global object-fit cascade ---
    function getEffectiveObjectFit(item, zoneSettings) {
        if (item.object_fit) return item.object_fit;
        const s = zoneSettings || settings;
        if (s.object_fit) return s.object_fit;
        return 'contain';
    }

    // --- Per-item → per-asset → global transition cascade ---
    function getEffectiveTransition(item) {
        const asset = item.asset || item;
        const type = item.transition_type || asset.transition_type || currentTransitionType;
        const duration = (item.transition_duration != null)
            ? item.transition_duration
            : (asset.transition_duration != null)
                ? asset.transition_duration
                : (settings.transition_duration != null ? settings.transition_duration : 1);
        return { type, duration };
    }

    // --- Motion Effects (Ken Burns) ---
    const EFFECT_PRESETS = ['zoom-in', 'zoom-out', 'pan-left', 'pan-right', 'pan-up', 'pan-down'];

    function getEffectiveEffect(item, zoneSettings) {
        if (item.effect) return item.effect;
        const s = zoneSettings || settings;
        if (s.effect) return s.effect;
        return 'none';
    }

    function resolveEffect(name) {
        if (name === 'random') {
            return EFFECT_PRESETS[Math.floor(Math.random() * EFFECT_PRESETS.length)];
        }
        return name;
    }

    function applyEffect(layer, item, zoneSettings) {
        const asset = item.asset || item;
        if (asset.asset_type !== 'image') return;

        const effectName = getEffectiveEffect(item, zoneSettings);
        if (!effectName || effectName === 'none') return;

        const resolved = resolveEffect(effectName);
        const img = layer.querySelector('img');
        if (!img) return;

        const duration = getAssetDuration(item);
        img.classList.add('has-effect');
        img.style.animationName = 'fx-' + resolved;
        img.style.animationDuration = duration + 's';
    }

    function applyZoneEffect(layer, item, ctrl) {
        const asset = item.asset || item;
        if (asset.asset_type !== 'image') return;

        const effectName = getEffectiveEffect(item, ctrl.settings);
        if (!effectName || effectName === 'none') return;

        const resolved = resolveEffect(effectName);
        const img = layer.querySelector('img');
        if (!img) return;

        const duration = zoneGetDuration(ctrl, item);
        img.classList.add('has-effect');
        img.style.animationName = 'fx-' + resolved;
        img.style.animationDuration = duration + 's';
    }

    // --- Asset Loading ---
    function loadAsset(item) {
        const asset = item.asset || item;
        const nextLayerId = currentLayer === 'a' ? 'b' : 'a';
        const nextLayer = document.getElementById(`layer-${nextLayerId}`);
        const currentLayerEl = document.getElementById(`layer-${currentLayer}`);

        cleanupLayer(nextLayer);

        const transition = getEffectiveTransition(item);
        const doTx = () => doTransition(nextLayer, currentLayerEl, nextLayerId, transition);

        let element;
        if (asset.asset_type === 'image') {
            element = document.createElement('img');
            element.onload = () => { setTimeout(doTx, 300); };
            element.onerror = () => {
                PlayerLog.error('Image load failed: ' + asset.uri);
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
                    PlayerLog.error('Video load timeout: ' + asset.uri);
                    element.oncanplay = null;
                    element.onerror = null;
                    element.onended = null;
                    advance();
                }
            }, 10000);

            element.oncanplay = () => { clearTimeout(videoLoadTimeout); setTimeout(doTx, 300); };

            element.onerror = () => {
                clearTimeout(videoLoadTimeout);
                PlayerLog.error('Video load failed: ' + asset.uri);
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
            if (element.tagName === 'IMG' || element.tagName === 'VIDEO') {
                element.style.objectFit = getEffectiveObjectFit(item);
            }
            nextLayer.appendChild(element);
            applyEffect(nextLayer, item);
        }
    }

    // --- Preloading ---
    function preloadAssets() {
        for (let i = 0; i < Math.min(PRELOAD_AHEAD, playlist.length); i++) {
            const idx = (currentIndex + 1 + i) % playlist.length;
            const asset = playlist[idx]?.asset;
            if (!asset) continue;

            if (asset.asset_type === 'image') {
                if (!preloadImg) preloadImg = new Image();
                preloadImg.src = '';                              // release previous decode buffer
                preloadImg.src = `${baseUrl}/media/${asset.uri}`;
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
        } else if (txType === 'slide') {
            const duration = txDuration != null
                ? txDuration
                : (parseFloat(
                    getComputedStyle(document.documentElement)
                        .getPropertyValue('--transition-duration')
                ) || 1);
            // Set up: incoming layer off-screen right, both visible
            inLayer.classList.add('slide-transition', 'slide-ready');
            outLayer.classList.add('slide-transition');
            if (txDuration != null) {
                inLayer.style.setProperty('--transition-duration', txDuration + 's');
                outLayer.style.setProperty('--transition-duration', txDuration + 's');
            }
            // Force layout so the starting position is applied before animating
            void inLayer.offsetWidth;
            // Animate: incoming slides in, outgoing slides out
            inLayer.classList.remove('slide-ready');
            inLayer.classList.add('slide-in');
            outLayer.classList.add('slide-out');
            const cleanSlide = () => {
                outLayer.removeEventListener('transitionend', cleanSlide);
                inLayer.classList.remove('slide-transition', 'slide-in');
                outLayer.classList.remove('slide-transition', 'slide-out');
                inLayer.style.removeProperty('--transition-duration');
                outLayer.style.removeProperty('--transition-duration');
                inLayer.classList.add('active');
                outLayer.classList.remove('active');
                cleanupLayer(outLayer);
            };
            outLayer.addEventListener('transitionend', cleanSlide);
            const slideFallbackTimer = setTimeout(() => {
                cleanSlide();
                delete layerTxCleanup[outLayer.id];
            }, (duration + 0.5) * 1000);
            layerTxCleanup[outLayer.id] = {
                el: outLayer,
                listener: cleanSlide,
                fallbackTimer: slideFallbackTimer,
            };
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
            const fadeFallbackTimer = setTimeout(() => {
                outLayer.removeEventListener('transitionend', onTransitionEnd);
                cleanupLayer(outLayer);
                inLayer.style.transitionDuration = '';
                outLayer.style.transitionDuration = '';
                delete layerTxCleanup[outLayer.id];
            }, (duration + 0.5) * 1000);
            layerTxCleanup[outLayer.id] = {
                el: outLayer,
                listener: onTransitionEnd,
                fallbackTimer: fadeFallbackTimer,
            };
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
            img.classList.remove('has-effect');
            img.style.animationName = '';
            img.removeAttribute('src');
            img.src = '';
        }
        const iframe = layer.querySelector('iframe');
        if (iframe) {
            iframe.onload = null;
            iframe.removeAttribute('src');
            iframe.srcdoc = '';   // synchronously clear document without navigation
        }
        // Cancel any in-flight transition cleanup on this layer so a stale
        // transitionend (or fallback timer) from a previous crossfade cannot
        // fire after we have appended the next slide's element — the race
        // that caused blank-first-slide when a trigger fired mid-fade.
        const pending = layerTxCleanup[layer.id];
        if (pending) {
            layer.removeEventListener('transitionend', pending.listener);
            clearTimeout(pending.fallbackTimer);
            delete layerTxCleanup[layer.id];
        }
        // Reset inline transition state so a follow-up doTransition starts clean.
        // .active is intentionally NOT stripped — doTransition owns that class
        // and removing it here would visually blink the current content.
        layer.style.transitionDuration = '';
        layer.style.removeProperty('--transition-duration');
        layer.style.transform = '';
        layer.classList.remove('slide-transition', 'slide-in', 'slide-out', 'slide-ready');
        layer.innerHTML = '';
    }

    // --- Status ---
    function setOnlineStatus(isOnline) {
        if (online !== isOnline) {
            PlayerLog.info(isOnline ? 'Connection restored' : 'Connection lost — playing from cache');
        }
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

    // --- Health Monitor ---
    function startRafProbe() {
        function tick() {
            lastRafTime = Date.now();
            rafResponsive = true;
            requestAnimationFrame(tick);
        }
        requestAnimationFrame(tick);
    }

    function startHealthMonitor() {
        // Load cached health settings from localStorage
        try {
            const cachedHour = localStorage.getItem('tinysignage_restart_hour');
            if (cachedHour !== null) serverRestartHour = cachedHour === 'null' ? null : parseInt(cachedHour, 10);
            const cachedLimit = localStorage.getItem('tinysignage_memory_limit_mb');
            if (cachedLimit !== null) serverMemoryLimitMb = parseInt(cachedLimit, 10) || 200;
        } catch { /* ok */ }

        startRafProbe();

        if (healthCheckTimer) clearInterval(healthCheckTimer);
        healthCheckTimer = setInterval(runHealthCheck, HEALTH_CHECK_INTERVAL);
    }

    function runHealthCheck() {
        const uptimeMs = Date.now() - startTime;

        // Memory check
        if (performance.memory && uptimeMs > MEMORY_GRACE_PERIOD) {
            const usedMb = Math.round(performance.memory.usedJSHeapSize / (1024 * 1024));
            if (usedMb > serverMemoryLimitMb) {
                PlayerLog.warn('Health: JS heap ' + usedMb + ' MB exceeds limit ' + serverMemoryLimitMb + ' MB');
                gracefulReload('memory');
                return;
            }
        }

        // WPE fallback: performance.memory unavailable, use uptime ceiling
        if (isWPE && serverRestartHour === null && uptimeMs > WPE_MAX_UPTIME) {
            PlayerLog.info('Health: WPE uptime ' + Math.round(uptimeMs / 3600000) + 'h — restarting as safety net');
            gracefulReload('wpe-uptime');
            return;
        }

        // Responsiveness check
        if (Date.now() - lastRafTime > RAF_STALE_THRESHOLD) {
            rafResponsive = false;
            PlayerLog.warn('Health: rAF stale for ' + Math.round((Date.now() - lastRafTime) / 1000) + 's');
            gracefulReload('unresponsive');
            return;
        }

        // Scheduled restart
        if (serverRestartHour !== null && uptimeMs > MIN_UPTIME_FOR_SCHEDULED_RESTART) {
            const currentHour = new Date().getHours();
            if (currentHour === serverRestartHour) {
                PlayerLog.info('Health: scheduled restart (hour=' + serverRestartHour + ')');
                gracefulReload('scheduled');
                return;
            }
        }
    }

    function gracefulReload(reason, retries) {
        if (retries === undefined) retries = 0;
        // Check if a crossfade is in flight
        if (Object.keys(layerTxCleanup).length > 0 && retries < 5) {
            setTimeout(function () { gracefulReload(reason, retries + 1); }, 1000);
            return;
        }
        PlayerLog.info('Reloading player: ' + reason + (retries > 0 ? ' (waited ' + retries + 's for crossfade)' : ''));
        location.reload();
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
            const payload = {
                device_id: deviceId,
                player_time: new Date().toISOString(),
                player_timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
                player_version: PLAYER_VERSION,
                player_type: /BrightSign/i.test(navigator.userAgent) ? 'brightsign'
                           : /TinySignageApp/i.test(navigator.userAgent) ? 'android'
                           : /WPE/i.test(navigator.userAgent) ? 'wpe'
                           : 'browser',
                uptime_seconds: Math.round((Date.now() - startTime) / 1000),
                dom_responsive: rafResponsive,
            };

            // Include memory telemetry if available
            if (performance.memory) {
                payload.js_heap_used_mb = Math.round(performance.memory.usedJSHeapSize / (1024 * 1024));
                payload.js_heap_total_mb = Math.round(performance.memory.totalJSHeapSize / (1024 * 1024));
            } else {
                payload.js_heap_used_mb = null;
            }

            const resp = await authFetch(apiUrl('/api/player/heartbeat'), {
                method: 'POST',
                headers: authHeaders(),
                body: JSON.stringify(payload),
            });

            // Process heartbeat response
            if (resp.ok) {
                const data = await resp.json();

                // Server-requested restart
                if (data.restart === true) {
                    PlayerLog.info('Server requested player restart');
                    gracefulReload('server-requested');
                    return;
                }

                // Cache health settings
                if (data.restart_hour !== undefined) {
                    serverRestartHour = data.restart_hour;
                    try { localStorage.setItem('tinysignage_restart_hour', String(data.restart_hour)); } catch { /* ok */ }
                }
                if (data.memory_limit_mb !== undefined && data.memory_limit_mb !== null) {
                    serverMemoryLimitMb = data.memory_limit_mb;
                    try { localStorage.setItem('tinysignage_memory_limit_mb', String(data.memory_limit_mb)); } catch { /* ok */ }
                }
            }

            // Upload player log alongside heartbeat (fire-and-forget)
            uploadPlayerLog();
        } catch (e) {
            PlayerLog.warn('Heartbeat failed: ' + e.message);
        }
    }

    async function uploadPlayerLog() {
        if (!deviceId) return;
        try {
            const entries = PlayerLog.getAll();
            if (entries.length === 0) return;
            await authFetch(apiUrl('/api/devices/' + deviceId + '/player-log'), {
                method: 'POST',
                headers: authHeaders(),
                body: JSON.stringify({ entries: entries }),
            });
        } catch (e) {
            // Don't log this to PlayerLog to avoid recursion-like noise
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
            PlayerLog.info('Override already expired client-side, clearing');
            activeOverride = null;
            hideEmergencyMessage();
            if (playlist.length > 0) { playCurrentAsset(); } else { showSplash(); }
            return;
        }
        overrideExpiryTimer = setTimeout(() => {
            PlayerLog.info('Override expired client-side, clearing');
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

        loadAsset(item);

        const duration = getAssetDuration(item);
        cancelPlayback();
        playbackTimer = setTimeout(() => {
            transitionIndex++;
            playTransitionAsset();
        }, duration * 1000);
    }

    function finishTransition() {
        PlayerLog.info('Transition playlist complete, switching to new content');
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
                player_type: /BrightSign/i.test(navigator.userAgent) ? 'brightsign'
                           : /TinySignageApp/i.test(navigator.userAgent) ? 'android'
                           : /WPE/i.test(navigator.userAgent) ? 'wpe'
                           : 'browser',
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

        // Browser storage quota → promoted to device storage columns
        if (navigator.storage && navigator.storage.estimate) {
            try {
                const est = await navigator.storage.estimate();
                const quotaMb = Math.round((est.quota || 0) / (1024 * 1024));
                const usageMb = Math.round((est.usage || 0) / (1024 * 1024));
                if (quotaMb > 0) {
                    payload.hardware.storage_total_mb = quotaMb;
                    payload.hardware.storage_free_mb = quotaMb - usageMb;
                    payload.hardware.browser_storage_quota_mb = quotaMb;
                    payload.hardware.browser_storage_usage_mb = usageMb;
                }
            } catch (e) { PlayerLog.warn('Storage quota check failed: ' + e.message); }
        }

        // Server-side hardware fallback for WPE and other non-Chromium browsers
        if (payload.hardware.ram_mb == null || payload.hardware.storage_total_mb == null) {
            try {
                const hwResp = await authFetch(apiUrl('/api/player/hardware'));
                if (hwResp.ok) {
                    const hw = await hwResp.json();
                    if (payload.hardware.ram_mb == null && hw.ram_total_mb != null)
                        payload.hardware.ram_mb = hw.ram_total_mb;
                    if (payload.hardware.storage_total_mb == null && hw.disk_total_mb != null) {
                        payload.hardware.storage_total_mb = hw.disk_total_mb;
                        payload.hardware.storage_free_mb = hw.disk_free_mb;
                    }
                }
            } catch (e) { PlayerLog.warn('Server hardware fallback failed: ' + e.message); }
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
            PlayerLog.info('Capabilities reported');
        } catch (e) {
            PlayerLog.warn('Capability report failed: ' + e.message);
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

    function initTriggerEngine(flowData, sourcePlaylistId, restoreLoopCount) {
        teardownTriggerEngine();
        triggerFlow = flowData;
        currentSourcePlaylistId = sourcePlaylistId;
        loopCount = restoreLoopCount || 0;

        PlayerLog.info('TriggerEngine init — flow: ' + flowData.id + ' source: ' + sourcePlaylistId);

        const branches = findBranchesForSource(sourcePlaylistId);
        if (branches.length === 0) {
            PlayerLog.info('No trigger branches for source playlist');
            return;
        }

        registerKeyboardTriggers(branches);
        createTouchZoneOverlays(branches);
        startTimeoutTriggers(branches);
        connectBridge(branches);
        initWebhookTracking(branches);
    }

    function teardownTriggerEngine() {
        // Remove keyboard listener
        if (triggerKeydownHandler) {
            document.removeEventListener('keydown', triggerKeydownHandler);
            triggerKeydownHandler = null;
        }

        // Remove touch zones
        const container = document.getElementById('touch-zones-container');
        if (container) container.innerHTML = '';

        // Clear timeout timer
        if (triggerTimeoutTimer) {
            clearTimeout(triggerTimeoutTimer);
            triggerTimeoutTimer = null;
        }

        // Disconnect GPIO/joystick bridge
        disconnectGpioBridge();

        triggerFlow = null;
        currentSourcePlaylistId = '';
        loopCount = 0;
        shuffleAdvanceCount = 0;
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
            // Skip if override is active or registration form is visible
            if (activeOverride) return;
            const regOverlay = document.getElementById('registration-overlay');
            if (regOverlay && !regOverlay.classList.contains('hidden')) return;

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
                PlayerLog.info('Keyboard trigger fired: ' + config.key);
                fireTrigger(branch);
                return;
            }
        };

        document.addEventListener('keydown', triggerKeydownHandler);
        PlayerLog.info('Registered ' + keyBranches.length + ' keyboard trigger(s)');
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
                PlayerLog.info('Touch zone trigger fired');
                fireTrigger(branch);
            };
            zone.addEventListener('click', handler);
            zone.addEventListener('touchstart', handler, { passive: false });

            container.appendChild(zone);
        });

        PlayerLog.info('Created ' + touchBranches.length + ' touch zone overlay(s)');
    }

    function startTimeoutTriggers(branches) {
        const timeoutBranch = branches.find(b => b.trigger_type === 'timeout');
        if (!timeoutBranch) return;

        const config = timeoutBranch.trigger_config || {};
        const seconds = config.seconds || 30;

        if (triggerTimeoutTimer) clearTimeout(triggerTimeoutTimer);
        triggerTimeoutTimer = setTimeout(() => {
            if (activeOverride) return;
            PlayerLog.info('Timeout trigger fired after ' + seconds + 's');
            fireTrigger(timeoutBranch);
        }, seconds * 1000);

        PlayerLog.info('Timeout trigger set for ' + seconds + 's');
    }

    function checkLoopCount() {
        if (!triggerFlow) return;
        loopCount++;

        const branches = findBranchesForSource(currentSourcePlaylistId);
        const loopBranch = branches.find(b => b.trigger_type === 'loop_count');
        const targetCount = loopBranch ? (loopBranch.trigger_config?.count || 3) : '?';
        PlayerLog.info('Loop ' + loopCount + '/' + targetCount + ' on ' + currentSourcePlaylistId);

        if (!loopBranch) return;

        if (loopCount >= (loopBranch.trigger_config?.count || 3)) {
            PlayerLog.info('Loop count trigger fired after ' + loopCount + ' loops');
            fireTrigger(loopBranch);
        }
    }

    function fireTrigger(branch) {
        if (!branch.target_playlist) {
            PlayerLog.warn('Trigger branch has no target_playlist data');
            return;
        }

        const target = branch.target_playlist;
        const oldSource = currentSourcePlaylistId;
        const newSource = branch.target_playlist_id;
        PlayerLog.info('Trigger fired ' + branch.trigger_type + ' ' + oldSource + '→' + newSource);
        PlayerLog.info('Firing trigger → target playlist: ' + (target.name || target.id));

        // Teardown current triggers before swapping
        if (triggerKeydownHandler) {
            document.removeEventListener('keydown', triggerKeydownHandler);
            triggerKeydownHandler = null;
        }
        const touchContainer = document.getElementById('touch-zones-container');
        if (touchContainer) touchContainer.innerHTML = '';
        if (triggerTimeoutTimer) {
            clearTimeout(triggerTimeoutTimer);
            triggerTimeoutTimer = null;
        }

        // Swap playlist and settings
        playlist = target.items || [];
        settings = target.settings || {};
        currentSourcePlaylistId = newSource;
        currentIndex = 0;
        loopCount = 0;
        shuffleAdvanceCount = 0;

        // If the target playlist carries its own trigger flow (chained flows),
        // swap to it so its branches (e.g. loop_count back to source) become
        // active. Without this swap, findBranchesForSource(newSource) below
        // would return [] and the player would stay stuck on the new playlist.
        if (target.trigger_flow) {
            triggerFlow = target.trigger_flow;
            PlayerLog.info('Swapped trigger flow → ' + target.trigger_flow.id);
        }

        applySettings(settings);
        cancelPlayback();

        if (playlist.length > 0) {
            preloadAssets();
            playCurrentAsset();
        } else {
            showSplash();
        }

        // Re-register triggers for the new source playlist
        const newBranches = findBranchesForSource(currentSourcePlaylistId);
        PlayerLog.info('Trigger flow now: ' + (triggerFlow?.id || 'none') + ' branches: ' + newBranches.length);
        if (newBranches.length > 0) {
            registerKeyboardTriggers(newBranches);
            createTouchZoneOverlays(newBranches);
            startTimeoutTriggers(newBranches);
            connectBridge(newBranches);
            initWebhookTracking(newBranches);
        } else {
            disconnectGpioBridge();
        }
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
                PlayerLog.info('Webhook trigger fired for branch: ' + branch.id);
                fireTrigger(branch);
                return;
            }
        }
    }

    // --- GPIO / Joystick WebSocket client ---
    function connectBridge(branches) {
        const gpioBranches = branches.filter(b => b.trigger_type === 'gpio');
        const joystickBranches = branches.filter(b => b.trigger_type === 'joystick');

        if (gpioBranches.length === 0 && joystickBranches.length === 0) {
            disconnectGpioBridge();
            return;
        }

        // Always update the branch sets so onmessage uses current branches
        activeGpioBranches = gpioBranches;
        activeJoystickBranches = joystickBranches;

        // Already connected — branch sets updated above, no reconnect needed
        if (gpioWebSocket && gpioWebSocket.readyState === WebSocket.OPEN) return;

        disconnectGpioBridge();
        activeGpioBranches = gpioBranches; // restore after disconnectGpioBridge clears
        activeJoystickBranches = joystickBranches;

        try {
            gpioWebSocket = new WebSocket(GPIO_BRIDGE_URL);

            gpioWebSocket.onopen = function () {
                PlayerLog.info('Bridge connected (GPIO + joystick)');
            };

            gpioWebSocket.onmessage = function (event) {
                try {
                    const data = JSON.parse(event.data);
                    if (data.type === 'gpio') {
                        handleGpioEvent(data, activeGpioBranches);
                    } else if (data.type === 'joystick') {
                        handleJoystickEvent(data, activeJoystickBranches);
                    }
                } catch (e) {
                    PlayerLog.warn('Bridge message parse error: ' + e.message);
                }
            };

            gpioWebSocket.onclose = function () {
                PlayerLog.info('Bridge disconnected');
                gpioWebSocket = null;
                // Auto-reconnect after 5s if branches still exist
                if (triggerFlow) {
                    gpioReconnectTimer = setTimeout(() => {
                        const currentBranches = findBranchesForSource(currentSourcePlaylistId);
                        connectBridge(currentBranches);
                    }, 5000);
                }
            };

            gpioWebSocket.onerror = function () {
                // onclose will fire after this, handling reconnect
            };
        } catch (e) {
            PlayerLog.warn('Bridge connect failed: ' + e.message);
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
        activeGpioBranches = [];
        activeJoystickBranches = [];
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
                    PlayerLog.info('GPIO trigger fired: pin ' + data.pin);
                    fireTrigger(branch);
                    return;
                }
            }
        }
    }

    function handleJoystickEvent(data, joystickBranches) {
        if (activeOverride) return;
        if (data.type !== 'joystick') return;

        for (const branch of joystickBranches) {
            const config = branch.trigger_config || {};

            // Optional device filter (null/undefined = match any)
            if (config.device != null && config.device !== data.device) continue;

            if (config.input === 'button' && data.event === 'button') {
                if (config.button === data.button) {
                    const expectedValue = config.value != null ? config.value : 1;
                    if (data.value === expectedValue) {
                        PlayerLog.info('Joystick trigger fired: button ' + data.button);
                        fireTrigger(branch);
                        return;
                    }
                }
            } else if (config.input === 'axis' && data.event === 'axis') {
                if (config.axis === data.axis && config.direction === data.direction) {
                    PlayerLog.info('Joystick trigger fired: axis ' + data.axis + ' ' + data.direction);
                    fireTrigger(branch);
                    return;
                }
            }
        }
    }

    // --- Debug overlay (Ctrl+Shift+D) ---
    function initDebugOverlay() {
        document.addEventListener('keydown', (e) => {
            if (e.ctrlKey && e.shiftKey && e.key === 'D') {
                e.preventDefault();
                toggleDebugOverlay();
            }
        });
    }

    function toggleDebugOverlay() {
        let overlay = document.getElementById('debug-log-overlay');
        if (overlay) {
            overlay.classList.toggle('hidden');
            if (!overlay.classList.contains('hidden')) {
                refreshDebugOverlay();
            }
            return;
        }
        // Create overlay
        overlay = document.createElement('div');
        overlay.id = 'debug-log-overlay';
        overlay.innerHTML =
            '<div class="debug-log-header">' +
                '<span>Player Log (' + LOG_MAX_ENTRIES + ' max)</span>' +
                '<span>' +
                    '<button id="debug-log-refresh">Refresh</button> ' +
                    '<button id="debug-log-clear">Clear</button> ' +
                    '<button id="debug-log-close">Close</button>' +
                '</span>' +
            '</div>' +
            '<pre id="debug-log-content"></pre>';
        document.body.appendChild(overlay);

        document.getElementById('debug-log-refresh').addEventListener('click', refreshDebugOverlay);
        document.getElementById('debug-log-clear').addEventListener('click', () => {
            PlayerLog.clear();
            refreshDebugOverlay();
        });
        document.getElementById('debug-log-close').addEventListener('click', () => {
            overlay.classList.add('hidden');
        });
        refreshDebugOverlay();
    }

    function refreshDebugOverlay() {
        const el = document.getElementById('debug-log-content');
        if (el) {
            el.textContent = PlayerLog.toText() || '(empty)';
            el.scrollTop = el.scrollHeight;
        }
    }

    initDebugOverlay();

    // --- Go ---
    init();
})();
