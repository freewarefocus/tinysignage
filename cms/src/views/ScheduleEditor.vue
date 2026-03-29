<template>
  <div>
    <div class="page-header">
      <h2>Schedules</h2>
      <div class="header-actions">
        <button class="btn-secondary" @click="showPreviewPanel = !showPreviewPanel">
          <i class="pi pi-eye"></i> {{ showPreviewPanel ? 'Hide' : 'Show' }} Preview
        </button>
        <button class="btn-primary" @click="openCreate">
          <i class="pi pi-plus"></i> New Schedule
        </button>
      </div>
    </div>

    <!-- 24-hour Preview Panel -->
    <div v-if="showPreviewPanel" class="preview-panel">
      <div class="preview-header">
        <h3>24-Hour Timeline Preview</h3>
        <div class="preview-controls">
          <select v-model="previewDeviceId" class="select-input preview-select" @change="loadPreview">
            <option value="">Select a device...</option>
            <option v-for="d in devices" :key="d.id" :value="d.id">{{ d.name }}</option>
          </select>
          <input v-model="previewDate" type="date" class="preview-date" @change="loadPreview" />
        </div>
      </div>
      <div v-if="previewLoading" class="loading">Loading timeline...</div>
      <div v-else-if="!previewDeviceId" class="preview-hint">Select a device to preview its schedule timeline.</div>
      <div v-else-if="previewSlots.length > 0" class="timeline-container">
        <div class="timeline-bar">
          <div
            v-for="(block, idx) in timelineBlocks"
            :key="idx"
            class="timeline-block"
            :style="{ left: block.left + '%', width: block.width + '%', background: block.color }"
            :title="block.label"
          >
            <span v-if="block.width > 4" class="timeline-block-label">{{ block.shortLabel }}</span>
          </div>
        </div>
        <div class="timeline-hours">
          <span v-for="h in [0,3,6,9,12,15,18,21]" :key="h" class="timeline-tick" :style="{ left: (h / 24 * 100) + '%' }">
            {{ h.toString().padStart(2, '0') }}:00
          </span>
        </div>
        <div class="timeline-legend">
          <div v-for="entry in timelineLegend" :key="entry.name" class="legend-item">
            <span class="legend-dot" :style="{ background: entry.color }"></span>
            {{ entry.name }}
          </div>
        </div>
      </div>
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

        <!-- Recurrence mode toggle -->
        <div class="form-group">
          <label>Recurrence</label>
          <div class="recurrence-toggle">
            <button
              :class="['toggle-btn', { active: !useRecurrenceRule }]"
              @click="useRecurrenceRule = false"
            >Simple (days)</button>
            <button
              :class="['toggle-btn', { active: useRecurrenceRule }]"
              @click="useRecurrenceRule = true"
            >Advanced (RRULE)</button>
          </div>
        </div>

        <!-- Simple day picker -->
        <div v-if="!useRecurrenceRule" class="form-group">
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

        <!-- Advanced recurrence rule builder -->
        <div v-if="useRecurrenceRule" class="form-group recurrence-builder">
          <div class="form-row">
            <div class="form-group">
              <label>Frequency</label>
              <select v-model="rruleFreq" class="select-input" @change="buildRrule">
                <option value="DAILY">Daily</option>
                <option value="WEEKLY">Weekly</option>
                <option value="MONTHLY">Monthly</option>
                <option value="YEARLY">Yearly</option>
              </select>
            </div>
            <div class="form-group">
              <label>Every N</label>
              <input v-model.number="rruleInterval" type="number" min="1" max="52" @input="buildRrule" />
              <p class="form-hint">{{ intervalLabel }}</p>
            </div>
          </div>
          <div v-if="rruleFreq === 'WEEKLY'" class="form-group">
            <label>On days</label>
            <div class="day-picker">
              <button
                v-for="(label, abbr) in rruleDayOptions"
                :key="abbr"
                :class="['day-btn', { active: rruleDays.includes(abbr) }]"
                @click="toggleRruleDay(abbr)"
              >{{ label }}</button>
            </div>
          </div>
          <div v-if="rruleFreq === 'MONTHLY'" class="form-group">
            <label>Day of month</label>
            <input v-model.number="rruleMonthDay" type="number" min="1" max="31" @input="buildRrule" />
          </div>
          <div class="form-group">
            <label>Rule</label>
            <input v-model="form.recurrence_rule" readonly class="rule-preview" />
            <p class="form-hint">iCal RRULE format. Auto-generated from selections above.</p>
          </div>
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
            <label>Weight</label>
            <input v-model.number="form.priority_weight" type="number" min="0.1" max="100" step="0.1" />
            <p class="form-hint">Weighted random selection among same-priority schedules.</p>
          </div>
        </div>

        <div class="form-group">
          <label>Transition Playlist (optional)</label>
          <select v-model="form.transition_playlist_id" class="select-input">
            <option :value="null">None — direct switch</option>
            <option v-for="pl in playlists" :key="pl.id" :value="pl.id">
              {{ pl.name }}
            </option>
          </select>
          <p class="form-hint">Bumper content played before switching to this schedule's playlist.</p>
        </div>

        <div class="form-group">
          <label>Active</label>
          <label class="toggle-label">
            <input type="checkbox" v-model="form.is_active" />
            <span>{{ form.is_active ? 'Enabled' : 'Disabled' }}</span>
          </label>
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
              <span v-if="s.recurrence_rule" class="badge-rrule" title="Recurrence rule active">RRULE</span>
            </div>
            <div class="row-details">
              <span class="detail-tag"><i class="pi pi-list"></i> {{ s.playlist_name || '—' }}</span>
              <span class="detail-tag"><i class="pi pi-desktop"></i> {{ targetLabel(s) }}</span>
              <span class="detail-tag"><i class="pi pi-clock"></i> {{ timeLabel(s) }}</span>
              <span class="detail-tag"><i class="pi pi-calendar"></i> {{ daysLabel(s) }}</span>
              <span class="detail-tag">Priority: {{ s.priority }}</span>
              <span v-if="s.priority_weight !== 1.0" class="detail-tag">Weight: {{ s.priority_weight }}</span>
              <span v-if="s.transition_playlist_name" class="detail-tag">
                <i class="pi pi-replay"></i> {{ s.transition_playlist_name }}
              </span>
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
import { ref, computed, onMounted, watch } from 'vue'
import { api } from '../api/client.js'

