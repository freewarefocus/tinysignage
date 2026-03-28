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
    path: '/playlist',
    name: 'playlist',
    component: () => import('../views/PlaylistEditor.vue'),
  },
  {
    path: '/settings',
    name: 'settings',
    component: () => import('../views/Settings.vue'),
  },
  {
    path: '/device',
    name: 'device',
    component: () => import('../views/DeviceInfo.vue'),
  },
]

const router = createRouter({
  history: createWebHistory('/cms/'),
  routes,
})

export default router
