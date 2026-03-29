<template>
  <div>
    <div class="page-header">
      <h2>Emergency Overrides</h2>
      <button class="btn-emergency" @click="openCreate">
        <i class="pi pi-exclamation-triangle"></i> New Override
      </button>
    </div>

    <!-- Create dialog -->
    <div v-if="showDialog" class="dialog-overlay" @click.self="closeDialog">
      <div class="dialog override-dialog">
        <h3>Activate Emergency Override</h3>
        <p class="dialog-desc">
          Overrides take absolute priority over all schedules and playlists.
          Players will switch immediately on next poll (up to 30 seconds).
        </p>

        <div class="form-group">
          <label>Name</label>
          <input v-model="form.name" placeholder="e.g. Fire Drill, Weather Alert" />
        </div>

        <div class="form-group">
          <label>Content Type</label>
          <div class="radio-row">
            <label class="radio-label">
              <input type="radio" v-model="form.content_type" value="message" />
              <span>Text Message</span>
            </label>
            <label class="radio-label">
              <input type="radio" v-model="form.content_type" value="playlist" />
              <span>Playlist</span>
            </label>
          </div>
        </div>

        <div v-if="form.content_type === 'message'" class="form-group">
          <label>Message</label>
          <textarea v-model="form.content" rows="3" placeholder="Emergency message displayed on all screens..."></textarea>
        </div>

        <div v-if="form.content_type === 'playlist'" class="form-group">
          <label>Playlist</label>
          <select v-model="form.content" class="select-input">
            <option value="">Select a playlist...</option>
            <option v-for="pl in playlists" :key="pl.id" :value="pl.id">
              {{ pl.name }}{{ pl.is_default ? ' (default)' : '' }}
            </option>
          </select>
        </div>

        <div class="form-row">
          <div class="form-group">
            <label>Target</label>
            <select v-model="form.target_type" class="select-input" @change="form.target_id = ''">
              <option value="all">All Devices</option>
              <option value="group">Device Group</option>
              <option value="device">Specific Device</option>
            </select>
          </div>
          <div v-if="form.target_type === 'group'" class="form-group">
            <label>Group</label>
            <select v-model="form.target_id" class="select-input">
              <option value="">Select a group...</option>
              <option v-for="g in groups" :key="g.id" :value="g.id">{{ g.name }}</option>
            </select>
          </div>
          <div v-if="form.target_type === 'device'" class="form-group">
            <label>Device</label>
            <select v-model="form.target_id" class="select-input">
              <option value="">Select a device...</option>
              <option v-for="d in devices" :key="d.id" :value="d.id">{{ d.name }}</option>
            </select>
          </div>
        </div>

        <div class="form-group">
          <label>Duration</label>
          <div class="duration-row">
            <button
              v-for="opt in durationOptions"
              :key="opt.value"
              :class="['duration-btn', { active: form.duration_minutes === opt.value }]"
              @click="form.duration_minutes = opt.value"
            >{{ opt.label }}</button>
          </div>
          <p class="form-hint">
            {{ form.duration_minutes
              ? `Auto-expires after ${form.duration_minutes} minutes.`
              : 'No expiry — must be cancelled manually.' }}
          </p>
        </div>

        <div class="dialog-actions">
          <button
            class="btn-emergency"
            @click="createOverride"
            :disabled="!canCreate"
          >Activate Override</button>
          <button class="btn-secondary" @click="closeDialog">Cancel</button>
        </div>
      </div>
    </div>

    <!-- Cancel confirmation -->
    <div v-if="cancelTarget" class="dialog-overlay" @click.self="cancelTarget = null">
      <div class="dialog">
        <h3>Cancel Override</h3>
        <p>Cancel <strong>{{ cancelTarget.name }}</strong>? Devices will return to their normal playlists on next poll.</p>
        <div class="dialog-actions">
          <button class="btn-danger" @click="confirmCancel">Cancel Override</button>
          <button class="btn-secondary" @click="cancelTarget = null">Keep Active</button>
        </div>
      </div>
    </div>

    <!-- Delete confirmation -->
    <div v-if="deleteTarget" class="dialog-overlay" @click.self="deleteTarget = null">
      <div class="dialog">
        <h3>Delete Override</h3>
        <p>Delete <strong>{{ deleteTarget.name }}</strong>? This cannot be undone.</p>
        <div class="dialog-actions">
          <button class="btn-danger" @click="confirmDelete">Delete</button>
          <button class="btn-secondary" @click="deleteTarget = null">Cancel</button>
        </div>
      </div>
    </div>

    <div v-if="loading" class="loading">Loading...</div>

    <template v-else>
      <!-- Active overrides -->
      <div v-if="activeOverrides.length > 0" class="section">
        <h3 class="section-heading active-heading">
          <span class="pulse-dot"></span>
          Active Overrides
        </h3>
        <div class="override-list">
          <div
            v-for="o in activeOverrides"
            :key="o.id"
            class="override-card active-card"
          >
            <div class="card-header">
              <div class="card-name">{{ o.name }}</div>
              <button class="btn-cancel" @click="cancelTarget = o">
                <i class="pi pi-times"></i> Cancel
              </button>
            </div>
            <div class="card-details">
              <span class="detail-tag type-tag" :class="o.content_type">
                <i :class="o.content_type === 'message' ? 'pi pi-comment' : 'pi pi-list'"></i>
                {{ o.content_type === 'message' ? 'Message' : 'Playlist' }}
              </span>
              <span class="detail-tag">
                <i class="pi pi-desktop"></i> {{ targetLabel(o) }}
              </span>
              <span v-if="o.expires_at" class="detail-tag">
                <i class="pi pi-clock"></i> Expires {{ formatRelative(o.expires_at) }}
              </span>
              <span v-else class="detail-tag">
                <i class="pi pi-clock"></i> No expiry
              </span>
              <span class="detail-tag">
                <i class="pi pi-user"></i> {{ o.creator_name || 'System' }}
              </span>
            </div>
            <div v-if="o.content_type === 'message'" class="card-preview">
              {{ o.content }}
            </div>
            <div v-else class="card-preview">
              Playlist: {{ playlistName(o.content) }}
            </div>
          </div>
        </div>
      </div>

      <!-- History -->
      <div class="section">
        <h3 class="section-heading">Override History</h3>
        <div v-if="inactiveOverrides.length === 0" class="empty">
          No past overrides.
        </div>
        <div v-else class="override-list">
          <div
            v-for="o in inactiveOverrides"
            :key="o.id"
            class="override-card inactive-card"
          >
            <div class="card-header">
              <div class="card-name">{{ o.name }}</div>
              <button class="btn-icon" @click="deleteTarget = o" title="Delete">
                <i class="pi pi-trash"></i>
              </button>
            </div>
            <div class="card-details">
              <span class="detail-tag type-tag" :class="o.content_type">
                <i :class="o.content_type === 'message' ? 'pi pi-comment' : 'pi pi-list'"></i>
                {{ o.content_type === 'message' ? 'Message' : 'Playlist' }}
              </span>
              <span class="detail-tag">
                <i class="pi pi-desktop"></i> {{ targetLabel(o) }}
              </span>
              <span class="detail-tag">
                <i class="pi pi-calendar"></i> {{ formatDate(o.created_at) }}
              </span>
              <span class="detail-tag">
                <i class="pi pi-user"></i> {{ o.creator_name || 'System' }}
              </span>
            </div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { api } from '../api/client.js'

