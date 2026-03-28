<template>
  <div>
    <h2>Settings</h2>

    <form v-if="settings" @submit.prevent="saveSettings" class="settings-form">
      <div class="form-group">
        <label>Transition Duration (seconds)</label>
        <input type="number" v-model.number="settings.transition_duration" step="0.1" min="0" />
      </div>
      <div class="form-group">
        <label>Transition Type</label>
        <select v-model="settings.transition_type">
          <option value="fade">Fade</option>
          <option value="cut">Cut</option>
        </select>
      </div>
      <div class="form-group">
        <label>Default Duration (seconds)</label>
        <input type="number" v-model.number="settings.default_duration" min="1" />
      </div>
      <div class="form-group checkbox">
        <label>
          <input type="checkbox" v-model="settings.shuffle" />
          Shuffle playlist
        </label>
      </div>
      <button type="submit" class="btn-save">Save Settings</button>
      <span v-if="saved" class="save-msg">Saved!</span>
    </form>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { api } from '../api/client.js'

const settings = ref(null)
const saved = ref(false)

async function loadSettings() {
  settings.value = await api.get('/settings')
}

async function saveSettings() {
  await api.patch('/settings', settings.value)
  saved.value = true
  setTimeout(() => (saved.value = false), 2000)
}

onMounted(loadSettings)
</script>

<style scoped>
h2 { margin-bottom: 1.5rem; color: #fff; }

.settings-form {
  max-width: 400px;
}

.form-group {
  margin-bottom: 1.2rem;
}

.form-group label {
  display: block;
  font-size: 0.85rem;
  color: #aaa;
  margin-bottom: 0.4rem;
}

.form-group input[type="number"],
.form-group select {
  width: 100%;
  background: #1a1d27;
  border: 1px solid #3a3a5a;
  color: #eee;
  padding: 0.5rem 0.6rem;
  border-radius: 4px;
  font-size: 0.9rem;
}

.form-group input:focus,
.form-group select:focus {
  outline: none;
  border-color: #7c83ff;
}

.checkbox label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  cursor: pointer;
  color: #ccc;
}

.btn-save {
  background: #7c83ff;
  color: #fff;
  border: none;
  padding: 0.6rem 1.5rem;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.9rem;
  transition: background 0.15s;
}

.btn-save:hover {
  background: #6b72e8;
}

.save-msg {
  margin-left: 1rem;
  color: #4caf50;
  font-size: 0.85rem;
}
</style>
