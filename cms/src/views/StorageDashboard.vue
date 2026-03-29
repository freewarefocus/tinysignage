<template>
  <div>
    <h2>Storage</h2>

    <div v-if="loading" class="loading">Loading storage info...</div>

    <template v-else-if="data">
      <!-- Warning banner -->
      <div v-if="data.warning_active" class="warning-banner">
        <i class="pi pi-exclamation-triangle"></i>
        <span>Low disk space! Only {{ data.disk.free_mb }} MB free (threshold: {{ data.warning_threshold_mb }} MB)</span>
      </div>

      <!-- Summary cards -->
      <div class="summary-row">
        <div class="summary-card">
          <div class="card-label">Disk Usage</div>
          <div class="card-value">{{ formatMB(data.disk.used_mb) }} / {{ formatMB(data.disk.total_mb) }}</div>
          <div class="progress-bar">
            <div class="progress-fill" :class="diskClass" :style="{ width: diskPct + '%' }"></div>
          </div>
          <div class="card-sub">{{ data.disk.free_mb >= 1024 ? formatMB(data.disk.free_mb) : data.disk.free_mb + ' MB' }} free</div>
        </div>

        <div class="summary-card">
          <div class="card-label">Media Files</div>
          <div class="card-value">{{ data.media.asset_count }} files</div>
          <div class="card-sub">{{ data.media.total_mb }} MB total</div>
        </div>

        <div class="summary-card">
          <div class="card-label">Thumbnails</div>
          <div class="card-value">{{ data.media.thumbnails_mb }} MB</div>
          <div class="card-sub">Auto-generated</div>
        </div>
      </div>

      <!-- Per-asset breakdown -->
      <h3>Largest Files</h3>
      <table class="asset-table">
        <thead>
          <tr>
            <th>Name</th>
            <th>Type</th>
            <th class="right">Size</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="a in data.assets" :key="a.id">
            <td class="name-col">{{ a.name }}</td>
            <td><span class="type-badge">{{ a.asset_type }}</span></td>
            <td class="right">{{ a.file_size_mb > 0 ? a.file_size_mb + ' MB' : '--' }}</td>
          </tr>
          <tr v-if="data.assets.length === 0">
            <td colspan="3" class="empty-row">No media files</td>
          </tr>
        </tbody>
      </table>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { api } from '../api/client.js'

const data = ref(null)
const loading = ref(true)

const diskPct = computed(() => {
  if (!data.value) return 0
  const { used_mb, total_mb } = data.value.disk
  return total_mb > 0 ? Math.round((used_mb / total_mb) * 100) : 0
})

const diskClass = computed(() => {
  const pct = diskPct.value
  if (pct >= 90) return 'danger'
  if (pct >= 75) return 'warn'
  return ''
})

function formatMB(mb) {
  if (mb >= 1024) return (mb / 1024).toFixed(1) + ' GB'
  return mb + ' MB'
}

async function loadStorage() {
  loading.value = true
  try {
    data.value = await api.get('/storage')
  } finally {
    loading.value = false
  }
}

onMounted(loadStorage)
</script>

<style scoped>
h2 { margin-bottom: 1.2rem; color: #fff; }
h3 { margin: 1.5rem 0 0.8rem; color: #ddd; font-size: 1rem; }

.loading {
  color: #888;
  padding: 2rem;
  text-align: center;
}

.warning-banner {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  background: rgba(255, 152, 0, 0.15);
  border: 1px solid rgba(255, 152, 0, 0.4);
  border-radius: 8px;
  padding: 0.8rem 1rem;
  margin-bottom: 1.2rem;
  color: #ffb74d;
  font-size: 0.9rem;
}

.warning-banner i { font-size: 1.1rem; }

.summary-row {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 1rem;
  margin-bottom: 1rem;
}

.summary-card {
  background: #1a1d27;
  border-radius: 8px;
  padding: 1rem 1.2rem;
}

.card-label {
  font-size: 0.75rem;
  color: #888;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 0.4rem;
}

.card-value {
  font-size: 1.3rem;
  font-weight: 600;
  color: #fff;
}

.card-sub {
  font-size: 0.8rem;
  color: #888;
  margin-top: 0.3rem;
}

.progress-bar {
  height: 6px;
  background: #252836;
  border-radius: 3px;
  margin-top: 0.6rem;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: #7c83ff;
  border-radius: 3px;
  transition: width 0.3s;
}

.progress-fill.warn { background: #ff9800; }
.progress-fill.danger { background: #ef5350; }

.asset-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.85rem;
}

.asset-table th {
  text-align: left;
  color: #888;
  font-weight: 500;
  padding: 0.5rem 0.75rem;
  border-bottom: 1px solid #2a2d3a;
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.asset-table td {
  padding: 0.5rem 0.75rem;
  border-bottom: 1px solid #1a1d27;
  color: #ccc;
}

.asset-table tr:hover td {
  background: #1a1d27;
}

.name-col {
  max-width: 300px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.right { text-align: right; }

.type-badge {
  background: #252836;
  padding: 1px 6px;
  border-radius: 3px;
  text-transform: uppercase;
  font-size: 0.65rem;
  letter-spacing: 0.5px;
}

.empty-row {
  text-align: center;
  color: #666;
  padding: 2rem 0 !important;
}
</style>
