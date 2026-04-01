<template>
  <div>
    <div class="header-row">
      <h2>Media Library</h2>
      <button v-if="canEdit" class="tag-mgmt-btn" @click="showTagManager = true" title="Manage tags">
        <i class="pi pi-tags"></i> Tags
      </button>
    </div>

    <!-- Tag filter bar -->
    <div v-if="tags.length > 0" class="tag-filter-bar">
      <button
        class="tag-chip"
        :class="{ active: !activeTagFilter }"
        @click="activeTagFilter = null"
      >All</button>
      <button
        v-for="t in tags"
        :key="t.id"
        class="tag-chip"
        :class="{ active: activeTagFilter === t.id }"
        :style="activeTagFilter === t.id ? { background: t.color + '33', borderColor: t.color, color: t.color } : {}"
        @click="activeTagFilter = t.id"
      >
        <span class="tag-dot" :style="{ background: t.color }"></span>
        {{ t.name }}
        <span class="tag-count">{{ t.asset_count }}</span>
      </button>
    </div>

    <div v-if="canEdit" class="action-area">
      <div class="upload-row">
        <UploadZone @uploaded="loadAssets" />
        <div class="action-side">
          <button class="btn-html-add" @click="openHtmlEditor()" title="Create custom slides — clocks, weather, scrolling text &amp; more">
            <i class="pi pi-code"></i> Add Custom Slide
          </button>
          <label class="auto-add-toggle" v-tooltip.bottom="'When on, uploads, custom slides, and duplicates are automatically added to your default playlist.'">
            <input type="checkbox" v-model="autoAdd" @change="saveAutoAdd" />
            Add to default playlist
            <i class="pi pi-info-circle auto-add-info"></i>
          </label>
        </div>
      </div>
      <p class="form-hint upload-hint">Large video files may take longer to load on the player.</p>
    </div>

    <div v-if="assets.length === 0" class="empty">
      <p v-if="activeTagFilter">No assets with this tag.</p>
      <p v-else>No media yet. Upload images and videos to use in your playlists. Drag files here or click Upload.</p>
    </div>

    <div v-else class="asset-grid">
      <AssetCard
        v-for="asset in assets"
        :key="asset.id"
        :asset="asset"
        :all-tags="tags"
        @updated="loadAssets"
        @replace="replaceAsset"
        @duplicate="duplicateAsset"
        @delete="deleteAsset"
        @tag-changed="loadAll"
        @edit-html="openHtmlEditor"
      />
    </div>

    <!-- Hidden file input for replace -->
    <input
      ref="replaceInput"
      type="file"
      accept="image/*,video/mp4,video/webm"
      hidden
      @change="onReplaceFile"
    />

    <!-- Tag Manager Dialog -->
    <div v-if="showTagManager" class="dialog-overlay" @click.self="showTagManager = false">
      <div class="dialog">
        <div class="dialog-header">
          <h3>Manage Tags</h3>
          <button class="close-btn" @click="showTagManager = false"><i class="pi pi-times"></i></button>
        </div>
        <div class="dialog-body">
          <!-- Create new tag -->
          <div class="new-tag-row">
            <input
              v-model="newTagName"
              placeholder="New tag name"
              class="tag-input"
              @keydown.enter="createTag"
            />
            <input v-model="newTagColor" type="color" class="color-input" />
            <button class="btn-primary" @click="createTag" :disabled="!newTagName.trim()">Add</button>
          </div>
          <!-- Tag list -->
          <div v-if="tags.length === 0" class="empty-tags">No tags yet</div>
          <div v-else class="tag-list">
            <div v-for="t in tags" :key="t.id" class="tag-row">
              <span class="tag-dot" :style="{ background: t.color }"></span>
              <span v-if="editingTag !== t.id" class="tag-name">{{ t.name }}</span>
              <input
                v-else
                v-model="editTagName"
                class="tag-input sm"
                @keydown.enter="saveTag(t)"
                @keydown.escape="editingTag = null"
              />
              <input
                v-if="editingTag === t.id"
                v-model="editTagColor"
                type="color"
                class="color-input"
              />
              <span class="tag-count-label">{{ t.asset_count }} assets</span>
              <div class="tag-actions">
                <button v-if="editingTag !== t.id" @click="startEditTag(t)" title="Edit"><i class="pi pi-pencil"></i></button>
                <button v-if="editingTag === t.id" @click="saveTag(t)" title="Save"><i class="pi pi-check"></i></button>
                <button v-if="editingTag === t.id" @click="editingTag = null" title="Cancel"><i class="pi pi-times"></i></button>
                <button @click="deleteTag(t)" title="Delete" class="danger"><i class="pi pi-trash"></i></button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- HTML Editor Dialog -->
    <div v-if="showHtmlEditor" class="dialog-overlay" @click.self="closeHtmlEditor">
      <div class="dialog html-editor-dialog">
        <div class="dialog-header">
          <h3>{{ htmlEditTarget ? 'Edit Custom Slide' : 'New Custom Slide' }}</h3>
          <button class="close-btn" @click="closeHtmlEditor"><i class="pi pi-times"></i></button>
        </div>
        <div class="dialog-body html-editor-body">
          <div class="html-name-row">
            <label>Name</label>
            <input v-model="htmlName" class="tag-input" placeholder="My Custom Slide" />
          </div>
          <!-- Widget picker -->
          <div v-if="!htmlEditTarget && widgets.length" class="widget-picker">
            <label class="html-editor-label">Insert Widget</label>
            <div class="widget-buttons">
              <button
                v-for="w in widgets"
                :key="w.id"
                class="widget-btn"
                @click="insertWidget(w)"
                :title="w.description"
              >
                <i :class="widgetIcon(w.id)"></i>
                {{ w.name }}
              </button>
            </div>
          </div>
          <label class="html-editor-label">HTML / CSS Content</label>
          <textarea
            v-model="htmlContent"
            class="html-editor-textarea"
            spellcheck="false"
            placeholder="<div style='text-align:center; color:white; font-size:3rem;'>Hello World</div>"
          ></textarea>
          <div class="html-editor-footer">
            <span class="html-size-hint">{{ htmlContentSize }}</span>
            <div class="html-editor-actions">
              <button class="btn-secondary" @click="closeHtmlEditor">Cancel</button>
              <button class="btn-primary" @click="saveHtmlAsset" :disabled="htmlSaving || !htmlContent.trim()">
                {{ htmlSaving ? 'Saving...' : (htmlEditTarget ? 'Update' : 'Create') }}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Delete confirmation -->
    <div v-if="deleteTarget" class="dialog-overlay" @click.self="deleteTarget = null">
      <div class="dialog" style="padding: 1.5rem;">
        <h3>{{ deleteTarget.type === 'asset' ? 'Delete Media' : 'Delete Tag' }}</h3>
        <p v-if="deleteTarget.type === 'asset'">
          Delete <strong>{{ deleteTarget.name }}</strong>? It will be removed from any playlists that currently use it.
        </p>
        <p v-else>
          Delete tag <strong>{{ deleteTarget.name }}</strong>? It will be removed from all assets.
        </p>
        <div class="dialog-actions">
          <button class="btn-secondary" @click="deleteTarget = null">Cancel</button>
          <button class="btn-danger" @click="doDelete">Delete</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { api } from '../api/client.js'
