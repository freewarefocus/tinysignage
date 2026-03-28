import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    redirect: '/media',
  },
  {
    path: '/media',
    name: 'media',
    component: () => import('../views/MediaLibrary.vue'),
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
    path: '/devices',
    name: 'devices',
    component: () => import('../views/DeviceInfo.vue'),
  },
  {
    // Backward compat: old single-device route redirects to dashboard
    path: '/device',
    redirect: '/devices',
  },
]

const router = createRouter({
  history: createWebHistory('/cms/'),
  routes,
})

export default router