const schedules = ref([])
const playlists = ref([])
const devices = ref([])
const groups = ref([])
const loading = ref(true)
const showDialog = ref(false)
const editing = ref(null)
const deleteTarget = ref(null)

// Preview panel state
const showPreviewPanel = ref(false)
const previewDeviceId = ref('')
const previewDate = ref(new Date().toISOString().split('T')[0])
const previewSlots = ref([])
const previewLoading = ref(false)
const previewMeta = ref({})

// Recurrence builder state
const useRecurrenceRule = ref(false)
const rruleFreq = ref('WEEKLY')
const rruleInterval = ref(1)
const rruleDays = ref([])
const rruleMonthDay = ref(1)

const dayLabels = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
const hours = Array.from({ length: 24 }, (_, i) => i)

const rruleDayOptions = {
  MO: 'Mon', TU: 'Tue', WE: 'Wed', TH: 'Thu', FR: 'Fri', SA: 'Sat', SU: 'Sun',
}

const intervalLabel = computed(() => {
  const labels = { DAILY: 'day(s)', WEEKLY: 'week(s)', MONTHLY: 'month(s)', YEARLY: 'year(s)' }
  return labels[rruleFreq.value] || ''
})

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
  priority_weight: 1.0,
  recurrence_rule: '',
  transition_playlist_id: null,
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

function toggleRruleDay(abbr) {
  const i = rruleDays.value.indexOf(abbr)
  if (i >= 0) {
    rruleDays.value.splice(i, 1)
  } else {
    rruleDays.value.push(abbr)
  }
  buildRrule()
}

function buildRrule() {
  let parts = [`FREQ=${rruleFreq.value}`]
  if (rruleInterval.value > 1) parts.push(`INTERVAL=${rruleInterval.value}`)
  if (rruleFreq.value === 'WEEKLY' && rruleDays.value.length > 0) {
    parts.push(`BYDAY=${rruleDays.value.join(',')}`)
  }
  if (rruleFreq.value === 'MONTHLY' && rruleMonthDay.value) {
    parts.push(`BYMONTHDAY=${rruleMonthDay.value}`)
  }
  form.value.recurrence_rule = parts.join(';')
}

function parseRruleToBuilder(rule) {
  if (!rule) return
  const parts = rule.split(';')
  for (const part of parts) {
    const [key, val] = part.split('=')
    if (key === 'FREQ') rruleFreq.value = val
    if (key === 'INTERVAL') rruleInterval.value = parseInt(val) || 1
    if (key === 'BYDAY') rruleDays.value = val.split(',')
    if (key === 'BYMONTHDAY') rruleMonthDay.value = parseInt(val) || 1
  }
}

