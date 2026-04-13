<template>
  <div>
    <h2>Settings</h2>

    <form v-if="settings" @submit.prevent="saveSettings" class="settings-form">
      <div class="form-group">
        <label>Transition Duration (seconds)</label>
        <input type="number" v-model.number="settings.transition_duration" step="0.1" min="0" />
      </div>
      <div class="form-group">
        <label>Transition Type</label>
        <select v-model="settings.transition_type">
          <option value="fade">Fade</option>
          <option value="slide">Slide</option>
          <option value="cut">Cut</option>
        </select>
      </div>
      <div class="form-group">
        <label>Default Duration (seconds)</label>
        <input type="number" v-model.number="settings.default_duration" min="1" />
      </div>
      <div class="form-group">
        <label>Default Scaling</label>
        <select v-model="settings.object_fit">
          <option value="contain">Fit inside (black bars)</option>
          <option value="cover">Fill & crop</option>
          <option value="fill">Stretch to fill</option>
          <option value="none">Original size</option>
        </select>
      </div>
      <div class="form-group">
        <label>Display Effect</label>
        <select v-model="settings.effect">
          <option value="none">None</option>
          <option value="zoom-in">Zoom In</option>
          <option value="zoom-out">Zoom Out</option>
          <option value="pan-left">Pan Left</option>
          <option value="pan-right">Pan Right</option>
          <option value="pan-up">Pan Up</option>
          <option value="pan-down">Pan Down</option>
          <option value="random">Random</option>
        </select>
        <span class="hint-text">Adds slow motion to images. Does not affect video.</span>
      </div>
      <div class="form-group checkbox">
        <label>
          <input type="checkbox" v-model="settings.shuffle" />
          Shuffle playlist
        </label>
      </div>
      <button type="submit" class="btn-save">Save Settings</button>
      <span v-if="saved" class="save-msg">Saved!</span>
    </form>

    <hr class="section-divider" />

    <h3>Player Health</h3>
    <p class="section-desc">Automatic recovery settings for player devices. Changes apply on the next heartbeat.</p>

    <div v-if="settings" class="settings-form">
      <div class="form-group">
        <label>Scheduled Daily Restart</label>
        <select v-model="settings.player_restart_hour" @change="saveSettings">
          <option :value="null">Disabled</option>
          <option v-for="h in 24" :key="h - 1" :value="h - 1">{{ (h - 1).toString().padStart(2, '0') }}:00</option>
        </select>
        <span class="hint-text">Restart all players once a day at this hour to reclaim memory. Requires at least 1 hour uptime.</span>
      </div>
    </div>

    <hr class="section-divider" />

    <h3>Network &amp; Security</h3>
    <p class="section-desc">How the CMS and players connect to this server. To change these, edit <code>config.yaml</code> and restart.</p>

    <div v-if="network" class="network-panel">
      <div class="form-group">
        <label>Protocol</label>
        <div v-if="network.https_enabled" class="status-row status-ok">
          <span class="dot"></span> HTTPS (encrypted)
        </div>
        <div v-else class="status-row status-warn">
          <span class="dot"></span> HTTP (not encrypted)
        </div>
        <span v-if="!network.https_enabled" class="hint-text">
          Re-run first-boot setup (or edit <code>config.yaml</code>) to enable HTTPS. See the docs for details.
        </span>
      </div>

      <div class="form-group">
        <label>Listening on</label>
        <div class="readonly-value">{{ network.host }}:{{ network.port }}</div>
      </div>

      <div v-if="network.server_url" class="form-group">
        <label>Server URL</label>
        <div class="readonly-value">{{ network.server_url }}</div>
      </div>

      <details v-if="network.https_enabled && network.cert_fingerprint_sha256" class="tech-details">
        <summary>Technical details</summary>
        <div class="form-group" style="margin-top: 0.8rem">
          <label>Certificate file</label>
          <div class="readonly-value">{{ network.cert_path }}</div>
        </div>
        <div class="form-group">
          <label>SHA-256 fingerprint</label>
          <input type="text" :value="network.cert_fingerprint_sha256" readonly @click="$event.target.select()" />
          <span class="hint-text">
            Verify with <code>openssl x509 -in {{ network.cert_path }} -noout -fingerprint -sha256</code>
          </span>
        </div>
      </details>
    </div>

    <hr class="section-divider" />

    <h3>Backup & Restore</h3>
    <p class="section-desc">Export or import a complete backup of your database and media files.</p>

    <div class="backup-actions">
      <div class="backup-group">
        <button @click="exportBackup" :disabled="exporting" class="btn-save">
          <i class="pi pi-download"></i>
          {{ exporting ? 'Exporting...' : 'Export Backup' }}
        </button>
        <p class="help-text">Download a ZIP containing your database and all media files.</p>
      </div>

      <div class="backup-group">
        <label v-if="!selectedFile" class="btn-import" :class="{ disabled: importing }">
          <i class="pi pi-upload"></i>
          Choose Backup File
          <input type="file" accept=".zip" @change="onFileSelected" :disabled="importing" hidden ref="fileInput" />
        </label>

        <div v-if="selectedFile" class="import-confirm">
          <p class="selected-file">
            <i class="pi pi-file"></i>
            {{ selectedFile.name }}
            <span class="file-size">({{ formatSize(selectedFile.size) }})</span>
          </p>
          <p class="warning">
            <i class="pi pi-exclamation-triangle"></i>
            This will replace ALL current data including database and media files.
            A server restart is required after restore.
          </p>
          <div class="confirm-actions">
            <button @click="confirmImport" :disabled="importing" class="btn-danger">
              {{ importing ? 'Restoring...' : 'Restore Backup' }}
            </button>
            <button @click="cancelImport" :disabled="importing" class="btn-cancel">Cancel</button>
          </div>
        </div>

        <p v-if="!selectedFile" class="help-text">Upload a previously exported backup to restore all data.</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useToast } from 'primevue/usetoast'