import UploadZone from '../components/UploadZone.vue'
import AssetCard from '../components/AssetCard.vue'

const userRole = (() => { try { return JSON.parse(localStorage.getItem('tinysignage_user') || '{}').role } catch { return 'viewer' } })()
const canEdit = ['admin', 'editor'].includes(userRole)

const assets = ref([])
const tags = ref([])
const activeTagFilter = ref(null)
const replaceInput = ref(null)
const replaceTarget = ref(null)

// Tag manager state
const showTagManager = ref(false)
const newTagName = ref('')
const newTagColor = ref('#7c83ff')
const editingTag = ref(null)
const editTagName = ref('')
const editTagColor = ref('#7c83ff')

const deleteTarget = ref(null)

// Auto-add to playlist toggle
const autoAdd = ref(true)

// Widget state
const widgets = ref([])

// HTML editor state
const showHtmlEditor = ref(false)
const htmlEditTarget = ref(null)
const htmlName = ref('')
const htmlContent = ref('')
const htmlSaving = ref(false)

const htmlContentSize = computed(() => {
  const bytes = new TextEncoder().encode(htmlContent.value).length
  if (bytes < 1024) return `${bytes} B`
  return `${(bytes / 1024).toFixed(1)} KB / 64 KB`
})

async function loadTags() {
  tags.value = await api.get('/tags')
}

