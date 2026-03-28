<template>
  <div>
    <h2>Playlist Editor</h2>

    <div v-if="!playlist" class="loading">Loading...</div>

    <template v-else>
      <div class="playlist-header">
        <span class="playlist-name">{{ playlist.name }}</span>
        <span class="item-count">{{ items.length }} item(s)</span>
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
import { ref, computed, onMounted } from 'vue'
import { api } from '../api/client.js'
import PlaylistRow from '../components/PlaylistRow.vue'

const playlist = ref(null)
const items = ref([])
const allAssets = ref([])

const availableAssets = computed(() => allAssets.value)

function typeIcon(asset) {
  switch (asset.asset_type) {
    case 'video': return 'pi pi-video'
    case 'url': return 'pi pi-globe'
    default: return 'pi pi-image'
  }
}

async function loadPlaylist() {
  const playlists = await api.get('/playlists')
  const def = playlists.find((p) => p.is_default)
  if (!def) return
  const full = await api.get(`/playlists/${def.id}`)
  playlist.value = full
  items.value = full.items || []
}

async function loadAssets() {
  allAssets.value = await api.get('/assets')
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

  // Find the drop target row
  const target = e.target.closest('[data-item-id]')
  if (!target) return

  const targetId = target.dataset.itemId
  if (draggedId === targetId) return

  // Reorder: move dragged item before target
  const ids = items.value.map((i) => i.id)
  const fromIdx = ids.indexOf(draggedId)
  const toIdx = ids.indexOf(targetId)
  if (fromIdx === -1 || toIdx === -1) return

  ids.splice(fromIdx, 1)
  ids.splice(toIdx, 0, draggedId)

  await api.post(`/playlists/${playlist.value.id}/reorder`, { item_ids: ids })
  await loadPlaylist()
}

onMounted(async () => {
  await Promise.all([loadPlaylist(), loadAssets()])
})
</script>

<style scoped>
h2 { margin-bottom: 1.2rem; color: #fff; }
h3 { margin-bottom: 0.8rem; color: #ddd; font-size: 1rem; }

.loading { color: #888; }

.playlist-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
  padding: 0.6rem 0.75rem;
  background: #1a1d27;
  border-radius: 6px;
}

.playlist-name { color: #fff; font-weight: 500; }
.item-count { color: #888; font-size: 0.85rem; }

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
