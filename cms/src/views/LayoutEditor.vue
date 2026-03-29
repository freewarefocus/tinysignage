<template>
  <div>
    <div class="page-header">
      <h2>Layouts</h2>
      <button class="btn-primary" @click="showCreate = true">
        <i class="pi pi-plus"></i> New Layout
      </button>
    </div>

    <!-- Create dialog -->
    <div v-if="showCreate" class="dialog-overlay" @click.self="showCreate = false">
      <div class="dialog">
        <h3>{{ editingLayout ? 'Edit Layout' : 'New Layout' }}</h3>
        <input v-model="formName" placeholder="Layout name" @keydown.enter="saveLayout" ref="nameInput" />
        <input v-model="formDesc" placeholder="Description (optional)" />
        <div class="dialog-actions">
          <button class="btn-primary" @click="saveLayout" :disabled="!formName.trim()">Save</button>
          <button class="btn-secondary" @click="closeForm">Cancel</button>
        </div>
      </div>
    </div>

    <!-- Zone editor dialog -->
    <div v-if="activeLayout" class="dialog-overlay" @click.self="closeEditor">
      <div class="dialog editor-dialog">
        <div class="editor-header">
          <h3>{{ activeLayout.name }}</h3>
          <button class="btn-icon" @click="closeEditor"><i class="pi pi-times"></i></button>
        </div>

        <!-- Visual preview -->
        <div class="preview-container">
          <div class="preview-screen" ref="previewScreen"
               @mousedown="onPreviewMouseDown"
               @mousemove="onPreviewMouseMove"
               @mouseup="onPreviewMouseUp">
            <div
              v-for="z in activeLayout.zones"
              :key="z.id"
              class="preview-zone"
              :class="{ selected: selectedZone?.id === z.id, dragging: dragState?.zoneId === z.id }"
              :style="zoneStyle(z)"
              @mousedown.stop="startDragZone($event, z)"
            >
              <div class="zone-label">{{ z.name }}</div>
              <div class="zone-type-badge">{{ z.zone_type }}</div>
              <div class="zone-playlist-label">{{ playlistName(z.playlist_id) }}</div>
              <!-- Resize handle -->
              <div class="resize-handle" @mousedown.stop="startResizeZone($event, z)"></div>
            </div>
          </div>
        </div>

        <!-- Zone list + controls -->
        <div class="zone-controls">
          <button class="btn-primary btn-sm" @click="addZone">
            <i class="pi pi-plus"></i> Add Zone
          </button>
        </div>

        <div v-if="selectedZone" class="zone-props">
          <h4>Zone: {{ selectedZone.name }}</h4>
          <div class="props-grid">
            <div class="prop-field">
              <label>Name</label>
              <input v-model="selectedZone.name" @change="updateZone(selectedZone)" />
            </div>
            <div class="prop-field">
              <label>Type</label>
              <select v-model="selectedZone.zone_type" @change="updateZone(selectedZone)">
                <option value="main">Main</option>
                <option value="sidebar">Sidebar</option>
                <option value="ticker">Ticker</option>
                <option value="pip">PiP</option>
              </select>
            </div>
            <div class="prop-field">
              <label>Playlist</label>
              <select v-model="selectedZone.playlist_id" @change="updateZone(selectedZone)">
                <option :value="null">None</option>
                <option v-for="pl in playlists" :key="pl.id" :value="pl.id">
                  {{ pl.name }}
                </option>
              </select>
            </div>
            <div class="prop-field">
              <label>Z-Index</label>
              <input type="number" v-model.number="selectedZone.z_index" @change="updateZone(selectedZone)" />
            </div>
            <div class="prop-field">
              <label>X %</label>
              <input type="number" v-model.number="selectedZone.x_percent" step="0.1" min="0" max="100" @change="updateZone(selectedZone)" />
            </div>
            <div class="prop-field">
              <label>Y %</label>
              <input type="number" v-model.number="selectedZone.y_percent" step="0.1" min="0" max="100" @change="updateZone(selectedZone)" />
            </div>
            <div class="prop-field">
              <label>Width %</label>
              <input type="number" v-model.number="selectedZone.width_percent" step="0.1" min="1" max="100" @change="updateZone(selectedZone)" />
            </div>
            <div class="prop-field">
              <label>Height %</label>
              <input type="number" v-model.number="selectedZone.height_percent" step="0.1" min="1" max="100" @change="updateZone(selectedZone)" />
            </div>
          </div>
          <button class="btn-danger btn-sm" @click="deleteZone(selectedZone)">
            <i class="pi pi-trash"></i> Delete Zone
          </button>
        </div>

        <div v-if="activeLayout.zones.length" class="zone-list">
          <div
            v-for="z in activeLayout.zones"
            :key="z.id"
            class="zone-list-item"
            :class="{ active: selectedZone?.id === z.id }"
            @click="selectedZone = z"
          >
            <span class="zone-list-name">{{ z.name }}</span>
            <span class="zone-list-type">{{ z.zone_type }}</span>
            <span class="zone-list-pl">{{ playlistName(z.playlist_id) }}</span>
          </div>
        </div>
      </div>
    </div>

    <div v-if="loading" class="loading">Loading layouts...</div>

    <div v-else-if="layouts.length === 0" class="empty">
      No layouts defined. Click <strong>New Layout</strong> to create a split-screen layout.
    </div>

    <div v-else class="layout-grid">
      <div v-for="l in layouts" :key="l.id" class="layout-card" @click="openEditor(l)">
        <div class="card-header">
          <span class="card-name">{{ l.name }}</span>
          <span class="card-count">{{ l.zone_count }} zone{{ l.zone_count !== 1 ? 's' : '' }}</span>
        </div>
        <div class="card-desc" v-if="l.description">{{ l.description }}</div>
        <!-- Mini preview -->
        <div class="mini-preview">
          <div
            v-for="z in l.zones"
            :key="z.id"
            class="mini-zone"
            :style="zoneStyle(z)"
            :title="z.name"
          ></div>
        </div>
        <div class="card-actions">
          <button class="btn-secondary btn-sm" @click.stop="startEdit(l)">
            <i class="pi pi-pencil"></i>
          </button>
          <button class="btn-danger btn-sm" @click.stop="confirmDelete(l)">
            <i class="pi pi-trash"></i>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick } from 'vue'
