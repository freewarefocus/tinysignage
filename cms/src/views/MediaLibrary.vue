<template>
  <div>
    <div class="header-row">
      <h2>Media Library</h2>
      <button class="tag-mgmt-btn" @click="showTagManager = true" title="Manage tags">
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

    <UploadZone @uploaded="loadAssets" />

    <div v-if="assets.length === 0" class="empty">
      <p v-if="activeTagFilter">No assets with this tag.</p>
      <p v-else>No media yet. Upload images or videos to get started.</p>
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
  </div>
</template>

<script setup>
import { ref, watch, onMounted } from 'vue'
import { api } from '../api/client.js'
import UploadZone from '../components/UploadZone.vue'
import AssetCard from '../components/AssetCard.vue'

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

async function deleteAsset(asset) {
  if (!confirm(`Delete "${asset.name}"?`)) return
  await api.delete(`/assets/${asset.id}`)
  await loadAll()
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

async function deleteTag(tag) {
  if (!confirm(`Delete tag "${tag.name}"? It will be removed from all assets.`)) return
  await api.delete(`/tags/${tag.id}`)
  if (activeTagFilter.value === tag.id) activeTagFilter.value = null
  await loadAll()
}

onMounted(loadAll)
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
</style>