import { api } from '../api/client.js'

const toast = useToast()
const settings = ref(null)
const network = ref(null)
const saved = ref(false)
const exporting = ref(false)
const importing = ref(false)
const selectedFile = ref(null)
const fileInput = ref(null)

async function loadSettings() {
  settings.value = await api.get('/settings')
}

async function loadNetwork() {
  try {
    network.value = await api.get('/settings/network')
  } catch (e) {
    // Non-fatal — panel just stays hidden
    network.value = null
  }
}

async function saveSettings() {
  await api.patch('/settings', settings.value)
  saved.value = true
  setTimeout(() => (saved.value = false), 2000)
}

function getAuthHeaders() {
  const token = localStorage.getItem('tinysignage_token') || localStorage.getItem('tinysignage_admin_token')
  return token ? { Authorization: `Bearer ${token}` } : {}
}

async function exportBackup() {
  exporting.value = true
  try {
    const resp = await fetch('/api/backup/export', {
      headers: getAuthHeaders(),
    })
    if (!resp.ok) {
      const data = await resp.json().catch(() => ({}))
      throw new Error(data.detail || `Export failed (${resp.status})`)
    }

    const blob = await resp.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    const disposition = resp.headers.get('Content-Disposition') || ''
    const match = disposition.match(/filename="(.+)"/)
    a.download = match ? match[1] : 'tinysignage-backup.zip'
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)

    toast.add({ severity: 'success', summary: 'Export Complete', detail: 'Backup downloaded.', life: 5000 })
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Export Failed', detail: e.message, life: 8000 })
  } finally {
    exporting.value = false
  }
}

function onFileSelected(event) {
  const file = event.target.files[0]
  if (file) {
    selectedFile.value = file
  }
}

function cancelImport() {
  selectedFile.value = null
  if (fileInput.value) {
    fileInput.value.value = ''
  }
}

async function confirmImport() {
  if (!selectedFile.value) return

  importing.value = true
  try {
    const formData = new FormData()
    formData.append('file', selectedFile.value)

    const resp = await fetch('/api/backup/import', {
      method: 'POST',
      headers: getAuthHeaders(),
      body: formData,
    })

    if (!resp.ok) {
      const data = await resp.json().catch(() => ({}))
      throw new Error(data.detail || `Import failed (${resp.status})`)
    }

    const data = await resp.json()
    toast.add({
      severity: 'success',
      summary: 'Restore Complete',
      detail: data.message,
      life: 15000,
    })

    selectedFile.value = null
    if (fileInput.value) {
      fileInput.value.value = ''
    }

    // Reload settings since the database was replaced
    await loadSettings()
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Restore Failed', detail: e.message, life: 8000 })
  } finally {
    importing.value = false
  }
}

