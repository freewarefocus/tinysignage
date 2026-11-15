<template>
  <div class="tze-overlay" @click.self="onOverlayClick">
    <div class="tze-dialog">
      <!-- Top bar -->
      <div class="tze-topbar">
        <span class="tze-title">Visual Zone Editor</span>
        <div class="tze-topbar-controls">
          <label class="tze-bg-label">Background:</label>
          <select v-model="bgAssetId" class="tze-bg-select" @change="onBgAssetChange">
            <option value="">None</option>
            <option v-for="a in visualAssets" :key="a.id" :value="a.id">{{ a.name }}</option>
          </select>
          <button class="tze-btn upload" @click="triggerUploadBg" title="Upload an image from your computer to use as background">
            <i class="pi pi-upload"></i>
          </button>
          <input type="file" ref="bgFileInput" accept="image/*" class="tze-hidden-input" @change="onBgFileUpload" />
          <button
            class="tze-btn"
            :class="{ active: interactionMode === 'draw' }"
            @click="toggleDrawMode"
            title="Draw a new touch zone (click and drag on canvas)"
          >
            <i class="pi pi-plus"></i> Add Zone
          </button>
          <button class="tze-btn close" @click="$emit('close')" title="Close editor">
            <i class="pi pi-times"></i>
          </button>
        </div>
      </div>

      <div class="tze-body">
        <!-- Canvas area -->
        <div class="tze-canvas-wrap">
          <div
            class="tze-canvas"
            ref="canvasEl"
            :class="{ drawing: interactionMode === 'draw' }"
            @mousedown="onCanvasMouseDown"
          >
            <!-- Background image -->
            <img
              v-if="bgSrc"
              :src="bgSrc"
              class="tze-bg-img"
              draggable="false"
            />
            <!-- Hidden video for frame capture -->
            <video
              v-if="selectedIsVideo"
              ref="bgVideoEl"
              :src="videoSrc"
              class="tze-hidden-video"
              preload="auto"
              muted
              @loadedmetadata="onVideoLoaded"
              @seeked="captureVideoFrame"
            ></video>
            <div v-if="!bgSrc" class="tze-bg-empty">
              <i class="pi pi-image"></i>
              <span>No background image selected</span>
              <span class="tze-bg-hint">Zones still work — pick a background above to see placement</span>
            </div>

            <!-- Existing zones -->
            <div
              v-for="(zone, idx) in zones"
              :key="zone.id"
              class="tze-zone"
              :class="{ selected: selectedZoneId === zone.id }"
              :style="zoneStyle(zone, idx)"
              @mousedown.stop="onZoneMouseDown($event, zone)"
            >
              <div class="tze-zone-label">
                <span class="tze-zone-num">{{ idx + 1 }}</span>
                {{ targetName(zone.target_playlist_id) }}
              </div>
              <div
                class="tze-resize-handle"
                @mousedown.stop="onResizeMouseDown($event, zone)"
              ></div>
            </div>

            <!-- Draw preview -->
            <div
              v-if="drawPreview"
              class="tze-draw-preview"
              :style="drawPreviewStyle"
            ></div>
          </div>
          <!-- Video frame scrubber -->
          <div v-if="selectedIsVideo" class="tze-video-scrub">
            <label class="tze-scrub-label">Seek video frame:</label>
            <input
              type="range"
              class="tze-scrub-range"
              min="0"
              :max="videoDuration"
              step="0.1"
              :value="videoTime"
              @input="seekVideo($event)"
            />
            <span class="tze-scrub-time">{{ videoTime.toFixed(1) }}s / {{ videoDuration.toFixed(1) }}s</span>
          </div>
        </div>

        <!-- Right sidebar -->
        <div class="tze-sidebar">
          <div class="tze-zone-list">
            <div class="tze-list-header">Zones ({{ zones.length }})</div>
            <div
              v-for="(zone, idx) in zones"
              :key="zone.id"
              class="tze-list-item"
              :class="{ selected: selectedZoneId === zone.id }"
              @click="selectedZoneId = zone.id"
            >
              <span class="tze-list-dot" :style="{ background: zoneColor(idx) }"></span>
              <span class="tze-list-num">{{ idx + 1 }}.</span>
              <span class="tze-list-name">{{ targetName(zone.target_playlist_id) }}</span>
              <button class="tze-list-del" @click.stop="confirmDelete(zone)" title="Delete zone">
                <i class="pi pi-times"></i>
              </button>
            </div>
            <div v-if="zones.length === 0" class="tze-list-empty">
              No touch zones yet. Click "Add Zone" then draw on the canvas.
            </div>
          </div>

          <!-- Properties panel -->
          <div v-if="selectedZone" class="tze-props">
            <div class="tze-props-title">Zone {{ selectedIndex + 1 }} Properties</div>
            <div class="tze-props-grid">
              <div class="tze-field">
                <label>X %</label>
                <input type="number" :value="selectedConfig.x_percent" @change="updateConfig('x_percent', $event)" step="0.1" min="0" max="100" />
              </div>
              <div class="tze-field">
                <label>Y %</label>
                <input type="number" :value="selectedConfig.y_percent" @change="updateConfig('y_percent', $event)" step="0.1" min="0" max="100" />
              </div>
              <div class="tze-field">
                <label>W %</label>
                <input type="number" :value="selectedConfig.width_percent" @change="updateConfig('width_percent', $event)" step="0.1" min="1" max="100" />
              </div>
              <div class="tze-field">
                <label>H %</label>
                <input type="number" :value="selectedConfig.height_percent" @change="updateConfig('height_percent', $event)" step="0.1" min="1" max="100" />
              </div>
            </div>
            <div class="tze-field full">
              <label>Target Playlist</label>
              <select :value="selectedZone.target_playlist_id" @change="updateTarget($event)">
                <option v-for="p in allPlaylists" :key="p.id" :value="p.id">{{ p.name }}</option>
              </select>
            </div>
            <div class="tze-field full">
              <label>Priority</label>
              <input type="number" :value="selectedZone.priority || 0" @change="updatePriority($event)" min="0" max="100" />
            </div>
            <button class="tze-btn danger" @click="confirmDelete(selectedZone)">
              <i class="pi pi-trash"></i> Delete Zone
            </button>
          </div>
          <div v-else class="tze-props-empty">
            Select a zone to edit its properties
          </div>
        </div>
      </div>

      <!-- Delete confirmation -->
      <div v-if="deleteTarget" class="tze-confirm-overlay" @click.self="deleteTarget = null">
        <div class="tze-confirm">
          <p>Delete this touch zone?</p>
          <div class="tze-confirm-actions">
            <button class="tze-btn danger" @click="doDelete">Delete</button>
            <button class="tze-btn" @click="deleteTarget = null">Cancel</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { api } from '../api/client.js'

