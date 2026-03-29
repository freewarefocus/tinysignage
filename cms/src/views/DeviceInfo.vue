<template>
  <div>
    <div class="page-header">
      <h2>Devices</h2>
      <div class="header-right">
        <span class="refresh-hint" v-if="lastRefresh">Updated {{ relativeTime(lastRefresh) }}</span>
        <button class="btn-primary" @click="showAddDevice = true">
          <i class="pi pi-plus"></i> Add Device
        </button>
      </div>
    </div>

    <!-- Add Device dialog -->
    <div v-if="showAddDevice" class="dialog-overlay" @click.self="closeAddDevice">
      <div class="dialog">
        <h3>Add Device</h3>
        <div v-if="!newDevice">
          <input
            v-model="newDeviceName"
            placeholder="Device name (e.g. Lobby Screen)"
            @keydown.enter="createDevice"
            @keydown.escape="closeAddDevice"
            ref="addInput"
          />
          <div class="dialog-actions">
            <button class="btn-primary" @click="createDevice" :disabled="creating">Create</button>
            <button class="btn-secondary" @click="closeAddDevice">Cancel</button>
          </div>
        </div>
        <div v-else class="pairing-result">
          <p>Device created. Use this pairing code on the player:</p>
          <div class="pairing-code">{{ newDevice.pairing_code }}</div>
          <div class="pairing-url">
            <label>Or open this URL on the player:</label>
            <code>{{ newDevice.pairing_url }}</code>
          </div>
          <p class="pairing-expires">Code expires in {{ formatCountdown(pairingCountdown) }}</p>
          <div class="dialog-actions">
            <button class="btn-primary" @click="closeAddDevice">Done</button>
          </div>
        </div>
      </div>
    </div>

    <!-- Device detail panel -->
    <div v-if="selectedDevice" class="dialog-overlay" @click.self="closeDetail">
      <div class="dialog detail-dialog">
        <div class="detail-header">
          <div>
            <div v-if="editingName" class="edit-row">
              <input
                v-model="nameInput"
                @keydown.enter="saveName"
                @keydown.escape="editingName = false"
                ref="nameEditInput"
                class="name-edit-input"
              />
              <button class="btn-primary btn-sm" @click="saveName">Save</button>
              <button class="btn-secondary btn-sm" @click="editingName = false">Cancel</button>
            </div>
            <h3 v-else class="editable-name" @click="startEditName">
              {{ selectedDevice.name }}
              <i class="pi pi-pencil edit-icon"></i>
            </h3>
          </div>
          <button class="btn-icon" @click="closeDetail"><i class="pi pi-times"></i></button>
        </div>

        <div class="detail-fields">
          <div class="detail-field">
            <label>Status</label>
            <span :class="'status-badge status-' + selectedDevice.status">{{ selectedDevice.status }}</span>
          </div>
          <div class="detail-field">
            <label>Last Seen</label>
            <span>{{ selectedDevice.last_seen ? relativeTime(selectedDevice.last_seen) : 'Never' }}</span>
          </div>
          <div class="detail-field">
            <label>IP Address</label>
            <span class="mono">{{ selectedDevice.ip_address || 'Unknown' }}</span>
          </div>
          <div class="detail-field">
            <label>Device ID</label>
            <span class="mono small">{{ selectedDevice.id }}</span>
          </div>
          <div class="detail-field">
            <label>Created</label>
            <span>{{ selectedDevice.created_at ? parseUTC(selectedDevice.created_at).toLocaleDateString() : '—' }}</span>
          </div>
        </div>

        <!-- Playlist assignment -->
        <div class="detail-section">
          <label>Assigned Playlist</label>
          <select v-model="detailPlaylistId" @change="assignPlaylist" class="select-input full">
            <option value="">None</option>
            <option v-for="pl in playlists" :key="pl.id" :value="pl.id">
              {{ pl.name }}{{ pl.is_default ? ' (default)' : '' }}
            </option>
          </select>
        </div>

        <!-- Health info -->
        <div v-if="deviceHealth" class="detail-section">
          <label>Health</label>
          <div class="health-fields">
            <div class="health-item">
              <span class="health-label">Player Version</span>
              <span>{{ deviceHealth.player_version || '—' }}</span>
            </div>
            <div class="health-item">
              <span class="health-label">Timezone</span>
              <span>{{ deviceHealth.player_timezone || '—' }}</span>
            </div>
            <div class="health-item">
              <span class="health-label">Clock Drift</span>
              <span :class="{ 'drift-warn': deviceHealth.clock_drift_seconds != null && Math.abs(deviceHealth.clock_drift_seconds) > 30 }">
                {{ deviceHealth.clock_drift_seconds != null ? deviceHealth.clock_drift_seconds + 's' : '—' }}
              </span>
            </div>
            <div v-if="deviceHealth.warnings?.length" class="health-item full-width">
              <span class="health-label">Warnings</span>
              <span class="health-warnings">{{ deviceHealth.warnings.join(', ') }}</span>
            </div>
          </div>
        </div>

        <!-- Pairing code -->
        <div class="detail-section">
          <label>Pairing Code</label>
          <div v-if="devicePairing">
            <div class="pairing-code small">{{ devicePairing.code }}</div>
            <code class="pairing-url-inline">{{ devicePairing.pairing_url }}</code>
            <p class="pairing-expires">Expires in {{ formatCountdown(pairingCountdown) }}</p>
          </div>
          <div v-else-if="selectedDevice.has_pairing_code" class="pairing-active">
            <span>Active pairing code exists.</span>
            <button class="btn-secondary btn-sm" @click="regeneratePairingCode">Regenerate</button>
          </div>
          <div v-else>
            <button class="btn-secondary btn-sm" @click="regeneratePairingCode">Generate Pairing Code</button>
          </div>
        </div>

        <!-- Delete -->
        <div class="detail-section detail-danger">
          <button class="btn-danger" @click="confirmDeleteDevice">
            <i class="pi pi-trash"></i> Delete Device
          </button>
        </div>
      </div>
    </div>

    <div v-if="loading" class="loading">Loading devices...</div>

    <div v-else-if="devices.length === 0" class="empty">
      No devices registered. Click <strong>Add Device</strong> to get started.
    </div>

    <div v-else class="device-grid">
      <div
        v-for="d in devices"
        :key="d.id"
        class="device-card"
        @click="openDevice(d)"
      >
        <div class="card-header">
          <span class="card-name">{{ d.name }}</span>
          <span :class="'status-dot status-' + d.status" :title="d.status"></span>
        </div>
        <div class="card-body">
          <div class="card-field">
            <i class="pi pi-list"></i>
            <span>{{ playlistName(d.playlist_id) }}</span>
          </div>
          <div class="card-field">
            <i class="pi pi-clock"></i>
            <span>{{ d.last_seen ? relativeTime(d.last_seen) : 'Never seen' }}</span>
          </div>
          <div v-if="d.ip_address" class="card-field">
            <i class="pi pi-globe"></i>
            <span class="mono">{{ d.ip_address }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { api } from '../api/client.js'
import { relativeTime, parseUTC } from '../utils/date.js'

const devices = ref([])
const playlists = ref([])
const loading = ref(true)
const lastRefresh = ref(null)
let refreshInterval = null

// Add Device
const showAddDevice = ref(false)
const newDeviceName = ref('')
const newDevice = ref(null)
const creating = ref(false)
const addInput = ref(null)

// Detail panel
const selectedDevice = ref(null)
const editingName = ref(false)
const nameInput = ref('')
const nameEditInput = ref(null)
const detailPlaylistId = ref('')
const devicePairing = ref(null)
const deviceHealth = ref(null)

// Pairing countdown
const pairingCountdown = ref(0)
let countdownInterval = null

function startCountdown(seconds) {
  if (countdownInterval) clearInterval(countdownInterval)
  pairingCountdown.value = seconds
  countdownInterval = setInterval(() => {
    pairingCountdown.value--
    if (pairingCountdown.value <= 0) {
      clearInterval(countdownInterval)
      countdownInterval = null
    }
  }, 1000)
}

function formatCountdown(totalSeconds) {
  if (totalSeconds <= 0) return 'expired'
  const m = Math.floor(totalSeconds / 60)
  const s = totalSeconds % 60
  return `${m}:${s.toString().padStart(2, '0')}`
}

watch(showAddDevice, async (val) => {
  if (val) {
    newDeviceName.value = ''
    newDevice.value = null
    creating.value = false
    await nextTick()
    addInput.value?.focus()
  }
})

function playlistName(playlistId) {
  if (!playlistId) return 'No playlist'
  const pl = playlists.value.find(p => p.id === playlistId)
  return pl ? pl.name : 'Unknown'
}

async function loadDevices() {
  try {
    devices.value = await api.get('/devices')
    lastRefresh.value = new Date()
  } finally {
    loading.value = false
  }
}

async function loadPlaylists() {
  playlists.value = await api.get('/playlists')
}

async function createDevice() {
  if (creating.value) return
  creating.value = true
  try {
    const name = newDeviceName.value.trim() || 'New Player'
    const result = await api.post('/devices', { name })
    newDevice.value = result
    startCountdown(600)
    await loadDevices()
  } finally {
    creating.value = false
  }
}

function closeAddDevice() {
  showAddDevice.value = false
  newDevice.value = null
  if (countdownInterval) { clearInterval(countdownInterval); countdownInterval = null }
}

async function openDevice(d) {
  selectedDevice.value = d
  detailPlaylistId.value = d.playlist_id || ''
  devicePairing.value = null
  deviceHealth.value = null
  editingName.value = false
  // Load health data for this device
  try {
    const dashboard = await api.get('/health/dashboard')
    deviceHealth.value = dashboard.devices?.find(h => h.id === d.id) || null
  } catch { /* ignore */ }
}

function closeDetail() {
  selectedDevice.value = null
  devicePairing.value = null
  deviceHealth.value = null
  if (countdownInterval) { clearInterval(countdownInterval); countdownInterval = null }
}

async function confirmDeleteDevice() {
  if (!selectedDevice.value) return
  if (!confirm(`Delete device "${selectedDevice.value.name}"? This will remove all associated schedules, tokens, and overrides.`)) return
  await api.delete(`/devices/${selectedDevice.value.id}`)
  closeDetail()
  await loadDevices()
}

function startEditName() {
  nameInput.value = selectedDevice.value.name
  editingName.value = true
  nextTick(() => nameEditInput.value?.focus())
}

async function saveName() {
  const name = nameInput.value.trim()
  if (name && name !== selectedDevice.value.name) {
    const updated = await api.patch(`/devices/${selectedDevice.value.id}`, { name })
    selectedDevice.value = updated
    await loadDevices()
  }
  editingName.value = false
}

async function assignPlaylist() {
  const playlistId = detailPlaylistId.value || null
  const updated = await api.patch(`/devices/${selectedDevice.value.id}`, { playlist_id: playlistId })
  selectedDevice.value = updated
  await loadDevices()
}

async function regeneratePairingCode() {
  const result = await api.post(`/devices/${selectedDevice.value.id}/pairing-code`)
  devicePairing.value = result
  startCountdown(result.expires_in)
  // Refresh device to update has_pairing_code
  const updated = await api.get(`/devices/${selectedDevice.value.id}`)
  selectedDevice.value = updated
}

onMounted(async () => {
  await Promise.all([loadDevices(), loadPlaylists()])
  // Auto-refresh every 30 seconds
  refreshInterval = setInterval(loadDevices, 30000)
})

onUnmounted(() => {
  if (refreshInterval) clearInterval(refreshInterval)
  if (countdownInterval) clearInterval(countdownInterval)
})
</script>

<style scoped>
h2 { color: #fff; }
h3 { color: #fff; margin-bottom: 0.5rem; }

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.5rem;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.refresh-hint {
  color: #666;
  font-size: 0.8rem;
}

.btn-primary {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  background: #7c83ff;
  color: #fff;
  border: none;
  padding: 0.5rem 1rem;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.85rem;
  transition: background 0.15s;
}

.btn-primary:hover { background: #6b72ee; }
.btn-primary:disabled { opacity: 0.5; cursor: default; }
.btn-primary.btn-sm { padding: 0.35rem 0.75rem; font-size: 0.8rem; }

.btn-secondary {
  background: #3a3a5a;
  color: #ccc;
  border: none;
  padding: 0.5rem 1rem;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.85rem;
}

.btn-secondary.btn-sm { padding: 0.35rem 0.75rem; font-size: 0.8rem; }

.btn-icon {
  background: none;
  border: none;
  color: #888;
  cursor: pointer;
  padding: 0.3rem;
  border-radius: 4px;
  transition: color 0.15s;
}

.btn-icon:hover { color: #fff; }

.loading, .empty {
  text-align: center;
  padding: 3rem;
  color: #666;
}

.empty strong { color: #7c83ff; }

/* Device Grid */
.device-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 1rem;
}

.device-card {
  background: #1a1d27;
  border-radius: 8px;
  padding: 1rem 1.2rem;
  cursor: pointer;
  transition: box-shadow 0.15s, background 0.15s;
  border: 1px solid transparent;
}

.device-card:hover {
  border-color: #7c83ff;
  background: #1e2130;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.6rem;
}

.card-name {
  font-size: 1rem;
  font-weight: 500;
  color: #fff;
}

.status-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
}

.status-dot.status-online { background: #4caf50; box-shadow: 0 0 6px rgba(76, 175, 80, 0.5); }
.status-dot.status-offline { background: #f44336; }
.status-dot.status-unknown { background: #666; }

.card-body {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.card-field {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  color: #999;
  font-size: 0.85rem;
}

.card-field i { font-size: 0.75rem; width: 1rem; text-align: center; color: #666; }

.mono { font-family: monospace; font-size: 0.82rem; }

/* Dialog */
.dialog-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.dialog {
  background: #1a1d27;
  border-radius: 10px;
  padding: 1.5rem;
  width: 420px;
  max-width: 90vw;
  border: 1px solid #2a2d3a;
}

.detail-dialog {
  width: 500px;
  max-height: 80vh;
  overflow-y: auto;
}

.dialog input {
  width: 100%;
  background: #0f1117;
  border: 1px solid #3a3a5a;
  color: #eee;
  padding: 0.5rem 0.75rem;
  border-radius: 6px;
  outline: none;
  font-size: 0.9rem;
  margin-bottom: 0.75rem;
}

.dialog input:focus { border-color: #7c83ff; }

.dialog p {
  color: #aaa;
  font-size: 0.9rem;
  margin-bottom: 0.75rem;
  line-height: 1.5;
}

.dialog-actions {
  display: flex;
  gap: 0.5rem;
  justify-content: flex-end;
}

/* Pairing */
.pairing-result { text-align: center; }

.pairing-code {
  font-size: 2.5rem;
  font-weight: 700;
  font-family: monospace;
  color: #7c83ff;
  letter-spacing: 0.3rem;
  margin: 1rem 0;
  text-align: center;
}

.pairing-code.small {
  font-size: 1.8rem;
  margin: 0.5rem 0;
}

.pairing-url {
  margin-bottom: 1rem;
}

.pairing-url label {
  display: block;
  font-size: 0.8rem;
  color: #888;
  margin-bottom: 0.3rem;
}

.pairing-url code,
.pairing-url-inline {
  display: block;
  background: #0f1117;
  padding: 0.5rem 0.75rem;
  border-radius: 4px;
  font-size: 0.8rem;
  color: #aaa;
  word-break: break-all;
}

.pairing-url-inline {
  margin-top: 0.3rem;
  margin-bottom: 0.3rem;
}

.pairing-expires {
  color: #888;
  font-size: 0.8rem;
}

.pairing-active {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  color: #aaa;
  font-size: 0.85rem;
}

/* Detail panel */
.detail-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 1rem;
  padding-bottom: 0.75rem;
  border-bottom: 1px solid #2a2d3a;
}

.editable-name {
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.edit-icon {
  font-size: 0.7rem;
  color: #555;
}

.editable-name:hover .edit-icon { color: #7c83ff; }

.edit-row {
  display: flex;
  gap: 0.5rem;
  align-items: center;
}

.name-edit-input {
  margin-bottom: 0 !important;
  width: auto !important;
  flex: 1;
}

.detail-fields {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.8rem;
  margin-bottom: 1.2rem;
}

.detail-field label {
  display: block;
  font-size: 0.75rem;
  color: #666;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 0.2rem;
}

.detail-field span {
  color: #ddd;
  font-size: 0.9rem;
}

.detail-field .small { font-size: 0.75rem; color: #888; }

.status-badge {
  text-transform: uppercase;
  font-size: 0.8rem;
  font-weight: 600;
}

.status-badge.status-online { color: #4caf50; }
.status-badge.status-offline { color: #f44336; }
.status-badge.status-unknown { color: #666; }

.detail-section {
  margin-bottom: 1.2rem;
}

.detail-section > label {
  display: block;
  font-size: 0.8rem;
  color: #888;
  margin-bottom: 0.4rem;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.select-input {
  background: #0f1117;
  border: 1px solid #3a3a5a;
  color: #eee;
  padding: 0.4rem 0.6rem;
  border-radius: 4px;
  outline: none;
  font-size: 0.85rem;
  cursor: pointer;
}

.select-input.full { width: 100%; }
.select-input:focus { border-color: #7c83ff; }

/* Health */
.health-fields {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.5rem;
}

.health-item {
  display: flex;
  flex-direction: column;
  gap: 0.1rem;
}

.health-item.full-width { grid-column: 1 / -1; }

.health-label {
  font-size: 0.7rem;
  color: #666;
  text-transform: uppercase;
  letter-spacing: 0.3px;
}

.health-item span:not(.health-label):not(.health-warnings) {
  color: #ccc;
  font-size: 0.85rem;
}

.drift-warn { color: #f0ad4e !important; }

.health-warnings {
  color: #f0ad4e;
  font-size: 0.8rem;
}

/* Delete */
.detail-danger {
  border-top: 1px solid #2a2d3a;
  padding-top: 1rem;
}

.btn-danger {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  background: #5a2030;
  color: #f88;
  border: none;
  padding: 0.5rem 1rem;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.85rem;
  transition: background 0.15s;
}

.btn-danger:hover { background: #7a2840; }
</style>