function openCreate() {
  editing.value = null
  form.value = defaultForm()
  selectedDays.value = []
  useRecurrenceRule.value = false
  rruleFreq.value = 'WEEKLY'
  rruleInterval.value = 1
  rruleDays.value = []
  rruleMonthDay.value = 1
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
    priority_weight: s.priority_weight ?? 1.0,
    recurrence_rule: s.recurrence_rule || '',
    transition_playlist_id: s.transition_playlist_id || null,
    is_active: s.is_active,
  }
  if (s.recurrence_rule) {
    useRecurrenceRule.value = true
    parseRruleToBuilder(s.recurrence_rule)
  } else {
    useRecurrenceRule.value = false
    selectedDays.value = s.days_of_week
      ? s.days_of_week.split(',').map(Number)
      : []
  }
  showDialog.value = true
}

function closeDialog() {
  showDialog.value = false
  editing.value = null
}

async function saveSchedule() {
  const payload = {
    ...form.value,
    start_time: form.value.start_time || null,
    end_time: form.value.end_time || null,
    start_date: form.value.start_date || null,
    end_date: form.value.end_date || null,
    target_id: form.value.target_type === 'all' ? null : form.value.target_id,
    transition_playlist_id: form.value.transition_playlist_id || null,
  }

  if (useRecurrenceRule.value) {
    payload.days_of_week = null
    payload.recurrence_rule = form.value.recurrence_rule || null
  } else {
    payload.recurrence_rule = null
    payload.days_of_week = selectedDays.value.length > 0
      ? selectedDays.value.sort((a, b) => a - b).join(',')
      : null
  }

  if (editing.value) {
    await api.patch(`/schedules/${editing.value.id}`, payload)
  } else {
    await api.post('/schedules', payload)
  }
  closeDialog()
  await loadSchedules()
  if (showPreviewPanel.value && previewDeviceId.value) loadPreview()
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

    // Check recurrence rule or simple days
    if (s.recurrence_rule) {
      // For the week grid, check BYDAY if FREQ=WEEKLY
      const rule = parseSimpleRrule(s.recurrence_rule)
      if (rule.freq === 'WEEKLY' && rule.byday.length > 0) {
        const dayAbbrs = ['MO', 'TU', 'WE', 'TH', 'FR', 'SA', 'SU']
        if (!rule.byday.includes(dayAbbrs[dayIdx])) return false
      } else if (rule.freq === 'DAILY') {
        // Daily matches all days in the grid
      } else {
        // Monthly/yearly — show on all days in the grid (can't determine exact dates)
      }
    } else if (s.days_of_week) {
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

function parseSimpleRrule(rule) {
  const result = { freq: '', byday: [], interval: 1 }
  if (!rule) return result
  for (const part of rule.split(';')) {
    const [key, val] = part.split('=')
    if (key === 'FREQ') result.freq = val
    if (key === 'BYDAY') result.byday = val.split(',')
    if (key === 'INTERVAL') result.interval = parseInt(val) || 1
  }
  return result
}

const colorPalette = [
  '#7c83ff', '#ff6b8a', '#4ecdc4', '#ff9f43', '#a78bfa',
  '#22d3ee', '#f472b6', '#34d399', '#fbbf24', '#6366f1',
]

function scheduleColor(s) {
  const idx = schedules.value.findIndex(x => x.id === s.id)
  return colorPalette[idx % colorPalette.length]
}

function playlistColor(playlistId) {
  if (!playlistId) return '#3a3a5a'
  const plIdx = playlists.value.findIndex(p => p.id === playlistId)
  return colorPalette[plIdx >= 0 ? plIdx % colorPalette.length : 0]
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
  if (s.recurrence_rule) {
    const rule = parseSimpleRrule(s.recurrence_rule)
    let label = rule.freq.charAt(0) + rule.freq.slice(1).toLowerCase()
    if (rule.interval > 1) label = `Every ${rule.interval} ${label.toLowerCase()}s`
    if (rule.byday.length > 0) label += ` (${rule.byday.join(',')})`
    return label
  }
  if (!s.days_of_week) return 'Every day'
  const days = s.days_of_week.split(',').map(Number)
  if (days.length === 7) return 'Every day'
  if (days.length === 5 && [0,1,2,3,4].every(d => days.includes(d))) return 'Weekdays'
  if (days.length === 2 && [5,6].every(d => days.includes(d))) return 'Weekends'
  return days.map(d => dayLabels[d]).join(', ')
}

// --- Preview timeline ---
async function loadPreview() {
  if (!previewDeviceId.value) return
  previewLoading.value = true
  try {
    const params = new URLSearchParams({ device_id: previewDeviceId.value })
    if (previewDate.value) params.append('date', previewDate.value)
    const data = await api.get(`/schedules/preview/timeline?${params}`)
    previewSlots.value = data.slots || []
    previewMeta.value = data
  } catch (e) {
    previewSlots.value = []
  } finally {
    previewLoading.value = false
  }
}

const timelineBlocks = computed(() => {
  if (previewSlots.value.length === 0) return []
  // Merge consecutive slots with same playlist into blocks
  const blocks = []
  let current = null
  for (const slot of previewSlots.value) {
    if (current && current.playlist_id === slot.playlist_id && current.schedule_id === slot.schedule_id) {
      current.endIdx++
    } else {
      if (current) blocks.push(current)
      current = {
        playlist_id: slot.playlist_id,
        playlist_name: slot.playlist_name,
        schedule_id: slot.schedule_id,
        schedule_name: slot.schedule_name,
        startIdx: previewSlots.value.indexOf(slot),
        endIdx: previewSlots.value.indexOf(slot),
      }
    }
  }
  if (current) blocks.push(current)

  return blocks.map(b => ({
    left: (b.startIdx / 48) * 100,
    width: ((b.endIdx - b.startIdx + 1) / 48) * 100,
    color: b.schedule_id ? playlistColor(b.playlist_id) : '#3a3a5a',
    label: `${b.schedule_name || 'Default'}: ${b.playlist_name || 'None'}`,
    shortLabel: b.playlist_name || 'Default',
  }))
})

const timelineLegend = computed(() => {
  const seen = new Map()
  for (const slot of previewSlots.value) {
    const key = slot.playlist_id || 'default'
    if (!seen.has(key)) {
      seen.set(key, {
        name: slot.playlist_name || 'No playlist',
        color: slot.schedule_id ? playlistColor(slot.playlist_id) : '#3a3a5a',
      })
    }
  }
  return Array.from(seen.values())
})

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

.header-actions { display: flex; gap: 0.5rem; }

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
  display: flex; align-items: center; gap: 0.4rem;
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
  width: 580px; max-height: 85vh; overflow-y: auto;
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

/* Recurrence toggle */
.recurrence-toggle { display: flex; gap: 0; }

.toggle-btn {
  background: #0f1117; border: 1px solid #3a3a5a; color: #999;
  padding: 0.4rem 0.8rem; cursor: pointer; font-size: 0.8rem;
  transition: all 0.15s;
}
.toggle-btn:first-child { border-radius: 6px 0 0 6px; }
.toggle-btn:last-child { border-radius: 0 6px 6px 0; border-left: none; }
.toggle-btn.active { background: #7c83ff; border-color: #7c83ff; color: #fff; }

.recurrence-builder { padding: 0.5rem; background: rgba(124,131,255,0.05); border-radius: 8px; }

.rule-preview {
  font-family: monospace; font-size: 0.8rem !important;
  background: #0a0b0f !important; color: #7c83ff !important;
}

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

/* Preview panel */
.preview-panel {
  background: #1a1d27; border: 1px solid #2a2d3a; border-radius: 10px;
  padding: 1rem 1.25rem; margin-bottom: 1.5rem;
}

.preview-header {
  display: flex; justify-content: space-between; align-items: center;
  margin-bottom: 0.75rem; flex-wrap: wrap; gap: 0.5rem;
}

.preview-controls { display: flex; gap: 0.5rem; align-items: center; }

.preview-select { width: 200px; }

.preview-date {
  background: #0f1117; border: 1px solid #3a3a5a; color: #eee;
  padding: 0.4rem 0.6rem; border-radius: 6px; font-size: 0.85rem;
}

.preview-hint { color: #666; font-size: 0.85rem; padding: 0.5rem 0; }

.timeline-container { padding: 0.5rem 0; }

.timeline-bar {
  position: relative; height: 36px; background: #0f1117;
  border-radius: 6px; overflow: hidden; margin-bottom: 0.25rem;
}

.timeline-block {
  position: absolute; top: 0; height: 100%;
  display: flex; align-items: center; justify-content: center;
  border-right: 1px solid #1a1d27; transition: opacity 0.15s;
  cursor: default;
}
.timeline-block:hover { opacity: 0.85; }

.timeline-block-label {
  color: #fff; font-size: 0.65rem; font-weight: 500;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  padding: 0 4px;
}

.timeline-hours {
  position: relative; height: 18px; margin-bottom: 0.5rem;
}

.timeline-tick {
  position: absolute; font-size: 0.65rem; color: #666;
  transform: translateX(-50%);
}

.timeline-legend {
  display: flex; flex-wrap: wrap; gap: 0.5rem;
}

.legend-item {
  display: flex; align-items: center; gap: 0.3rem;
  font-size: 0.75rem; color: #aaa;
}

.legend-dot {
  width: 10px; height: 10px; border-radius: 3px; flex-shrink: 0;
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

.badge-rrule {
  background: rgba(124,131,255,0.2); color: #7c83ff; font-size: 0.6rem;
  padding: 1px 5px; border-radius: 3px; font-weight: 600; letter-spacing: 0.5px;
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