import { api } from '../api/client.js'

const layouts = ref([])
const playlists = ref([])
const loading = ref(true)

// Create/edit form
const showCreate = ref(false)
const editingLayout = ref(null)
const formName = ref('')
const formDesc = ref('')
const nameInput = ref(null)

// Zone editor
const activeLayout = ref(null)
const selectedZone = ref(null)

// Drag state
const dragState = ref(null)

function zoneStyle(z) {
  return {
    left: z.x_percent + '%',
    top: z.y_percent + '%',
    width: z.width_percent + '%',
    height: z.height_percent + '%',
    zIndex: z.z_index || 0,
  }
}

function playlistName(id) {
  if (!id) return 'No playlist'
  const pl = playlists.value.find(p => p.id === id)
  return pl ? pl.name : 'Unknown'
}

async function loadLayouts() {
  try {
    layouts.value = await api.get('/layouts')
  } finally {
    loading.value = false
  }
}

async function loadPlaylists() {
  playlists.value = await api.get('/playlists')
}

// --- Layout CRUD ---
function closeForm() {
  showCreate.value = false
  editingLayout.value = null
  formName.value = ''
  formDesc.value = ''
}

function startEdit(layout) {
  editingLayout.value = layout
  formName.value = layout.name
  formDesc.value = layout.description || ''
  showCreate.value = true
  nextTick(() => nameInput.value?.focus())
}

async function saveLayout() {
  const name = formName.value.trim()
  if (!name) return

  if (editingLayout.value) {
    await api.patch(`/layouts/${editingLayout.value.id}`, {
      name,
      description: formDesc.value.trim() || null,
    })
  } else {
    await api.post('/layouts', {
      name,
      description: formDesc.value.trim() || null,
    })
  }
  closeForm()
  await loadLayouts()
}

async function confirmDelete(layout) {
  if (!confirm(`Delete layout "${layout.name}"? All zones will be removed.`)) return
  await api.delete(`/layouts/${layout.id}`)
  await loadLayouts()
}

// --- Zone editor ---
async function openEditor(layout) {
  const full = await api.get(`/layouts/${layout.id}`)
  activeLayout.value = full
  selectedZone.value = null
}

function closeEditor() {
  activeLayout.value = null
  selectedZone.value = null
  loadLayouts()
}

