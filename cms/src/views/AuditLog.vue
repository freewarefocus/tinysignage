<template>
  <div>
    <h2>Audit Log</h2>

    <div class="filters">
      <select v-model="filterAction" @change="loadEntries()" class="filter-select">
        <option value="">All Actions</option>
        <option v-for="a in availableActions" :key="a" :value="a">{{ formatAction(a) }}</option>
      </select>
      <select v-model="filterEntity" @change="loadEntries()" class="filter-select">
        <option value="">All Types</option>
        <option v-for="t in availableTypes" :key="t" :value="t">{{ t }}</option>
      </select>
      <input
        v-model="filterUser"
        type="text"
        placeholder="Filter by user..."
        class="search-input"
        @input="debouncedLoad"
      />
      <input
        v-model="filterSearch"
        type="text"
        placeholder="Search details..."
        class="search-input"
        @input="debouncedLoad"
      />
      <input
        v-model="filterDateFrom"
        type="date"
        class="filter-date"
        @change="loadEntries()"
      />
      <span class="date-sep">to</span>
      <input
        v-model="filterDateTo"
        type="date"
        class="filter-date"
        @change="loadEntries()"
      />
      <button class="btn btn-secondary" @click="clearFilters">Clear</button>
      <button class="btn btn-secondary" @click="exportLog" :disabled="!entries.length">Export</button>
    </div>

    <div v-if="loading" class="status-msg">Loading...</div>
    <div v-else-if="!entries.length" class="status-msg">No audit entries found.</div>

    <table v-else class="log-table">
      <thead>
        <tr>
          <th style="width: 160px">Timestamp</th>
          <th style="width: 120px">User</th>
          <th style="width: 100px">Action</th>
          <th style="width: 90px">Type</th>
          <th>Details</th>
          <th style="width: 110px">IP</th>
        </tr>
      </thead>
      <tbody>
        <template v-for="(entry, i) in entries" :key="entry.id">
          <tr class="log-row" @click="toggle(i)">
            <td class="ts">{{ formatTime(entry.timestamp) }}</td>
            <td class="user">{{ entry.username || '-' }}</td>
            <td>
              <span class="action-badge" :class="actionClass(entry.action)">
                {{ formatAction(entry.action) }}
              </span>
            </td>
            <td class="entity-type">{{ entry.entity_type }}</td>
            <td class="details-summary">{{ summarize(entry) }}</td>
            <td class="ts">{{ entry.ip_address || '-' }}</td>
          </tr>
          <tr v-if="expanded === i" class="detail-row">
            <td colspan="6">
              <pre class="detail-json">{{ JSON.stringify(entry.details, null, 2) }}</pre>
              <div class="detail-meta">
                Entity ID: {{ entry.entity_id || '-' }}
              </div>
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

    <div v-if="total" class="total-count">{{ total }} total entries</div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { api } from '../api/client.js'

const entries = ref([])
const total = ref(0)
const loading = ref(true)
const expanded = ref(null)
const pageSize = 50

const filterAction = ref('')
const filterEntity = ref('')
const filterUser = ref('')
const filterSearch = ref('')
const filterDateFrom = ref('')
const filterDateTo = ref('')

const availableActions = ref([])
const availableTypes = ref([])

let debounceTimer = null

async function loadFilterOptions() {
  try {
    const data = await api.get('/audit/actions')
    availableActions.value = data.actions
    availableTypes.value = data.entity_types
  } catch {
    // Filters will just be empty
  }
}

async function loadEntries(append = false) {
  loading.value = !append
  const offset = append ? entries.value.length : 0
  const params = new URLSearchParams({ limit: pageSize, offset })
  if (filterAction.value) params.set('action', filterAction.value)
  if (filterEntity.value) params.set('entity_type', filterEntity.value)
  if (filterUser.value) params.set('user', filterUser.value)
  if (filterSearch.value) params.set('search', filterSearch.value)
  if (filterDateFrom.value) params.set('date_from', filterDateFrom.value)
  if (filterDateTo.value) params.set('date_to', filterDateTo.value)

  const data = await api.get(`/audit?${params}`)
  if (append) {
    entries.value.push(...data.entries)
  } else {
    entries.value = data.entries
  }
  total.value = data.total
  loading.value = false
}

