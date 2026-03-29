<template>
  <div>
    <div class="page-header">
      <h2>User Management</h2>
      <button class="btn-primary" @click="showCreate = true">
        <i class="pi pi-plus"></i> Add User
      </button>
    </div>

    <div v-if="loading" class="loading">Loading users...</div>

    <table v-else class="users-table">
      <thead>
        <tr>
          <th>Username</th>
          <th>Display Name</th>
          <th>Role</th>
          <th>Status</th>
          <th>Last Login</th>
          <th>Actions</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="user in users" :key="user.id">
          <td>{{ user.username }}</td>
          <td>{{ user.display_name || '—' }}</td>
          <td>
            <span class="role-badge" :class="'role-' + user.role">
              {{ user.role }}
            </span>
          </td>
          <td>
            <span class="status-badge" :class="user.is_active ? 'active' : 'inactive'">
              {{ user.is_active ? 'Active' : 'Disabled' }}
            </span>
          </td>
          <td>{{ user.last_login ? formatDate(user.last_login) : 'Never' }}</td>
          <td class="actions">
            <button class="btn-icon" title="Edit" @click="startEdit(user)">
              <i class="pi pi-pencil"></i>
            </button>
            <button
              v-if="user.id !== currentUserId"
              class="btn-icon btn-danger"
              title="Delete"
              @click="confirmDelete(user)"
            >
              <i class="pi pi-trash"></i>
            </button>
          </td>
        </tr>
      </tbody>
    </table>

    <!-- Create/Edit Dialog -->
    <div v-if="showCreate || editUser" class="modal-overlay" @click.self="closeDialog">
      <div class="modal">
        <h3>{{ editUser ? 'Edit User' : 'Create User' }}</h3>
        <form @submit.prevent="editUser ? saveEdit() : createUser()">
          <label>Username</label>
          <input
            v-model="form.username"
            type="text"
            required
            minlength="3"
            :disabled="!!editUser"
          />
          <label>Display Name</label>
          <input v-model="form.display_name" type="text" />
          <label>Role</label>
          <select v-model="form.role">
            <option value="admin">Admin</option>
            <option value="editor">Editor</option>
            <option value="viewer">Viewer</option>
          </select>
          <template v-if="editUser">
            <label>
              <input type="checkbox" v-model="form.is_active" />
              Active
            </label>
            <label>New Password (leave blank to keep current)</label>
            <input v-model="form.password" type="password" minlength="8" placeholder="Min. 8 characters" />
          </template>
          <template v-else>
            <label>Password</label>
            <input v-model="form.password" type="password" required minlength="8" placeholder="Min. 8 characters" />
          </template>
          <div v-if="formError" class="error">{{ formError }}</div>
          <div class="modal-actions">
            <button type="button" class="btn-secondary" @click="closeDialog">Cancel</button>
            <button type="submit" class="btn-primary">{{ editUser ? 'Save' : 'Create' }}</button>
          </div>
        </form>
      </div>
    </div>

    <!-- Delete Confirmation -->
    <div v-if="deleteTarget" class="modal-overlay" @click.self="deleteTarget = null">
      <div class="modal">
        <h3>Delete User</h3>
        <p>Are you sure you want to delete <strong>{{ deleteTarget.username }}</strong>?</p>
        <div class="modal-actions">
          <button class="btn-secondary" @click="deleteTarget = null">Cancel</button>
          <button class="btn-danger-solid" @click="doDelete">Delete</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { api } from '../api/client'

const users = ref([])
const loading = ref(true)
const showCreate = ref(false)
const editUser = ref(null)
const deleteTarget = ref(null)
const formError = ref('')
const form = ref({ username: '', display_name: '', role: 'viewer', password: '', is_active: true })

const currentUser = JSON.parse(localStorage.getItem('tinysignage_user') || '{}')
const currentUserId = currentUser.id

async function loadUsers() {
  loading.value = true
  try {
    users.value = await api.get('/users')
  } catch { /* toast handles it */ }
  loading.value = false
}

function formatDate(iso) {
  return new Date(iso).toLocaleString()
}

function closeDialog() {
  showCreate.value = false
  editUser.value = null
  formError.value = ''
  form.value = { username: '', display_name: '', role: 'viewer', password: '', is_active: true }
}

async function createUser() {
  formError.value = ''
  try {
    await api.post('/users', {
      username: form.value.username,
      display_name: form.value.display_name,
      password: form.value.password,
      role: form.value.role,
    })
    closeDialog()
    await loadUsers()
  } catch (e) {
    formError.value = e.message.replace(/^\d+:\s*/, '')
  }
}

