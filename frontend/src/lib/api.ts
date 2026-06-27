const API_VERSION_PATH = '/api/v1'
const PRODUCTION_API_URL = 'https://autoai-platform-production.up.railway.app'

function getDefaultApiUrl() {
  if (typeof window !== 'undefined' && window.location.hostname) {
    const { hostname, protocol } = window.location
    if (hostname === 'localhost' || hostname === '127.0.0.1') {
      return `${protocol}//${hostname}:8000`
    }
  }
  return PRODUCTION_API_URL
}

function buildApiBase(url: string | undefined) {
  const configuredBase = (url || '').trim()
  const base = (/^https?:\/\//i.test(configuredBase) ? configuredBase : getDefaultApiUrl()).replace(/\/+$/, '')
  return base.endsWith(API_VERSION_PATH) ? base : `${base}${API_VERSION_PATH}`
}

function getApiBase() {
  return buildApiBase(process.env.NEXT_PUBLIC_API_URL)
}

export function formatApiError(err: any): string {
  const detail = err?.detail ?? err?.message ?? err

  if (typeof detail === 'string') return detail

  if (Array.isArray(detail)) {
    const messages = detail
      .map(item => {
        if (typeof item === 'string') return item
        if (item && typeof item.msg === 'string') return item.msg
        if (item && typeof item.message === 'string') return item.message
        return null
      })
      .filter(Boolean)

    if (messages.length) return messages.join(' ')
  }

  return 'Došlo je do greške. Pokušaj ponovo.'
}

async function api(path: string, opts?: RequestInit) {
  const token = typeof window !== 'undefined' ? localStorage.getItem('token') : null
  const url = `${getApiBase()}${path.startsWith('/') ? path : `/${path}`}`
  const res = await fetch(url, {
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    ...opts,
  })
  if (!res.ok) {
    let body: any = null
    try {
      body = await res.json()
    } catch {
      body = { detail: res.statusText }
    }
    throw new Error(formatApiError(body))
  }
  return res.json()
}

// ── Pretraga ──────────────────────────────────────────────────
export const searchListings = (params: Record<string, any>) => {
  const q = new URLSearchParams(
    Object.entries(params).filter(([, v]) => v != null && v !== '').map(([k, v]) => [k, String(v)])
  )
  const query = q.toString()
  return api(`/search${query ? `?${query}` : ''}`).then(data => normalizeSearchResponse(data, params))
}

function normalizeSearchResponse(data: any, params: Record<string, any> = {}) {
  const body = data?.data && !Array.isArray(data.data) ? data.data : data
  const results =
    pickArray(body?.results) ||
    pickArray(body?.items) ||
    pickArray(body?.listings) ||
    pickArray(data?.data) ||
    []

  const page = toPositiveInt(
    body?.page ??
    body?.pagination?.page ??
    body?.meta?.page ??
    params.page,
    1,
  )
  const limit = toPositiveInt(
    body?.limit ??
    body?.per_page ??
    body?.page_size ??
    body?.pagination?.limit ??
    body?.pagination?.per_page ??
    body?.pagination?.page_size ??
    params.limit,
    20,
  )
  const total = toNonNegativeInt(
    body?.total ??
    body?.total_count ??
    body?.count ??
    body?.pagination?.total ??
    body?.meta?.total,
    results.length,
  )
  const pages = toPositiveInt(
    body?.pages ??
    body?.total_pages ??
    body?.pagination?.pages ??
    body?.pagination?.total_pages,
    Math.max(1, Math.ceil(total / limit)),
  )

  return {
    ...body,
    total,
    page,
    pages,
    results,
    filters_applied: body?.filters_applied || {},
    price_rating_counts: body?.price_rating_counts || {},
  }
}

function pickArray(value: any) {
  return Array.isArray(value) ? value : null
}

function toPositiveInt(value: any, fallback: number) {
  const parsed = Number(value)
  if (!Number.isFinite(parsed) || parsed < 1) return fallback
  return Math.floor(parsed)
}

function toNonNegativeInt(value: any, fallback: number) {
  const parsed = Number(value)
  if (!Number.isFinite(parsed) || parsed < 0) return fallback
  return Math.floor(parsed)
}

export const getSearchStats = () => api('/search/stats')
export const getCoverageStats = () => api('/stats/coverage')
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
export const toggleAlert = (id: string) => api(`/alerts/${id}/toggle`, { method: 'PATCH' })