async function addZone() {
  const zoneCount = activeLayout.value.zones.length
  const zone = await api.post(`/layouts/${activeLayout.value.id}/zones`, {
    name: `Zone ${zoneCount + 1}`,
    zone_type: zoneCount === 0 ? 'main' : 'sidebar',
    x_percent: zoneCount === 0 ? 0 : 50,
    y_percent: 0,
    width_percent: zoneCount === 0 ? 100 : 50,
    height_percent: 100,
    z_index: zoneCount,
  })
  activeLayout.value.zones.push(zone)
  selectedZone.value = zone
}

async function updateZone(zone) {
  await api.patch(`/layouts/${activeLayout.value.id}/zones/${zone.id}`, {
    name: zone.name,
    zone_type: zone.zone_type,
    x_percent: zone.x_percent,
    y_percent: zone.y_percent,
    width_percent: zone.width_percent,
    height_percent: zone.height_percent,
    z_index: zone.z_index,
    playlist_id: zone.playlist_id,
  })
}

async function deleteZone(zone) {
  if (!confirm(`Delete zone "${zone.name}"?`)) return
  await api.delete(`/layouts/${activeLayout.value.id}/zones/${zone.id}`)
  activeLayout.value.zones = activeLayout.value.zones.filter(z => z.id !== zone.id)
  if (selectedZone.value?.id === zone.id) selectedZone.value = null
}

// --- Drag & resize ---
const previewScreen = ref(null)

function startDragZone(e, zone) {
  selectedZone.value = zone
  const rect = previewScreen.value.getBoundingClientRect()
  dragState.value = {
    zoneId: zone.id,
    mode: 'move',
    startX: e.clientX,
    startY: e.clientY,
    origX: zone.x_percent,
    origY: zone.y_percent,
    screenW: rect.width,
    screenH: rect.height,
  }
}

function startResizeZone(e, zone) {
  selectedZone.value = zone
  const rect = previewScreen.value.getBoundingClientRect()
  dragState.value = {
    zoneId: zone.id,
    mode: 'resize',
    startX: e.clientX,
    startY: e.clientY,
    origW: zone.width_percent,
    origH: zone.height_percent,
    screenW: rect.width,
    screenH: rect.height,
  }
}

function onPreviewMouseDown() {
  // clicked empty area — deselect
}

function onPreviewMouseMove(e) {
  if (!dragState.value) return
  const ds = dragState.value
  const zone = activeLayout.value.zones.find(z => z.id === ds.zoneId)
  if (!zone) return

  const dx = ((e.clientX - ds.startX) / ds.screenW) * 100
  const dy = ((e.clientY - ds.startY) / ds.screenH) * 100

  if (ds.mode === 'move') {
    zone.x_percent = Math.max(0, Math.min(100 - zone.width_percent, Math.round((ds.origX + dx) * 10) / 10))
    zone.y_percent = Math.max(0, Math.min(100 - zone.height_percent, Math.round((ds.origY + dy) * 10) / 10))
  } else if (ds.mode === 'resize') {
    zone.width_percent = Math.max(5, Math.min(100 - zone.x_percent, Math.round((ds.origW + dx) * 10) / 10))
    zone.height_percent = Math.max(5, Math.min(100 - zone.y_percent, Math.round((ds.origH + dy) * 10) / 10))
  }
}

function onPreviewMouseUp() {
  if (dragState.value) {
    const zone = activeLayout.value.zones.find(z => z.id === dragState.value.zoneId)
    if (zone) updateZone(zone)
    dragState.value = null
  }
}

onMounted(async () => {
  await Promise.all([loadLayouts(), loadPlaylists()])
})
</script>

