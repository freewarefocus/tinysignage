<template>
  <div>
    <div class="page-header">
      <h2>Emergency Overrides</h2>
      <button class="btn-create-template" @click="openCreate">
        <i class="pi pi-plus"></i> Create Template
      </button>
    </div>

    <!-- Create / Edit dialog -->
    <div v-if="showDialog" class="dialog-overlay" @click.self="closeDialog">
      <div class="dialog override-dialog">
        <h3>{{ editTarget ? 'Edit Template' : 'Create Emergency Template' }}</h3>
        <p class="dialog-desc">
          Templates are prepared ahead of time. When an emergency happens, just hit Activate.
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
              ? `When activated, auto-expires after ${form.duration_minutes} minutes.`
              : 'When activated, stays active until manually deactivated.' }}
          </p>
        </div>

        <div class="dialog-actions">
          <button
            class="btn-save-template"
            @click="saveTemplate"
            :disabled="!canSave"
          >Save Template</button>
          <button class="btn-secondary" @click="closeDialog">Cancel</button>
        </div>
      </div>
    </div>

    <!-- Activate confirmation -->
    <div v-if="activateTarget" class="dialog-overlay" @click.self="activateTarget = null">
      <div class="dialog">
        <h3>Activate Override</h3>
        <p>Activate <strong>{{ activateTarget.name }}</strong>? Devices will show this on next poll (up to 30 seconds).</p>
        <p class="duration-info">
          {{ activateTarget.duration_minutes
            ? `Auto-expires in ${formatDuration(activateTarget.duration_minutes)}.`
            : 'No auto-expiry — must be deactivated manually.' }}
        </p>
        <div class="dialog-actions">
          <button class="btn-emergency" @click="confirmActivate">Activate Now</button>
          <button class="btn-secondary" @click="activateTarget = null">Cancel</button>
        </div>
      </div>
    </div>

    <!-- Deactivate confirmation -->
    <div v-if="deactivateTarget" class="dialog-overlay" @click.self="deactivateTarget = null">
      <div class="dialog">
        <h3>Deactivate Override</h3>
        <p>Deactivate <strong>{{ deactivateTarget.name }}</strong>? Devices return to normal on next poll.</p>
        <div class="dialog-actions">
          <button class="btn-danger" @click="confirmDeactivate">Deactivate</button>
          <button class="btn-secondary" @click="deactivateTarget = null">Keep Active</button>
        </div>
      </div>
    </div>

    <!-- Delete confirmation -->
    <div v-if="deleteTarget" class="dialog-overlay" @click.self="deleteTarget = null">
      <div class="dialog">
        <h3>Delete Template</h3>
        <p>Delete <strong>{{ deleteTarget.name }}</strong>? This cannot be undone.</p>
        <div class="dialog-actions">
          <button class="btn-danger" @click="confirmDelete">Delete</button>
          <button class="btn-secondary" @click="deleteTarget = null">Cancel</button>
        </div>
      </div>
    </div>

    <div v-if="loading" class="loading">Loading...</div>

    <template v-else>
      <!-- Empty state -->
      <div v-if="overrides.length === 0" class="empty-state">
        <i class="pi pi-shield"></i>
        <p>No emergency templates yet.</p>
        <p class="empty-hint">Create your first one so you're ready when you need it.</p>
        <button class="btn-create-template" @click="openCreate">
          <i class="pi pi-plus"></i> Create Template
        </button>
      </div>

      <!-- Template card grid -->
      <div v-else class="template-grid">
        <div
          v-for="o in sortedOverrides"
          :key="o.id"
          :class="['template-card', { 'active-card': o.is_active }]"
        >
          <div class="card-header">
            <div class="card-name-row">
              <span v-if="o.is_active" class="pulse-dot"></span>
              <span class="card-name">{{ o.name }}</span>
            </div>
            <div class="card-actions">
              <template v-if="o.is_active">
                <button class="btn-deactivate" @click="deactivateTarget = o">
                  <i class="pi pi-power-off"></i> Deactivate
                </button>
              </template>
              <template v-else>
                <button class="btn-activate" @click="activateTarget = o">
                  <i class="pi pi-bolt"></i> Activate
                </button>
                <button class="btn-icon" @click="openEdit(o)" title="Edit">
                  <i class="pi pi-pencil"></i>
                </button>
                <button class="btn-icon" @click="deleteTarget = o" title="Delete">
                  <i class="pi pi-trash"></i>
                </button>
              </template>
            </div>
          </div>

          <div class="card-details">
            <span class="detail-tag type-tag" :class="o.content_type">
              <i :class="o.content_type === 'message' ? 'pi pi-comment' : 'pi pi-list'"></i>
              {{ o.content_type === 'message' ? 'Message' : 'Playlist' }}
            </span>
            <span class="detail-tag">
              <i class="pi pi-desktop"></i> {{ targetLabel(o) }}
            </span>
            <span v-if="o.duration_minutes" class="detail-tag">
              <i class="pi pi-clock"></i> {{ formatDuration(o.duration_minutes) }}
            </span>
            <span v-else class="detail-tag">
              <i class="pi pi-clock"></i> No expiry
            </span>
            <span v-if="o.is_active && o.expires_at" class="detail-tag countdown-tag">
              <i class="pi pi-stopwatch"></i> Expires {{ formatRelative(o.expires_at) }}
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
const editTarget = ref(null)
const activateTarget = ref(null)
const deactivateTarget = ref(null)
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