function startEdit(user) {
  editUser.value = user
  form.value = {
    username: user.username,
    display_name: user.display_name || '',
    role: user.role,
    password: '',
    is_active: user.is_active,
  }
}

async function saveEdit() {
  formError.value = ''
  const body = {
    display_name: form.value.display_name,
    role: form.value.role,
    is_active: form.value.is_active,
  }
  if (form.value.password) {
    body.password = form.value.password
  }
  try {
    await api.put(`/users/${editUser.value.id}`, body)
    closeDialog()
    await loadUsers()
  } catch (e) {
    formError.value = e.message.replace(/^\d+:\s*/, '')
  }
}

function confirmDelete(user) {
  deleteTarget.value = user
}

async function doDelete() {
  try {
    await api.delete(`/users/${deleteTarget.value.id}`)
    deleteTarget.value = null
    await loadUsers()
  } catch { /* toast handles it */ }
}

onMounted(loadUsers)
</script>

<style scoped>
.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 1.5rem;
}

.page-header h2 {
  font-size: 1.3rem;
  color: #fff;
}

.users-table {
  width: 100%;
  border-collapse: collapse;
}

.users-table th {
  text-align: left;
  padding: 0.6rem 0.8rem;
  font-size: 0.8rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: #888;
  border-bottom: 1px solid #2a2d3a;
}

.users-table td {
  padding: 0.7rem 0.8rem;
  border-bottom: 1px solid #1e2130;
  font-size: 0.9rem;
}

.role-badge {
  display: inline-block;
  padding: 0.15rem 0.5rem;
  border-radius: 4px;
  font-size: 0.8rem;
  font-weight: 500;
  text-transform: capitalize;
}

.role-admin { background: #7c83ff22; color: #7c83ff; }
.role-editor { background: #4caf5022; color: #4caf50; }
.role-viewer { background: #ff980022; color: #ff9800; }

.status-badge {
  font-size: 0.8rem;
}

.status-badge.active { color: #4caf50; }
.status-badge.inactive { color: #888; }

.actions {
  display: flex;
  gap: 0.3rem;
}

.btn-icon {
  background: none;
  border: 1px solid #3a3a5a;
  color: #ccc;
  padding: 0.3rem 0.5rem;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.8rem;
}

.btn-icon:hover { background: #252836; color: #fff; }
.btn-icon.btn-danger:hover { background: #ef535033; color: #ef5350; }

.btn-primary {
  background: #7c83ff;
  color: #fff;
  border: none;
  padding: 0.5rem 1rem;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.9rem;
  display: flex;
  align-items: center;
  gap: 0.4rem;
}

.btn-primary:hover { background: #6b72e8; }

.btn-secondary {
  background: #2a2d3a;
  color: #ccc;
  border: none;
  padding: 0.5rem 1rem;
  border-radius: 6px;
  cursor: pointer;
}

.btn-danger-solid {
  background: #ef5350;
  color: #fff;
  border: none;
  padding: 0.5rem 1rem;
  border-radius: 6px;
  cursor: pointer;
}

.btn-danger-solid:hover { background: #d32f2f; }

.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal {
  background: #1a1d27;
  border: 1px solid #2a2d3a;
  border-radius: 12px;
  padding: 1.5rem;
  width: 100%;
  max-width: 400px;
}

.modal h3 {
  color: #fff;
  margin-bottom: 1rem;
}

.modal label {
  display: block;
  font-size: 0.85rem;
  color: #aaa;
  margin-bottom: 0.3rem;
  margin-top: 0.5rem;
}

.modal input[type="text"],
.modal input[type="password"] {
  width: 100%;
  background: #0f1117;
  border: 1px solid #3a3a5a;
  color: #eee;
  padding: 0.5rem;
  border-radius: 4px;
  font-size: 0.9rem;
}

.modal input[type="text"]:focus,
.modal input[type="password"]:focus {
  outline: none;
  border-color: #7c83ff;
}

.modal input[type="checkbox"] {
  margin-right: 0.4rem;
}

.modal select {
  width: 100%;
  background: #0f1117;
  border: 1px solid #3a3a5a;
  color: #eee;
  padding: 0.5rem;
  border-radius: 4px;
  font-size: 0.9rem;
}

.modal-actions {
  display: flex;
  gap: 0.5rem;
  justify-content: flex-end;
  margin-top: 1.2rem;
}

.error {
  color: #ef5350;
  font-size: 0.85rem;
  margin-top: 0.5rem;
}

.loading {
  color: #888;
  padding: 2rem;
  text-align: center;
}

input:disabled {
  opacity: 0.5;
}
</style>