<style scoped>
h2 { color: #fff; }
h3 { color: #fff; margin-bottom: 0.5rem; }
h4 { color: #ccc; margin-bottom: 0.5rem; font-size: 0.9rem; }

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.5rem;
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
}
.btn-icon:hover { color: #fff; }

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
}
.btn-danger:hover { background: #7a2840; }
.btn-danger.btn-sm { padding: 0.35rem 0.75rem; font-size: 0.8rem; }

.loading, .empty {
  text-align: center;
  padding: 3rem;
  color: #666;
}
.empty strong { color: #7c83ff; }

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

.editor-dialog {
  width: 800px;
  max-width: 95vw;
  max-height: 90vh;
  overflow-y: auto;
}

.editor-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
  padding-bottom: 0.5rem;
  border-bottom: 1px solid #2a2d3a;
}

.dialog input, .dialog select {
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
.dialog input:focus, .dialog select:focus { border-color: #7c83ff; }

.dialog-actions {
  display: flex;
  gap: 0.5rem;
  justify-content: flex-end;
}

/* Layout grid */
.layout-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 1rem;
}

.layout-card {
  background: #1a1d27;
  border-radius: 8px;
  padding: 1rem 1.2rem;
  cursor: pointer;
  border: 1px solid transparent;
  transition: border-color 0.15s;
}
.layout-card:hover { border-color: #7c83ff; }

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.4rem;
}
.card-name { font-size: 1rem; font-weight: 500; color: #fff; }
.card-count { font-size: 0.8rem; color: #888; }
.card-desc { font-size: 0.85rem; color: #999; margin-bottom: 0.5rem; }

.card-actions {
  display: flex;
  gap: 0.5rem;
  margin-top: 0.5rem;
}

/* Mini preview */
.mini-preview {
  position: relative;
  width: 100%;
  height: 80px;
  background: #0f1117;
  border-radius: 4px;
  overflow: hidden;
}

.mini-zone {
  position: absolute;
  background: rgba(124, 131, 255, 0.3);
  border: 1px solid rgba(124, 131, 255, 0.6);
  border-radius: 2px;
}

/* Visual zone editor */
.preview-container {
  margin-bottom: 1rem;
}

.preview-screen {
  position: relative;
  width: 100%;
  aspect-ratio: 16 / 9;
  background: #0a0b10;
  border: 2px solid #2a2d3a;
  border-radius: 6px;
  overflow: hidden;
  cursor: default;
  user-select: none;
}

.preview-zone {
  position: absolute;
  background: rgba(124, 131, 255, 0.15);
  border: 2px solid rgba(124, 131, 255, 0.5);
  border-radius: 4px;
  cursor: move;
  transition: border-color 0.15s;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.2rem;
  overflow: hidden;
}

.preview-zone.selected {
  border-color: #7c83ff;
  background: rgba(124, 131, 255, 0.25);
}

.preview-zone.dragging {
  opacity: 0.8;
}

.zone-label {
  font-size: 0.75rem;
  font-weight: 600;
  color: #fff;
  text-shadow: 0 1px 3px rgba(0,0,0,0.8);
}

.zone-type-badge {
  font-size: 0.6rem;
  color: #7c83ff;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.zone-playlist-label {
  font-size: 0.6rem;
  color: #888;
  text-overflow: ellipsis;
  white-space: nowrap;
  overflow: hidden;
  max-width: 90%;
  text-align: center;
}

.resize-handle {
  position: absolute;
  right: 0;
  bottom: 0;
  width: 14px;
  height: 14px;
  cursor: se-resize;
  background: linear-gradient(135deg, transparent 50%, #7c83ff 50%);
  border-radius: 0 0 2px 0;
}

/* Zone controls */
.zone-controls {
  margin-bottom: 1rem;
}

/* Zone properties */
.zone-props {
  background: #0f1117;
  border-radius: 6px;
  padding: 1rem;
  margin-bottom: 1rem;
}

.props-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.5rem;
  margin-bottom: 0.75rem;
}

.prop-field label {
  display: block;
  font-size: 0.7rem;
  color: #666;
  text-transform: uppercase;
  letter-spacing: 0.3px;
  margin-bottom: 0.2rem;
}

.prop-field input, .prop-field select {
  width: 100%;
  background: #1a1d27;
  border: 1px solid #3a3a5a;
  color: #eee;
  padding: 0.35rem 0.5rem;
  border-radius: 4px;
  font-size: 0.85rem;
  outline: none;
  margin-bottom: 0;
}
.prop-field input:focus, .prop-field select:focus { border-color: #7c83ff; }

/* Zone list */
.zone-list {
  border-top: 1px solid #2a2d3a;
  padding-top: 0.75rem;
}

.zone-list-item {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.5rem 0.75rem;
  border-radius: 4px;
  cursor: pointer;
  transition: background 0.1s;
}
.zone-list-item:hover { background: #1e2130; }
.zone-list-item.active { background: #252840; }

.zone-list-name { color: #ddd; font-size: 0.85rem; font-weight: 500; flex: 1; }
.zone-list-type { color: #7c83ff; font-size: 0.75rem; text-transform: uppercase; }
.zone-list-pl { color: #888; font-size: 0.8rem; }
</style>
