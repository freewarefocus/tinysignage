<template>
  <div>
    <div class="page-header">
      <div class="breadcrumb">
        <router-link to="/playlists" class="breadcrumb-link">Playlists</router-link>
        <i class="pi pi-angle-right breadcrumb-sep"></i>
        <template v-if="playlist">
          <span v-if="!editingName" class="breadcrumb-current" @click="startEditName">
            {{ playlist.name }}
            <i class="pi pi-pencil edit-hint"></i>
          </span>
          <span v-else class="breadcrumb-edit">
            <input
              v-model="nameInput"
              @keydown.enter="saveName"
              @keydown.escape="editingName = false"
              ref="nameInputEl"
            />
            <button class="btn-sm" @click="saveName">Save</button>
            <button class="btn-sm secondary" @click="editingName = false">Cancel</button>
          </span>
        </template>
      </div>
    </div>

    <div v-if="!playlist" class="loading">Loading...</div>

    <template v-else>
      <div class="playlist-header">
        <div class="header-left">
          <span v-if="playlist.is_default" class="default-badge">Default</span>
          <span class="item-count">{{ items.length }} item(s)</span>
        </div>
        <div class="header-right">
          <span class="hash-label">Hash: {{ playlist.hash?.slice(0, 8) }}</span>
          <button class="btn-toggle" @click="showSettings = !showSettings">
            <i class="pi pi-cog"></i>
            <span>Settings</span>
            <i :class="showSettings ? 'pi pi-chevron-up' : 'pi pi-chevron-down'" class="toggle-arrow"></i>
          </button>
        </div>
      </div>

      <!-- Per-playlist settings panel -->
      <div v-if="showSettings" class="settings-panel">
        <div class="settings-grid">
          <div class="setting-field">
            <label>Transition Type</label>
            <select v-model="plSettings.transition_type" @change="saveSettings" class="setting-select">
              <option :value="null">Global default</option>
              <option value="fade">Fade</option>
              <option value="slide">Slide</option>
              <option value="none">None</option>
            </select>
          </div>
          <div class="setting-field">
            <label>Transition Duration (s)</label>
            <div class="number-input-row">
              <input
                type="number"
                :value="plSettings.transition_duration"
                @change="updateNumber('transition_duration', $event)"
                min="0" max="10" step="0.1"
                class="setting-number"
                placeholder="Global default"
              />
              <button
                v-if="plSettings.transition_duration !== null"
                class="btn-clear"
                @click="clearSetting('transition_duration')"
                title="Reset to global default"
              >&times;</button>
            </div>
          </div>
          <div class="setting-field">
            <label>Default Duration (s)</label>
            <div class="number-input-row">
              <input
                type="number"
                :value="plSettings.default_duration"
                @change="updateNumber('default_duration', $event)"
                min="1" max="3600" step="1"
                class="setting-number"
                placeholder="Global default"
              />
              <button
                v-if="plSettings.default_duration !== null"
                class="btn-clear"
                @click="clearSetting('default_duration')"
                title="Reset to global default"
              >&times;</button>
            </div>
          </div>
          <div class="setting-field">
            <label>Shuffle</label>
            <select v-model="plSettings.shuffle" @change="saveSettings" class="setting-select">
              <option :value="null">Global default</option>
              <option :value="true">On</option>
              <option :value="false">Off</option>
            </select>
          </div>
        </div>
        <p class="settings-hint">
          Leave blank or "Global default" to inherit from global settings.
        </p>
      </div>

      <div
        class="playlist-items"
        @dragover.prevent="onDragOver"
        @drop.prevent="onDrop"
      >
        <div v-if="items.length === 0" class="empty">
          <p>Playlist is empty. Add media from the library below.</p>
        </div>
        <PlaylistRow
          v-for="item in items"
          :key="item.id"
          :item="item"
          :data-item-id="item.id"
          @remove="removeItem"
        />
      </div>

      <div class="add-section">
        <h3>Add from Media Library</h3>
        <div v-if="availableAssets.length === 0" class="empty-hint">
          No media available. Upload files in the Media Library first.
        </div>
        <div v-else class="add-grid">
          <div
            v-for="asset in availableAssets"
            :key="asset.id"
            class="add-card"
            @click="addToPlaylist(asset)"
          >
            <div class="add-thumb">
              <img
                v-if="asset.thumbnail_path"
                :src="`/api/assets/${asset.id}/thumbnail`"
                alt=""
              />
              <i v-else :class="typeIcon(asset)" class="add-icon"></i>
            </div>
            <div class="add-name">{{ asset.name }}</div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '../api/client.js'