async function loadAssets() {
  const params = activeTagFilter.value ? `?tag=${activeTagFilter.value}` : ''
  assets.value = await api.get(`/assets${params}`)
}

async function loadAll() {
  await Promise.all([loadTags(), loadAssets()])
}

watch(activeTagFilter, loadAssets)

function replaceAsset(asset) {
  replaceTarget.value = asset
  replaceInput.value.click()
}

async function onReplaceFile(e) {
  const file = e.target.files?.[0]
  if (!file || !replaceTarget.value) return

  const formData = new FormData()
  formData.append('file', file)

  await api.put(`/assets/${replaceTarget.value.id}/replace`, formData)
  replaceTarget.value = null
  e.target.value = ''
  await loadAssets()
}

async function duplicateAsset(asset) {
  await api.post(`/assets/${asset.id}/duplicate`)
  await loadAssets()
}

function deleteAsset(asset) {
  deleteTarget.value = { ...asset, type: 'asset' }
}

// Tag manager actions
async function createTag() {
  const name = newTagName.value.trim()
  if (!name) return
  await api.post('/tags', { name, color: newTagColor.value })
  newTagName.value = ''
  newTagColor.value = '#7c83ff'
  await loadTags()
}

function startEditTag(tag) {
  editingTag.value = tag.id
  editTagName.value = tag.name
  editTagColor.value = tag.color
}

async function saveTag(tag) {
  if (!editTagName.value.trim()) return
  await api.patch(`/tags/${tag.id}`, { name: editTagName.value.trim(), color: editTagColor.value })
  editingTag.value = null
  await loadTags()
}

function deleteTag(tag) {
  deleteTarget.value = { ...tag, type: 'tag' }
}

async function doDelete() {
  if (!deleteTarget.value) return
  const target = deleteTarget.value
  deleteTarget.value = null
  if (target.type === 'asset') {
    await api.delete(`/assets/${target.id}`)
  } else {
    await api.delete(`/tags/${target.id}`)
    if (activeTagFilter.value === target.id) activeTagFilter.value = null
  }
  await loadAll()
}

// HTML editor actions
async function openHtmlEditor(asset = null) {
  htmlEditTarget.value = asset
  if (asset) {
    htmlName.value = asset.name
    // Fetch existing HTML content
    try {
      const resp = await fetch(`/api/assets/${asset.id}/content`, {
        headers: { Authorization: `Bearer ${localStorage.getItem('tinysignage_token') || localStorage.getItem('tinysignage_admin_token')}` },
      })
      if (resp.ok) {
        htmlContent.value = await resp.text()
      }
    } catch (err) {
      console.warn('[MediaLibrary] Failed to load HTML content for asset:', asset.id, err)
      htmlContent.value = ''
    }
  } else {
    htmlName.value = ''
    htmlContent.value = ''
  }
  showHtmlEditor.value = true
}

function closeHtmlEditor() {
  showHtmlEditor.value = false
  htmlEditTarget.value = null
  htmlName.value = ''
  htmlContent.value = ''
}

async function saveHtmlAsset() {
  if (!htmlContent.value.trim()) return
  htmlSaving.value = true
  try {
    if (htmlEditTarget.value) {
      // Update existing
      const body = { content: htmlContent.value }
      if (htmlName.value.trim() && htmlName.value !== htmlEditTarget.value.name) {
        body.name = htmlName.value.trim()
      }
      await api.patch(`/assets/${htmlEditTarget.value.id}`, body)
    } else {
      // Create new — use FormData since the endpoint expects Form fields
      const formData = new FormData()
      formData.append('asset_type', 'html')
      formData.append('content', htmlContent.value)
      if (htmlName.value.trim()) {
        formData.append('name', htmlName.value.trim())
      }
      await api.post('/assets', formData)
    }
    closeHtmlEditor()
    await loadAssets()
  } finally {
    htmlSaving.value = false
  }
}

