<template>
  <div>
    <div class="page-header">
      <h2>Device Groups</h2>
      <button class="btn-primary" @click="showCreate = true">
        <i class="pi pi-plus"></i> New Group
      </button>
    </div>

    <!-- Create dialog -->
    <div v-if="showCreate" class="dialog-overlay" @click.self="showCreate = false">
      <div class="dialog">
        <h3>Create Group</h3>
        <input
          v-model="newName"
          placeholder="Group name"
          @keydown.enter="createGroup"
          @keydown.escape="showCreate = false"
          ref="createInput"
        />
        <input
          v-model="newDescription"
          placeholder="Description (optional)"
          @keydown.enter="createGroup"
        />
        <div class="dialog-actions">
          <button class="btn-primary" @click="createGroup" :disabled="!newName.trim()">Create</button>
          <button class="btn-secondary" @click="showCreate = false">Cancel</button>
        </div>
      </div>
    </div>

    <!-- Delete confirmation -->
    <div v-if="deleteTarget" class="dialog-overlay" @click.self="deleteTarget = null">
      <div class="dialog">
        <h3>Delete Group</h3>
        <p>Delete <strong>{{ deleteTarget.name }}</strong>? Devices will be removed from this group but not deleted.</p>
        <div class="dialog-actions">
          <button class="btn-danger" @click="confirmDelete">Delete</button>
          <button class="btn-secondary" @click="deleteTarget = null">Cancel</button>
        </div>
      </div>
    </div>

    <!-- Group detail panel -->
    <div v-if="selectedGroup" class="dialog-overlay" @click.self="closeDetail">
      <div class="dialog detail-dialog">
        <div class="detail-header">
          <div>
            <h3>{{ selectedGroup.name }}</h3>
            <p v-if="selectedGroup.description" class="detail-desc">{{ selectedGroup.description }}</p>
          </div>
          <button class="btn-icon" @click="closeDetail"><i class="pi pi-times"></i></button>
        </div>

        <!-- Assign playlist to group -->
        <div class="detail-section">
          <label>Push Playlist to Group</label>
          <div class="push-row">
            <select v-model="pushPlaylistId" class="select-input">
              <option value="">Select a playlist...</option>
              <option v-for="pl in playlists" :key="pl.id" :value="pl.id">
                {{ pl.name }}{{ pl.is_default ? ' (default)' : '' }}
              </option>
            </select>
            <button
              class="btn-primary btn-sm"
              @click="pushPlaylist"
              :disabled="!pushPlaylistId"
            >Push</button>
          </div>
          <p v-if="pushMessage" class="push-msg">{{ pushMessage }}</p>
        </div>

        <!-- Members list -->
        <div class="detail-section">
          <label>Members ({{ selectedGroup.members?.length || 0 }})</label>
          <div v-if="!selectedGroup.members?.length" class="empty-hint">
            No devices in this group yet.
          </div>
          <div v-else class="member-list">
            <div v-for="m in selectedGroup.members" :key="m.device_id" class="member-row">
              <div class="member-info">
                <span class="member-name">{{ m.name }}</span>
                <span :class="'status-' + m.status" class="member-status">{{ m.status }}</span>
              </div>
              <button class="btn-icon" @click="removeMember(m.device_id)" title="Remove">
                <i class="pi pi-times"></i>
              </button>
            </div>
          </div>
        </div>

        <!-- Add device -->
        <div class="detail-section">
          <label>Add Device</label>
          <div class="push-row">
            <select v-model="addDeviceId" class="select-input">
              <option value="">Select a device...</option>
              <option
                v-for="d in availableDevices"
                :key="d.id"
                :value="d.id"
              >{{ d.name }}</option>
            </select>
            <button
              class="btn-primary btn-sm"
              @click="addMember"
              :disabled="!addDeviceId"
            >Add</button>
          </div>
        </div>
      </div>
    </div>

    <div v-if="loading" class="loading">Loading...</div>

    <div v-else-if="groups.length === 0" class="empty">
      No groups yet. Create one to organize your devices.
    </div>

    <div v-else class="group-grid">
      <div
        v-for="g in groups"
        :key="g.id"
        class="group-card"
        @click="openGroup(g)"
      >
        <div class="card-header">
          <span class="card-name">{{ g.name }}</span>
          <div class="card-actions" @click.stop>
            <button class="btn-icon" @click="deleteTarget = g" title="Delete">
              <i class="pi pi-trash"></i>
            </button>
          </div>
        </div>
        <div class="card-body">
          <p v-if="g.description" class="card-desc">{{ g.description }}</p>
          <div class="card-stat">
            <i class="pi pi-desktop"></i>
            <span>{{ g.member_count }} device{{ g.member_count !== 1 ? 's' : '' }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick, watch } from 'vue'
import { api } from '../api/client.js'

const groups = ref([])
const devices = ref([])
const playlists = ref([])
const loading = ref(true)
const showCreate = ref(false)
const newName = ref('')
const newDescription = ref('')
const createInput = ref(null)
const deleteTarget = ref(null)
const selectedGroup = ref(null)
const pushPlaylistId = ref('')
const pushMessage = ref('')
const addDeviceId = ref('')

const availableDevices = computed(() => {
  const memberIds = new Set((selectedGroup.value?.members || []).map(m => m.device_id))
  return devices.value.filter(d => !memberIds.has(d.id))
})