const overrides = ref([])
const playlists = ref([])
const devices = ref([])
const groups = ref([])
const loading = ref(true)
const showDialog = ref(false)
const cancelTarget = ref(null)
const deleteTarget = ref(null)

const durationOptions = [
  { label: '15 min', value: 15 },
  { label: '30 min', value: 30 },
  { label: '1 hour', value: 60 },
  { label: '2 hours', value: 120 },
  { label: '4 hours', value: 240 },
  { label: 'No expiry', value: null },
]

const defaultForm = () => ({
  name: '',
  content_type: 'message',
  content: '',
  target_type: 'all',
  target_id: '',
  duration_minutes: 30,
})

const form = ref(defaultForm())

const activeOverrides = computed(() =>
  overrides.value.filter(o => o.is_active)
)

const inactiveOverrides = computed(() =>
  overrides.value.filter(o => !o.is_active)
)

const canCreate = computed(() => {
  if (!form.value.name.trim()) return false
  if (!form.value.content.trim()) return false
  if (form.value.target_type !== 'all' && !form.value.target_id) return false
  return true
})

function openCreate() {
  form.value = defaultForm()
  showDialog.value = true
}

function closeDialog() {
  showDialog.value = false
}

async function createOverride() {
  const payload = {
    name: form.value.name,
    content_type: form.value.content_type,
    content: form.value.content,
    target_type: form.value.target_type,
    target_id: form.value.target_type === 'all' ? null : form.value.target_id,
    duration_minutes: form.value.duration_minutes,
  }
  await api.post('/overrides', payload)
  closeDialog()
  await loadOverrides()
}

