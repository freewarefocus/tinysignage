<template>
  <div>
    <h2>System</h2>

    <!-- Error Log Section -->
    <section class="log-section">
      <div class="section-header">
        <h3>Error Log</h3>
        <div class="header-actions">
          <input
            v-model="search"
            type="text"
            placeholder="Search errors..."
            class="search-input"
            @input="debouncedLoad"
          />
          <button class="btn btn-secondary" @click="exportAll" :disabled="!entries.length">
            Export All
          </button>
          <button class="btn btn-danger" @click="clearLog" :disabled="!entries.length">
            Clear Log
          </button>
        </div>
      </div>

      <div v-if="loading" class="status-msg">Loading...</div>
      <div v-else-if="!entries.length" class="status-msg">No errors logged.</div>

      <table v-else class="log-table">
        <thead>
          <tr>
            <th style="width: 170px">Timestamp</th>
            <th style="width: 70px">Level</th>
            <th style="width: 120px">Module</th>
            <th>Message</th>
            <th style="width: 60px"></th>
          </tr>
        </thead>
        <tbody>
          <template v-for="(entry, i) in entries" :key="i">
            <tr class="log-row" :class="entry.level?.toLowerCase()" @click="toggle(i)">
              <td class="ts">{{ formatTime(entry.timestamp) }}</td>
              <td><span class="level-badge" :class="entry.level?.toLowerCase()">{{ entry.level }}</span></td>
              <td>{{ entry.module }}</td>
              <td class="msg">{{ entry.message }}</td>
              <td>
                <button class="btn-icon" @click.stop="copyEntry(entry)" title="Copy JSON">
                  <i class="pi pi-copy"></i>
                </button>
              </td>
            </tr>
            <tr v-if="expanded === i" class="detail-row">
              <td colspan="5">
                <pre class="traceback">{{ formatDetail(entry) }}</pre>
              </td>
            </tr>
          </template>
        </tbody>
      </table>

      <div v-if="total > entries.length" class="pagination">
        <button class="btn btn-secondary" @click="loadMore">
          Load more ({{ total - entries.length }} remaining)
        </button>
      </div>
    </section>

    <!-- Health Dashboard Section -->
    <section class="log-section">
      <div class="section-header">
        <h3>Device Health</h3>
        <button class="btn btn-secondary" @click="loadHealth">Refresh</button>
      </div>

      <div v-if="!health" class="status-msg">Loading...</div>
      <table v-else-if="health.devices?.length" class="log-table">
        <thead>
          <tr>
            <th>Device</th>
            <th>Status</th>
            <th>Last Heartbeat</th>
            <th>Version</th>
            <th>Drift</th>
            <th>Warnings</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="d in health.devices" :key="d.id">
            <td>{{ d.name || d.id }}</td>
            <td>
              <span class="status-dot" :class="d.status"></span>
              {{ d.status }}
            </td>
            <td class="ts">{{ d.last_heartbeat ? formatTime(d.last_heartbeat) : 'Never' }}</td>
            <td>{{ d.player_version || '-' }}</td>
            <td>{{ d.clock_drift_seconds != null ? d.clock_drift_seconds + 's' : '-' }}</td>
            <td class="msg">{{ d.warnings?.join(', ') || 'None' }}</td>
          </tr>
        </tbody>
      </table>
      <div v-else class="status-msg">No devices registered.</div>
    </section>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { api } from '../api/client.js'

const entries = ref([])
const total = ref(0)
const loading = ref(true)
const expanded = ref(null)
const search = ref('')
const health = ref(null)
const pageSize = 100

let debounceTimer = null

async function loadErrors(append = false) {
  loading.value = !append
  const offset = append ? entries.value.length : 0
  const params = new URLSearchParams({ limit: pageSize, offset })
  if (search.value) params.set('search', search.value)

  const data = await api.get(`/logs/errors?${params}`)
  if (append) {
    entries.value.push(...data.entries)
  } else {
    entries.value = data.entries
  }
  total.value = data.total
  loading.value = false
}

function loadMore() {
  loadErrors(true)
}

function debouncedLoad() {
  clearTimeout(debounceTimer)
  debounceTimer = setTimeout(() => loadErrors(), 300)
}

