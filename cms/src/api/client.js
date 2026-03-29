import { getErrorMessage, getErrorSeverity } from './errorMessages'

const BASE = '/api'

/** Event bus for API errors — App.vue listens to this */
export const errorBus = new EventTarget()

function getAuthHeaders() {
  // New key first, fall back to legacy key for migration
  const token = localStorage.getItem('tinysignage_token') || localStorage.getItem('tinysignage_admin_token')
  return token ? { Authorization: `Bearer ${token}` } : {}
}

async function request(method, path, body = null, options = {}) {
  const url = `${BASE}${path}`
  const authHeaders = getAuthHeaders()
  const init = { method, ...options }

  if (body && !(body instanceof FormData)) {
    init.headers = { 'Content-Type': 'application/json', ...authHeaders, ...init.headers }
    init.body = JSON.stringify(body)
  } else if (body instanceof FormData) {
    init.headers = { ...authHeaders, ...init.headers }
    init.body = body
  } else {
    init.headers = { ...authHeaders, ...init.headers }
  }

  let resp
  try {
    resp = await fetch(url, init)
  } catch (networkError) {
    const event = new CustomEvent('api-error', {
      detail: {
        summary: 'Network error — cannot reach the server.',
        severity: 'error',
        sticky: false,
      },
    })
    errorBus.dispatchEvent(event)
    throw networkError
  }

  if (!resp.ok) {
    let serverDetail = null
    try {
      serverDetail = await resp.json()
    } catch {
      // Response wasn't JSON — use status text
    }

    const summary = getErrorMessage(resp.status, serverDetail)
    const severity = getErrorSeverity(resp.status)
    const sticky = resp.status === 401

    // 401: clear tokens and redirect to login
    if (resp.status === 401) {
      localStorage.removeItem('tinysignage_token')
      localStorage.removeItem('tinysignage_admin_token')
      localStorage.removeItem('tinysignage_user')
      // Only redirect if not already on login page
      if (!window.location.pathname.includes('/login')) {
        window.location.href = '/cms/login'
        return
      }
    }

    const event = new CustomEvent('api-error', {
      detail: { summary, severity, sticky, status: resp.status, serverDetail },
    })
    errorBus.dispatchEvent(event)

    const errorMsg = serverDetail?.detail || resp.statusText
    throw new Error(`${resp.status}: ${errorMsg}`)
  }
  return resp.json()
}

export const api = {
  get: (path) => request('GET', path),
  post: (path, body) => request('POST', path, body),
  patch: (path, body) => request('PATCH', path, body),
  put: (path, body) => request('PUT', path, body),
  delete: (path) => request('DELETE', path),
}