const props = defineProps({
  flowId: String,
  sourcePlaylistId: String,
  items: Array,
  allPlaylists: Array,
})

const emit = defineEmits(['close', 'updated'])

const ZONE_COLORS = [
  '#4fc3f7', '#81c784', '#ffb74d', '#e57373',
  '#ba68c8', '#4dd0e1', '#fff176', '#f06292',
]

function zoneColor(idx) {
  return ZONE_COLORS[idx % ZONE_COLORS.length]
}

// State
const canvasEl = ref(null)
const bgVideoEl = ref(null)
const bgFileInput = ref(null)
const interactionMode = ref('select') // 'select' | 'draw'
const selectedZoneId = ref(null)
const bgAssetId = ref('')
const bgOverrideUrl = ref(null) // data URL from uploaded image or video frame capture
const deleteTarget = ref(null)
const flowData = ref(null)
const videoDuration = ref(0)
const videoTime = ref(0)

// Drag state
const dragState = ref(null)
// Draw state
const drawStart = ref(null)
const drawPreview = ref(null)

// Computed
const visualAssets = computed(() => {
  if (!props.items) return []
  return props.items.filter(it => {
    const t = it.asset_type || ''
    return t === 'image' || t === 'video'
  })
})

const selectedBgItem = computed(() => {
  if (!bgAssetId.value) return null
  return props.items?.find(it => it.asset_id === bgAssetId.value || it.id === bgAssetId.value) || null
})