// Widget helpers
async function loadWidgets() {
  try {
    widgets.value = await api.get('/widgets')
  } catch (err) {
    console.warn('[MediaLibrary] Failed to load widgets:', err)
    widgets.value = []
  }
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

function insertWidget(w) {
  htmlContent.value = w.html
  if (!htmlName.value.trim()) {
    htmlName.value = w.name + ' Widget'
  }
}

async function loadAutoAdd() {
  try {
    const settings = await api.get('/settings')
    autoAdd.value = settings.auto_add_to_playlist
  } catch (err) {
    console.warn('[MediaLibrary] Failed to load auto-add setting:', err)
  }
}

async function saveAutoAdd() {
  try {
    await api.patch('/settings', { auto_add_to_playlist: autoAdd.value })
  } catch (err) {
    console.warn('[MediaLibrary] Failed to save auto-add setting:', err)
    autoAdd.value = !autoAdd.value // revert on failure
  }
}

onMounted(() => { loadAll(); loadWidgets(); loadAutoAdd() })
</script>

<style scoped>
h2 {
  margin-bottom: 0;
  color: #fff;
}

.header-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 1rem;
}

.tag-mgmt-btn {
  background: #252836;
  border: 1px solid #2a2d3a;
  color: #ccc;
  padding: 0.4rem 0.8rem;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.85rem;
  display: flex;
  align-items: center;
  gap: 0.4rem;
  transition: background 0.15s, color 0.15s;
}

.tag-mgmt-btn:hover {
  background: #2a2d3a;
  color: #fff;
}

.tag-filter-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
  margin-bottom: 1rem;
}

.tag-chip {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  background: #1a1d27;
  border: 1px solid #2a2d3a;
  color: #aaa;
  padding: 0.3rem 0.65rem;
  border-radius: 20px;
  cursor: pointer;
  font-size: 0.8rem;
  transition: all 0.15s;
}

.tag-chip:hover {
  border-color: #555;
  color: #ddd;
}

.tag-chip.active {
  background: #7c83ff22;
  border-color: #7c83ff;
  color: #7c83ff;
}

.tag-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.tag-count {
  font-size: 0.7rem;
  opacity: 0.6;
}

.empty {
  text-align: center;
  padding: 3rem;
  color: #666;
}

.asset-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 1rem;
}

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
  border-radius: 12px;
  border: 1px solid #2a2d3a;
  width: 460px;
  max-height: 80vh;
  display: flex;
  flex-direction: column;
}

.dialog-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1rem 1.2rem;
  border-bottom: 1px solid #2a2d3a;
}

.dialog-header h3 {
  color: #fff;
  font-size: 1rem;
}

.close-btn {
  background: none;
  border: none;
  color: #888;
  cursor: pointer;
  font-size: 0.9rem;
  padding: 0.3rem;
}

