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
          <option value="fade">Crossfade</option>
          <option value="slide">Slide</option>
          <option value="cut">Cut</option>
        </select>
      </div>
      <div class="form-group">
        <label>Default Duration (seconds)</label>
        <input type="number" v-model.number="settings.default_duration" min="1" />
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

    <h3>Registration Key</h3>
    <p class="section-desc">Players use this key to self-register. They appear as "pending" until you approve them.</p>

    <div class="regkey-section">
      <div v-if="regKeyStatus">
        <div class="regkey-status">
          <span v-if="regKeyStatus.has_key" class="regkey-active">Active</span>
          <span v-else class="regkey-none">Not configured</span>
          <span v-if="regKeyStatus.has_key && regKeyStatus.created_at" class="regkey-date">
            Created {{ relativeDate(regKeyStatus.created_at) }}
          </span>
        </div>
      </div>

      <div v-if="generatedKey" class="regkey-display">
        <div class="regkey-value">
          <input type="text" :value="generatedKey" readonly @click="$event.target.select()" class="regkey-input" />
          <button @click="copyRegKey" class="btn-copy">Copy</button>
        </div>
        <p class="regkey-warning">This key is shown once. If lost, regenerate a new one. Already-registered devices are not affected.</p>
      </div>

      <button @click="regenerateRegKey" :disabled="regenerating" class="btn-save">
        {{ regKeyStatus?.has_key ? 'Regenerate Key' : 'Generate Key' }}
      </button>
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
const saved = ref(false)
const exporting = ref(false)
const importing = ref(false)
const selectedFile = ref(null)
const fileInput = ref(null)

// Registration key
const regKeyStatus = ref(null)
const generatedKey = ref(null)
const regenerating = ref(false)

async function loadSettings() {
  settings.value = await api.get('/settings')
}

async function loadRegKeyStatus() {
  try {
    regKeyStatus.value = await api.get('/settings/registration-key')
  } catch (err) { console.warn('[Settings] Failed to load reg key status:', err) }
}

async function regenerateRegKey() {
  regenerating.value = true
  try {
    const result = await api.post('/settings/registration-key/regenerate')
    generatedKey.value = result.registration_key
    await loadRegKeyStatus()
    toast.add({ severity: 'success', summary: 'Key Generated', detail: 'Copy it now — it won\'t be shown again.', life: 8000 })
  } finally {
    regenerating.value = false
  }
}

function copyRegKey() {
  if (generatedKey.value) {
    navigator.clipboard.writeText(generatedKey.value)
    toast.add({ severity: 'info', summary: 'Copied', detail: 'Registration key copied to clipboard.', life: 3000 })
  }
}

function relativeDate(iso) {
  if (!iso) return ''
  const d = new Date(iso + 'Z')
  return d.toLocaleDateString()
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
  loadRegKeyStatus()
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

/* Registration key */
.regkey-section {
  max-width: 500px;
}

.regkey-status {
  display: flex;
  align-items: center;
  gap: 0.8rem;
  margin-bottom: 0.8rem;
}

.regkey-active {
  color: #4caf50;
  font-weight: 600;
  font-size: 0.9rem;
}

.regkey-none {
  color: #888;
  font-size: 0.9rem;
}

.regkey-date {
  color: #666;
  font-size: 0.8rem;
}

.regkey-display {
  background: #1a1d27;
  border: 1px solid #3a3a5a;
  border-radius: 6px;
  padding: 1rem;
  margin-bottom: 1rem;
}

.regkey-value {
  display: flex;
  gap: 0.5rem;
  margin-bottom: 0.5rem;
}

.regkey-input {
  flex: 1;
  background: #0f1117;
  border: 1px solid #3a3a5a;
  color: #f0ad4e;
  padding: 0.6rem;
  border-radius: 4px;
  font-family: monospace;
  font-size: 1.1rem;
  text-align: center;
  letter-spacing: 0.15em;
}

.btn-copy {
  background: #3a3a5a;
  color: #ccc;
  border: none;
  padding: 0.5rem 1rem;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.85rem;
  white-space: nowrap;
  transition: background 0.15s;
}

.btn-copy:hover {
  background: #4a4d5a;
  color: #fff;
}

.regkey-warning {
  color: #888;
  font-size: 0.78rem;
  margin: 0;
}
</style>