const selectedIsVideo = computed(() => {
  return selectedBgItem.value?.asset_type === 'video'
})

const videoSrc = computed(() => {
  if (!selectedIsVideo.value) return null
  const item = selectedBgItem.value
  if (item.file_path) return `/media/${item.file_path}`
  return null
})

const bgSrc = computed(() => {
  // Custom upload or captured video frame takes priority
  if (bgOverrideUrl.value) return bgOverrideUrl.value
  if (!bgAssetId.value) return null
  const item = selectedBgItem.value
  if (!item) return null
  if (item.asset_type === 'video' && item.thumbnail_path) {
    return `/media/thumbs/${item.thumbnail_path}`
  }
  if (item.file_path) return `/media/${item.file_path}`
  if (item.thumbnail_path) return `/media/thumbs/${item.thumbnail_path}`
  return null
})

const zones = computed(() => {
  if (!flowData.value?.branches) return []
  return flowData.value.branches.filter(b => b.trigger_type === 'touch_zone')
})

const selectedZone = computed(() => {
  if (!selectedZoneId.value) return null
  return zones.value.find(z => z.id === selectedZoneId.value) || null
})

const selectedIndex = computed(() => {
  if (!selectedZone.value) return -1
  return zones.value.findIndex(z => z.id === selectedZone.value.id)
})

const selectedConfig = computed(() => {
  if (!selectedZone.value) return {}
  const cfg = selectedZone.value.trigger_config
  return typeof cfg === 'string' ? JSON.parse(cfg) : (cfg || {})
})

const drawPreviewStyle = computed(() => {
  if (!drawPreview.value) return {}
  const d = drawPreview.value
  return {
    left: d.x + '%',
    top: d.y + '%',
    width: d.w + '%',
    height: d.h + '%',
  }
})

// Helpers
function targetName(playlistId) {
  const pl = props.allPlaylists?.find(p => p.id === playlistId)
  return pl?.name || 'Unknown'
}

function getConfig(zone) {
  const cfg = zone.trigger_config
  return typeof cfg === 'string' ? JSON.parse(cfg) : (cfg || {})
}

function zoneStyle(zone, idx) {
  const cfg = getConfig(zone)
  const color = zoneColor(idx)
  return {
    left: (cfg.x_percent || 0) + '%',
    top: (cfg.y_percent || 0) + '%',
    width: (cfg.width_percent || 10) + '%',
    height: (cfg.height_percent || 10) + '%',
    '--zone-color': color,
  }
}

// Auto-select first visual asset as background
function autoSelectBg() {
  if (visualAssets.value.length > 0 && !bgAssetId.value) {
    const first = visualAssets.value[0]
    bgAssetId.value = first.asset_id || first.id
  }
}

// Background: upload custom image
function triggerUploadBg() {
  bgFileInput.value?.click()
}

function onBgFileUpload(e) {
  const file = e.target.files?.[0]
  if (!file) return
  const reader = new FileReader()
  reader.onload = () => {
    bgAssetId.value = '' // clear asset selection
    bgOverrideUrl.value = reader.result
  }
  reader.readAsDataURL(file)
  // Reset input so same file can be re-selected
  e.target.value = ''
}

function onBgAssetChange() {
  // When user picks an asset from dropdown, clear any custom upload
  bgOverrideUrl.value = null
  videoDuration.value = 0
  videoTime.value = 0
}

// Background: video frame capture
function onVideoLoaded() {
  if (bgVideoEl.value) {
    videoDuration.value = bgVideoEl.value.duration || 0
    // Auto-capture first frame
    captureVideoFrame()
  }
}

function seekVideo(e) {
  const t = parseFloat(e.target.value)
  videoTime.value = t
  if (bgVideoEl.value) {
    bgVideoEl.value.currentTime = t
  }
}

