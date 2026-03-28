<template>
  <div>
    <div class="page-header">
      <h2>Schedules</h2>
      <button class="btn-primary" @click="openCreate">
        <i class="pi pi-plus"></i> New Schedule
      </button>
    </div>

    <!-- Create / Edit dialog -->
    <div v-if="showDialog" class="dialog-overlay" @click.self="closeDialog">
      <div class="dialog schedule-dialog">
        <h3>{{ editing ? 'Edit Schedule' : 'Create Schedule' }}</h3>

        <div class="form-group">
          <label>Name</label>
          <input v-model="form.name" placeholder="e.g. Morning Lobby Content" />
        </div>

        <div class="form-group">
          <label>Playlist</label>
          <select v-model="form.playlist_id" class="select-input">
            <option value="">Select a playlist...</option>
            <option v-for="pl in playlists" :key="pl.id" :value="pl.id">
              {{ pl.name }}{{ pl.is_default ? ' (default)' : '' }}
            </option>
          </select>
        </div>

        <div class="form-row">
          <div class="form-group">
            <label>Target</label>
            <select v-model="form.target_type" class="select-input" @change="onTargetTypeChange">
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

        <div class="form-row">
          <div class="form-group">
            <label>Start Time</label>
            <input v-model="form.start_time" type="time" />
          </div>
          <div class="form-group">
            <label>End Time</label>
            <input v-model="form.end_time" type="time" />
          </div>
        </div>
        <p class="form-hint">Leave both blank for all-day.</p>

        <div class="form-group">
          <label>Days of Week</label>
          <div class="day-picker">
            <button
              v-for="(label, idx) in dayLabels"
              :key="idx"
              :class="['day-btn', { active: selectedDays.includes(idx) }]"
              @click="toggleDay(idx)"
            >{{ label }}</button>
          </div>
          <p class="form-hint">Select none for every day.</p>
        </div>

        <div class="form-row">
          <div class="form-group">
            <label>Start Date (optional)</label>
            <input v-model="form.start_date" type="date" />
          </div>
          <div class="form-group">
            <label>End Date (optional)</label>
            <input v-model="form.end_date" type="date" />
          </div>
        </div>

        <div class="form-row">
          <div class="form-group">
            <label>Priority</label>
            <input v-model.number="form.priority" type="number" min="0" max="100" />
            <p class="form-hint">Higher priority wins when schedules overlap.</p>
          </div>
          <div class="form-group">
            <label>Active</label>
            <label class="toggle-label">
              <input type="checkbox" v-model="form.is_active" />
              <span>{{ form.is_active ? 'Enabled' : 'Disabled' }}</span>
            </label>
          </div>
        </div>

        <div class="dialog-actions">
          <button
            class="btn-primary"
            @click="saveSchedule"
            :disabled="!canSave"
          >{{ editing ? 'Save' : 'Create' }}</button>
          <button class="btn-secondary" @click="closeDialog">Cancel</button>
        </div>
      </div>
    </div>

    <!-- Delete confirmation -->
    <div v-if="deleteTarget" class="dialog-overlay" @click.self="deleteTarget = null">
      <div class="dialog">
        <h3>Delete Schedule</h3>
        <p>Delete <strong>{{ deleteTarget.name }}</strong>? This cannot be undone.</p>
        <div class="dialog-actions">
          <button class="btn-danger" @click="confirmDelete">Delete</button>
          <button class="btn-secondary" @click="deleteTarget = null">Cancel</button>
        </div>
      </div>
    </div>

    <div v-if="loading" class="loading">Loading...</div>

    <div v-else-if="schedules.length === 0" class="empty">
      No schedules yet. Create one to automate playlist assignment by time, day, or date range.
    </div>

    <!-- Week view -->
    <div v-else>
      <div class="schedule-grid">
        <div class="grid-header">
          <div class="grid-cell time-col"></div>
          <div v-for="(label, idx) in dayLabels" :key="idx" class="grid-cell day-header">{{ label }}</div>
        </div>
        <div v-for="hour in hours" :key="hour" class="grid-row">
          <div class="grid-cell time-col time-label">{{ formatHour(hour) }}</div>
          <div v-for="(_, dayIdx) in dayLabels" :key="dayIdx" class="grid-cell day-cell">
            <div
              v-for="s in schedulesAt(dayIdx, hour)"
              :key="s.id"
              class="schedule-block"
              :style="{ background: scheduleColor(s) }"
              :title="s.name + ' — ' + (s.playlist_name || 'Unknown')"
              @click="openEdit(s)"
            >
              <span class="block-name">{{ s.name }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Schedule list below the calendar -->
      <h3 class="list-heading">All Schedules</h3>
      <div class="schedule-list">
        <div
          v-for="s in schedules"
          :key="s.id"
          class="schedule-row"
          :class="{ inactive: !s.is_active }"
        >
          <div class="row-main" @click="openEdit(s)">
            <div class="row-name">
              <span class="dot" :style="{ background: scheduleColor(s) }"></span>
              {{ s.name }}
              <span v-if="!s.is_active" class="badge-inactive">OFF</span>
            </div>
            <div class="row-details">
              <span class="detail-tag"><i class="pi pi-list"></i> {{ s.playlist_name || '—' }}</span>
              <span class="detail-tag"><i class="pi pi-desktop"></i> {{ targetLabel(s) }}</span>
              <span class="detail-tag"><i class="pi pi-clock"></i> {{ timeLabel(s) }}</span>
              <span class="detail-tag"><i class="pi pi-calendar"></i> {{ daysLabel(s) }}</span>
              <span class="detail-tag">Priority: {{ s.priority }}</span>
            </div>
          </div>
          <div class="row-actions">
            <button class="btn-icon" @click="openEdit(s)" title="Edit">
              <i class="pi pi-pencil"></i>
            </button>
            <button class="btn-icon" @click="deleteTarget = s" title="Delete">
              <i class="pi pi-trash"></i>
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { api } from '../api/client.js'

const schedules = ref([])
const playlists = ref([])
const devices = ref([])
const groups = ref([])
const loading = ref(true)
const showDialog = ref(false)
const editing = ref(null)
const deleteTarget = ref(null)

const dayLabels = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
const hours = Array.from({ length: 24 }, (_, i) => i)

const defaultForm = () => ({
  name: '',
  playlist_id: '',
  target_type: 'all',
  target_id: '',
  start_time: '',
  end_time: '',
  days_of_week: '',
  start_date: '',
  end_date: '',
  priority: 0,
  is_active: true,
})

const form = ref(defaultForm())
const selectedDays = ref([])

const canSave = computed(() => {
  if (!form.value.name.trim() || !form.value.playlist_id) return false
  if (form.value.target_type !== 'all' && !form.value.target_id) return false
  return true
})

function onTargetTypeChange() {
  form.value.target_id = ''
}

function toggleDay(idx) {
  const i = selectedDays.value.indexOf(idx)
  if (i >= 0) {
    selectedDays.value.splice(i, 1)
  } else {
    selectedDays.value.push(idx)
  }
}

function openCreate() {
  editing.value = null
  form.value = defaultForm()
  selectedDays.value = []
  showDialog.value = true
}

function openEdit(s) {
  editing.value = s
  form.value = {
    name: s.name,
    playlist_id: s.playlist_id,
    target_type: s.target_type,
    target_id: s.target_id || '',
    start_time: s.start_time || '',
    end_time: s.end_time || '',
    days_of_week: s.days_of_week || '',
    start_date: s.start_date ? s.start_date.split('T')[0] : '',
    end_date: s.end_date ? s.end_date.split('T')[0] : '',
    priority: s.priority,
    is_active: s.is_active,
  }
  selectedDays.value = s.days_of_week
    ? s.days_of_week.split(',').map(Number)
    : []
  showDialog.value = true
}

function closeDialog() {
  showDialog.value = false
  editing.value = null
}

async function saveSchedule() {
  const payload = {
    ...form.value,
    days_of_week: selectedDays.value.length > 0
      ? selectedDays.value.sort((a, b) => a - b).join(',')
      : null,
    start_time: form.value.start_time || null,
    end_time: form.value.end_time || null,
    start_date: form.value.start_date || null,
    end_date: form.value.end_date || null,
    target_id: form.value.target_type === 'all' ? null : form.value.target_id,
  }

  if (editing.value) {
    await api.patch(`/schedules/${editing.value.id}`, payload)
  } else {
    await api.post('/schedules', payload)
  }
  closeDialog()
  await loadSchedules()
}

async function confirmDelete() {
  if (!deleteTarget.value) return
  await api.delete(`/schedules/${deleteTarget.value.id}`)
  deleteTarget.value = null
  await loadSchedules()
}

function formatHour(h) {
  return `${h.toString().padStart(2, '0')}:00`
}

function schedulesAt(dayIdx, hour) {
  const hh = hour.toString().padStart(2, '0') + ':00'
  return schedules.value.filter(s => {
    if (!s.is_active) return false

    // Check day
    if (s.days_of_week) {
      const days = s.days_of_week.split(',').map(Number)
      if (!days.includes(dayIdx)) return false
    }

    // Check time
    if (s.start_time && s.end_time) {
      if (s.start_time <= s.end_time) {
        if (!(hh >= s.start_time && hh < s.end_time)) return false
      } else {
        if (!(hh >= s.start_time || hh < s.end_time)) return false
      }
    } else if (s.start_time) {
      if (hh < s.start_time) return false
    } else if (s.end_time) {
      if (hh >= s.end_time) return false
    }

    return true
  })
}

const colorPalette = [
  '#7c83ff', '#ff6b8a', '#4ecdc4', '#ff9f43', '#a78bfa',
  '#22d3ee', '#f472b6', '#34d399', '#fbbf24', '#6366f1',
]

function scheduleColor(s) {
  const idx = schedules.value.findIndex(x => x.id === s.id)
  return colorPalette[idx % colorPalette.length]
}

function targetLabel(s) {
  if (s.target_type === 'all') return 'All devices'
  if (s.target_type === 'group') {
    const g = groups.value.find(x => x.id === s.target_id)
    return g ? g.name : 'Unknown group'
  }
  if (s.target_type === 'device') {
    const d = devices.value.find(x => x.id === s.target_id)
    return d ? d.name : 'Unknown device'
  }
  return '—'
}

function timeLabel(s) {
  if (s.start_time && s.end_time) return `${s.start_time}–${s.end_time}`
  if (s.start_time) return `From ${s.start_time}`
  if (s.end_time) return `Until ${s.end_time}`
  return 'All day'
}

function daysLabel(s) {
  if (!s.days_of_week) return 'Every day'
  const days = s.days_of_week.split(',').map(Number)
  if (days.length === 7) return 'Every day'
  if (days.length === 5 && [0,1,2,3,4].every(d => days.includes(d))) return 'Weekdays'
  if (days.length === 2 && [5,6].every(d => days.includes(d))) return 'Weekends'
  return days.map(d => dayLabels[d]).join(', ')
}

async function loadSchedules() {
  try {
    schedules.value = await api.get('/schedules')
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  await Promise.all([
    loadSchedules(),
    api.get('/playlists').then(r => playlists.value = r),
    api.get('/devices').then(r => devices.value = r),
    api.get('/groups').then(r => groups.value = r),
  ])
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

/* Buttons */
.btn-primary {
  display: flex; align-items: center; gap: 0.4rem;
  background: #7c83ff; color: #fff; border: none;
  padding: 0.5rem 1rem; border-radius: 6px; cursor: pointer;
  font-size: 0.85rem; transition: background 0.15s;
}
.btn-primary:hover { background: #6b72ee; }
.btn-primary:disabled { opacity: 0.5; cursor: default; }

.btn-secondary {
  background: #3a3a5a; color: #ccc; border: none;
  padding: 0.5rem 1rem; border-radius: 6px; cursor: pointer; font-size: 0.85rem;
}

.btn-danger {
  background: #dc3545; color: #fff; border: none;
  padding: 0.5rem 1rem; border-radius: 6px; cursor: pointer; font-size: 0.85rem;
}
.btn-danger:hover { background: #c82333; }

.btn-icon {
  background: none; border: none; color: #888; cursor: pointer;
  padding: 0.3rem; border-radius: 4px; transition: color 0.15s;
}
.btn-icon:hover { color: #fff; }

.loading, .empty {
  text-align: center; padding: 3rem; color: #666;
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

.schedule-dialog {
  width: 540px; max-height: 85vh; overflow-y: auto;
}

.dialog p { color: #aaa; font-size: 0.9rem; margin-bottom: 0.75rem; line-height: 1.5; }

.dialog-actions { display: flex; gap: 0.5rem; justify-content: flex-end; margin-top: 1rem; }

/* Form */
.form-group {
  margin-bottom: 0.8rem; flex: 1;
}

.form-group label {
  display: block; font-size: 0.8rem; color: #888;
  margin-bottom: 0.3rem; text-transform: uppercase; letter-spacing: 0.5px;
}

.form-group input,
.form-group .select-input {
  width: 100%; background: #0f1117; border: 1px solid #3a3a5a;
  color: #eee; padding: 0.5rem 0.75rem; border-radius: 6px;
  outline: none; font-size: 0.9rem;
}

.form-group input:focus,
.form-group .select-input:focus { border-color: #7c83ff; }

.select-input { cursor: pointer; }

.form-row { display: flex; gap: 0.75rem; }

.form-hint { color: #666; font-size: 0.75rem; margin: 0.2rem 0 0.5rem; }

/* Day picker */
.day-picker { display: flex; gap: 0.3rem; }

.day-btn {
  background: #0f1117; border: 1px solid #3a3a5a; color: #999;
  padding: 0.35rem 0.5rem; border-radius: 4px; cursor: pointer;
  font-size: 0.8rem; transition: all 0.15s; min-width: 2.5rem; text-align: center;
}
.day-btn:hover { border-color: #7c83ff; color: #fff; }
.day-btn.active { background: #7c83ff; border-color: #7c83ff; color: #fff; }

/* Toggle */
.toggle-label {
  display: flex !important; align-items: center; gap: 0.5rem;
  cursor: pointer; text-transform: none !important; font-size: 0.9rem !important;
  color: #ccc !important;
}

.toggle-label input[type="checkbox"] {
  width: auto; accent-color: #7c83ff;
}

/* Week grid */
.schedule-grid {
  border: 1px solid #2a2d3a; border-radius: 8px; overflow: hidden;
  margin-bottom: 2rem; max-height: 500px; overflow-y: auto;
}

.grid-header {
  display: flex; background: #1e2130; position: sticky; top: 0; z-index: 1;
}

.grid-row { display: flex; }
.grid-row:nth-child(even) { background: rgba(255,255,255,0.02); }

.grid-cell {
  flex: 1; padding: 0.25rem 0.3rem; border-right: 1px solid #1e2130;
  border-bottom: 1px solid #1e2130; min-height: 28px; font-size: 0.75rem;
}

.time-col {
  flex: 0 0 55px; text-align: right; padding-right: 0.5rem;
}

.time-label { color: #666; }

.day-header {
  text-align: center; font-weight: 500; color: #aaa; padding: 0.4rem;
}

.day-cell { position: relative; }

.schedule-block {
  font-size: 0.65rem; color: #fff; padding: 1px 4px;
  border-radius: 3px; margin-bottom: 1px; cursor: pointer;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  opacity: 0.85; transition: opacity 0.15s;
}
.schedule-block:hover { opacity: 1; }

.block-name { font-weight: 500; }

/* Schedule list */
.list-heading { margin: 1.5rem 0 0.75rem; }

.schedule-list { display: flex; flex-direction: column; gap: 0.4rem; }

.schedule-row {
  display: flex; justify-content: space-between; align-items: center;
  background: #1a1d27; border-radius: 8px; padding: 0.75rem 1rem;
  border: 1px solid transparent; transition: border-color 0.15s;
}
.schedule-row:hover { border-color: #7c83ff; }
.schedule-row.inactive { opacity: 0.5; }

.row-main { cursor: pointer; flex: 1; }

.row-name {
  font-size: 0.95rem; color: #fff; font-weight: 500;
  display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.3rem;
}

.dot {
  width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0;
}

.badge-inactive {
  background: #3a3a5a; color: #999; font-size: 0.65rem;
  padding: 1px 6px; border-radius: 3px; font-weight: 400;
}

.row-details {
  display: flex; flex-wrap: wrap; gap: 0.4rem; padding-left: 1.4rem;
}

.detail-tag {
  display: flex; align-items: center; gap: 0.25rem;
  color: #888; font-size: 0.75rem; background: #0f1117;
  padding: 2px 6px; border-radius: 3px;
}
.detail-tag i { font-size: 0.7rem; }

.row-actions { display: flex; gap: 0.2rem; flex-shrink: 0; }
</style>
