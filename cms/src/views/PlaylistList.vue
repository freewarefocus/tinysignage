<template>
  <div>
    <div class="page-header">
      <h2>Playlists</h2>
      <button class="btn-primary" @click="showCreate = true">
        <i class="pi pi-plus"></i> New Playlist
      </button>
    </div>

    <!-- Create dialog -->
    <div v-if="showCreate" class="dialog-overlay" @click.self="showCreate = false">
      <div class="dialog">
        <h3>Create Playlist</h3>
        <input
          v-model="newName"
          placeholder="Playlist name"
          @keydown.enter="createPlaylist"
          @keydown.escape="showCreate = false"
          ref="createInput"
        />
        <div class="dialog-actions">
          <button class="btn-primary" @click="createPlaylist" :disabled="!newName.trim()">Create</button>
          <button class="btn-secondary" @click="showCreate = false">Cancel</button>
        </div>
      </div>
    </div>

    <!-- Delete confirmation dialog -->
    <div v-if="deleteTarget" class="dialog-overlay" @click.self="deleteTarget = null">
      <div class="dialog">
        <h3>Delete Playlist</h3>
        <p>Delete <strong>{{ deleteTarget.name }}</strong>? This removes all items in the playlist. Devices assigned to it will have no content until reassigned.</p>
        <div class="dialog-actions">
          <button class="btn-danger" @click="confirmDelete">Delete</button>
          <button class="btn-secondary" @click="deleteTarget = null">Cancel</button>
        </div>
      </div>
    </div>

    <div v-if="loading" class="loading">Loading...</div>

    <div v-else-if="playlists.length === 0" class="empty">
      No playlists yet. Create one to get started.
    </div>

    <div v-else class="playlist-grid">
      <div
        v-for="pl in playlists"
        :key="pl.id"
        class="playlist-card"
        @click="openPlaylist(pl)"
      >
        <div class="card-header">
          <div class="card-title-row">
            <template v-if="editingId === pl.id">
              <input
                v-model="editName"
                class="inline-edit"
                @click.stop
                @keydown.enter.stop="saveRename(pl)"
                @keydown.escape.stop="editingId = null"
                ref="renameInput"
              />
              <button class="btn-icon" @click.stop="saveRename(pl)" title="Save">
                <i class="pi pi-check"></i>
              </button>
              <button class="btn-icon" @click.stop="editingId = null" title="Cancel">
                <i class="pi pi-times"></i>
              </button>
            </template>
            <template v-else>
              <span class="card-name">{{ pl.name }}</span>
              <span v-if="pl.is_default" class="default-badge">Default</span>
              <span v-if="pl.mode === 'advanced'" class="mode-badge">Advanced</span>
            </template>
          </div>
          <div class="card-actions" @click.stop v-if="editingId !== pl.id">
            <button class="btn-icon" @click="startRename(pl)" title="Rename">
              <i class="pi pi-pencil"></i>
            </button>
            <button
              class="btn-icon"
              @click="deleteTarget = pl"
              title="Delete"
              :disabled="pl.is_default"
            >
              <i class="pi pi-trash"></i>
            </button>
          </div>
        </div>
        <div class="card-body">
          <div class="card-stat">
            <i class="pi pi-images"></i>
            <span>{{ pl.item_count }} item{{ pl.item_count !== 1 ? 's' : '' }}</span>
          </div>
          <div class="card-meta">
            {{ formatDate(pl.updated_at || pl.created_at) }}
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick, watch } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api/client.js'
import { relativeTime } from '../utils/date.js'

const router = useRouter()

const playlists = ref([])
const loading = ref(true)
const showCreate = ref(false)
const newName = ref('')
const createInput = ref(null)
const editingId = ref(null)
const editName = ref('')
const renameInput = ref(null)
const deleteTarget = ref(null)

watch(showCreate, async (val) => {
  if (val) {
    newName.value = ''
    await nextTick()
    createInput.value?.focus()
  }
})

async function loadPlaylists() {
  try {
    playlists.value = await api.get('/playlists')
  } finally {
    loading.value = false
  }
}

async function createPlaylist() {
  const name = newName.value.trim()
  if (!name) return
  const created = await api.post('/playlists', { name })
  showCreate.value = false
  await loadPlaylists()
  router.push(`/playlists/${created.id}`)
}