function formatSize(bytes) {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  if (bytes < 1024 * 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
  return (bytes / (1024 * 1024 * 1024)).toFixed(1) + ' GB'
}

onMounted(() => {
  loadSettings()
  loadNetwork()
})
</script>

<style scoped>
h2 { margin-bottom: 1.5rem; color: #fff; }
h3 { color: #fff; margin-bottom: 0.5rem; }

.settings-form {
  max-width: 400px;
}

.form-group {
  margin-bottom: 1.2rem;
}

.form-group label {
  display: block;
  font-size: 0.85rem;
  color: #aaa;
  margin-bottom: 0.4rem;
}

.form-group input[type="number"],
.form-group select {
  width: 100%;
  background: #1a1d27;
  border: 1px solid #3a3a5a;
  color: #eee;
  padding: 0.5rem 0.6rem;
  border-radius: 4px;
  font-size: 0.9rem;
}

.form-group input:focus,
.form-group select:focus {
  outline: none;
  border-color: #7c83ff;
}

.hint-text {
  display: block;
  font-size: 0.75rem;
  color: #777;
  margin-top: 0.3rem;
}

.checkbox label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  cursor: pointer;
  color: #ccc;
}

.btn-save {
  background: #7c83ff;
  color: #fff;
  border: none;
  padding: 0.6rem 1.5rem;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.9rem;
  transition: background 0.15s;
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
}

.btn-save:hover {
  background: #6b72e8;
}

.btn-save:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.save-msg {
  margin-left: 1rem;
  color: #4caf50;
  font-size: 0.85rem;
}

.section-divider {
  border: none;
  border-top: 1px solid #2a2d3a;
  margin: 2rem 0;
}

.network-panel {
  max-width: 500px;
}

.network-panel code {
  background: #1a1d27;
  border: 1px solid #2a2d3a;
  padding: 0.05rem 0.3rem;
  border-radius: 3px;
  font-size: 0.78rem;
  color: #bbb;
}

.status-row {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.9rem;
}

.status-row .dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  display: inline-block;
}

.status-ok {
  color: #4caf50;
}

.status-ok .dot {
  background: #4caf50;
}

.status-warn {
  color: #aaa;
}

.status-warn .dot {
  background: #555;
  border: 1px solid #777;
}

.readonly-value {
  background: #1a1d27;
  border: 1px solid #3a3a5a;
  color: #ccc;
  padding: 0.5rem 0.6rem;
  border-radius: 4px;
  font-size: 0.85rem;
  font-family: ui-monospace, Menlo, Consolas, monospace;
  word-break: break-all;
}

.network-panel input[type="text"][readonly] {
  width: 100%;
  background: #1a1d27;
  border: 1px solid #3a3a5a;
  color: #ccc;
  padding: 0.5rem 0.6rem;
  border-radius: 4px;
  font-size: 0.78rem;
  font-family: ui-monospace, Menlo, Consolas, monospace;
}

.tech-details {
  margin-top: 0.5rem;
}

.tech-details summary {
  color: #888;
  font-size: 0.82rem;
  cursor: pointer;
}

.tech-details summary:hover {
  color: #bbb;
}

.section-desc {
  color: #999;
  font-size: 0.85rem;
  margin-bottom: 1.2rem;
}

.backup-actions {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
  max-width: 500px;
}

.backup-group {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.help-text {
  color: #777;
  font-size: 0.8rem;
}

.btn-import {
  background: #2a2d3a;
  color: #ccc;
  border: 1px dashed #4a4d5a;
  padding: 0.6rem 1.5rem;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.9rem;
  transition: background 0.15s, border-color 0.15s;
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  width: fit-content;
}

.btn-import:hover {
  background: #353846;
  border-color: #7c83ff;
  color: #fff;
}

.btn-import.disabled {
  opacity: 0.6;
  cursor: not-allowed;
  pointer-events: none;
}

.import-confirm {
  background: #1a1d27;
  border: 1px solid #3a3a5a;
  border-radius: 6px;
  padding: 1rem;
}

.selected-file {
  color: #ddd;
  font-size: 0.9rem;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.6rem;
}

.file-size {
  color: #888;
  font-size: 0.8rem;
}

.warning {
  color: #ff9800;
  font-size: 0.8rem;
  display: flex;
  align-items: flex-start;
  gap: 0.5rem;
  margin-bottom: 1rem;
  line-height: 1.4;
}

.warning i {
  margin-top: 0.1rem;
  flex-shrink: 0;
}

.confirm-actions {
  display: flex;
  gap: 0.8rem;
}

.btn-danger {
  background: #e53935;
  color: #fff;
  border: none;
  padding: 0.5rem 1.2rem;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.85rem;
  transition: background 0.15s;
}

.btn-danger:hover {
  background: #c62828;
}

.btn-danger:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.btn-cancel {
  background: transparent;
  color: #aaa;
  border: 1px solid #3a3a5a;
  padding: 0.5rem 1.2rem;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.85rem;
  transition: background 0.15s, color 0.15s;
}

.btn-cancel:hover {
  background: #2a2d3a;
  color: #fff;
}

.btn-cancel:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

</style>
