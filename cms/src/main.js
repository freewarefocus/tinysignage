import { createApp } from 'vue'
import PrimeVue from 'primevue/config'
import ToastService from 'primevue/toastservice'
import Aura from '@primevue/themes/aura'
import 'primeicons/primeicons.css'

import App from './App.vue'
import router from './router'

const app = createApp(App)

app.use(PrimeVue, {
  theme: {
    preset: Aura,
    options: {
      darkModeSelector: '.dark-mode',
    },
  },
})

app.use(ToastService)
app.use(router)

// Safety net: catch Vue component errors
app.config.errorHandler = (err, instance, info) => {
  console.error('[Vue error]', err, info)
}

// Safety net: catch unhandled promise rejections (e.g. forgotten awaits)
window.addEventListener('unhandledrejection', (event) => {
  console.error('[Unhandled rejection]', event.reason)
})

app.mount('#app')
