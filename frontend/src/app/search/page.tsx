'use client'
import { Suspense, useState, useEffect, useCallback } from 'react'
import { useSearchParams, useRouter } from 'next/navigation'
import { createAlert, getMakes, getModels, searchListings, parseQuery } from '@/lib/api'

const FUEL_LABELS: Record<string, string> = {
  diesel: 'Dizel', petrol: 'Benzin', electric: 'Električni', hybrid: 'Hibrid', lpg: 'Plin',
}
const BODY_LABELS: Record<string, string> = {
  sedan: 'Sedan', suv: 'SUV', hatchback: 'Hatchback',
  kombi: 'Kombi', coupe: 'Coupé', cabrio: 'Kabriolet',
}
const COUNTRY_LABELS: Record<string, string> = {
  DE: 'Nemačka',
  AT: 'Austrija',
  BE: 'Belgija',
  NL: 'Holandija',
  FR: 'Francuska',
  IT: 'Italija',
}

const SOURCE_LABELS: Record<string, string> = {
  autoscout24: 'Verifikovan izvor',
  willhaben: 'Verifikovan izvor',
  mobile_de: 'Verifikovan izvor',
  demo_seed: 'Demo',
}

const RATING_LABELS: Record<string, {label: string, color: string}> = {
  great:     { label: '🟢 Odlična cena',  color: '#22C55E' },
  good:      { label: '🟡 Dobra cena',    color: '#84CC16' },
  fair:      { label: '⚪ Fer cena',       color: '#6B7280' },
  high:      { label: '🟠 Visoka cena',   color: '#F97316' },
  overpriced:{ label: '🔴 Preskupo',      color: '#EF4444' },
}

const DEFAULT_SEARCH_FILTERS = {
  make: '',
  model: '',
  min_price: '',
  max_price: '',
  min_year: '',
  max_year: '',
  max_km: '',
  fuel_type: '',
  body_type: '',
  country: '',
  source: '',
  price_rating: '',
  sort_by: 'date',
  page: 1,
}

export default function SearchPage() {
  return (
    <Suspense fallback={null}>
      <SearchPageContent />
    </Suspense>
  )
}

