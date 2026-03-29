<template>
  <div class="app-layout">
    <aside class="sidebar">
      <div class="sidebar-header">
        <h1>TinySignage</h1>
      </div>
      <nav>
        <router-link to="/media" class="nav-item" active-class="active">
          <i class="pi pi-images"></i>
          <span>Media</span>
        </router-link>
        <router-link to="/playlists" class="nav-item" active-class="active">
          <i class="pi pi-list"></i>
          <span>Playlists</span>
        </router-link>
        <router-link to="/groups" class="nav-item" active-class="active">
          <i class="pi pi-sitemap"></i>
          <span>Groups</span>
        </router-link>
        <router-link to="/schedules" class="nav-item" active-class="active">
          <i class="pi pi-calendar"></i>
          <span>Schedules</span>
        </router-link>
        <router-link to="/settings" class="nav-item" active-class="active">
          <i class="pi pi-cog"></i>
          <span>Settings</span>
        </router-link>
        <router-link to="/devices" class="nav-item" active-class="active">
          <i class="pi pi-desktop"></i>
          <span>Devices</span>
        </router-link>
        <router-link to="/system" class="nav-item" active-class="active">
          <i class="pi pi-server"></i>
          <span>System</span>
        </router-link>
      </nav>
      <div class="sidebar-footer">
        <a href="/player" target="_blank" class="nav-item">
          <i class="pi pi-external-link"></i>
          <span>Open Player</span>
        </a>
      </div>
    </aside>
    <main class="content">
      <router-view />
    </main>
    <Toast position="bottom-right" />
  </div>
</template>

<script setup>
import { onMounted, onUnmounted } from 'vue'
import { useToast } from 'primevue/usetoast'
import Toast from 'primevue/toast'
import { errorBus } from './api/client'

const toast = useToast()

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

onMounted(() => {
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

.content {
  flex: 1;
  padding: 1.5rem 2rem;
  overflow-y: auto;
}
</style>
