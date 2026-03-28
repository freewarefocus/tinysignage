const BASE = '/api'

async function request(method, path, body = null, options = {}) {
  const url = `${BASE}${path}`
  const init = { method, ...options }

  if (body && !(body instanceof FormData)) {
    init.headers = { 'Content-Type': 'application/json', ...init.headers }
    init.body = JSON.stringify(body)
  } else if (body instanceof FormData) {
    init.body = body
  }

  const resp = await fetch(url, init)
  if (!resp.ok) {
    const detail = await resp.text().catch(() => resp.statusText)
    throw new Error(`${resp.status}: ${detail}`)
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