function SearchPageContent() {
  const searchParams = useSearchParams()
  const queryString = searchParams.toString()
  const router = useRouter()

  const [results, setResults] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [aiQuery, setAiQuery] = useState(searchParams.get('q') || '')
  const [aiLoading, setAiLoading] = useState(false)
  const [saveMessage, setSaveMessage] = useState('')
  const [isLoggedIn, setIsLoggedIn] = useState(false)
  const [makes, setMakes] = useState<any[]>([])
  const [models, setModels] = useState<any[]>([])
  const [modelsLoading, setModelsLoading] = useState(false)

  const [filters, setFilters] = useState(() => readSearchFilters(searchParams))

  const doSearch = useCallback(async (f: Record<string, any>) => {
    setLoading(true)
    try {
      const data = await searchListings(f)
      setResults(data)
    } catch { setResults(null) }
    finally { setLoading(false) }
  }, [])

  useEffect(() => {
    setIsLoggedIn(Boolean(localStorage.getItem('token')))
    getMakes().then(setMakes).catch(() => setMakes([]))
  }, [])

  useEffect(() => {
    const params = new URLSearchParams(queryString)
    const next = readSearchFilters(params)
    if (!params.has('page')) {
      router.replace(buildSearchUrl(next, params.get('q') || ''), { scroll: false })
      return
    }
    setFilters(next)
    setAiQuery(params.get('q') || '')
    doSearch(next)
  }, [queryString, doSearch, router])

  const pushSearchState = (nextFilters: Record<string, any>, queryText = aiQuery) => {
    router.push(buildSearchUrl(nextFilters, queryText), { scroll: false })
  }

  const setFilter = (key: string, val: any) => {
    const shouldResetPage = key !== 'page'
    const next = {
      ...filters,
      [key]: val,
      ...(key === 'make' ? { model: '' } : {}),
      ...(shouldResetPage ? { page: 1 } : {}),
    }
    setFilters(next)
    pushSearchState(next)
  }

  useEffect(() => {
    if (!filters.make) {
      setModels([])
      return
    }

    setModelsLoading(true)
    getModels(filters.make)
      .then(setModels)
      .catch(() => setModels([]))
      .finally(() => setModelsLoading(false))
  }, [filters.make])

  const handleAiSearch = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!aiQuery.trim()) return
    setAiLoading(true)
    try {
      const { filters: parsed, explanation } = await parseQuery(aiQuery)
      const next = { ...filters, ...parsed, page: 1 }
      setFilters(next)
      pushSearchState(next, aiQuery.trim())
    } finally { setAiLoading(false) }
  }

  const saveSearch = async () => {
    setSaveMessage('')
    if (!localStorage.getItem('token')) {
      const params = new URLSearchParams(
        Object.entries(filters)
          .filter(([, value]) => value !== '')
          .map(([key, value]) => [key, String(value)])
      )
      if (aiQuery.trim()) params.set('q', aiQuery.trim())
      const next = `/search${params.toString() ? `?${params}` : ''}`
      router.push(`/login?next=${encodeURIComponent(next)}`)
      return
    }

    const activeFilters = Object.fromEntries(
      Object.entries(filters).filter(([key, value]) =>
        !['page', 'sort_by'].includes(key) && value !== ''
      )
    )
    const savedFilters = {
      ...activeFilters,
      ...(aiQuery.trim() ? { query_text: aiQuery.trim() } : {}),
    }
    const name = window.prompt('Naziv potrage', aiQuery || buildSearchName(savedFilters))
    if (!name) return

    try {
      await createAlert({ name, filters: savedFilters, frequency: 'daily' })
      setSaveMessage('Potraga je sačuvana u sekciji Moja potraga.')
    } catch (err: any) {
      setSaveMessage(err?.message || 'Potraga nije sačuvana.')
    }
  }

  return (
    <div style={{ padding: '24px 0 60px' }}>
      <div className="container">

        {/* AI Search Bar */}
        <form onSubmit={handleAiSearch} style={{ marginBottom: 28 }}>
          <div style={{
            display: 'flex', gap: 8,
            background: 'var(--bg3)', border: '1px solid var(--border2)',
            borderRadius: 12, padding: 6,
          }}>
            <div style={{ flex: 1, display: 'flex', alignItems: 'center', gap: 10, padding: '0 12px' }}>
              <span style={{ fontSize: 16 }}>🤖</span>
              <input value={aiQuery} onChange={e => setAiQuery(e.target.value)}
                placeholder='Pretraži slobodnim jezikom...'
                style={{ flex: 1, background: 'none', border: 'none', outline: 'none', color: 'var(--text)', fontSize: 15 }}
              />
            </div>
            <button type="submit" disabled={aiLoading} style={{
              background: 'var(--accent)', color: '#fff', border: 'none',
              borderRadius: 8, padding: '10px 20px', fontSize: 14, fontWeight: 600,
            }}>{aiLoading ? '...' : 'AI Pretraga'}</button>
          </div>
        </form>

        <div style={{ display: 'grid', gridTemplateColumns: '240px 1fr', gap: 24, alignItems: 'start' }}>

          {/* Sidebar Filters */}
          <aside style={{
            background: 'var(--bg2)', border: '1px solid var(--border)',
            borderRadius: 'var(--radius)', padding: 20, position: 'sticky', top: 76,
            maxHeight: 'calc(100vh - 96px)', overflowY: 'auto',
          }}>
            <h3 style={{ fontSize: 14, marginBottom: 16, color: 'var(--text2)', letterSpacing: '0.05em' }}>FILTERI</h3>

            <button onClick={saveSearch} style={{
              width: '100%', padding: '10px', borderRadius: 8, marginBottom: 14,
              background: isLoggedIn ? 'var(--accent)' : 'transparent',
              border: isLoggedIn ? 'none' : '1px solid var(--accent)',
              color: isLoggedIn ? '#fff' : 'var(--accent)',
              fontSize: 13, fontWeight: 700, cursor: 'pointer',
            }}>{isLoggedIn ? 'Sačuvaj ovu pretragu' : 'Prijavi se da sačuvaš potragu'}</button>
            {saveMessage && (
              <div style={{ color: 'var(--text3)', fontSize: 12, margin: '-6px 0 14px' }}>
                {saveMessage}
              </div>
            )}

            <FilterSection label="Marka">
              <select value={filters.make} onChange={e => setFilter('make', e.target.value)}
                style={{ ...inputStyle, width: '100%' }}>
                <option value="">Sve marke</option>
                {makes.map((item: any) => (
                  <option key={item.make} value={item.make}>
                    {item.make}{item.count ? ` (${item.count})` : ''}
                  </option>
                ))}
              </select>
            </FilterSection>

            <FilterSection label="Model">
              <select value={filters.model} onChange={e => setFilter('model', e.target.value)}
                disabled={!filters.make || modelsLoading}
                style={{ ...inputStyle, width: '100%', opacity: !filters.make ? 0.65 : 1 }}>
                <option value="">{filters.make ? 'Svi modeli' : 'Prvo izaberi marku'}</option>
                {models.map((item: any) => (
                  <option key={item.model} value={item.model}>
                    {item.model}{item.count ? ` (${item.count})` : ''}
                  </option>
                ))}
              </select>
            </FilterSection>

            <FilterSection label="Zemlja">
              <select value={filters.country} onChange={e => setFilter('country', e.target.value)}
                style={{ ...inputStyle, width: '100%' }}>
                <option value="">Sve zemlje</option>
                {Object.entries(COUNTRY_LABELS).map(([code, label]) => (
                  <option key={code} value={code}>{label}</option>
                ))}
              </select>
            </FilterSection>

            <FilterSection label="Izvor">
              <select value={filters.source} onChange={e => setFilter('source', e.target.value)}
                style={{ ...inputStyle, width: '100%' }}>
                <option value="">Svi izvori</option>
                {Object.entries(SOURCE_LABELS).map(([source, label]) => (
                  <option key={source} value={source}>{label}</option>
                ))}
              </select>
            </FilterSection>

            <FilterSection label="Cena (EUR)">
              <div style={{ display: 'flex', gap: 6 }}>
                <input type="number" placeholder="Od" value={filters.min_price}
                  onChange={e => setFilter('min_price', e.target.value)}
                  style={inputStyle} />
                <input type="number" placeholder="Do" value={filters.max_price}
                  onChange={e => setFilter('max_price', e.target.value)}
                  style={inputStyle} />
              </div>
            </FilterSection>

            <FilterSection label="Godište">
              <div style={{ display: 'flex', gap: 6 }}>
                <input type="number" placeholder="Od" value={filters.min_year}
                  onChange={e => setFilter('min_year', e.target.value)}
                  style={inputStyle} />
                <input type="number" placeholder="Do" value={filters.max_year}
                  onChange={e => setFilter('max_year', e.target.value)}
                  style={inputStyle} />
              </div>
            </FilterSection>

            <FilterSection label="Max km">
              <input type="number" placeholder="npr. 150000" value={filters.max_km}
                onChange={e => setFilter('max_km', e.target.value)}
                style={{ ...inputStyle, width: '100%' }} />
            </FilterSection>

            <FilterSection label="Gorivo">
              {Object.entries(FUEL_LABELS).map(([val, label]) => (
                <FilterChip key={val} label={label} active={filters.fuel_type === val}
                  onClick={() => setFilter('fuel_type', filters.fuel_type === val ? '' : val)} />
              ))}
            </FilterSection>

            <FilterSection label="Karoserija">
              {Object.entries(BODY_LABELS).map(([val, label]) => (
                <FilterChip key={val} label={label} active={filters.body_type === val}
                  onClick={() => setFilter('body_type', filters.body_type === val ? '' : val)} />
              ))}
            </FilterSection>

            <FilterSection label="Ocjena cene">
              {Object.entries(RATING_LABELS).map(([val, {label, color}]) => {
                const count = Number(results?.price_rating_counts?.[val] || 0)
                const active = filters.price_rating === val
                const disabled = count === 0 && !active
                return (
                  <FilterChip key={val} label={`${label} (${count})`} active={active}
                    onClick={() => {
                      if (disabled) return
                      setFilter('price_rating', active ? '' : val)
                    }}
                    color={color}
                    disabled={disabled} />
                )
              })}
            </FilterSection>

            <button onClick={() => {
              const reset = { make:'', model:'', min_price:'', max_price:'', min_year:'', max_year:'', max_km:'', fuel_type:'', body_type:'', country:'', source:'', price_rating:'', sort_by:'date', page:1 }
              setFilters(reset); pushSearchState(reset, '')
            }} style={{
              width: '100%', padding: '10px', borderRadius: 8, marginTop: 8,
              background: 'transparent', border: '1px solid var(--border)',
              color: 'var(--text3)', fontSize: 13, cursor: 'pointer',
            }}>Resetuj filtere</button>
          </aside>

          {/* Results */}
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
              <span style={{ color: 'var(--text2)', fontSize: 14 }}>
                {loading ? 'Učitavam...' : `${results?.total?.toLocaleString() || 0} oglasa`}
              </span>
              <select value={filters.sort_by} onChange={e => setFilter('sort_by', e.target.value)}
                style={{ ...inputStyle, padding: '6px 12px' }}>
                <option value="date">Najnoviji</option>
                <option value="price_asc">Cena ↑</option>
                <option value="price_desc">Cena ↓</option>
                <option value="best_deal">Najbolja ponuda</option>
                <option value="year_desc">Najmlađi</option>
              </select>
            </div>

            {loading ? (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 16 }}>
                {[...Array(6)].map((_, i) => (
                  <div key={i} className="skeleton" style={{ height: 300, borderRadius: 'var(--radius)' }} />
                ))}
              </div>
            ) : results?.results?.length ? (
              <>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 16 }}>
                  {results.results.map((l: any) => <ListingCard key={l.id} listing={l} />)}
                </div>
                {results.pages > 1 && (
                  <Pagination
                    currentPage={filters.page}
                    totalPages={results.pages}
                    onPageChange={(page) => setFilter('page', page)}
                  />
                )}
              </>
            ) : (
              <div style={{ textAlign: 'center', padding: '80px 0', color: 'var(--text3)' }}>
                <div style={{ fontSize: 48, marginBottom: 16 }}>🔍</div>
                <p>Nema rezultata. Pokušaj sa različitim filterima.</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

function Pagination({
  currentPage,
  totalPages,
  onPageChange,
}: {
  currentPage: number
  totalPages: number
  onPageChange: (page: number) => void
}) {
  const page = Math.min(Math.max(1, Number(currentPage) || 1), totalPages)
  const pages = getPaginationItems(page, totalPages)
  const goToPage = (nextPage: number) => {
    const safePage = Math.min(Math.max(1, nextPage), totalPages)
    if (safePage !== page) onPageChange(safePage)
  }

  return (
    <nav aria-label="Paginacija" style={{
      display: 'flex',
      justifyContent: 'center',
      alignItems: 'center',
      gap: 8,
      marginTop: 32,
      flexWrap: 'wrap',
    }}>
      <PaginationButton label="<< Prva" title="Prva stranica" disabled={page === 1} onClick={() => goToPage(1)} />
      <PaginationButton label="< Prethodna" title="Prethodna stranica" disabled={page === 1} onClick={() => goToPage(page - 1)} />

      {pages.map((item) => item === 'ellipsis-start' || item === 'ellipsis-end' ? (
        <span key={item} style={{
          minWidth: 28,
          height: 36,
          display: 'inline-flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: 'var(--text3)',
          fontSize: 14,
        }}>...</span>
      ) : (
        <PaginationButton
          key={item}
          label={String(item)}
          title={`Stranica ${item}`}
          active={page === item}
          onClick={() => goToPage(item)}
        />
      ))}

      <PaginationButton label="> Sledeća" title="Sledeća stranica" disabled={page === totalPages} onClick={() => goToPage(page + 1)} />
      <PaginationButton label=">> Poslednja" title="Poslednja stranica" disabled={page === totalPages} onClick={() => goToPage(totalPages)} />
    </nav>
  )
}

function PaginationButton({
  label,
  title,
  active = false,
  disabled = false,
  onClick,
}: {
  label: string
  title: string
  active?: boolean
  disabled?: boolean
  onClick: () => void
}) {
  return (
    <button
      type="button"
      title={title}
      aria-label={title}
      aria-current={active ? 'page' : undefined}
      disabled={disabled}
      onClick={onClick}
      style={{
        minWidth: label.length > 2 ? 44 : 36,
        height: 36,
        padding: '0 10px',
        borderRadius: 8,
        border: '1px solid var(--border)',
        background: active ? 'var(--accent)' : 'var(--bg2)',
        color: active ? '#fff' : 'var(--text2)',
        fontSize: 14,
        cursor: disabled ? 'not-allowed' : 'pointer',
        opacity: disabled ? 0.45 : 1,
      }}
    >
      {label}
    </button>
  )
}

function getPaginationItems(currentPage: number, totalPages: number) {
  const total = Math.max(1, Number(totalPages) || 1)
  const current = Math.min(Math.max(1, Number(currentPage) || 1), total)
  if (total <= 8) return Array.from({ length: total }, (_, index) => index + 1)

  const items: Array<number | 'ellipsis-start' | 'ellipsis-end'> = [1]
  const start = Math.max(2, current - 2)
  const end = Math.min(total - 1, current + 2)

  if (start > 2) items.push('ellipsis-start')
  for (let page = start; page <= end; page += 1) items.push(page)
  if (end < total - 1) items.push('ellipsis-end')
  items.push(total)

  return items
}

function ListingCard({ listing }: { listing: any }) {
  const rating = RATING_LABELS[listing.price_rating]
  const img = listing.images?.[0]

  return (
    <a href={`/listing/${listing.id}`} style={{
      display: 'block', background: 'var(--bg2)', border: '1px solid var(--border)',
      borderRadius: 'var(--radius)', overflow: 'hidden', transition: 'all .2s',
      textDecoration: 'none',
    }}
    onMouseEnter={e => { const t = e.currentTarget as HTMLElement; t.style.borderColor='var(--accent)'; t.style.transform='translateY(-2px)'; t.style.boxShadow='0 8px 32px rgba(0,0,0,.3)' }}
    onMouseLeave={e => { const t = e.currentTarget as HTMLElement; t.style.borderColor='var(--border)'; t.style.transform='translateY(0)'; t.style.boxShadow='none' }}
    >
      {/* Image */}
      <div style={{ height: 180, background: 'var(--bg3)', position: 'relative', overflow: 'hidden' }}>
        {img ? (
          <img src={img} alt={`${listing.make} ${listing.model}`}
            style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
        ) : (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', fontSize: 40 }}>🚗</div>
        )}
        {rating && (
          <span style={{
            position: 'absolute', top: 10, right: 10,
            background: 'rgba(0,0,0,.8)', borderRadius: 20,
            padding: '3px 10px', fontSize: 11, color: rating.color,
            backdropFilter: 'blur(4px)',
          }}>{rating.label}</span>
        )}
        {listing.special_vehicle && (
          <span style={{
            position: 'absolute', top: rating ? 38 : 10, right: 10,
            background: 'rgba(245, 158, 11, .95)', borderRadius: 20,
            padding: '3px 10px', fontSize: 11, color: '#111827',
            fontWeight: 700,
          }}>⚠️ Specijalno vozilo</span>
        )}
        <span style={{
          position: 'absolute', bottom: 10, left: 10,
          background: 'rgba(0,0,0,.7)', borderRadius: 4, padding: '2px 8px',
          fontSize: 11, color: 'var(--text2)', backdropFilter: 'blur(4px)',
        }}>Verifikovan izvor</span>
      </div>

      {/* Info */}
      <div style={{ padding: 16 }}>
        <h3 style={{ fontSize: 15, marginBottom: 4, fontFamily: 'Syne, sans-serif' }}>
          {listing.year} {listing.make} {listing.model}
        </h3>

        <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, marginBottom: 10 }}>
          <span style={{ fontSize: 20, fontWeight: 700, color: 'var(--accent)' }}>
            {listing.price ? `${Number(listing.price).toLocaleString()} €` : 'Cena na upit'}
          </span>
          {listing.price_estimated && listing.price_delta_pct && (
            <span style={{ fontSize: 12, color: Number(listing.price_delta_pct) < 0 ? '#22C55E' : '#EF4444' }}>
              {Number(listing.price_delta_pct) > 0 ? '+' : ''}{Number(listing.price_delta_pct).toFixed(0)}%
            </span>
          )}
        </div>

        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', fontSize: 12, color: 'var(--text3)' }}>
          {listing.mileage && <span>🛣 {Number(listing.mileage).toLocaleString()} km</span>}
          {listing.fuel_type && <span>⛽ {FUEL_LABELS[listing.fuel_type] || listing.fuel_type}</span>}
          {listing.country && <span>📍 {listing.country}</span>}
        </div>
      </div>
    </a>
  )
}

