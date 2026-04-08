<template>
  <div class="designer">
    <!-- Topbar -->
    <div class="topbar">
      <input
        v-model="slideName"
        class="name-input"
        placeholder="Slide name"
        v-tooltip.bottom="'Name shown in the Media Library'"
      />
      <div class="topbar-spacer"></div>
      <button class="tb-btn" @click="undo" :disabled="!undoStack.length" v-tooltip.bottom="'Undo (Ctrl+Z)'">
        <i class="pi pi-undo"></i>
      </button>
      <button class="tb-btn" @click="redo" :disabled="!redoStack.length" v-tooltip.bottom="'Redo (Ctrl+Y)'">
        <i class="pi pi-refresh"></i>
      </button>
      <label class="tb-toggle" v-tooltip.bottom="'Snap moves and resizes to whole percent steps'">
        <input type="checkbox" v-model="snapEnabled" />
        Snap
      </label>
      <div class="topbar-spacer"></div>
      <button class="tb-btn secondary" @click="showPreview = true" v-tooltip.bottom="'Preview at full screen size'">
        <i class="pi pi-eye"></i> Preview
      </button>
      <button class="tb-btn primary" @click="save" :disabled="saving" v-tooltip.bottom="'Save as a custom slide in the Media Library'">
        <i class="pi pi-save"></i> {{ saving ? 'Saving…' : 'Save' }}
      </button>
      <button class="tb-btn secondary" @click="exit" v-tooltip.bottom="'Back to Media Library'">
        <i class="pi pi-times"></i>
      </button>
    </div>

    <div v-if="legacyMode" class="legacy-banner">
      <i class="pi pi-info-circle"></i>
      This slide was created with the raw HTML editor and can't be opened visually.
      <button class="link-btn" @click="openInRawEditor">Open in raw HTML editor instead</button>
    </div>

    <div class="main-area">
      <!-- Left palette -->
      <aside class="palette">
        <div class="palette-tabs">
          <button :class="{ active: leftTab === 'elements' }" @click="leftTab = 'elements'">Elements</button>
          <button :class="{ active: leftTab === 'templates' }" @click="leftTab = 'templates'">Templates</button>
          <button :class="{ active: leftTab === 'layers' }" @click="leftTab = 'layers'">Layers</button>
        </div>

        <!-- Elements tab -->
        <div v-if="leftTab === 'elements'" class="palette-body">
          <div class="palette-section-title">Text</div>
          <div class="palette-grid">
            <button class="palette-tile" @click="addElement('text', { variant: 'heading' })" v-tooltip.right="'Big heading text'">
              <i class="pi pi-bold"></i><span>Heading</span>
            </button>
            <button class="palette-tile" @click="addElement('text', { variant: 'body' })" v-tooltip.right="'Body / subtitle text'">
              <i class="pi pi-align-left"></i><span>Body</span>
            </button>
          </div>

          <div class="palette-section-title">Image</div>
          <div class="palette-grid">
            <button class="palette-tile" @click="addElement('image')" v-tooltip.right="'Pick an image from your Media Library'">
              <i class="pi pi-image"></i><span>Image</span>
            </button>
          </div>

          <div class="palette-section-title">Shapes</div>
          <div class="palette-grid">
            <button class="palette-tile" @click="addElement('shape', { shape: 'rect' })" v-tooltip.right="'Rectangle'">
              <i class="pi pi-stop"></i><span>Rect</span>
            </button>
            <button class="palette-tile" @click="addElement('shape', { shape: 'circle' })" v-tooltip.right="'Circle'">
              <i class="pi pi-circle"></i><span>Circle</span>
            </button>
            <button class="palette-tile" @click="addElement('shape', { shape: 'divider' })" v-tooltip.right="'Thin horizontal divider line'">
              <i class="pi pi-minus"></i><span>Line</span>
            </button>
          </div>

          <div class="palette-section-title">Live Widgets</div>
          <div v-if="!widgets.length" class="palette-empty">Loading widgets…</div>
          <div v-else class="palette-grid">
            <button
              v-for="w in widgets"
              :key="w.id"
              class="palette-tile"
              @click="addElement('widget', { widgetId: w.id })"
              v-tooltip.right="w.description"
            >
              <i :class="widgetIcon(w.id)"></i>
              <span>{{ w.name }}</span>
            </button>
          </div>

          <div class="palette-section-title">Background</div>
          <div class="bg-row">
            <button
              v-for="c in bgSwatches"
              :key="c"
              class="bg-swatch"
              :class="{ active: canvasBg === c }"
              :style="{ background: c }"
              @click="setCanvasBg(c)"
              v-tooltip.bottom="c"
            ></button>
            <input type="color" :value="canvasBg" @change="setCanvasBg($event.target.value)" class="bg-color-input" v-tooltip.bottom="'Custom color'" />
          </div>
        </div>

        <!-- Templates tab -->
        <div v-else-if="leftTab === 'templates'" class="palette-body">
          <p class="palette-hint">Click a template to load it onto the canvas. Replaces the current design.</p>
          <div class="template-list">
            <button
              v-for="t in templates"
              :key="t.id"
              class="template-card"
              @click="loadTemplate(t)"
              v-tooltip.right="t.description"
            >
              <i :class="t.icon"></i>
              <span class="template-name">{{ t.name }}</span>
            </button>
          </div>
        </div>

        <!-- Layers tab -->
        <div v-else class="palette-body">
          <p class="palette-hint">Top of the list draws on top.</p>
          <div v-if="!elements.length" class="palette-empty">No elements yet</div>
          <div v-else class="layer-list">
            <div
              v-for="(el, idx) in [...elements].reverse()"
              :key="el.id"
              class="layer-row"
              :class="{ active: selectedId === el.id }"
              @click="selectedId = el.id"
            >
              <i :class="elementIcon(el)"></i>
              <span class="layer-label">{{ elementLabel(el) }}</span>
              <button class="layer-action" @click.stop="moveLayer(el.id, -1)" v-tooltip.left="'Move up'">
                <i class="pi pi-chevron-up"></i>
              </button>
              <button class="layer-action" @click.stop="moveLayer(el.id, 1)" v-tooltip.left="'Move down'">
                <i class="pi pi-chevron-down"></i>
              </button>
            </div>
          </div>
        </div>
      </aside>

      <!-- Center canvas -->
      <div class="canvas-area" ref="canvasArea">
        <div
          class="canvas-frame"
          :style="canvasFrameStyle"
        >
          <div
            class="canvas"
            ref="canvasEl"
            :style="{ background: canvasBg }"
            @mousedown="onCanvasMouseDown"
          >
            <div
              v-for="(el, idx) in elements"
              :key="el.id"
              class="canvas-el"
              :class="{ selected: selectedId === el.id }"
              :style="elementStyle(el, idx)"
              @mousedown.stop="startDrag($event, el)"
            >
              <component :is="'div'" class="el-content" v-html="renderElementPreview(el)"></component>
              <template v-if="selectedId === el.id">
                <div class="resize-handle nw" @mousedown.stop="startResize($event, el, 'nw')"></div>
                <div class="resize-handle ne" @mousedown.stop="startResize($event, el, 'ne')"></div>
                <div class="resize-handle sw" @mousedown.stop="startResize($event, el, 'sw')"></div>
                <div class="resize-handle se" @mousedown.stop="startResize($event, el, 'se')"></div>
              </template>
            </div>
            <div v-if="!elements.length" class="canvas-empty">
              Click an element on the left to add it here
            </div>
          </div>
        </div>
      </div>

      <!-- Right properties panel -->
      <aside class="props-panel">
        <div v-if="!selected" class="props-empty">
          <i class="pi pi-mouse-pointer"></i>
          <p>Select an element to edit its properties.</p>
        </div>
        <div v-else class="props-body">
          <h3 class="props-title">{{ elementLabel(selected) }}</h3>

          <!-- Universal position fields -->
          <div class="props-grid">
            <div class="prop-field">
              <label>X %</label>
              <input type="number" step="0.1" v-model.number="selected.x" @focus="onPropFocus" @change="onPropChange" />
            </div>
            <div class="prop-field">
              <label>Y %</label>
              <input type="number" step="0.1" v-model.number="selected.y" @focus="onPropFocus" @change="onPropChange" />
            </div>
            <div class="prop-field">
              <label>W %</label>
              <input type="number" step="0.1" v-model.number="selected.w" @focus="onPropFocus" @change="onPropChange" />
            </div>
            <div class="prop-field">
              <label>H %</label>
              <input type="number" step="0.1" v-model.number="selected.h" @focus="onPropFocus" @change="onPropChange" />
            </div>
          </div>
          <div class="prop-field">
            <label>Opacity</label>
            <input type="range" min="0" max="1" step="0.05" v-model.number="selected.opacity" @mousedown="onPropFocus" @change="onPropChange" />
            <span class="prop-value">{{ Math.round(selected.opacity * 100) }}%</span>
          </div>

          <hr class="props-sep" />

          <!-- Text-specific -->
          <template v-if="selected.type === 'text'">
            <div class="prop-field">
              <label>Text</label>
              <textarea v-model="selected.props.text" rows="3" @focus="onPropFocus" @blur="onPropChange"></textarea>
            </div>
            <div class="prop-field">
              <label>Font size (px @ 1080p)</label>
              <input type="number" min="8" max="400" v-model.number="selected.props.fontSize" @focus="onPropFocus" @change="onPropChange" />
              <p class="form-hint">Scales with screen size — preview at full size to check.</p>
            </div>
            <div class="prop-field">
              <label>Color</label>
              <input type="color" v-model="selected.props.color" @focus="onPropFocus" @change="onPropChange" />
            </div>
            <div class="props-grid">
              <div class="prop-field">
                <label>Weight</label>
                <select v-model.number="selected.props.fontWeight" @focus="onPropFocus" @change="onPropChange">
                  <option :value="300">Light</option>
                  <option :value="400">Regular</option>
                  <option :value="600">Semibold</option>
                  <option :value="700">Bold</option>
                </select>
              </div>
              <div class="prop-field">
                <label>Align</label>
                <select v-model="selected.props.align" @focus="onPropFocus" @change="onPropChange">
                  <option value="left">Left</option>
                  <option value="center">Center</option>
                  <option value="right">Right</option>
                </select>
              </div>
            </div>
            <div class="prop-field">
              <label>Font family</label>
              <select v-model="selected.props.fontFamily" @focus="onPropFocus" @change="onPropChange">
                <option value="sans-serif">Sans-serif</option>
                <option value="serif">Serif</option>
                <option value="monospace">Monospace</option>
              </select>
            </div>
          </template>

          <!-- Image-specific -->
          <template v-else-if="selected.type === 'image'">
            <div class="prop-field">
              <label>Image</label>
              <select v-model="selected.props.assetId" @focus="onPropFocus" @change="onPropChange">
                <option :value="null">— Pick an image —</option>
                <option v-for="img in imageAssets" :key="img.id" :value="img.id">
                  {{ img.name }}
                </option>
              </select>
              <p v-if="!imageAssets.length" class="form-hint">No images in your library yet. Upload one in Media Library first.</p>
            </div>
            <div class="prop-field">
              <label>Fit</label>
              <select v-model="selected.props.fit" @focus="onPropFocus" @change="onPropChange">
                <option value="cover">Cover (fill, may crop)</option>
                <option value="contain">Contain (fit inside)</option>
                <option value="fill">Stretch</option>
              </select>
            </div>
          </template>

          <!-- Shape-specific -->
          <template v-else-if="selected.type === 'shape'">
            <div class="prop-field">
              <label>Shape</label>
              <select v-model="selected.props.shape" @focus="onPropFocus" @change="onPropChange">
                <option value="rect">Rectangle</option>
                <option value="circle">Circle</option>
                <option value="divider">Divider line</option>
              </select>
            </div>
            <div class="prop-field">
              <label>Fill</label>
              <input type="color" v-model="selected.props.fill" @focus="onPropFocus" @change="onPropChange" />
            </div>
            <div v-if="selected.props.shape === 'rect'" class="prop-field">
              <label>Border radius (px)</label>
              <input type="number" min="0" max="200" v-model.number="selected.props.borderRadius" @focus="onPropFocus" @change="onPropChange" />
            </div>
          </template>

          <!-- Widget-specific -->
          <template v-else-if="selected.type === 'widget'">
            <div class="prop-field">
              <label>Widget</label>
              <select v-model="selected.props.widgetId" @focus="onPropFocus" @change="onWidgetChange">
                <option v-for="w in widgets" :key="w.id" :value="w.id">{{ w.name }}</option>
              </select>
              <p v-if="selectedWidgetDef" class="form-hint">{{ selectedWidgetDef.description }}</p>
            </div>
            <div v-if="selectedWidgetDef" class="widget-params">
              <div v-for="param in selectedWidgetDef.params" :key="param.name" class="prop-field">
                <label>{{ param.label }}</label>
                <input
                  v-if="param.type === 'boolean'"
                  type="checkbox"
                  :checked="getWidgetParam(param)"
                  @change="setWidgetParam(param, $event.target.checked)"
                />
                <input
                  v-else-if="param.type === 'number'"
                  type="number"
                  step="any"
                  :value="getWidgetParam(param)"
                  @change="setWidgetParam(param, parseFloat($event.target.value))"
                />
                <input
                  v-else
                  type="text"
                  :value="getWidgetParam(param)"
                  @change="setWidgetParam(param, $event.target.value)"
                />
              </div>
            </div>
          </template>

          <hr class="props-sep" />
          <div class="props-actions">
            <button class="btn-secondary btn-sm" @click="duplicateSelected" v-tooltip.top="'Make a copy'">
              <i class="pi pi-copy"></i> Duplicate
            </button>
            <button class="btn-danger btn-sm" @click="deleteSelected" v-tooltip.top="'Delete element'">
              <i class="pi pi-trash"></i> Delete
            </button>
          </div>
        </div>
      </aside>
    </div>

    <!-- Preview overlay -->
    <div v-if="showPreview" class="preview-overlay" @click.self="showPreview = false">
      <button class="preview-close" @click="showPreview = false" v-tooltip.left="'Close (Esc)'">
        <i class="pi pi-times"></i>
      </button>
      <iframe class="preview-iframe" :srcdoc="previewHtml"></iframe>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '../api/client.js'