function loadMore() {
  loadEntries(true)
}

function debouncedLoad() {
  clearTimeout(debounceTimer)
  debounceTimer = setTimeout(() => loadEntries(), 300)
}

function clearFilters() {
  filterAction.value = ''
  filterEntity.value = ''
  filterUser.value = ''
  filterSearch.value = ''
  filterDateFrom.value = ''
  filterDateTo.value = ''
  loadEntries()
}

function toggle(i) {
  expanded.value = expanded.value === i ? null : i
}

function formatTime(iso) {
  if (!iso) return ''
  return new Date(iso).toLocaleString()
}

function formatAction(action) {
  if (!action) return ''
  return action.replace(/_/g, ' ')
}

function actionClass(action) {
  if (action === 'delete') return 'danger'
  if (action === 'create' || action === 'register') return 'success'
  if (action === 'login' || action === 'logout') return 'info'
  return 'default'
}

function summarize(entry) {
  if (!entry.details) return '-'
  const d = entry.details
  if (d.name) return d.name
  if (d.username) return d.username
  if (d.changes) {
    const keys = Object.keys(d.changes)
    return keys.length ? keys.join(', ') : '-'
  }
  return '-'
}

function exportLog() {
  const lines = entries.value.map((e) => JSON.stringify(e)).join('\n')
  const blob = new Blob([lines], { type: 'application/jsonl' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `tinysignage-audit-${new Date().toISOString().slice(0, 10)}.jsonl`
  a.click()
  URL.revokeObjectURL(url)
}

onMounted(() => {
  loadFilterOptions()
  loadEntries()
})
</script>

<style scoped>
h2 { margin-bottom: 1.5rem; color: #fff; }

.filters {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 1rem;
  flex-wrap: wrap;
}

.filter-select {
  background: #1a1d27;
  border: 1px solid #3a3a5a;
  color: #eee;
  padding: 0.4rem 0.5rem;
  border-radius: 4px;
  font-size: 0.85rem;
}

.search-input {
  background: #1a1d27;
  border: 1px solid #3a3a5a;
  color: #eee;
  padding: 0.4rem 0.7rem;
  border-radius: 4px;
  font-size: 0.85rem;
  width: 160px;
}

.filter-date {
  background: #1a1d27;
  border: 1px solid #3a3a5a;
  color: #eee;
  padding: 0.35rem 0.5rem;
  border-radius: 4px;
  font-size: 0.82rem;
  color-scheme: dark;
}

.date-sep {
  color: #888;
  font-size: 0.85rem;
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

.user {
  color: #b0b0ff;
  font-size: 0.85rem;
}

.entity-type {
  color: #aaa;
  text-transform: capitalize;
}

.details-summary {
  color: #ccc;
  max-width: 300px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.action-badge {
  display: inline-block;
  padding: 0.1rem 0.5rem;
  border-radius: 3px;
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: capitalize;
}
.action-badge.danger {
  background: #5a2030;
  color: #f88;
}
.action-badge.success {
  background: #1a4030;
  color: #8f8;
}
.action-badge.info {
  background: #1a3050;
  color: #8cf;
}
.action-badge.default {
  background: #2a2d3a;
  color: #ccc;
}

.detail-row td {
  background: #12141c;
  padding: 0.8rem 1rem;
}
.detail-json {
  color: #ccc;
  font-family: 'Cascadia Code', 'Fira Code', monospace;
  font-size: 0.8rem;
  white-space: pre-wrap;
  word-break: break-word;
  margin: 0 0 0.5rem;
  line-height: 1.5;
}
.detail-meta {
  color: #888;
  font-size: 0.8rem;
}

.pagination {
  margin-top: 1rem;
}

.total-count {
  color: #888;
  font-size: 0.8rem;
  margin-top: 0.5rem;
}
</style>