function openPlaylist(pl) {
  router.push(`/playlists/${pl.id}`)
}

function startRename(pl) {
  editingId.value = pl.id
  editName.value = pl.name
  nextTick(() => {
    const inputs = document.querySelectorAll('.inline-edit')
    if (inputs.length) inputs[inputs.length - 1].focus()
  })
}

async function saveRename(pl) {
  const name = editName.value.trim()
  if (!name || name === pl.name) {
    editingId.value = null
    return
  }
  await api.patch(`/playlists/${pl.id}`, { name })
  editingId.value = null
  await loadPlaylists()
}

async function confirmDelete() {
  if (!deleteTarget.value) return
  await api.delete(`/playlists/${deleteTarget.value.id}`)
  deleteTarget.value = null
  await loadPlaylists()
}

function formatDate(iso) {
  return relativeTime(iso)
}

onMounted(loadPlaylists)
</script>

<style scoped>
h2 { color: #fff; }
h3 { color: #fff; margin-bottom: 1rem; }

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
  transition: background 0.15s;
}

.btn-primary:hover { background: #6b72ee; }
.btn-primary:disabled { opacity: 0.5; cursor: default; }

.btn-secondary {
  background: #3a3a5a;
  color: #ccc;
  border: none;
  padding: 0.5rem 1rem;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.85rem;
}

.btn-danger {
  background: #dc3545;
  color: #fff;
  border: none;
  padding: 0.5rem 1rem;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.85rem;
}

.btn-danger:hover { background: #c82333; }

.btn-icon {
  background: none;
  border: none;
  color: #888;
  cursor: pointer;
  padding: 0.3rem;
  border-radius: 4px;
  transition: color 0.15s;
}

.btn-icon:hover { color: #fff; }
.btn-icon:disabled { opacity: 0.3; cursor: default; }
.btn-icon:disabled:hover { color: #888; }

.loading, .empty {
  text-align: center;
  padding: 3rem;
  color: #666;
}

.playlist-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 1rem;
}

.playlist-card {
  background: #1a1d27;
  border-radius: 8px;
  padding: 1rem 1.2rem;
  cursor: pointer;
  transition: box-shadow 0.15s, background 0.15s;
  border: 1px solid transparent;
}

.playlist-card:hover {
  border-color: #7c83ff;
  background: #1e2130;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 0.75rem;
}

.card-title-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex: 1;
  min-width: 0;
}

.card-name {
  font-size: 1rem;
  font-weight: 500;
  color: #fff;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.default-badge {
  background: #252836;
  color: #7c83ff;
  font-size: 0.65rem;
  padding: 2px 6px;
  border-radius: 3px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  flex-shrink: 0;
}

.mode-badge {
  background: #2d2545;
  color: #a78bfa;
  font-size: 0.65rem;
  padding: 2px 6px;
  border-radius: 3px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  flex-shrink: 0;
}

.card-actions {
  display: flex;
  gap: 0.2rem;
  flex-shrink: 0;
}

.inline-edit {
  flex: 1;
  min-width: 0;
  background: #0f1117;
  border: 1px solid #7c83ff;
  color: #eee;
  padding: 0.2rem 0.5rem;
  border-radius: 4px;
  outline: none;
  font-size: 0.95rem;
}

.card-body {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.card-stat {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  color: #999;
  font-size: 0.85rem;
}

.card-stat i { font-size: 0.8rem; }

.card-meta {
  color: #666;
  font-size: 0.8rem;
}

/* Dialog overlay */
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
  width: 380px;
  max-width: 90vw;
  border: 1px solid #2a2d3a;
}

.dialog input {
  width: 100%;
  background: #0f1117;
  border: 1px solid #3a3a5a;
  color: #eee;
  padding: 0.5rem 0.75rem;
  border-radius: 6px;
  outline: none;
  font-size: 0.9rem;
  margin-bottom: 1rem;
}

.dialog input:focus { border-color: #7c83ff; }

.dialog p {
  color: #aaa;
  font-size: 0.9rem;
  margin-bottom: 1rem;
  line-height: 1.5;
}

.dialog-actions {
  display: flex;
  gap: 0.5rem;
  justify-content: flex-end;
}
</style>