function captureVideoFrame() {
  const video = bgVideoEl.value
  if (!video || !video.videoWidth) return
  const canvas = document.createElement('canvas')
  canvas.width = video.videoWidth
  canvas.height = video.videoHeight
  const ctx = canvas.getContext('2d')
  ctx.drawImage(video, 0, 0)
  bgOverrideUrl.value = canvas.toDataURL('image/jpeg', 0.92)
  videoTime.value = video.currentTime
}

// Data loading
async function loadFlow() {
  if (!props.flowId) return
  flowData.value = await api.get(`/trigger-flows/${props.flowId}`)
}

// Draw mode
function toggleDrawMode() {
  if (interactionMode.value === 'draw') {
    interactionMode.value = 'select'
    drawStart.value = null
    drawPreview.value = null
  } else {
    interactionMode.value = 'draw'
    selectedZoneId.value = null
  }
}

function canvasPercent(e) {
  const rect = canvasEl.value.getBoundingClientRect()
  return {
    x: ((e.clientX - rect.left) / rect.width) * 100,
    y: ((e.clientY - rect.top) / rect.height) * 100,
  }
}

// Canvas mouse handling
function onCanvasMouseDown(e) {
  if (e.button !== 0) return
  if (interactionMode.value === 'draw') {
    const pt = canvasPercent(e)
    drawStart.value = pt
    drawPreview.value = { x: pt.x, y: pt.y, w: 0, h: 0 }
  } else {
    // Clicked empty canvas area — deselect
    selectedZoneId.value = null
  }
}

function onZoneMouseDown(e, zone) {
  if (e.button !== 0) return
  if (interactionMode.value === 'draw') return
  selectedZoneId.value = zone.id
  const rect = canvasEl.value.getBoundingClientRect()
  const cfg = getConfig(zone)
  dragState.value = {
    zoneId: zone.id,
    mode: 'move',
    startX: e.clientX,
    startY: e.clientY,
    origX: cfg.x_percent || 0,
    origY: cfg.y_percent || 0,
    origW: cfg.width_percent || 10,
    origH: cfg.height_percent || 10,
    screenW: rect.width,
    screenH: rect.height,
  }
}

function onResizeMouseDown(e, zone) {
  if (e.button !== 0) return
  selectedZoneId.value = zone.id
  const rect = canvasEl.value.getBoundingClientRect()
  const cfg = getConfig(zone)
  dragState.value = {
    zoneId: zone.id,
    mode: 'resize',
    startX: e.clientX,
    startY: e.clientY,
    origX: cfg.x_percent || 0,
    origY: cfg.y_percent || 0,
    origW: cfg.width_percent || 10,
    origH: cfg.height_percent || 10,
    screenW: rect.width,
    screenH: rect.height,
  }
}

function onWindowMouseMove(e) {
  // Draw mode
  if (drawStart.value && drawPreview.value) {
    const pt = canvasPercent(e)
    const x1 = Math.min(drawStart.value.x, pt.x)
    const y1 = Math.min(drawStart.value.y, pt.y)
    const x2 = Math.max(drawStart.value.x, pt.x)
    const y2 = Math.max(drawStart.value.y, pt.y)
    drawPreview.value = {
      x: Math.max(0, x1),
      y: Math.max(0, y1),
      w: Math.min(100 - Math.max(0, x1), x2 - x1),
      h: Math.min(100 - Math.max(0, y1), y2 - y1),
    }
    return
  }

  // Drag/resize mode
  if (!dragState.value) return
  const ds = dragState.value
  const branch = flowData.value?.branches?.find(b => b.id === ds.zoneId)
  if (!branch) return

  const cfg = getConfig(branch)
  const dx = ((e.clientX - ds.startX) / ds.screenW) * 100
  const dy = ((e.clientY - ds.startY) / ds.screenH) * 100

  if (ds.mode === 'move') {
    cfg.x_percent = Math.max(0, Math.min(100 - ds.origW, Math.round((ds.origX + dx) * 10) / 10))
    cfg.y_percent = Math.max(0, Math.min(100 - ds.origH, Math.round((ds.origY + dy) * 10) / 10))
  } else if (ds.mode === 'resize') {
    cfg.width_percent = Math.max(2, Math.min(100 - ds.origX, Math.round((ds.origW + dx) * 10) / 10))
    cfg.height_percent = Math.max(2, Math.min(100 - ds.origY, Math.round((ds.origH + dy) * 10) / 10))
  }

  // Update in-place for live preview
  branch.trigger_config = cfg
}