import { DESIGNER_TEMPLATES } from '../presets/designerTemplates.js'

const route = useRoute()
const router = useRouter()

// ─── State ───────────────────────────────────────────────
const slideName = ref('My Custom Slide')
const editingAssetId = ref(null)
const elements = ref([])
const selectedId = ref(null)
const canvasBg = ref('#111111')
const undoStack = ref([])
const redoStack = ref([])
const snapEnabled = ref(true)
const widgets = ref([])
const imageAssets = ref([])
const showPreview = ref(false)
const saving = ref(false)
const legacyMode = ref(false)
const leftTab = ref('elements')

const canvasArea = ref(null)
const canvasEl = ref(null)
const canvasScale = ref(0.5)

const templates = DESIGNER_TEMPLATES
const bgSwatches = ['#000000', '#111111', '#1a1d27', '#0f2744', '#1a2a1a', '#1a0a2e', '#ffffff', '#f4f1ea']

const selected = computed(() => elements.value.find(e => e.id === selectedId.value) || null)
const selectedWidgetDef = computed(() => {
  if (selected.value?.type !== 'widget') return null
  return widgets.value.find(w => w.id === selected.value.props.widgetId) || null
})

// ─── Element factory ─────────────────────────────────────
let elIdCounter = 1
function nextId() { return `el-${Date.now()}-${elIdCounter++}` }