async function confirmCancel() {
  if (!cancelTarget.value) return
  await api.patch(`/overrides/${cancelTarget.value.id}`, { is_active: false })
  cancelTarget.value = null
  await loadOverrides()
}

async function confirmDelete() {
  if (!deleteTarget.value) return
  await api.delete(`/overrides/${deleteTarget.value.id}`)
  deleteTarget.value = null
  await loadOverrides()
}

function targetLabel(o) {
  if (o.target_type === 'all') return 'All devices'
  if (o.target_type === 'group') {
    const g = groups.value.find(x => x.id === o.target_id)
    return g ? g.name : 'Unknown group'
  }
  if (o.target_type === 'device') {
    const d = devices.value.find(x => x.id === o.target_id)
    return d ? d.name : 'Unknown device'
  }
  return '-'
}

function playlistName(id) {
  const pl = playlists.value.find(x => x.id === id)
  return pl ? pl.name : 'Unknown'
}

function formatRelative(isoStr) {
  if (!isoStr) return ''
  const target = new Date(isoStr + 'Z')  // Server stores UTC naive
  const now = new Date()
  const diffMs = target - now
  if (diffMs <= 0) return 'expired'
  const mins = Math.floor(diffMs / 60000)
  if (mins < 60) return `in ${mins}m`
  const hours = Math.floor(mins / 60)
  const remainMins = mins % 60
  return `in ${hours}h ${remainMins}m`
}

function formatDate(isoStr) {
  if (!isoStr) return ''
  const d = new Date(isoStr + 'Z')
  return d.toLocaleString()
}

async function loadOverrides() {
  try {
    overrides.value = await api.get('/overrides')
  } finally {
    loading.value = false
  }
}

let refreshInterval = null

onMounted(async () => {
  await Promise.all([
    loadOverrides(),
    api.get('/playlists').then(r => playlists.value = r),
    api.get('/devices').then(r => devices.value = r),
    api.get('/groups').then(r => groups.value = r),
  ])
  // Auto-refresh every 30s so expired overrides update in the UI
  refreshInterval = setInterval(loadOverrides, 30000)
})

