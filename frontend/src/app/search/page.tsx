'use client'
import { useState, useEffect, useCallback } from 'react'
import { useSearchParams, useRouter } from 'next/navigation'
import { searchListings, parseQuery } from '@/lib/api'

const FUEL_LABELS: Record<string, string> = {
  diesel: 'Dizel', petrol: 'Benzin', electric: 'Električni', hybrid: 'Hibrid', lpg: 'Plin',
}
const BODY_LABELS: Record<string, string> = {
  sedan: 'Sedan', suv: 'SUV', hatchback: 'Hatchback',
  kombi: 'Kombi', coupe: 'Coupé', cabrio: 'Kabriolet',
}
const RATING_LABELS: Record<string, {label: string, color: string}> = {
  great:     { label: '🟢 Odlična cena',  color: '#22C55E' },
  good:      { label: '🟡 Dobra cena',    color: '#84CC16' },
  fair:      { label: '⚪ Fer cena',       color: '#6B7280' },
  high:      { label: '🟠 Visoka cena',   color: '#F97316' },
  overpriced:{ label: '🔴 Preskupo',      color: '#EF4444' },
}

export default function SearchPage() {
  const searchParams = useSearchParams()
  const router = useRouter()

  const [results, setResults] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [aiQuery, setAiQuery] = useState(searchParams.get('q') || '')
  const [aiLoading, setAiLoading] = useState(false)

  const [filters, setFilters] = useState({
    make: searchParams.get('make') || '',
    model: searchParams.get('model') || '',
    min_price: searchParams.get('min_price') || '',
    max_price: searchParams.get('max_price') || '',
    min_year: searchParams.get('min_year') || '',
    max_year: searchParams.get('max_year') || '',
    max_km: searchParams.get('max_km') || '',
    fuel_type: searchParams.get('fuel_type') || '',
    body_type: searchParams.get('body_type') || '',
    country: searchParams.get('country') || '',
    price_rating: searchParams.get('price_rating') || '',
    sort_by: searchParams.get('sort_by') || 'date',
    page: 1,
  })

  const doSearch = useCallback(async (f = filters) => {
    setLoading(true)
    try {
      const data = await searchListings(f)
      setResults(data)
    } catch { setResults(null) }
    finally { setLoading(false) }
  }, [filters])

  useEffect(() => { doSearch() }, [])

  const setFilter = (key: string, val: any) => {
    const next = { ...filters, [key]: val, page: 1 }
    setFilters(next)
    doSearch(next)
  }

  const handleAiSearch = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!aiQuery.trim()) return
    setAiLoading(true)
    try {
      const { filters: parsed, explanation } = await parseQuery(aiQuery)
      const next = { ...filters, ...parsed, page: 1 }
      setFilters(next)
      doSearch(next)
    } finally { setAiLoading(false) }
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
            borderRadius: 'var(--radius)', padding: 20, position: 'sticky', top: 80,
          }}>
            <h3 style={{ fontSize: 14, marginBottom: 16, color: 'var(--text2)', letterSpacing: '0.05em' }}>FILTERI</h3>

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
              {Object.entries(RATING_LABELS).map(([val, {label, color}]) => (
                <FilterChip key={val} label={label} active={filters.price_rating === val}
                  onClick={() => setFilter('price_rating', filters.price_rating === val ? '' : val)}
                  color={color} />
              ))}
            </FilterSection>

            <button onClick={() => {
              const reset = { make:'', model:'', min_price:'', max_price:'', min_year:'', max_year:'', max_km:'', fuel_type:'', body_type:'', country:'', price_rating:'', sort_by:'date', page:1 }
              setFilters(reset); doSearch(reset)
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
                  <div style={{ display: 'flex', justifyContent: 'center', gap: 8, marginTop: 32 }}>
                    {[...Array(Math.min(results.pages, 8))].map((_, i) => (
                      <button key={i} onClick={() => setFilter('page', i + 1)} style={{
                        width: 36, height: 36, borderRadius: 8, border: '1px solid var(--border)',
                        background: filters.page === i + 1 ? 'var(--accent)' : 'var(--bg2)',
                        color: filters.page === i + 1 ? '#fff' : 'var(--text2)',
                        fontSize: 14, cursor: 'pointer',
                      }}>{i + 1}</button>
                    ))}
                  </div>
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
        <span style={{
          position: 'absolute', bottom: 10, left: 10,
          background: 'rgba(0,0,0,.7)', borderRadius: 4, padding: '2px 8px',
          fontSize: 11, color: 'var(--text2)', backdropFilter: 'blur(4px)',
        }}>{listing.source}</span>
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

function FilterChip({ label, active, onClick, color }: { label: string, active: boolean, onClick: () => void, color?: string }) {
  return (
    <button onClick={onClick} style={{
      display: 'inline-block', margin: '0 4px 4px 0',
      padding: '4px 10px', borderRadius: 20, fontSize: 12,
      background: active ? (color ? color + '20' : 'var(--accent)20') : 'transparent',
      border: `1px solid ${active ? (color || 'var(--accent)') : 'var(--border)'}`,
      color: active ? (color || 'var(--accent)') : 'var(--text3)',
      cursor: 'pointer', transition: 'all .15s',
    }}>{label}</button>
  )
}

const inputStyle: React.CSSProperties = {
  flex: 1, background: 'var(--bg3)', border: '1px solid var(--border)',
  borderRadius: 8, padding: '8px 10px', color: 'var(--text)', fontSize: 13, outline: 'none',
}