function addElement(type, opts = {}) {
  pushUndo()
  const base = {
    id: nextId(),
    type,
    x: 25, y: 40, w: 50, h: 20,
    opacity: 1,
    props: {},
  }
  if (type === 'text') {
    if (opts.variant === 'heading') {
      Object.assign(base, { x: 10, y: 35, w: 80, h: 20 })
      base.props = { text: 'Heading Text', fontSize: 96, color: '#ffffff', fontWeight: 700, align: 'center', fontFamily: 'sans-serif' }
    } else {
      Object.assign(base, { x: 15, y: 55, w: 70, h: 12 })
      base.props = { text: 'Body text goes here', fontSize: 48, color: '#ffffff', fontWeight: 400, align: 'center', fontFamily: 'sans-serif' }
    }
  } else if (type === 'image') {
    Object.assign(base, { x: 25, y: 25, w: 50, h: 50 })
    base.props = { assetId: imageAssets.value[0]?.id || null, fit: 'cover' }
  } else if (type === 'shape') {
    const shape = opts.shape || 'rect'
    if (shape === 'divider') {
      Object.assign(base, { x: 10, y: 50, w: 80, h: 0.8 })
    } else if (shape === 'circle') {
      Object.assign(base, { x: 35, y: 30, w: 30, h: 30 * (16 / 9) })
    } else {
      Object.assign(base, { x: 25, y: 30, w: 50, h: 30 })
    }
    base.props = { shape, fill: '#7c83ff', borderRadius: 0 }
  } else if (type === 'widget') {
    const widgetId = opts.widgetId || widgets.value[0]?.id || 'clock'
    Object.assign(base, { x: 25, y: 30, w: 50, h: 30 })
    base.props = { widgetId, params: {} }
  }
  elements.value.push(base)
  selectedId.value = base.id
}