onUnmounted(() => {
  if (refreshInterval) clearInterval(refreshInterval)
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

/* Emergency button */
.btn-emergency {
  display: flex; align-items: center; gap: 0.4rem;
  background: #dc3545; color: #fff; border: none;
  padding: 0.5rem 1rem; border-radius: 6px; cursor: pointer;
  font-size: 0.85rem; font-weight: 500; transition: background 0.15s;
}
.btn-emergency:hover { background: #c82333; }
.btn-emergency:disabled { opacity: 0.5; cursor: default; }

.btn-secondary {
  background: #3a3a5a; color: #ccc; border: none;
  padding: 0.5rem 1rem; border-radius: 6px; cursor: pointer; font-size: 0.85rem;
}

.btn-danger {
  background: #dc3545; color: #fff; border: none;
  padding: 0.5rem 1rem; border-radius: 6px; cursor: pointer; font-size: 0.85rem;
}
.btn-danger:hover { background: #c82333; }

.btn-cancel {
  display: flex; align-items: center; gap: 0.3rem;
  background: rgba(220, 53, 69, 0.2); color: #ff6b6b; border: 1px solid #dc3545;
  padding: 0.35rem 0.75rem; border-radius: 6px; cursor: pointer;
  font-size: 0.8rem; transition: all 0.15s;
}
.btn-cancel:hover { background: #dc3545; color: #fff; }

.btn-icon {
  background: none; border: none; color: #888; cursor: pointer;
  padding: 0.3rem; border-radius: 4px; transition: color 0.15s;
}
.btn-icon:hover { color: #fff; }

.loading, .empty {
  text-align: center; padding: 2rem; color: #666;
}

/* Dialog */
.dialog-overlay {
  position: fixed; inset: 0; background: rgba(0,0,0,0.6);
  display: flex; align-items: center; justify-content: center; z-index: 1000;
}

.dialog {
  background: #1a1d27; border-radius: 10px; padding: 1.5rem;
  width: 380px; max-width: 90vw; border: 1px solid #2a2d3a;
}

.override-dialog {
  width: 540px; max-height: 85vh; overflow-y: auto;
}

.dialog p { color: #aaa; font-size: 0.9rem; margin-bottom: 0.75rem; line-height: 1.5; }
.dialog-desc { color: #ff9999 !important; font-size: 0.85rem !important; }
.dialog-actions { display: flex; gap: 0.5rem; justify-content: flex-end; margin-top: 1rem; }

/* Form */
.form-group { margin-bottom: 0.8rem; flex: 1; }

.form-group label {
  display: block; font-size: 0.8rem; color: #888;
  margin-bottom: 0.3rem; text-transform: uppercase; letter-spacing: 0.5px;
}

.form-group input,
.form-group textarea,
.form-group .select-input {
  width: 100%; background: #0f1117; border: 1px solid #3a3a5a;
  color: #eee; padding: 0.5rem 0.75rem; border-radius: 6px;
  outline: none; font-size: 0.9rem; font-family: inherit;
}

.form-group textarea { resize: vertical; min-height: 60px; }
.form-group input:focus,
.form-group textarea:focus,
.form-group .select-input:focus { border-color: #dc3545; }

.select-input { cursor: pointer; }
.form-row { display: flex; gap: 0.75rem; }
.form-hint { color: #666; font-size: 0.75rem; margin: 0.2rem 0 0.5rem; }

/* Radio */
.radio-row { display: flex; gap: 1rem; }
.radio-label {
  display: flex !important; align-items: center; gap: 0.4rem;
  cursor: pointer; text-transform: none !important; font-size: 0.9rem !important;
  color: #ccc !important;
}
.radio-label input[type="radio"] {
  width: auto; accent-color: #dc3545;
}

/* Duration picker */
.duration-row { display: flex; gap: 0.3rem; flex-wrap: wrap; }

.duration-btn {
  background: #0f1117; border: 1px solid #3a3a5a; color: #999;
  padding: 0.35rem 0.7rem; border-radius: 4px; cursor: pointer;
  font-size: 0.8rem; transition: all 0.15s;
}
.duration-btn:hover { border-color: #dc3545; color: #fff; }
.duration-btn.active { background: #dc3545; border-color: #dc3545; color: #fff; }

/* Sections */
.section { margin-bottom: 2rem; }

.section-heading {
  display: flex; align-items: center; gap: 0.5rem;
  margin-bottom: 0.75rem; font-size: 1rem;
}

.active-heading { color: #ff6b6b; }

.pulse-dot {
  width: 10px; height: 10px; border-radius: 50%; background: #dc3545;
  animation: pulse 1.5s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; box-shadow: 0 0 0 0 rgba(220, 53, 69, 0.7); }
  50% { opacity: 0.8; box-shadow: 0 0 0 6px rgba(220, 53, 69, 0); }
}

/* Override cards */
.override-list { display: flex; flex-direction: column; gap: 0.5rem; }

.override-card {
  background: #1a1d27; border-radius: 8px; padding: 0.75rem 1rem;
  border: 1px solid transparent; transition: border-color 0.15s;
}

.active-card { border-color: #dc3545; }
.inactive-card { opacity: 0.6; }
.inactive-card:hover { opacity: 0.8; }

.card-header {
  display: flex; justify-content: space-between; align-items: center;
  margin-bottom: 0.4rem;
}

.card-name { font-size: 0.95rem; color: #fff; font-weight: 500; }

.card-details {
  display: flex; flex-wrap: wrap; gap: 0.4rem; margin-bottom: 0.4rem;
}

.detail-tag {
  display: flex; align-items: center; gap: 0.25rem;
  color: #888; font-size: 0.75rem; background: #0f1117;
  padding: 2px 6px; border-radius: 3px;
}
.detail-tag i { font-size: 0.7rem; }

.type-tag.message { color: #ffc107; }
.type-tag.playlist { color: #7c83ff; }

.card-preview {
  color: #999; font-size: 0.85rem; padding: 0.4rem 0.6rem;
  background: #0f1117; border-radius: 4px; margin-top: 0.3rem;
  white-space: pre-wrap; word-break: break-word; max-height: 80px;
  overflow: hidden;
}
</style>