function toggle(i) {
  expanded.value = expanded.value === i ? null : i
}

function formatTime(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  return d.toLocaleString()
}

function formatDetail(entry) {
  const parts = []
  if (entry.function) parts.push(`Function: ${entry.function} (${entry.module}:${entry.line})`)
  if (entry.request) {
    parts.push(`Request: ${entry.request.method} ${entry.request.path} from ${entry.request.client_ip}`)
  }
  if (entry.traceback) parts.push('\n' + entry.traceback)
  return parts.join('\n') || 'No additional details.'
}

async function copyEntry(entry) {
  await navigator.clipboard.writeText(JSON.stringify(entry, null, 2))
}

function exportAll() {
  const lines = entries.value.map((e) => JSON.stringify(e)).join('\n')
  const blob = new Blob([lines], { type: 'application/jsonl' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `tinysignage-errors-${new Date().toISOString().slice(0, 10)}.jsonl`
  a.click()
  URL.revokeObjectURL(url)
}

async function clearLog() {
  await api.delete('/logs/errors')
  entries.value = []
  total.value = 0
  expanded.value = null
}

async function loadHealth() {
  health.value = await api.get('/health/dashboard')
}

onMounted(() => {
  loadErrors()
  loadHealth()
})
</script>

<style scoped>
h2 { margin-bottom: 1.5rem; color: #fff; }
h3 { color: #fff; font-size: 1rem; }

.log-section {
  margin-bottom: 2.5rem;
}

.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 1rem;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.search-input {
  background: #1a1d27;
  border: 1px solid #3a3a5a;
  color: #eee;
  padding: 0.4rem 0.7rem;
  border-radius: 4px;
  font-size: 0.85rem;
  width: 200px;
}

.btn {
  padding: 0.4rem 0.8rem;
  border: none;
  border-radius: 4px;
  font-size: 0.8rem;
  cursor: pointer;
  white-space: nowrap;
}
.btn:disabled {
  opacity: 0.4;
  cursor: default;
}
.btn-secondary {
  background: #2a2d3a;
  color: #ccc;
}
.btn-secondary:hover:not(:disabled) {
  background: #3a3d4a;
}
.btn-danger {
  background: #5a2030;
  color: #f88;
}
.btn-danger:hover:not(:disabled) {
  background: #7a2840;
}

.status-msg {
  color: #888;
  font-size: 0.9rem;
  padding: 1rem 0;
}

.log-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.85rem;
}
.log-table th {
  text-align: left;
  color: #888;
  font-weight: 500;
  padding: 0.5rem 0.6rem;
  border-bottom: 1px solid #2a2d3a;
}
.log-table td {
  padding: 0.5rem 0.6rem;
  border-bottom: 1px solid #1a1d27;
  vertical-align: top;
}

.log-row {
  cursor: pointer;
  transition: background 0.1s;
}
.log-row:hover {
  background: #1e2130;
}

.ts {
  color: #888;
  font-size: 0.8rem;
  white-space: nowrap;
}
.msg {
  word-break: break-word;
  max-width: 400px;
}

.level-badge {
  display: inline-block;
  padding: 0.1rem 0.4rem;
  border-radius: 3px;
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
}
.level-badge.error {
  background: #5a2030;
  color: #f88;
}
.level-badge.critical {
  background: #6a1020;
  color: #faa;
}
.level-badge.warning {
  background: #5a4020;
  color: #fd8;
}

.detail-row td {
  background: #12141c;
  padding: 0.8rem 1rem;
}
.traceback {
  color: #ccc;
  font-family: 'Cascadia Code', 'Fira Code', monospace;
  font-size: 0.8rem;
  white-space: pre-wrap;
  word-break: break-word;
  margin: 0;
  line-height: 1.5;
}

.btn-icon {
  background: none;
  border: none;
  color: #888;
  cursor: pointer;
  padding: 0.2rem;
  font-size: 0.9rem;
}
.btn-icon:hover {
  color: #fff;
}

.pagination {
  margin-top: 1rem;
}

.status-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-right: 0.4rem;
}
.status-dot.online { background: #4caf50; }
.status-dot.offline { background: #f44336; }
.status-dot.unknown { background: #888; }
</style>