function elementLabel(el) {
  if (el.type === 'text') return el.props.text?.slice(0, 30) || 'Text'
  if (el.type === 'image') {
    const img = imageAssets.value.find(i => i.id === el.props.assetId)
    return img ? `Image: ${img.name}` : 'Image (none picked)'
  }
  if (el.type === 'shape') return `${el.props.shape || 'shape'}`
  if (el.type === 'widget') {
    const w = widgets.value.find(x => x.id === el.props.widgetId)
    return w ? `${w.name} widget` : 'Widget'
  }
  return el.type
}

function elementIcon(el) {
  if (el.type === 'text') return 'pi pi-align-left'
  if (el.type === 'image') return 'pi pi-image'
  if (el.type === 'shape') {
    if (el.props.shape === 'circle') return 'pi pi-circle'
    if (el.props.shape === 'divider') return 'pi pi-minus'
    return 'pi pi-stop'
  }
  if (el.type === 'widget') return widgetIcon(el.props.widgetId)
  return 'pi pi-box'
}

function widgetIcon(id) {
  const icons = {
    clock: 'pi pi-clock',
    date: 'pi pi-calendar',
    weather: 'pi pi-cloud',
    centered_text: 'pi pi-align-center',
    heading_subtitle: 'pi pi-bars',
    scrolling_text: 'pi pi-arrows-h',
    countdown: 'pi pi-hourglass',
  }
  return icons[id] || 'pi pi-box'
}

// ─── Selection / canvas mouse ────────────────────────────
function onCanvasMouseDown(e) {
  if (e.target === canvasEl.value || e.target.classList.contains('canvas-empty')) {
    selectedId.value = null
  }
}

function elementStyle(el, idx) {
  return {
    left: el.x + '%',
    top: el.y + '%',
    width: el.w + '%',
    height: el.h + '%',
    opacity: el.opacity,
    zIndex: idx + 1,
  }
}

const canvasFrameStyle = computed(() => ({
  width: 1920 * canvasScale.value + 'px',
  height: 1080 * canvasScale.value + 'px',
}))

function fitCanvas() {
  if (!canvasArea.value) return
  const rect = canvasArea.value.getBoundingClientRect()
  const padding = 32
  const sx = (rect.width - padding * 2) / 1920
  const sy = (rect.height - padding * 2) / 1080
  canvasScale.value = Math.max(0.1, Math.min(sx, sy))
}

// ─── Drag / resize ───────────────────────────────────────
const dragState = ref(null)

function getCanvasRect() {
  return canvasEl.value.getBoundingClientRect()
}

function startDrag(e, el) {
  selectedId.value = el.id
  const rect = getCanvasRect()
  dragState.value = {
    mode: 'move',
    elId: el.id,
    startX: e.clientX,
    startY: e.clientY,
    origX: el.x,
    origY: el.y,
    rectW: rect.width,
    rectH: rect.height,
    moved: false,
    preSnapshot: snapshot(),
  }
}

function startResize(e, el, corner) {
  selectedId.value = el.id
  const rect = getCanvasRect()
  dragState.value = {
    mode: 'resize',
    corner,
    elId: el.id,
    startX: e.clientX,
    startY: e.clientY,
    origX: el.x,
    origY: el.y,
    origW: el.w,
    origH: el.h,
    rectW: rect.width,
    rectH: rect.height,
    moved: false,
    preSnapshot: snapshot(),
  }
}

function onWindowMouseMove(e) {
  const ds = dragState.value
  if (!ds) return
  const el = elements.value.find(x => x.id === ds.elId)
  if (!el) return
  const dxPct = ((e.clientX - ds.startX) / ds.rectW) * 100
  const dyPct = ((e.clientY - ds.startY) / ds.rectH) * 100
  ds.moved = true

  if (ds.mode === 'move') {
    let nx = ds.origX + dxPct
    let ny = ds.origY + dyPct
    if (snapEnabled.value) { nx = Math.round(nx); ny = Math.round(ny) }
    el.x = clamp(nx, -50, 100)
    el.y = clamp(ny, -50, 100)
  } else if (ds.mode === 'resize') {
    let nx = ds.origX, ny = ds.origY, nw = ds.origW, nh = ds.origH
    if (ds.corner.includes('e')) nw = ds.origW + dxPct
    if (ds.corner.includes('s')) nh = ds.origH + dyPct
    if (ds.corner.includes('w')) { nw = ds.origW - dxPct; nx = ds.origX + dxPct }
    if (ds.corner.includes('n')) { nh = ds.origH - dyPct; ny = ds.origY + dyPct }
    if (snapEnabled.value) {
      nx = Math.round(nx); ny = Math.round(ny)
      nw = Math.round(nw); nh = Math.round(nh)
    }
    el.w = Math.max(0.5, nw)
    el.h = Math.max(0.5, nh)
    el.x = nx
    el.y = ny
  }
}

function onWindowMouseUp() {
  if (dragState.value && dragState.value.moved && dragState.value.preSnapshot) {
    // Commit the pre-drag snapshot to the undo stack so undo restores the prior position
    undoStack.value.push(dragState.value.preSnapshot)
    if (undoStack.value.length > MAX_UNDO) undoStack.value.shift()
    redoStack.value = []
  }
  dragState.value = null
}

function clamp(v, lo, hi) { return Math.max(lo, Math.min(hi, v)) }

