import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/login',
    name: 'login',
    component: () => import('../views/Login.vue'),
    meta: { public: true },
  },
  {
    path: '/',
    redirect: '/devices',
  },
  {
    path: '/media',
    name: 'media',
    component: () => import('../views/MediaLibrary.vue'),
  },
  {
    path: '/designer/:assetId?',
    name: 'designer',
    component: () => import('../views/PageDesigner.vue'),
  },
  {
    path: '/playlists',
    name: 'playlists',
    component: () => import('../views/PlaylistList.vue'),
  },
  {
    path: '/playlists/:id',
    name: 'playlist-editor',
    component: () => import('../views/PlaylistEditor.vue'),
  },
  {
    // Backward compat: old single-playlist route redirects to list
    path: '/playlist',
    redirect: '/playlists',
  },
  {
    path: '/layouts',
    name: 'layouts',
    component: () => import('../views/LayoutEditor.vue'),
  },
  {
    path: '/groups',
    name: 'groups',
    component: () => import('../views/DeviceGroups.vue'),
  },
  {
    path: '/schedules',
    name: 'schedules',
    component: () => import('../views/ScheduleEditor.vue'),
  },
  {
    path: '/settings',
    name: 'settings',
    component: () => import('../views/Settings.vue'),
  },
  {
    path: '/storage',
    name: 'storage',
    component: () => import('../views/StorageDashboard.vue'),
  },
  {
    path: '/devices',
    name: 'devices',
    component: () => import('../views/DeviceInfo.vue'),
  },
  {
    // Backward compat: old single-device route redirects to dashboard
    path: '/device',
    redirect: '/devices',
  },
  {
    path: '/system',
    name: 'system',
    component: () => import('../views/SystemLog.vue'),
  },
  {
    path: '/overrides',
    name: 'overrides',
    component: () => import('../views/EmergencyOverrides.vue'),
    meta: { requiresAdmin: true },
  },
  {
    path: '/audit',
    name: 'audit',
    component: () => import('../views/AuditLog.vue'),
    meta: { requiresAdmin: true },
  },
  {
    path: '/users',
    name: 'users',
    component: () => import('../views/UserManagement.vue'),
    meta: { requiresAdmin: true },
  },
]

const router = createRouter({
  history: createWebHistory('/cms/'),
  routes,
})

router.beforeEach((to) => {
  // Public routes (login) don't need auth
  if (to.meta.public) return true

  // Check for auth token
  const token = localStorage.getItem('tinysignage_token') || localStorage.getItem('tinysignage_admin_token')
  if (!token) {
    return { name: 'login' }
  }

  // Check admin requirement
  if (to.meta.requiresAdmin) {
    const user = JSON.parse(localStorage.getItem('tinysignage_user') || '{}')
    if (user.role !== 'admin') {
      return { name: 'devices' }
    }
  }

  return true
})

export default router