watch(showCreate, async (val) => {
  if (val) {
    newName.value = ''
    newDescription.value = ''
    await nextTick()
    createInput.value?.focus()
  }
})

async function loadGroups() {
  try {
    groups.value = await api.get('/groups')
  } finally {
    loading.value = false
  }
}

async function loadDevices() {
  devices.value = await api.get('/devices')
}

async function loadPlaylists() {
  playlists.value = await api.get('/playlists')
}

async function createGroup() {
  const name = newName.value.trim()
  if (!name) return
  await api.post('/groups', { name, description: newDescription.value.trim() || null })
  showCreate.value = false
  await loadGroups()
}

async function openGroup(g) {
  const detail = await api.get(`/groups/${g.id}`)
  selectedGroup.value = detail
  pushPlaylistId.value = ''
  pushMessage.value = ''
  addDeviceId.value = ''
}

function closeDetail() {
  selectedGroup.value = null
}

async function confirmDelete() {
  if (!deleteTarget.value) return
  const deletedId = deleteTarget.value.id
  await api.delete(`/groups/${deletedId}`)
  deleteTarget.value = null
  if (selectedGroup.value?.id === deletedId) {
    selectedGroup.value = null
  }
  await loadGroups()
}

async function pushPlaylist() {
  if (!pushPlaylistId.value || !selectedGroup.value) return
  const result = await api.post(`/groups/${selectedGroup.value.id}/assign-playlist`, {
    playlist_id: pushPlaylistId.value,
  })
  pushMessage.value = `Playlist assigned to ${result.updated_count} device(s)`
  await loadDevices()
  // Refresh the detail panel
  await openGroup(selectedGroup.value)
}

async function addMember() {
  if (!addDeviceId.value || !selectedGroup.value) return
  await api.post(`/groups/${selectedGroup.value.id}/members`, {
    device_id: addDeviceId.value,
  })
  addDeviceId.value = ''
  await Promise.all([loadGroups(), openGroup(selectedGroup.value)])
}

async function removeMember(deviceId) {
  if (!selectedGroup.value) return
  await api.delete(`/groups/${selectedGroup.value.id}/members/${deviceId}`)
  await Promise.all([loadGroups(), openGroup(selectedGroup.value)])
}

onMounted(async () => {
  await Promise.all([loadGroups(), loadDevices(), loadPlaylists()])
})
</script>

<style scoped>
h2 { color: #fff; }
h3 { color: #fff; margin-bottom: 0.5rem; }

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

.loading, .empty {
  text-align: center;
  padding: 3rem;
  color: #666;
}

.empty-hint {
  color: #666;
  font-size: 0.85rem;
  padding: 0.5rem 0;
}

/* Grid */
.group-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 1rem;
}

.group-card {
  background: #1a1d27;
  border-radius: 8px;
  padding: 1rem 1.2rem;
  cursor: pointer;
  transition: box-shadow 0.15s, background 0.15s;
  border: 1px solid transparent;
}

.group-card:hover {
  border-color: #7c83ff;
  background: #1e2130;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 0.5rem;
}

.card-name {
  font-size: 1rem;
  font-weight: 500;
  color: #fff;
}

.card-actions { display: flex; gap: 0.2rem; flex-shrink: 0; }

.card-body {}

.card-desc {
  color: #888;
  font-size: 0.85rem;
  margin-bottom: 0.5rem;
}

.card-stat {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  color: #999;
  font-size: 0.85rem;
}

.card-stat i { font-size: 0.8rem; }

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
  width: 380px;
  max-width: 90vw;
  border: 1px solid #2a2d3a;
}

.detail-dialog {
  width: 500px;
  max-height: 80vh;
  overflow-y: auto;
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
  margin-bottom: 0.75rem;
}

.dialog input:focus { border-color: #7c83ff; }

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
}

/* Detail panel */
.detail-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 1rem;
  padding-bottom: 0.75rem;
  border-bottom: 1px solid #2a2d3a;
}

.detail-desc { color: #888; font-size: 0.85rem; margin-top: 0.25rem; }

.detail-section {
  margin-bottom: 1.2rem;
}

.detail-section label {
  display: block;
  font-size: 0.8rem;
  color: #888;
  margin-bottom: 0.4rem;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.push-row {
  display: flex;
  gap: 0.5rem;
  align-items: center;
}

.select-input {
  flex: 1;
  background: #0f1117;
  border: 1px solid #3a3a5a;
  color: #eee;
  padding: 0.4rem 0.6rem;
  border-radius: 4px;
  outline: none;
  font-size: 0.85rem;
  cursor: pointer;
}

.select-input:focus { border-color: #7c83ff; }

.push-msg {
  color: #4caf50;
  font-size: 0.8rem;
  margin-top: 0.4rem;
}

.member-list {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
}

.member-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.4rem 0.6rem;
  background: #0f1117;
  border-radius: 4px;
}

.member-info {
  display: flex;
  align-items: center;
  gap: 0.6rem;
}

.member-name { color: #eee; font-size: 0.9rem; }

.member-status { font-size: 0.75rem; text-transform: uppercase; }

.status-online { color: #4caf50; }
.status-offline { color: #f44336; }
</style>