// ─── Undo / redo ─────────────────────────────────────────
const MAX_UNDO = 50
function snapshot() {
  return JSON.stringify({ elements: elements.value, canvasBg: canvasBg.value })
}
function pushUndo() {
  undoStack.value.push(snapshot())
  if (undoStack.value.length > MAX_UNDO) undoStack.value.shift()
  redoStack.value = []
}
function undo() {
  if (!undoStack.value.length) return
  redoStack.value.push(snapshot())
  applySnapshot(undoStack.value.pop())
}
function redo() {
  if (!redoStack.value.length) return
  undoStack.value.push(snapshot())
  applySnapshot(redoStack.value.pop())
}
function applySnapshot(s) {
  const data = JSON.parse(s)
  elements.value = data.elements
  canvasBg.value = data.canvasBg
  if (!elements.value.find(e => e.id === selectedId.value)) {
    selectedId.value = null
  }
}

// Capture snapshot when a user starts editing a field, not after the change
let pendingFieldSnapshot = null
function onPropFocus() {
  pendingFieldSnapshot = snapshot()
}
function onPropChange() {
  if (pendingFieldSnapshot && pendingFieldSnapshot !== snapshot()) {
    undoStack.value.push(pendingFieldSnapshot)
    if (undoStack.value.length > MAX_UNDO) undoStack.value.shift()
    redoStack.value = []
  }
  pendingFieldSnapshot = null
}

function setCanvasBg(c) {
  if (canvasBg.value === c) return
  pushUndo()
  canvasBg.value = c
}

// ─── Element actions ─────────────────────────────────────
function duplicateSelected() {
  if (!selected.value) return
  pushUndo()
  const copy = JSON.parse(JSON.stringify(selected.value))
  copy.id = nextId()
  copy.x = Math.min(95, copy.x + 3)
  copy.y = Math.min(95, copy.y + 3)
  elements.value.push(copy)
  selectedId.value = copy.id
}

function deleteSelected() {
  if (!selected.value) return
  pushUndo()
  elements.value = elements.value.filter(e => e.id !== selectedId.value)
  selectedId.value = null
}

function moveLayer(id, dir) {
  // dir: -1 = up (later in array = on top), +1 = down
  // Layers list is reversed, so up in list = +1 in array
  pushUndo()
  const idx = elements.value.findIndex(e => e.id === id)
  if (idx === -1) return
  const target = idx + (dir === -1 ? 1 : -1)
  if (target < 0 || target >= elements.value.length) return
  const arr = elements.value
  ;[arr[idx], arr[target]] = [arr[target], arr[idx]]
}

// ─── Widget params helpers ───────────────────────────────
function getWidgetParam(param) {
  const stored = selected.value?.props?.params?.[param.name]
  return stored !== undefined ? stored : param.default
}

function setWidgetParam(param, value) {
  if (!selected.value) return
  pushUndo()
  if (!selected.value.props.params) selected.value.props.params = {}
  selected.value.props.params[param.name] = value
}

function onWidgetChange() {
  // Reset params when widget changes (snapshot already pushed via @focus)
  if (selected.value) {
    selected.value.props.params = {}
  }
}

// ─── Templates ───────────────────────────────────────────
function loadTemplate(t) {
  pushUndo()
  // Deep clone so re-loading the same template behaves correctly
  const clone = JSON.parse(JSON.stringify(t.design))
  canvasBg.value = clone.canvas?.background || '#111111'
  elements.value = (clone.elements || []).map(el => ({ ...el, id: nextId() }))
  selectedId.value = null
  leftTab.value = 'elements'
}

