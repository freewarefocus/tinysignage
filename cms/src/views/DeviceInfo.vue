<template>
  <div>
    <h2>Device Info</h2>

    <div v-if="device" class="device-card">
      <div class="field">
        <label>Device Name</label>
        <div v-if="editingName" class="edit-row">
          <input v-model="nameInput" @keydown.enter="saveName" @keydown.escape="editingName = false" />
          <button @click="saveName" class="btn-sm">Save</button>
          <button @click="editingName = false" class="btn-sm secondary">Cancel</button>
        </div>
        <div v-else class="value editable" @click="startEditName">
          {{ device.name }}
          <i class="pi pi-pencil edit-icon"></i>
        </div>
      </div>
      <div class="field">
        <label>Device ID</label>
        <div class="value mono">{{ device.id }}</div>
      </div>
      <div class="field">
        <label>Status</label>
        <div class="value">
          <span :class="'status-' + device.status">{{ device.status }}</span>
        </div>
      </div>
      <div class="field">
        <label>Last Seen</label>
        <div class="value">{{ device.last_seen ? new Date(device.last_seen).toLocaleString() : 'Never' }}</div>
      </div>
      <div class="field">
        <label>Assigned Playlist</label>
        <div class="value">{{ device.playlist_id ? 'Default Playlist' : 'None' }}</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { api } from '../api/client.js'

const device = ref(null)
const editingName = ref(false)
const nameInput = ref('')

async function loadDevice() {
  const devices = await api.get('/devices')
  if (devices.length > 0) device.value = devices[0]
}

function startEditName() {
  nameInput.value = device.value.name
  editingName.value = true
}

async function saveName() {
  if (nameInput.value && nameInput.value !== device.value.name) {
    await api.patch(`/devices/${device.value.id}`, { name: nameInput.value })
    await loadDevice()
  }
  editingName.value = false
}

onMounted(loadDevice)
</script>

<style scoped>
h2 { margin-bottom: 1.5rem; color: #fff; }

.device-card {
  max-width: 500px;
  background: #1a1d27;
  border-radius: 8px;
  padding: 1.5rem;
}

.field {
  margin-bottom: 1.2rem;
}

.field:last-child { margin-bottom: 0; }

.field label {
  display: block;
  font-size: 0.8rem;
  color: #888;
  margin-bottom: 0.3rem;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.value {
  font-size: 0.95rem;
  color: #eee;
}

.value.mono {
  font-family: monospace;
  font-size: 0.85rem;
  color: #aaa;
}

.value.editable {
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.edit-icon {
  font-size: 0.75rem;
  color: #555;
}

.edit-row {
  display: flex;
  gap: 0.5rem;
  align-items: center;
}

.edit-row input {
  flex: 1;
  background: #0f1117;
  border: 1px solid #7c83ff;
  color: #eee;
  padding: 0.3rem 0.5rem;
  border-radius: 4px;
  outline: none;
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

.btn-sm.secondary {
  background: #3a3a5a;
}

.status-online { color: #4caf50; }
.status-offline { color: #f44336; }
</style>