import PlaylistRow from '../components/PlaylistRow.vue'

const route = useRoute()
const router = useRouter()

const playlist = ref(null)
const items = ref([])
const allAssets = ref([])
const editingName = ref(false)
const nameInput = ref('')
const nameInputEl = ref(null)
const showSettings = ref(false)
const plSettings = ref({
  transition_type: null,
  transition_duration: null,
  default_duration: null,
  shuffle: null,
})

const availableAssets = computed(() => allAssets.value)

const playlistId = computed(() => route.params.id)

function typeIcon(asset) {
  switch (asset.asset_type) {
    case 'video': return 'pi pi-video'
    case 'url': return 'pi pi-globe'
    default: return 'pi pi-image'
  }
}

async function loadPlaylist() {
  const id = playlistId.value
  if (!id) return
  try {
    const full = await api.get(`/playlists/${id}`)
    playlist.value = full
    items.value = full.items || []
    plSettings.value = {
      transition_type: full.transition_type ?? null,
      transition_duration: full.transition_duration ?? null,
      default_duration: full.default_duration ?? null,
      shuffle: full.shuffle ?? null,
    }
  } catch (e) {
    router.push('/playlists')
  }
}

async function loadAssets() {
  allAssets.value = await api.get('/assets')
}

function startEditName() {
  nameInput.value = playlist.value.name
  editingName.value = true
  nextTick(() => nameInputEl.value?.focus())
}

async function saveName() {
  const name = nameInput.value.trim()
  if (name && name !== playlist.value.name) {
    await api.patch(`/playlists/${playlist.value.id}`, { name })
    await loadPlaylist()
  }
  editingName.value = false
}

async function saveSettings() {
  if (!playlist.value) return
  await api.patch(`/playlists/${playlist.value.id}`, {
    transition_type: plSettings.value.transition_type,
    transition_duration: plSettings.value.transition_duration,
    default_duration: plSettings.value.default_duration,
    shuffle: plSettings.value.shuffle,
  })
}

function updateNumber(field, event) {
  const val = event.target.value
  plSettings.value[field] = val === '' ? null : Number(val)
  saveSettings()
}

function clearSetting(field) {
  plSettings.value[field] = null
  saveSettings()
}

async function addToPlaylist(asset) {
  if (!playlist.value) return
  await api.post(`/playlists/${playlist.value.id}/items`, { asset_id: asset.id })
  await loadPlaylist()
}

async function removeItem(item) {
  if (!playlist.value) return
  await api.delete(`/playlists/${playlist.value.id}/items/${item.id}`)
  await loadPlaylist()
}

// Drag-and-drop reorder
function onDragOver(e) {
  e.dataTransfer.dropEffect = 'move'
}

async function onDrop(e) {
  const draggedId = e.dataTransfer.getData('text/plain')
  if (!draggedId || !playlist.value) return

  const target = e.target.closest('[data-item-id]')
  if (!target) return

  const targetId = target.dataset.itemId
  if (draggedId === targetId) return

  const ids = items.value.map((i) => i.id)
  const fromIdx = ids.indexOf(draggedId)
  const toIdx = ids.indexOf(targetId)
  if (fromIdx === -1 || toIdx === -1) return

  ids.splice(fromIdx, 1)
  ids.splice(toIdx, 0, draggedId)

  await api.post(`/playlists/${playlist.value.id}/reorder`, { item_ids: ids })
  await loadPlaylist()
}

// Watch for route param changes (navigating between playlists)
watch(playlistId, () => {
  playlist.value = null
  items.value = []
  loadPlaylist()
})

onMounted(async () => {
  await Promise.all([loadPlaylist(), loadAssets()])
})
</script>