// ─── Render to HTML ──────────────────────────────────────
function escapeHtml(s) {
  return String(s ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

function escapeAttr(s) {
  return escapeHtml(s)
}

// Mirror server-side _safe_value: strip chars that could break out of CSS/JS values.
function safeValue(val) {
  let s = String(val)
  s = s.replace(/\\/g, '\\\\').replace(/'/g, "\\'")
  s = s.replace(/<\//g, '<\\/')
  s = s.replace(/;/g, '').replace(/\{/g, '').replace(/\}/g, '')
  return s
}

function pxToVmin(px) {
  return Math.round((px / 1080) * 100 * 10) / 10
}

function renderWidgetHtml(el) {
  const w = widgets.value.find(x => x.id === el.props.widgetId)
  if (!w) return ''
  // Use the raw template if exposed, otherwise fall back to the rendered default html.
  const tpl = w.template || w.html
  let html = tpl
  const values = {}
  for (const p of w.params) {
    values[p.name] = el.props.params?.[p.name] !== undefined ? el.props.params[p.name] : p.default
  }
  for (const [key, val] of Object.entries(values)) {
    let replacement
    if (typeof val === 'boolean') {
      replacement = val ? 'true' : 'false'
    } else {
      replacement = safeValue(val)
    }
    html = html.split('{{' + key + '}}').join(replacement)
  }
  return html
}

function renderElementPreview(el) {
  // Lightweight preview render for the canvas (synchronous, no scripts)
  if (el.type === 'text') {
    const p = el.props
    const fs = pxToVmin(p.fontSize) + 'vmin'
    const style = `width:100%;height:100%;display:flex;align-items:center;justify-content:${p.align === 'left' ? 'flex-start' : p.align === 'right' ? 'flex-end' : 'center'};color:${p.color};font-size:${fs};font-weight:${p.fontWeight};text-align:${p.align};font-family:${p.fontFamily};line-height:1.2;padding:0 2%;overflow:hidden;`
    return `<div style="${style}">${escapeHtml(p.text || '')}</div>`
  }
  if (el.type === 'image') {
    const img = imageAssets.value.find(i => i.id === el.props.assetId)
    if (!img) {
      return `<div style="width:100%;height:100%;display:flex;align-items:center;justify-content:center;background:#252836;color:#666;font-size:0.8rem;border:1px dashed #444;">No image picked</div>`
    }
    return `<img src="/media/${escapeAttr(img.uri)}" style="width:100%;height:100%;object-fit:${el.props.fit};display:block;" />`
  }
  if (el.type === 'shape') {
    const p = el.props
    const radius = p.shape === 'circle' ? '50%' : (p.borderRadius || 0) + 'px'
    return `<div style="width:100%;height:100%;background:${p.fill};border-radius:${radius};"></div>`
  }
  if (el.type === 'widget') {
    const w = widgets.value.find(x => x.id === el.props.widgetId)
    if (!w) return `<div style="width:100%;height:100%;background:#252836;color:#666;display:flex;align-items:center;justify-content:center;font-size:0.7rem;">Pick a widget</div>`
    // Show a static placeholder in the canvas to keep things light; live preview is in the Preview overlay.
    return `<div style="width:100%;height:100%;background:rgba(108,184,230,0.08);border:1px dashed rgba(108,184,230,0.4);color:#6cb8e6;display:flex;align-items:center;justify-content:center;font-size:0.85rem;text-align:center;padding:4px;"><div><i class="${widgetIcon(w.id)}" style="font-size:1.2rem;display:block;margin-bottom:0.2rem;"></i>${escapeHtml(w.name)}</div></div>`
  }
  return ''
}

function renderElementHtml(el) {
  const baseStyle = `position:absolute;left:${el.x}%;top:${el.y}%;width:${el.w}%;height:${el.h}%;opacity:${el.opacity};box-sizing:border-box;`
  if (el.type === 'text') {
    const p = el.props
    const fs = pxToVmin(p.fontSize) + 'vmin'
    const style = baseStyle + `display:flex;align-items:center;justify-content:${p.align === 'left' ? 'flex-start' : p.align === 'right' ? 'flex-end' : 'center'};color:${p.color};font-size:${fs};font-weight:${p.fontWeight};text-align:${p.align};font-family:${p.fontFamily};line-height:1.2;padding:0 2%;overflow:hidden;`
    return `<div style="${style}">${escapeHtml(p.text || '')}</div>`
  }
  if (el.type === 'image') {
    const img = imageAssets.value.find(i => i.id === el.props.assetId)
    if (!img) return ''
    return `<img src="/media/${escapeAttr(img.uri)}" style="${baseStyle}object-fit:${el.props.fit};display:block;" />`
  }
  if (el.type === 'shape') {
    const p = el.props
    const radius = p.shape === 'circle' ? '50%' : (p.borderRadius || 0) + 'px'
    return `<div style="${baseStyle}background:${p.fill};border-radius:${radius};"></div>`
  }
  if (el.type === 'widget') {
    const widgetHtml = renderWidgetHtml(el)
    if (!widgetHtml) return ''
    return `<iframe sandbox="allow-scripts" srcdoc="${escapeAttr(widgetHtml)}" style="${baseStyle}border:none;background:transparent;"></iframe>`
  }
  return ''
}

function renderHtml() {
  const body = elements.value.map(renderElementHtml).join('\n')
  return `<!DOCTYPE html><html><head><meta charset="UTF-8"><style>
html,body{margin:0;padding:0;width:100%;height:100%;overflow:hidden;background:${canvasBg.value};font-family:system-ui,sans-serif;}
</style></head><body>${body}</body></html>`
}

const previewHtml = computed(() => renderHtml())

// ─── Save / load ─────────────────────────────────────────
async function save() {
  const html = renderHtml()
  const designSourceObj = {
    version: 1,
    canvas: { background: canvasBg.value },
    elements: elements.value,
  }
  const designSource = JSON.stringify(designSourceObj)
  saving.value = true
  try {
    if (editingAssetId.value) {
      await api.patch(`/assets/${editingAssetId.value}`, {
        name: slideName.value,
        content: html,
        design_source: designSource,
      })
    } else {
      const fd = new FormData()
      fd.append('asset_type', 'html')
      fd.append('name', slideName.value)
      fd.append('content', html)
      fd.append('design_source', designSource)
      const created = await api.post('/assets', fd)
      editingAssetId.value = created.id
      router.replace(`/designer/${created.id}`)
    }
  } finally {
    saving.value = false
  }
}

async function loadAsset(id) {
  const asset = await api.get(`/assets/${id}`)
  slideName.value = asset.name
  editingAssetId.value = asset.id
  if (asset.design_source) {
    const ds = typeof asset.design_source === 'string' ? JSON.parse(asset.design_source) : asset.design_source
    canvasBg.value = ds.canvas?.background || '#111111'
    elements.value = ds.elements || []
    legacyMode.value = false
  } else {
    legacyMode.value = true
  }
}

function openInRawEditor() {
  router.push({ path: '/media', query: { editHtml: editingAssetId.value } })
}

function exit() {
  router.push('/media')
}

// ─── Lifecycle ───────────────────────────────────────────
async function loadWidgets() {
  try {
    widgets.value = await api.get('/widgets')
  } catch (err) {
    console.warn('[PageDesigner] Failed to load widgets:', err)
    widgets.value = []
  }
}

async function loadImageAssets() {
  try {
    const all = await api.get('/assets')
    imageAssets.value = all.filter(a => a.asset_type === 'image')
  } catch (err) {
    console.warn('[PageDesigner] Failed to load image assets:', err)
    imageAssets.value = []
  }
}

function onKeyDown(e) {
  if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.tagName === 'SELECT') return
  if (e.key === 'Escape') {
    if (showPreview.value) showPreview.value = false
    else selectedId.value = null
    return
  }
  if ((e.key === 'Delete' || e.key === 'Backspace') && selected.value) {
    e.preventDefault()
    deleteSelected()
    return
  }
  if (e.ctrlKey || e.metaKey) {
    if (e.key === 'z') { e.preventDefault(); undo() }
    else if (e.key === 'y') { e.preventDefault(); redo() }
    else if (e.key === 'd' && selected.value) { e.preventDefault(); duplicateSelected() }
  }
}

function onWindowResize() {
  fitCanvas()
}

onMounted(async () => {
  // Push initial empty snapshot so undo can return to start
  await Promise.all([loadWidgets(), loadImageAssets()])
  if (route.params.assetId) {
    try {
      await loadAsset(route.params.assetId)
    } catch (err) {
      console.warn('[PageDesigner] Failed to load asset:', err)
      router.replace('/media')
      return
    }
  }
  await nextTick()
  fitCanvas()
  window.addEventListener('mousemove', onWindowMouseMove)
  window.addEventListener('mouseup', onWindowMouseUp)
  window.addEventListener('keydown', onKeyDown)
  window.addEventListener('resize', onWindowResize)
})

onUnmounted(() => {
  window.removeEventListener('mousemove', onWindowMouseMove)
  window.removeEventListener('mouseup', onWindowMouseUp)
  window.removeEventListener('keydown', onKeyDown)
  window.removeEventListener('resize', onWindowResize)
})
</script>

<style scoped>
.designer {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 0px);
  margin: -1.5rem -2rem;
  background: #0f1117;
  color: #ddd;
}

/* ─── Topbar ─── */
.topbar {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.6rem 1rem;
  background: #1a1d27;
  border-bottom: 1px solid #2a2d3a;
  flex-shrink: 0;
}

.name-input {
  background: #0f1117;
  border: 1px solid #2a2d3a;
  color: #eee;
  padding: 0.45rem 0.7rem;
  border-radius: 6px;
  font-size: 0.9rem;
  outline: none;
  width: 240px;
}
.name-input:focus { border-color: #7c83ff; }

.topbar-spacer { flex: 1; }

.tb-btn {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  background: #252836;
  border: 1px solid #2a2d3a;
  color: #ccc;
  padding: 0.45rem 0.75rem;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.85rem;
  transition: background 0.15s, border-color 0.15s;
}
.tb-btn:hover:not(:disabled) { background: #2a2d3a; color: #fff; }
.tb-btn:disabled { opacity: 0.4; cursor: default; }
.tb-btn.primary { background: #7c83ff; border-color: #7c83ff; color: #fff; }
.tb-btn.primary:hover:not(:disabled) { background: #6b72e8; }
.tb-btn.secondary { background: #252836; }

.tb-toggle {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  color: #ccc;
  font-size: 0.8rem;
  user-select: none;
  cursor: pointer;
}
.tb-toggle input { accent-color: #7c83ff; }

.legacy-banner {
  background: #3a3220;
  color: #f5d273;
  padding: 0.6rem 1rem;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.85rem;
  border-bottom: 1px solid #4a4230;
}
.link-btn {
  background: none; border: none; color: #7c83ff; cursor: pointer;
  text-decoration: underline; font-size: 0.85rem; padding: 0;
}

/* ─── Main 3-col layout ─── */
.main-area {
  display: flex;
  flex: 1;
  min-height: 0;
}

.palette {
  width: 240px;
  background: #1a1d27;
  border-right: 1px solid #2a2d3a;
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  overflow: hidden;
}

.palette-tabs {
  display: flex;
  border-bottom: 1px solid #2a2d3a;
}
.palette-tabs button {
  flex: 1;
  background: none;
  border: none;
  color: #888;
  padding: 0.7rem 0.5rem;
  cursor: pointer;
  font-size: 0.8rem;
  border-bottom: 2px solid transparent;
  transition: color 0.15s, border-color 0.15s;
}
.palette-tabs button:hover { color: #ccc; }
.palette-tabs button.active { color: #7c83ff; border-bottom-color: #7c83ff; }

.palette-body {
  flex: 1;
  overflow-y: auto;
  padding: 0.75rem;
}
.palette-section-title {
  font-size: 0.7rem;
  text-transform: uppercase;
  color: #666;
  letter-spacing: 0.5px;
  margin: 0.75rem 0 0.4rem;
}
.palette-section-title:first-child { margin-top: 0; }
.palette-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.4rem;
}
.palette-tile {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.25rem;
  background: #252836;
  border: 1px solid #2a2d3a;
  color: #ccc;
  padding: 0.6rem 0.4rem;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.7rem;
  transition: background 0.15s, border-color 0.15s;
}
.palette-tile:hover { background: #2a2d3a; border-color: #7c83ff; color: #fff; }
.palette-tile i { font-size: 1rem; color: #7c83ff; }

.palette-empty, .palette-hint {
  color: #666;
  font-size: 0.75rem;
  text-align: center;
  padding: 0.4rem 0;
}
.palette-hint { text-align: left; }

.bg-row {
  display: flex;
  flex-wrap: wrap;
  gap: 0.3rem;
  align-items: center;
}
.bg-swatch {
  width: 24px; height: 24px;
  border-radius: 4px;
  border: 2px solid #2a2d3a;
  cursor: pointer;
  padding: 0;
}
.bg-swatch:hover { border-color: #7c83ff; }
.bg-swatch.active { border-color: #7c83ff; box-shadow: 0 0 0 2px rgba(124,131,255,0.3); }
.bg-color-input {
  width: 28px; height: 28px;
  border: 1px solid #2a2d3a;
  border-radius: 4px;
  background: none;
  cursor: pointer;
  padding: 1px;
}

.template-list {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}
.template-card {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  background: #252836;
  border: 1px solid #2a2d3a;
  color: #ccc;
  padding: 0.6rem 0.7rem;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.85rem;
  text-align: left;
  transition: background 0.15s, border-color 0.15s;
}
.template-card:hover { background: #2a2d3a; border-color: #7c83ff; color: #fff; }
.template-card i { color: #7c83ff; font-size: 1rem; }

.layer-list {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
}
.layer-row {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.4rem 0.5rem;
  background: #252836;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.75rem;
  border: 1px solid transparent;
}
.layer-row:hover { background: #2a2d3a; }
.layer-row.active { border-color: #7c83ff; background: #2a2d3a; color: #fff; }
.layer-row i { color: #7c83ff; }
.layer-label {
  flex: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.layer-action {
  background: none;
  border: none;
  color: #888;
  cursor: pointer;
  padding: 0.15rem;
  font-size: 0.7rem;
}
.layer-action:hover { color: #fff; }

/* ─── Canvas area ─── */
.canvas-area {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #0a0b10;
  overflow: hidden;
  min-width: 0;
}
.canvas-frame {
  position: relative;
  box-shadow: 0 8px 32px rgba(0,0,0,0.5);
}
.canvas {
  position: absolute;
  inset: 0;
  overflow: hidden;
  user-select: none;
}
.canvas-empty {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #555;
  font-size: 1rem;
  pointer-events: none;
}
.canvas-el {
  position: absolute;
  cursor: move;
}
.canvas-el.selected {
  outline: 2px solid #7c83ff;
  outline-offset: 0;
}
.el-content {
  width: 100%;
  height: 100%;
  pointer-events: none;
}
.el-content :deep(*) {
  pointer-events: none;
}

.resize-handle {
  position: absolute;
  width: 12px;
  height: 12px;
  background: #7c83ff;
  border: 2px solid #fff;
  border-radius: 50%;
  z-index: 10;
}
.resize-handle.nw { top: -6px; left: -6px; cursor: nw-resize; }
.resize-handle.ne { top: -6px; right: -6px; cursor: ne-resize; }
.resize-handle.sw { bottom: -6px; left: -6px; cursor: sw-resize; }
.resize-handle.se { bottom: -6px; right: -6px; cursor: se-resize; }

/* ─── Properties panel ─── */
.props-panel {
  width: 300px;
  background: #1a1d27;
  border-left: 1px solid #2a2d3a;
  flex-shrink: 0;
  overflow-y: auto;
  padding: 1rem;
}
.props-empty {
  text-align: center;
  color: #555;
  margin-top: 3rem;
}
.props-empty i { font-size: 2rem; display: block; margin-bottom: 0.5rem; }
.props-empty p { font-size: 0.85rem; color: #666; }

.props-title {
  color: #fff;
  font-size: 0.95rem;
  margin-bottom: 0.75rem;
}

.props-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.5rem;
  margin-bottom: 0.5rem;
}

.prop-field {
  margin-bottom: 0.65rem;
}
.prop-field label {
  display: block;
  font-size: 0.7rem;
  color: #888;
  text-transform: uppercase;
  letter-spacing: 0.3px;
  margin-bottom: 0.2rem;
}
.prop-field input[type="text"],
.prop-field input[type="number"],
.prop-field select,
.prop-field textarea {
  width: 100%;
  background: #0f1117;
  border: 1px solid #2a2d3a;
  color: #eee;
  padding: 0.4rem 0.55rem;
  border-radius: 4px;
  font-size: 0.85rem;
  outline: none;
  font-family: inherit;
}
.prop-field textarea { resize: vertical; min-height: 60px; }
.prop-field input:focus, .prop-field select:focus, .prop-field textarea:focus { border-color: #7c83ff; }
.prop-field input[type="color"] {
  width: 100%;
  height: 32px;
  background: #0f1117;
  border: 1px solid #2a2d3a;
  border-radius: 4px;
  cursor: pointer;
  padding: 2px;
}
.prop-field input[type="range"] {
  width: 100%;
  accent-color: #7c83ff;
}
.prop-field input[type="checkbox"] {
  accent-color: #7c83ff;
  width: 16px; height: 16px;
}
.prop-value {
  font-size: 0.75rem;
  color: #888;
}

.props-sep {
  border: none;
  border-top: 1px solid #2a2d3a;
  margin: 0.75rem 0;
}

.form-hint {
  color: #666;
  font-size: 0.7rem;
  margin: 0.25rem 0 0;
}

.props-actions {
  display: flex;
  gap: 0.5rem;
}
.btn-secondary, .btn-danger {
  background: #252836;
  border: 1px solid #2a2d3a;
  color: #ccc;
  padding: 0.4rem 0.7rem;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.8rem;
  display: flex;
  align-items: center;
  gap: 0.3rem;
  flex: 1;
  justify-content: center;
}
.btn-secondary:hover { background: #2a2d3a; color: #fff; }
.btn-danger { background: #5a2030; color: #f88; border-color: #6a2840; }
.btn-danger:hover { background: #7a2840; }

.widget-params {
  margin-top: 0.5rem;
  padding-top: 0.5rem;
  border-top: 1px solid #2a2d3a;
}

/* ─── Preview overlay ─── */
.preview-overlay {
  position: fixed;
  inset: 0;
  background: #000;
  z-index: 2000;
  display: flex;
  align-items: center;
  justify-content: center;
}
.preview-iframe {
  width: 100%;
  height: 100%;
  border: none;
  background: #000;
}
.preview-close {
  position: absolute;
  top: 1rem;
  right: 1rem;
  width: 40px;
  height: 40px;
  background: rgba(255,255,255,0.1);
  border: 1px solid rgba(255,255,255,0.2);
  color: #fff;
  border-radius: 50%;
  cursor: pointer;
  font-size: 1rem;
  z-index: 2001;
}
.preview-close:hover { background: rgba(255,255,255,0.2); }
</style>
