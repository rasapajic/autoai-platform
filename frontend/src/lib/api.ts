const BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1'

async function api(path: string, opts?: RequestInit) {
  const token = typeof window !== 'undefined' ? localStorage.getItem('token') : null
  const res = await fetch(`${BASE}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    ...opts,
  })
  if (!res.ok) throw await res.json()
  return res.json()
}

// ── Pretraga ──────────────────────────────────────────────────
export const searchListings = (params: Record<string, any>) => {
  const q = new URLSearchParams(
    Object.entries(params).filter(([, v]) => v != null && v !== '').map(([k, v]) => [k, String(v)])
  )
  return api(`/search/?${q}`)
}

export const getSearchStats = () => api('/search/stats')
export const getMakes = () => api('/search/makes')
export const getModels = (make: string) => api(`/search/models?make=${encodeURIComponent(make)}`)

// ── Oglasi ────────────────────────────────────────────────────
export const getListing = (id: string) => api(`/listings/${id}`)
export const getPriceHistory = (id: string) => api(`/listings/${id}/price-history`)
export const getSimilar = (id: string) => api(`/listings/${id}/similar`)
export const compareListings = (ids: string[]) => api(`/listings/compare/multi?ids=${ids.join(',')}`)
export const addFavorite = (id: string) => api(`/listings/${id}/favorite`, { method: 'POST' })
export const removeFavorite = (id: string) => api(`/listings/${id}/favorite`, { method: 'DELETE' })

// ── AI ────────────────────────────────────────────────────────
export const parseQuery = (query: string) =>
  api('/ai/parse-query', { method: 'POST', body: JSON.stringify({ query }) })

export const estimatePrice = (data: any) =>
  api('/ai/estimate-price', { method: 'POST', body: JSON.stringify(data) })

export const importCost = (data: any) =>
  api('/ai/import-cost', { method: 'POST', body: JSON.stringify(data) })

export const fraudCheck = (id: string) => api(`/ai/fraud-check/${id}`)

// ── Korisnici ─────────────────────────────────────────────────
export const register = (data: any) =>
  api('/users/register', { method: 'POST', body: JSON.stringify(data) })

export const login = (data: any) =>
  api('/users/login', { method: 'POST', body: JSON.stringify(data) })

export const getProfile = () => api('/users/me')
export const getFavorites = () => api('/users/me/favorites')

// ── Alertovi ──────────────────────────────────────────────────
export const getAlerts = () => api('/alerts/')
export const createAlert = (data: any) =>
  api('/alerts/', { method: 'POST', body: JSON.stringify(data) })
export const deleteAlert = (id: string) => api(`/alerts/${id}`, { method: 'DELETE' })