function FilterSection({ label, children }: { label: string, children: React.ReactNode }) {
  return (
    <div style={{ marginBottom: 20 }}>
      <div style={{ fontSize: 11, color: 'var(--text3)', letterSpacing: '0.08em', marginBottom: 8 }}>{label.toUpperCase()}</div>
      {children}
    </div>
  )
}

function FilterChip({ label, active, onClick, color, disabled = false }: { label: string, active: boolean, onClick: () => void, color?: string, disabled?: boolean }) {
  return (
    <button onClick={onClick} disabled={disabled} style={{
      display: 'inline-block', margin: '0 4px 4px 0',
      padding: '4px 10px', borderRadius: 20, fontSize: 12,
      background: active ? (color ? color + '20' : 'var(--accent)20') : 'transparent',
      border: `1px solid ${active ? (color || 'var(--accent)') : 'var(--border)'}`,
      color: active ? (color || 'var(--accent)') : 'var(--text3)',
      cursor: disabled ? 'not-allowed' : 'pointer',
      opacity: disabled ? 0.45 : 1,
      transition: 'all .15s',
    }}>{label}</button>
  )
}

const inputStyle: React.CSSProperties = {
  flex: 1, background: 'var(--bg3)', border: '1px solid var(--border)',
  borderRadius: 8, padding: '8px 10px', color: 'var(--text)', fontSize: 13, outline: 'none',
}

