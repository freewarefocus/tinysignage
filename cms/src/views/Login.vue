<template>
  <div class="login-page">
    <div class="login-card">
      <h1>TinySignage</h1>
      <p class="subtitle">Sign in to manage your displays</p>
      <form @submit.prevent="handleLogin">
        <label for="username">Username</label>
        <input
          id="username"
          v-model="username"
          type="text"
          autocomplete="username"
          required
          :disabled="loading"
        />
        <label for="password">Password</label>
        <input
          id="password"
          v-model="password"
          type="password"
          autocomplete="current-password"
          required
          :disabled="loading"
        />
        <div v-if="error" class="error">{{ error }}</div>
        <button type="submit" :disabled="loading">
          {{ loading ? 'Signing in...' : 'Sign In' }}
        </button>
      </form>
      <p class="recovery-hint">Forgot your password? Ask your TinySignage administrator to reset it from the Users page.</p>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()
const username = ref('')
const password = ref('')
const error = ref('')
const loading = ref(false)

async function handleLogin() {
  error.value = ''
  loading.value = true
  try {
    const resp = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        username: username.value,
        password: password.value,
      }),
    })
    if (!resp.ok) {
      const data = await resp.json().catch(() => ({}))
      error.value = data.detail || 'Login failed'
      return
    }
    const data = await resp.json()
    localStorage.setItem('tinysignage_token', data.token)
    localStorage.setItem('tinysignage_user', JSON.stringify(data.user))
    // Migrate away from old key
    localStorage.removeItem('tinysignage_admin_token')
    router.push('/')
  } catch (err) {
    console.error('[Login] Login failed:', err)
    error.value = 'Cannot reach the server'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  background: #0f1117;
}

.login-card {
  background: #1a1d27;
  padding: 2.5rem;
  border-radius: 12px;
  width: 100%;
  max-width: 380px;
}

.login-card h1 {
  font-size: 1.5rem;
  color: #fff;
  margin-bottom: 0.3rem;
}

.subtitle {
  color: #888;
  font-size: 0.9rem;
  margin-bottom: 1.5rem;
}

label {
  display: block;
  font-size: 0.85rem;
  color: #aaa;
  margin-bottom: 0.3rem;
}

input {
  width: 100%;
  background: #0f1117;
  border: 1px solid #3a3a5a;
  color: #eee;
  padding: 0.6rem;
  border-radius: 4px;
  margin-bottom: 1rem;
  font-size: 0.9rem;
}

input:focus {
  outline: none;
  border-color: #7c83ff;
}

button {
  background: #7c83ff;
  color: #fff;
  border: none;
  padding: 0.7rem 2rem;
  border-radius: 6px;
  cursor: pointer;
  font-size: 1rem;
  width: 100%;
}

button:hover:not(:disabled) {
  background: #6b72e8;
}

button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.error {
  color: #ef5350;
  font-size: 0.85rem;
  margin-bottom: 0.8rem;
}

.recovery-hint {
  color: #666;
  font-size: 0.78rem;
  text-align: center;
  margin-top: 1.2rem;
  line-height: 1.4;
}
</style>