async function onWindowMouseUp() {
  // Draw mode — create new zone
  if (drawStart.value && drawPreview.value) {
    const d = drawPreview.value
    drawStart.value = null
    drawPreview.value = null

    // Enforce minimum size
    if (d.w < 2 || d.h < 2) {
      return
    }

    const config = {
      x_percent: Math.round(d.x * 10) / 10,
      y_percent: Math.round(d.y * 10) / 10,
      width_percent: Math.round(d.w * 10) / 10,
      height_percent: Math.round(d.h * 10) / 10,
    }

    const branch = await api.post(`/trigger-flows/${props.flowId}/branches`, {
      source_playlist_id: props.sourcePlaylistId,
      target_playlist_id: props.sourcePlaylistId,
      trigger_type: 'touch_zone',
      trigger_config: config,
      priority: 0,
    })

    interactionMode.value = 'select'
    await loadFlow()
    selectedZoneId.value = branch.id
    emit('updated')
    return
  }

  // Drag/resize — commit
  if (dragState.value) {
    const ds = dragState.value
    dragState.value = null
    const branch = flowData.value?.branches?.find(b => b.id === ds.zoneId)
    if (!branch) return
    const cfg = getConfig(branch)
    await api.patch(`/trigger-branches/${ds.zoneId}`, {
      trigger_config: cfg,
    })
    await loadFlow()
    emit('updated')
  }
}

function onKeyDown(e) {
  // Escape: cancel draw > deselect > close
  if (e.key === 'Escape') {
    if (interactionMode.value === 'draw') {
      interactionMode.value = 'select'
      drawStart.value = null
      drawPreview.value = null
      e.preventDefault()
    } else if (selectedZoneId.value) {
      selectedZoneId.value = null
      e.preventDefault()
    } else {
      emit('close')
    }
    return
  }

  // Delete/Backspace: delete selected zone
  if ((e.key === 'Delete' || e.key === 'Backspace') && selectedZone.value) {
    // Don't trigger if user is typing in an input
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT') return
    confirmDelete(selectedZone.value)
    e.preventDefault()
  }
}

// Property updates
async function updateConfig(field, event) {
  if (!selectedZone.value) return
  const val = parseFloat(event.target.value)
  if (isNaN(val)) return
  const cfg = { ...selectedConfig.value, [field]: val }
  await api.patch(`/trigger-branches/${selectedZone.value.id}`, {
    trigger_config: cfg,
  })
  await loadFlow()
  emit('updated')
}

async function updateTarget(event) {
  if (!selectedZone.value) return
  await api.patch(`/trigger-branches/${selectedZone.value.id}`, {
    target_playlist_id: event.target.value,
  })
  await loadFlow()
  emit('updated')
}

async function updatePriority(event) {
  if (!selectedZone.value) return
  const val = parseInt(event.target.value) || 0
  await api.patch(`/trigger-branches/${selectedZone.value.id}`, {
    priority: val,
  })
  await loadFlow()
  emit('updated')
}

// Delete
function confirmDelete(zone) {
  deleteTarget.value = zone
}

async function doDelete() {
  if (!deleteTarget.value) return
  const id = deleteTarget.value.id
  deleteTarget.value = null
  if (selectedZoneId.value === id) selectedZoneId.value = null
  await api.delete(`/trigger-branches/${id}`)
  await loadFlow()
  emit('updated')
}

function onOverlayClick() {
  emit('close')
}

// Lifecycle
onMounted(async () => {
  await loadFlow()
  autoSelectBg()
  window.addEventListener('mousemove', onWindowMouseMove)
  window.addEventListener('mouseup', onWindowMouseUp)
  window.addEventListener('keydown', onKeyDown)
})

onUnmounted(() => {
  window.removeEventListener('mousemove', onWindowMouseMove)
  window.removeEventListener('mouseup', onWindowMouseUp)
  window.removeEventListener('keydown', onKeyDown)
})
</script>

