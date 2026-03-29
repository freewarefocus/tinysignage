<template>
  <div v-if="isLoginPage">
    <router-view />
  </div>
  <div v-else class="app-layout">
    <aside class="sidebar">
      <div class="sidebar-header">
        <h1>TinySignage</h1>
      </div>
      <nav>
        <router-link v-if="canEdit" to="/media" class="nav-item" active-class="active">
          <i class="pi pi-images"></i>
          <span>Media</span>
        </router-link>
        <router-link v-if="canEdit" to="/playlists" class="nav-item" active-class="active">
          <i class="pi pi-list"></i>
          <span>Playlists</span>
        </router-link>
        <router-link to="/groups" class="nav-item" active-class="active">
          <i class="pi pi-sitemap"></i>
          <span>Groups</span>
        </router-link>
        <router-link v-if="canEdit" to="/schedules" class="nav-item" active-class="active">
          <i class="pi pi-calendar"></i>
          <span>Schedules</span>
        </router-link>
        <router-link v-if="isAdmin" to="/settings" class="nav-item" active-class="active">
          <i class="pi pi-cog"></i>
          <span>Settings</span>
        </router-link>
        <router-link to="/devices" class="nav-item" active-class="active">
          <i class="pi pi-desktop"></i>
          <span>Devices</span>
        </router-link>
        <router-link v-if="isAdmin" to="/users" class="nav-item" active-class="active">
          <i class="pi pi-users"></i>
          <span>Users</span>
        </router-link>
        <router-link v-if="isAdmin" to="/audit" class="nav-item" active-class="active">
          <i class="pi pi-history"></i>
          <span>Audit Log</span>
        </router-link>
        <router-link v-if="isAdmin" to="/system" class="nav-item" active-class="active">
          <i class="pi pi-server"></i>
          <span>System</span>
        </router-link>
      </nav>
      <div class="sidebar-footer">
        <a href="/player" target="_blank" class="nav-item">
          <i class="pi pi-external-link"></i>
          <span>Open Player</span>
        </a>
        <div v-if="currentUser" class="user-info">
          <div class="user-details">
            <span class="user-name">{{ currentUser.display_name || currentUser.username }}</span>
            <span class="user-role">{{ currentUser.role }}</span>
          </div>
          <button class="logout-btn" title="Sign out" @click="logout">
            <i class="pi pi-sign-out"></i>
          </button>
        </div>
      </div>
    </aside>
    <main class="content">
      <router-view />
    </main>
    <Toast position="bottom-right" />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useToast } from 'primevue/usetoast'
import Toast from 'primevue/toast'
import { errorBus } from './api/client'

const toast = useToast()
const route = useRoute()
const router = useRouter()

const currentUser = ref(null)

const isLoginPage = computed(() => route.name === 'login')
const isAdmin = computed(() => currentUser.value?.role === 'admin')
const canEdit = computed(() => {
  const role = currentUser.value?.role
  return role === 'admin' || role === 'editor'
})

function loadUser() {
  const stored = localStorage.getItem('tinysignage_user')
  if (stored) {
    try {
      currentUser.value = JSON.parse(stored)
    } catch {
      currentUser.value = null
    }
  } else {
    // Legacy: user logged in with API token (no user object stored)
    const token = localStorage.getItem('tinysignage_token') || localStorage.getItem('tinysignage_admin_token')
    if (token) {
      currentUser.value = { username: 'API Token', role: 'admin' }
    } else {
      currentUser.value = null
    }
  }
}

function logout() {
  // Fire and forget the logout API call
  const token = localStorage.getItem('tinysignage_token') || localStorage.getItem('tinysignage_admin_token')
  if (token) {
    fetch('/api/auth/logout', {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}` },
    }).catch(() => {})
  }
  localStorage.removeItem('tinysignage_token')
  localStorage.removeItem('tinysignage_admin_token')
  localStorage.removeItem('tinysignage_user')
  currentUser.value = null
  router.push('/login')
}

function onApiError(event) {
  const { summary, severity, sticky } = event.detail
  toast.add({
    severity: severity || 'error',
    summary: 'Error',
    detail: summary,
    life: sticky ? undefined : 5000,
    sticky: sticky || false,
  })
}

// Reload user info when route changes (e.g. after login redirect)
watch(() => route.name, loadUser)

onMounted(() => {
  loadUser()
  errorBus.addEventListener('api-error', onApiError)
})

onUnmounted(() => {
  errorBus.removeEventListener('api-error', onApiError)
})
</script>

<style>
* { margin: 0; padding: 0; box-sizing: border-box; }

body {
  font-family: system-ui, -apple-system, sans-serif;
  background: #0f1117;
  color: #e0e0e0;
}

.app-layout {
  display: flex;
  min-height: 100vh;
}

.sidebar {
  width: 220px;
  background: #1a1d27;
  border-right: 1px solid #2a2d3a;
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
}

.sidebar-header {
  padding: 1.2rem 1rem;
  border-bottom: 1px solid #2a2d3a;
}

.sidebar-header h1 {
  font-size: 1.1rem;
  font-weight: 600;
  color: #fff;
}

nav {
  flex: 1;
  padding: 0.5rem 0;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.7rem 1rem;
  color: #999;
  text-decoration: none;
  font-size: 0.9rem;
  transition: background 0.15s, color 0.15s;
}

.nav-item:hover {
  background: #252836;
  color: #fff;
}

.nav-item.active {
  background: #252836;
  color: #7c83ff;
  border-right: 3px solid #7c83ff;
}

.nav-item i {
  font-size: 1rem;
  width: 1.2rem;
  text-align: center;
}

.sidebar-footer {
  border-top: 1px solid #2a2d3a;
  padding: 0.5rem 0;
}

.user-info {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.6rem 1rem;
  border-top: 1px solid #2a2d3a;
  margin-top: 0.3rem;
}

.user-details {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.user-name {
  font-size: 0.85rem;
  color: #ddd;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.user-role {
  font-size: 0.7rem;
  color: #888;
  text-transform: capitalize;
}

.logout-btn {
  background: none;
  border: none;
  color: #888;
  cursor: pointer;
  padding: 0.3rem;
  border-radius: 4px;
  font-size: 0.9rem;
}

.logout-btn:hover {
  color: #ef5350;
  background: #ef535022;
}

.content {
  flex: 1;
  padding: 1.5rem 2rem;
  overflow-y: auto;
}
</style>