const sortedOverrides = computed(() => {
  const active = overrides.value.filter(o => o.is_active)
  const inactive = overrides.value.filter(o => !o.is_active)
  inactive.sort((a, b) => (a.name || '').localeCompare(b.name || ''))
  return [...active, ...inactive]
})

const canSave = computed(() => {
  if (!form.value.name.trim()) return false
  if (!form.value.content.trim()) return false
  if (form.value.target_type !== 'all' && !form.value.target_id) return false
  return true
})

function openCreate() {
  editTarget.value = null
  form.value = defaultForm()
  showDialog.value = true
}

function openEdit(o) {
  editTarget.value = o
  form.value = {
    name: o.name,
    content_type: o.content_type,
    content: o.content,
    target_type: o.target_type,
    target_id: o.target_id || '',
    duration_minutes: o.duration_minutes,
  }
  showDialog.value = true
}

function closeDialog() {
  showDialog.value = false
  editTarget.value = null
}

async function saveTemplate() {
  if (editTarget.value) {
    // Edit existing template
    const payload = {
      name: form.value.name,
      content_type: form.value.content_type,
      content: form.value.content,
      target_type: form.value.target_type,
      target_id: form.value.target_type === 'all' ? null : form.value.target_id,
      duration_minutes: form.value.duration_minutes,
    }
    await api.patch(`/overrides/${editTarget.value.id}`, payload)
  } else {
    // Create new template
    const payload = {
      name: form.value.name,
      content_type: form.value.content_type,
      content: form.value.content,
      target_type: form.value.target_type,
      target_id: form.value.target_type === 'all' ? null : form.value.target_id,
      duration_minutes: form.value.duration_minutes,
    }
    await api.post('/overrides', payload)
  }
  closeDialog()
  await loadOverrides()
}

async function confirmActivate() {
  if (!activateTarget.value) return
  await api.patch(`/overrides/${activateTarget.value.id}`, { is_active: true })
  activateTarget.value = null
  await loadOverrides()
}

