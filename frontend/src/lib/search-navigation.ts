const FILTER_DEFAULTS = {
  make: '', model: '', model_exact: false, min_price: '', max_price: '',
  min_year: '', max_year: '', max_km: '', fuel_type: '', country: '',
  price_rating: '', sort_by: 'date', page: 1,
}
const EXTRA_FILTERS = ['query', 'min_km', 'transmission', 'body_type', 'source', 'countries']
const SNAPSHOT_KEY = 'autoai_search_snapshots'
const INTERNAL_PAGES = new Set(['/', '/search', '/favorites', '/searches', '/compare', '/analyze', '/import-calculator', '/inbox', '/profile', '/vin'])

export function searchFiltersFromParams(params: { get: (key: string) => string | null }) {
  const filters: Record<string, any> & typeof FILTER_DEFAULTS = { ...FILTER_DEFAULTS }
  for (const key of Object.keys(FILTER_DEFAULTS)) {
    if (key !== 'page' && key !== 'model_exact') filters[key] = params.get(key) || FILTER_DEFAULTS[key as keyof typeof FILTER_DEFAULTS]
  }
  filters.model_exact = params.get('model_exact') === 'true'
  const page = Number(params.get('page'))
  filters.page = Number.isSafeInteger(page) && page > 0 ? page : 1
  for (const key of EXTRA_FILTERS) if (params.get(key)) filters[key] = params.get(key)
  return filters
}

export function searchUrl(filters: Record<string, any>, query = '', pathname = '/search') {
  const params = new URLSearchParams()
  for (const key of [...Object.keys(FILTER_DEFAULTS), ...EXTRA_FILTERS]) {
    const value = filters[key]
    if (value === undefined || value === null || value === '' || value === false) continue
    if (key === 'page' && Number(value) === 1 || key === 'sort_by' && value === 'date') continue
    params.set(key, String(value))
  }
  if (query) params.set('q', query)
  const path = pathname === '/' ? '/' : '/search'
  return path + (params.size ? '?' + params.toString() : '')
}

export function safeReturnUrl(raw: unknown): string | null {
  if (typeof raw !== 'string' || raw.length > 8000 || !raw.startsWith('/') || raw.startsWith('//') || /[\\\u0000-\u0020]/.test(raw)) return null
  try {
    const url = new URL(raw, 'https://autoai.invalid')
    if (url.origin !== 'https://autoai.invalid' || !(INTERNAL_PAGES.has(url.pathname) || /^\/listing\/[a-zA-Z0-9-]+$/.test(url.pathname))) return null
    return url.pathname + url.search
  } catch { return null }
}

export function resolveReturnUrl(explicit: unknown, referrer: string, origin: string, current: string, saved: unknown) {
  try {
    const previous = new URL(referrer)
    const path = safeReturnUrl(previous.pathname + previous.search)
    if (previous.origin === origin && path && path !== current) {
      return previous.pathname === '/' || previous.pathname === '/search' ? safeReturnUrl(explicit) || path : path
    }
  } catch {}
  return safeReturnUrl(explicit) || safeReturnUrl(saved) || '/search'
}

export function listingHref(id: string, returnUrl: string) {
  return `/listing/${encodeURIComponent(id)}?returnTo=${encodeURIComponent(safeReturnUrl(returnUrl) || '/search')}`
}

export function restoreSearchHref(raw: string) {
  const path = safeReturnUrl(raw) || '/search'
  const url = new URL(path, 'https://autoai.invalid')
  if (url.pathname === '/' || url.pathname === '/search') url.searchParams.set('restore', '1')
  return url.pathname + url.search
}

export type SearchSnapshot = {
  url: string; y: number; filterY: number; modelY: number
  otherMakesOpen: boolean; mobileFiltersOpen: boolean
  listingId?: string; listingOffset?: number
}

type SnapshotStorage = { getItem(key: string): string | null; setItem(key: string, value: string): void }
function readSnapshots(storage: SnapshotStorage): SearchSnapshot[] {
  try {
    const data = JSON.parse(storage.getItem(SNAPSHOT_KEY) || '[]')
    return Array.isArray(data) ? data.filter(s => s && safeReturnUrl(s.url) && Number.isFinite(s.y) && s.y >= 0 && Number.isFinite(s.filterY) && s.filterY >= 0).slice(0, 10) : []
  } catch { return [] }
}

export function rememberSearch(storage: SnapshotStorage, snapshot: SearchSnapshot) {
  try {
    if (!safeReturnUrl(snapshot.url)) return
    const previous = readSnapshots(storage).filter(s => s.url !== snapshot.url)
    storage.setItem(SNAPSHOT_KEY, JSON.stringify([snapshot, ...previous].slice(0, 10)))
    storage.setItem('autoai_search_url', snapshot.url)
  } catch {} // Storage may be disabled or full; the URL still retains filters.
}

export function savedSearch(storage: SnapshotStorage, url: string): SearchSnapshot | null {
  try { return readSnapshots(storage).find(s => s.url === url) || null } catch { return null }
}

export function restoredScrollY(snapshot: SearchSnapshot, currentY: number, anchorTop?: number) {
  if (Number.isFinite(anchorTop) && Number.isFinite(snapshot.listingOffset)) {
    return Math.max(0, currentY + anchorTop! - snapshot.listingOffset!)
  }
  return snapshot.y
}