<style scoped>
h3 { margin-bottom: 0.8rem; color: #ddd; font-size: 1rem; }

.loading { color: #888; }

.page-header {
  margin-bottom: 1.2rem;
}

.breadcrumb {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.breadcrumb-link {
  color: #7c83ff;
  text-decoration: none;
  font-size: 1.1rem;
  font-weight: 600;
}

.breadcrumb-link:hover { text-decoration: underline; }

.breadcrumb-sep {
  color: #555;
  font-size: 0.8rem;
}

.breadcrumb-current {
  color: #fff;
  font-size: 1.1rem;
  font-weight: 600;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 0.4rem;
}

.edit-hint {
  font-size: 0.7rem;
  color: #555;
}

.breadcrumb-edit {
  display: flex;
  align-items: center;
  gap: 0.4rem;
}

.breadcrumb-edit input {
  background: #0f1117;
  border: 1px solid #7c83ff;
  color: #eee;
  padding: 0.3rem 0.5rem;
  border-radius: 4px;
  outline: none;
  font-size: 1rem;
}

.btn-sm {
  background: #7c83ff;
  color: #fff;
  border: none;
  padding: 0.3rem 0.8rem;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.8rem;
}

.btn-sm.secondary { background: #3a3a5a; }

.playlist-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
  padding: 0.6rem 0.75rem;
  background: #1a1d27;
  border-radius: 6px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.default-badge {
  background: #252836;
  color: #7c83ff;
  font-size: 0.65rem;
  padding: 2px 6px;
  border-radius: 3px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.item-count { color: #888; font-size: 0.85rem; }

.header-right {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.hash-label { color: #555; font-size: 0.75rem; font-family: monospace; }

.btn-toggle {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  background: #252836;
  color: #999;
  border: none;
  padding: 0.35rem 0.7rem;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.8rem;
  transition: color 0.15s, background 0.15s;
}

.btn-toggle:hover { color: #fff; background: #2f3348; }
.toggle-arrow { font-size: 0.65rem; }

/* Per-playlist settings */
.settings-panel {
  background: #1a1d27;
  border-radius: 6px;
  padding: 1rem;
  margin-bottom: 1rem;
  border: 1px solid #2a2d3a;
}

.settings-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 1rem;
}

.setting-field label {
  display: block;
  font-size: 0.75rem;
  color: #888;
  margin-bottom: 0.3rem;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.setting-select,
.setting-number {
  width: 100%;
  background: #0f1117;
  border: 1px solid #3a3a5a;
  color: #eee;
  padding: 0.4rem 0.5rem;
  border-radius: 4px;
  outline: none;
  font-size: 0.85rem;
}

.setting-select:focus,
.setting-number:focus { border-color: #7c83ff; }

.number-input-row {
  display: flex;
  gap: 0.3rem;
  align-items: center;
}

.number-input-row .setting-number { flex: 1; }

.btn-clear {
  background: #3a3a5a;
  color: #aaa;
  border: none;
  width: 24px;
  height: 28px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 1rem;
  line-height: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}

.btn-clear:hover { color: #fff; background: #555; }

.settings-hint {
  color: #666;
  font-size: 0.75rem;
  margin-top: 0.75rem;
}

.playlist-items {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  margin-bottom: 2rem;
  min-height: 60px;
}

.empty, .empty-hint {
  text-align: center;
  padding: 2rem;
  color: #666;
}

.add-section {
  border-top: 1px solid #2a2d3a;
  padding-top: 1.5rem;
}

.add-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 0.75rem;
}

.add-card {
  background: #1a1d27;
  border-radius: 6px;
  cursor: pointer;
  overflow: hidden;
  transition: box-shadow 0.15s;
}

.add-card:hover {
  box-shadow: 0 0 0 1px #7c83ff;
}

.add-thumb {
  aspect-ratio: 16 / 9;
  background: #0f1117;
  display: flex;
  align-items: center;
  justify-content: center;
}

.add-thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.add-icon { font-size: 1.5rem; color: #444; }

.add-name {
  padding: 0.4rem 0.5rem;
  font-size: 0.8rem;
  color: #ccc;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
</style>