function buildSearchName(filters: Record<string, any>) {
  const makeModel = [filters.make, filters.model].filter(Boolean).join(' ')
  if (makeModel) return makeModel
  if (filters.query_text) return filters.query_text
  return 'Moja potraga'
}

function readSearchFilters(params: { get: (key: string) => string | null }) {
  return {
    ...DEFAULT_SEARCH_FILTERS,
    make: params.get('make') || '',
    model: params.get('model') || '',
    min_price: params.get('min_price') || '',
    max_price: params.get('max_price') || '',
    min_year: params.get('min_year') || '',
    max_year: params.get('max_year') || '',
    max_km: params.get('max_km') || '',
    fuel_type: params.get('fuel_type') || '',
    body_type: params.get('body_type') || '',
    country: params.get('country') || '',
    source: params.get('source') || '',
    price_rating: params.get('price_rating') || '',
    sort_by: params.get('sort_by') || 'date',
    page: Math.max(1, Number(params.get('page') || 1) || 1),
  }
}

function buildSearchUrl(filters: Record<string, any>, queryText = '') {
  const params = new URLSearchParams()
  Object.entries(filters).forEach(([key, value]) => {
    if (value === null || value === undefined || value === '') return
    if (key === 'sort_by' && value === 'date') return
    params.set(key, String(value))
  })
  if (!params.has('page')) params.set('page', '1')
  if (queryText.trim()) params.set('q', queryText.trim())
  const query = params.toString()
  return `/search${query ? `?${query}` : ''}`
}