.close-btn:hover { color: #fff; }

.dialog-body {
  padding: 1rem 1.2rem;
  overflow-y: auto;
}

.new-tag-row {
  display: flex;
  gap: 0.5rem;
  margin-bottom: 1rem;
}

.tag-input {
  flex: 1;
  background: #0f1117;
  border: 1px solid #2a2d3a;
  color: #eee;
  padding: 0.45rem 0.6rem;
  border-radius: 6px;
  font-size: 0.85rem;
  outline: none;
}

.tag-input:focus { border-color: #7c83ff; }
.tag-input.sm { width: 120px; flex: unset; }

.color-input {
  width: 36px;
  height: 36px;
  border: 1px solid #2a2d3a;
  border-radius: 6px;
  background: #0f1117;
  cursor: pointer;
  padding: 2px;
}

.btn-primary {
  background: #7c83ff;
  border: none;
  color: #fff;
  padding: 0.45rem 1rem;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.85rem;
}

.btn-primary:hover { background: #6b72e8; }
.btn-primary:disabled { opacity: 0.4; cursor: default; }

.empty-tags {
  text-align: center;
  color: #666;
  padding: 1.5rem;
}

.tag-list {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
}

.tag-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.45rem 0.5rem;
  border-radius: 6px;
  transition: background 0.1s;
}

.tag-row:hover { background: #252836; }

.tag-name {
  color: #ddd;
  font-size: 0.85rem;
  flex: 1;
}

.tag-count-label {
  font-size: 0.75rem;
  color: #666;
  margin-right: 0.3rem;
}

.tag-actions {
  display: flex;
  gap: 0.2rem;
}

.tag-actions button {
  background: none;
  border: none;
  color: #888;
  cursor: pointer;
  padding: 0.25rem;
  border-radius: 4px;
  font-size: 0.8rem;
}

.tag-actions button:hover { color: #fff; background: #252836; }
.tag-actions button.danger:hover { color: #ef5350; background: #ef535022; }

/* Action area */
.action-area {
  margin-bottom: 1.5rem;
}

.upload-row {
  display: flex;
  align-items: stretch;
  gap: 0.75rem;
}

.upload-row > :first-child {
  flex: 1;
}

.action-side {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  justify-content: center;
}

.upload-hint {
  margin-top: 0.25rem;
  margin-bottom: 0;
}

.auto-add-toggle {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  color: #ccc;
  font-size: 0.8rem;
  cursor: pointer;
  white-space: nowrap;
}

.auto-add-toggle input[type="checkbox"] {
  accent-color: #7c83ff;
}

.auto-add-info {
  font-size: 0.75rem;
  color: #888;
  margin-left: 0.1rem;
}

.btn-html-add {
  background: #1a3a2a;
  border: 1px solid #2a5a3a;
  color: #4caf50;
  padding: 0.6rem 1rem;
  border-radius: 8px;
  cursor: pointer;
  font-size: 0.85rem;
  display: flex;
  align-items: center;
  gap: 0.4rem;
  white-space: nowrap;
  transition: background 0.15s, border-color 0.15s;
}

.btn-html-add:hover {
  background: #1f4a32;
  border-color: #4caf50;
}

/* HTML Editor Dialog */
.html-editor-dialog {
  width: 720px;
  max-width: 90vw;
  max-height: 85vh;
}

.html-editor-body {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  flex: 1;
  min-height: 0;
}

.html-name-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.html-name-row label {
  color: #888;
  font-size: 0.8rem;
  white-space: nowrap;
}

.html-name-row .tag-input {
  flex: 1;
}

.html-editor-label {
  color: #888;
  font-size: 0.8rem;
}

.html-editor-textarea {
  width: 100%;
  min-height: 180px;
  max-height: 50vh;
  flex: 1;
  background: #0f1117;
  border: 1px solid #2a2d3a;
  color: #e0e0e0;
  padding: 0.75rem;
  border-radius: 6px;
  font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
  font-size: 0.85rem;
  line-height: 1.5;
  resize: vertical;
  outline: none;
  tab-size: 2;
}

.html-editor-textarea:focus {
  border-color: #7c83ff;
}

.html-editor-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 0.25rem;
}

.html-size-hint {
  font-size: 0.75rem;
  color: #666;
  font-family: monospace;
}

.html-editor-actions {
  display: flex;
  gap: 0.5rem;
}

.btn-secondary {
  background: #252836;
  border: 1px solid #2a2d3a;
  color: #ccc;
  padding: 0.45rem 1rem;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.85rem;
}

.btn-secondary:hover {
  background: #2a2d3a;
  color: #fff;
}

/* Widget picker */
.widget-picker {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.widget-buttons {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.widget-btn {
  background: #1a2a3a;
  border: 1px solid #2a4a5a;
  color: #6cb8e6;
  padding: 0.4rem 0.75rem;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.8rem;
  display: flex;
  align-items: center;
  gap: 0.35rem;
  transition: background 0.15s, border-color 0.15s;
}

.widget-btn:hover {
  background: #1f3a4a;
  border-color: #6cb8e6;
}

.dialog h3 {
  color: #fff;
  font-size: 1rem;
  margin-bottom: 0.5rem;
}

.dialog p {
  color: #aaa;
  font-size: 0.9rem;
  margin-bottom: 0.75rem;
  line-height: 1.5;
}

.dialog-actions {
  display: flex;
  gap: 0.5rem;
  justify-content: flex-end;
  margin-top: 1rem;
}

.btn-danger {
  background: #5a2030;
  color: #f88;
  border: none;
  padding: 0.5rem 1rem;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.85rem;
}
.btn-danger:hover { background: #7a2840; }
</style>