<style scoped>
/* Overlay fills screen */
.tze-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.7);
  z-index: 2000;
  display: flex;
  align-items: center;
  justify-content: center;
}

.tze-dialog {
  background: var(--bg-surface);
  border-radius: 10px;
  width: 95vw;
  height: 90vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border: 1px solid var(--border);
}

/* Top bar */
.tze-topbar {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.6rem 1rem;
  background: var(--bg-raised);
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}

.tze-title {
  color: var(--text-primary);
  font-weight: 600;
  font-size: 0.95rem;
  margin-right: auto;
}

.tze-topbar-controls {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.tze-bg-label {
  color: var(--text-muted);
  font-size: 0.8rem;
}

.tze-bg-select {
  background: var(--bg-page);
  border: 1px solid var(--border-strong);
  color: var(--text);
  padding: 0.3rem 0.5rem;
  border-radius: 4px;
  font-size: 0.8rem;
  max-width: 180px;
}

.tze-btn {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  background: var(--bg-accent);
  color: var(--accent-soft);
  border: none;
  padding: 0.35rem 0.7rem;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.8rem;
  transition: background 0.15s;
  white-space: nowrap;
}

.tze-btn:hover { background: var(--accent-soft-hover); }
.tze-btn.active { background: var(--accent); color: #fff; }
.tze-btn.upload { background: var(--bg-raised); color: var(--text-tertiary); padding: 0.35rem 0.5rem; }
.tze-btn.upload:hover { color: var(--accent-soft); background: var(--bg-accent); }
.tze-btn.close { background: var(--bg-raised); color: var(--text-tertiary); }
.tze-btn.close:hover { color: var(--text-primary); background: var(--border-strong); }
.tze-btn.danger { background: #dc3545; color: #fff; }
.tze-btn.danger:hover { background: #c82333; }

.tze-hidden-input { display: none; }

/* Body: canvas + sidebar */
.tze-body {
  display: flex;
  flex: 1;
  min-height: 0;
}

/* Canvas area */
.tze-canvas-wrap {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1rem;
  background: var(--bg-page);
  min-width: 0;
}

.tze-canvas {
  position: relative;
  width: 100%;
  aspect-ratio: 16 / 9;
  max-height: 100%;
  background: #1a1a2e;
  border-radius: 4px;
  overflow: hidden;
  cursor: default;
  user-select: none;
}

.tze-canvas.drawing {
  cursor: crosshair;
}

.tze-bg-img {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: contain;
  pointer-events: none;
}

.tze-bg-empty {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: var(--text-ghost);
  gap: 0.5rem;
}

.tze-bg-empty i { font-size: 2rem; }
.tze-bg-empty span { font-size: 0.85rem; }
.tze-bg-hint { font-size: 0.7rem; opacity: 0.6; }

.tze-hidden-video {
  position: absolute;
  width: 0;
  height: 0;
  opacity: 0;
  pointer-events: none;
}

/* Video scrubber bar */
.tze-video-scrub {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.4rem 0;
  flex-shrink: 0;
}

.tze-scrub-label {
  color: var(--text-muted);
  font-size: 0.75rem;
  white-space: nowrap;
}

.tze-scrub-range {
  flex: 1;
  accent-color: var(--accent);
  cursor: pointer;
}

.tze-scrub-time {
  color: var(--text-ghost);
  font-size: 0.7rem;
  font-family: monospace;
  white-space: nowrap;
  min-width: 90px;
  text-align: right;
}

/* Zone rectangles on canvas */
.tze-zone {
  position: absolute;
  background: color-mix(in srgb, var(--zone-color) 25%, transparent);
  border: 2px solid var(--zone-color);
  border-radius: 2px;
  cursor: move;
  display: flex;
  align-items: flex-start;
  justify-content: flex-start;
  overflow: hidden;
}

.tze-zone.selected {
  border-width: 2px;
  border-style: solid;
  box-shadow: 0 0 0 2px var(--zone-color), inset 0 0 0 1px rgba(255,255,255,0.2);
}

.tze-zone-label {
  font-size: 0.65rem;
  color: #fff;
  background: color-mix(in srgb, var(--zone-color) 70%, black);
  padding: 1px 4px;
  border-radius: 0 0 3px 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 100%;
  pointer-events: none;
}

.tze-zone-num {
  font-weight: 700;
  margin-right: 3px;
}

/* Resize handle */
.tze-resize-handle {
  position: absolute;
  right: 0;
  bottom: 0;
  width: 12px;
  height: 12px;
  cursor: se-resize;
  background: var(--zone-color);
  border-radius: 2px 0 2px 0;
  opacity: 0;
  transition: opacity 0.15s;
}

.tze-zone:hover .tze-resize-handle,
.tze-zone.selected .tze-resize-handle {
  opacity: 1;
}

/* Draw preview */
.tze-draw-preview {
  position: absolute;
  border: 2px dashed #fff;
  background: rgba(255, 255, 255, 0.1);
  pointer-events: none;
  border-radius: 2px;
}

/* Sidebar */
.tze-sidebar {
  width: 260px;
  flex-shrink: 0;
  border-left: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  background: var(--bg-surface);
  overflow-y: auto;
}

/* Zone list */
.tze-zone-list {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  border-bottom: 1px solid var(--border);
}

.tze-list-header {
  padding: 0.6rem 0.75rem;
  font-size: 0.75rem;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  font-weight: 600;
  position: sticky;
  top: 0;
  background: var(--bg-surface);
  border-bottom: 1px solid var(--border);
}

.tze-list-item {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.4rem 0.75rem;
  cursor: pointer;
  font-size: 0.8rem;
  color: var(--text-secondary);
  transition: background 0.1s;
}

.tze-list-item:hover { background: var(--bg-hover); }
.tze-list-item.selected { background: var(--bg-accent); color: var(--text-primary); }

.tze-list-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.tze-list-num {
  color: var(--text-ghost);
  font-size: 0.7rem;
  min-width: 18px;
}

.tze-list-name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tze-list-del {
  background: none;
  border: none;
  color: var(--text-faint);
  cursor: pointer;
  padding: 2px;
  font-size: 0.7rem;
  opacity: 0;
  transition: opacity 0.1s, color 0.1s;
}

.tze-list-item:hover .tze-list-del { opacity: 1; }
.tze-list-del:hover { color: #dc3545; }

.tze-list-empty {
  padding: 1rem 0.75rem;
  color: var(--text-faint);
  font-size: 0.8rem;
  line-height: 1.5;
}

/* Properties panel */
.tze-props {
  padding: 0.75rem;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.tze-props-title {
  font-size: 0.75rem;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  font-weight: 600;
  margin-bottom: 0.25rem;
}

.tze-props-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.4rem;
}

.tze-field label {
  display: block;
  font-size: 0.65rem;
  color: var(--text-ghost);
  margin-bottom: 0.15rem;
  text-transform: uppercase;
  letter-spacing: 0.3px;
}

.tze-field input,
.tze-field select {
  width: 100%;
  background: var(--bg-page);
  border: 1px solid var(--border-strong);
  color: var(--text);
  padding: 0.3rem 0.4rem;
  border-radius: 4px;
  font-size: 0.8rem;
}

.tze-field input:focus,
.tze-field select:focus {
  border-color: var(--accent);
  outline: none;
}

.tze-field.full {
  grid-column: 1 / -1;
}

.tze-props-empty {
  padding: 1rem 0.75rem;
  color: var(--text-faint);
  font-size: 0.8rem;
  text-align: center;
}

/* Delete confirmation */
.tze-confirm-overlay {
  position: absolute;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 10;
}

.tze-confirm {
  background: var(--bg-surface);
  border-radius: 8px;
  padding: 1.25rem;
  border: 1px solid var(--border);
  min-width: 240px;
}

.tze-confirm p {
  color: var(--text-secondary);
  font-size: 0.9rem;
  margin-bottom: 1rem;
}

.tze-confirm-actions {
  display: flex;
  gap: 0.5rem;
  justify-content: flex-end;
}
</style>
