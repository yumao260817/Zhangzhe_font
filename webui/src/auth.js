const KEY = 'zz_auth_token'

export function getToken() {
  return localStorage.getItem(KEY) || ''
}

export function setToken(t) {
  if (t) localStorage.setItem(KEY, t)
  else localStorage.removeItem(KEY)
}

export async function api(url, opts = {}) {
  const headers = { ...(opts.headers || {}) }
  const token = getToken()
  if (token) headers.Authorization = `Bearer ${token}`
  const res = await fetch(url, { ...opts, headers })
  return res
}

export async function authHeaders() {
  const headers = {}
  const token = getToken()
  if (token) headers.Authorization = `Bearer ${token}`
  return headers
}