async function confirmDeactivate() {
  if (!deactivateTarget.value) return
  await api.patch(`/overrides/${deactivateTarget.value.id}`, { is_active: false })
  deactivateTarget.value = null
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

function formatDuration(minutes) {
  if (!minutes) return ''
  if (minutes < 60) return `${minutes} min`
  const h = Math.floor(minutes / 60)
  const m = minutes % 60
  return m ? `${h}h ${m}m` : `${h} hour${h > 1 ? 's' : ''}`
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

/* Create Template button */
.btn-create-template {
  display: flex; align-items: center; gap: 0.4rem;
  background: #3a3a5a; color: #ccc; border: 1px solid #4a4a6a;
  padding: 0.5rem 1rem; border-radius: 6px; cursor: pointer;
  font-size: 0.85rem; font-weight: 500; transition: all 0.15s;
}
.btn-create-template:hover { background: #4a4a6a; color: #fff; }

/* Emergency activate button */
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

.btn-save-template {
  display: flex; align-items: center; gap: 0.3rem;
  background: #5a61d6; color: #fff; border: none;
  padding: 0.5rem 1rem; border-radius: 6px; cursor: pointer;
  font-size: 0.85rem; font-weight: 500; transition: background 0.15s;
}
.btn-save-template:hover { background: #4a50c6; }
.btn-save-template:disabled { opacity: 0.5; cursor: default; }

.btn-activate {
  display: flex; align-items: center; gap: 0.3rem;
  background: rgba(220, 53, 69, 0.15); color: #ff6b6b; border: 1px solid #dc3545;
  padding: 0.35rem 0.75rem; border-radius: 6px; cursor: pointer;
  font-size: 0.8rem; font-weight: 500; transition: all 0.15s;
}
.btn-activate:hover { background: #dc3545; color: #fff; }

.btn-deactivate {
  display: flex; align-items: center; gap: 0.3rem;
  background: rgba(220, 53, 69, 0.2); color: #ff6b6b; border: 1px solid #dc3545;
  padding: 0.35rem 0.75rem; border-radius: 6px; cursor: pointer;
  font-size: 0.8rem; transition: all 0.15s;
}
.btn-deactivate:hover { background: #dc3545; color: #fff; }

.btn-icon {
  background: none; border: none; color: #888; cursor: pointer;
  padding: 0.3rem; border-radius: 4px; transition: color 0.15s;
}
.btn-icon:hover { color: #fff; }

.loading {
  text-align: center; padding: 2rem; color: #666;
}

/* Empty state */
.empty-state {
  text-align: center; padding: 3rem; color: #666;
}
.empty-state i { font-size: 2.5rem; color: #444; margin-bottom: 0.75rem; }
.empty-state p { margin: 0.3rem 0; }
.empty-hint { color: #555; font-size: 0.9rem; margin-bottom: 1rem !important; }

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
.dialog-desc { color: #999 !important; font-size: 0.85rem !important; }
.dialog-actions { display: flex; gap: 0.5rem; justify-content: flex-end; margin-top: 1rem; }

.duration-info { color: #ff9999 !important; font-weight: 500; }

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
.form-group .select-input:focus { border-color: #5a61d6; }

.select-input { cursor: pointer; }
.form-row { display: flex; gap: 0.75rem; }
/* Radio */
.radio-row { display: flex; gap: 1rem; }
.radio-label {
  display: flex !important; align-items: center; gap: 0.4rem;
  cursor: pointer; text-transform: none !important; font-size: 0.9rem !important;
  color: #ccc !important;
}
.radio-label input[type="radio"] {
  width: auto; accent-color: #5a61d6;
}

/* Duration picker */
.duration-row { display: flex; gap: 0.3rem; flex-wrap: wrap; }

.duration-btn {
  background: #0f1117; border: 1px solid #3a3a5a; color: #999;
  padding: 0.35rem 0.7rem; border-radius: 4px; cursor: pointer;
  font-size: 0.8rem; transition: all 0.15s;
}
.duration-btn:hover { border-color: #5a61d6; color: #fff; }
.duration-btn.active { background: #5a61d6; border-color: #5a61d6; color: #fff; }

/* Template grid */
.template-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
  gap: 0.75rem;
}

.template-card {
  background: #1a1d27; border-radius: 8px; padding: 0.75rem 1rem;
  border: 1px solid #2a2d3a; transition: border-color 0.15s;
}

.active-card {
  border-color: #dc3545;
  background: linear-gradient(135deg, #1a1d27 0%, rgba(220, 53, 69, 0.05) 100%);
}

.card-header {
  display: flex; justify-content: space-between; align-items: center;
  margin-bottom: 0.4rem;
}

.card-name-row {
  display: flex; align-items: center; gap: 0.5rem;
}

.card-name { font-size: 0.95rem; color: #fff; font-weight: 500; }

.card-actions {
  display: flex; align-items: center; gap: 0.3rem;
}

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

.countdown-tag { color: #ff6b6b; font-weight: 500; }

.card-preview {
  color: #999; font-size: 0.85rem; padding: 0.4rem 0.6rem;
  background: #0f1117; border-radius: 4px; margin-top: 0.3rem;
  white-space: pre-wrap; word-break: break-word; max-height: 80px;
  overflow: hidden;
}

/* Pulse dot */
.pulse-dot {
  width: 10px; height: 10px; border-radius: 50%; background: #dc3545;
  display: inline-block; flex-shrink: 0;
  animation: pulse 1.5s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; box-shadow: 0 0 0 0 rgba(220, 53, 69, 0.7); }
  50% { opacity: 0.8; box-shadow: 0 0 0 6px rgba(220, 53, 69, 0); }
}
</style>
