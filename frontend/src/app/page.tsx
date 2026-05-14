'use client'
import { useState, useEffect, useCallback } from 'react'
import { useSearchParams, useRouter } from 'next/navigation'
import { searchListings, parseQuery } from '@/lib/api'

// ── Constants ─────────────────────────────────────────────────

const FUEL_LABELS: Record<string, string> = {
  diesel: 'Dizel', petrol: 'Benzin', electric: 'Električni',
  hybrid: 'Hibrid', lpg: 'Plin',
}
const BODY_LABELS: Record<string, string> = {
  sedan: 'Sedan', suv: 'SUV', hatchback: 'Hatchback',
  kombi: 'Kombi', coupe: 'Coupé', cabrio: 'Kabriolet',
}
const AI_BADGES: Record<string, { label: string; color: string; bg: string; insight: string }> = {
  great:      { label: '🟢 DOBRA KUPOVINA',  color: '#22C55E', bg: 'rgba(34,197,94,.12)',  insight: 'ispod tržišne cene' },
  good:       { label: '🟡 FER CENA',         color: '#EAB308', bg: 'rgba(234,179,8,.12)',  insight: 'blizu tržišne vrednosti' },
  fair:       { label: '⚪ PROSEČNA CENA',    color: '#9CA3AF', bg: 'rgba(156,163,175,.1)', insight: 'tržišna cena' },
  high:       { label: '🟠 VISOKA CENA',      color: '#F97316', bg: 'rgba(249,115,22,.12)', insight: 'iznad tržišne cene' },
  overpriced: { label: '🔴 PREVISOKA CENA',   color: '#EF4444', bg: 'rgba(239,68,68,.12)',  insight: 'znatno precenjeno' },
}

// ── Import cost calculator (Serbia) ──────────────────────────
function calcSerbiaImport(price: number): number {
  const customs   = price * 0.05
  const vat       = (price + customs) * 0.20
  const transport = 420
  const reg       = 280
  return Math.round(price + customs + vat + transport + reg)
}

// ── Main page ─────────────────────────────────────────────────
export default function SearchPage() {
  const searchParams = useSearchParams()
  const router = useRouter()

  const [results, setResults] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [aiQuery, setAiQuery] = useState(searchParams.get('q') || '')
  const [aiLoading, setAiLoading] = useState(false)
  const [sidebarOpen, setSidebarOpen] = useState(false)

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
    const next = { ...filters, [key]: val, page: key === 'page' ? val : 1 }
    setFilters(next)
    doSearch(next)
  }

  const handleAiSearch = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!aiQuery.trim()) return
    setAiLoading(true)
    try {
      const { filters: parsed } = await parseQuery(aiQuery)
      const next = { ...filters, ...parsed, page: 1 }
      setFilters(next)
      doSearch(next)
    } finally { setAiLoading(false) }
  }

  const activeFiltersCount = [
    filters.make, filters.model, filters.min_price, filters.max_price,
    filters.min_year, filters.max_year, filters.max_km,
    filters.fuel_type, filters.body_type, filters.price_rating,
  ].filter(Boolean).length

  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg)' }}>
      <style>{`
        @media (max-width: 768px) {
          .search-grid { grid-template-columns: 1fr !important; }
          .sidebar-desktop { display: none !important; }
          .results-grid { grid-template-columns: 1fr !important; }
          .hero-text { font-size: 20px !important; }
          .hero-sub { font-size: 13px !important; }
        }
        @media (min-width: 769px) {
          .mobile-filter-btn { display: none !important; }
          .sidebar-mobile { display: none !important; }
        }
        .card-hover:hover { 
          border-color: var(--accent) !important; 
          transform: translateY(-3px) !important; 
          box-shadow: 0 12px 40px rgba(0,0,0,.4) !important; 
        }
        .card-hover { transition: all .2s ease !important; }
        .chip-btn:hover { opacity: .85 !important; }
      `}</style>

      <div className="container" style={{ padding: '24px 16px 80px' }}>

        {/* ── Hero positioning strip ── */}
        <div style={{
          background: 'linear-gradient(135deg, rgba(255,107,0,.08) 0%, rgba(255,107,0,.02) 100%)',
          border: '1px solid rgba(255,107,0,.2)',
          borderRadius: 16, padding: '20px 24px', marginBottom: 20,
          display: 'flex', gap: 16, alignItems: 'center', flexWrap: 'wrap',
        }}>
          <div style={{ flex: 1, minWidth: 200 }}>
            <p className="hero-text" style={{
              fontSize: 22, fontWeight: 700, margin: 0,
              fontFamily: 'Syne, sans-serif', lineHeight: 1.3,
              color: 'var(--text)',
            }}>
              Ne kupuj auto iz EU naslepo
            </p>
            <p className="hero-sub" style={{
              fontSize: 14, color: 'var(--text2)', margin: '6px 0 0',
            }}>
              AI analizira cene · Računa pravi troškak uvoza · Otkriva precenjene ponude
            </p>
          </div>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {['🤖 AI analiza', '🛡️ Zaštita od prevare', '🇷🇸 Troškak uvoza'].map(tag => (
              <span key={tag} style={{
                padding: '6px 12px', borderRadius: 20, fontSize: 12, fontWeight: 500,
                background: 'rgba(255,107,0,.1)', border: '1px solid rgba(255,107,0,.25)',
                color: 'var(--accent)', whiteSpace: 'nowrap',
              }}>{tag}</span>
            ))}
          </div>
        </div>

        {/* ── AI Search Bar ── */}
        <form onSubmit={handleAiSearch} style={{ marginBottom: 24 }}>
          <div style={{
            display: 'flex', gap: 8,
            background: 'var(--bg3)', border: '1px solid var(--border2)',
            borderRadius: 14, padding: 6,
            boxShadow: '0 4px 20px rgba(0,0,0,.2)',
          }}>
            <div style={{ flex: 1, display: 'flex', alignItems: 'center', gap: 10, padding: '4px 14px' }}>
              <span style={{ fontSize: 18 }}>🤖</span>
              <input value={aiQuery} onChange={e => setAiQuery(e.target.value)}
                placeholder='npr. "Golf diesel do 15000€, max 100000km, noviji od 2018"'
                style={{
                  flex: 1, background: 'none', border: 'none', outline: 'none',
                  color: 'var(--text)', fontSize: 15,
                }}
              />
            </div>
            <button type="submit" disabled={aiLoading} style={{
              background: aiLoading ? 'var(--bg2)' : 'var(--accent)',
              color: aiLoading ? 'var(--text3)' : '#fff',
              border: 'none', borderRadius: 10,
              padding: '12px 22px', fontSize: 14, fontWeight: 700,
              cursor: aiLoading ? 'default' : 'pointer', whiteSpace: 'nowrap',
            }}>{aiLoading ? '⏳ Analiziram...' : '🔍 AI Pretraga'}</button>
          </div>
        </form>

        {/* ── Mobile filter toggle ── */}
        <button className="mobile-filter-btn chip-btn" onClick={() => setSidebarOpen(!sidebarOpen)} style={{
          display: 'flex', alignItems: 'center', gap: 8,
          padding: '10px 16px', borderRadius: 10, marginBottom: 16,
          background: activeFiltersCount > 0 ? 'rgba(255,107,0,.1)' : 'var(--bg2)',
          border: `1px solid ${activeFiltersCount > 0 ? 'var(--accent)' : 'var(--border)'}`,
          color: activeFiltersCount > 0 ? 'var(--accent)' : 'var(--text2)',
          fontSize: 14, fontWeight: 600, cursor: 'pointer', width: '100%',
          justifyContent: 'center',
        }}>
          ⚙️ Filteri {activeFiltersCount > 0 && `(${activeFiltersCount} aktivnih)`}
          <span style={{ marginLeft: 'auto' }}>{sidebarOpen ? '▲' : '▼'}</span>
        </button>

        <div className="search-grid" style={{
          display: 'grid', gridTemplateColumns: '260px 1fr', gap: 24, alignItems: 'start',
        }}>

          {/* ── Sidebar ── */}
          <aside className="sidebar-desktop" style={{
            background: 'var(--bg2)', border: '1px solid var(--border)',
            borderRadius: 16, padding: 20, position: 'sticky', top: 80,
          }}>
            <SidebarContent
              filters={filters} setFilter={setFilter}
              onReset={() => {
                const reset = {
                  make:'', model:'', min_price:'', max_price:'', min_year:'',
                  max_year:'', max_km:'', fuel_type:'', body_type:'', country:'',
                  price_rating:'', sort_by:'date', page: 1,
                }
                setFilters(reset); doSearch(reset)
              }}
            />
          </aside>

          {/* ── Mobile sidebar ── */}
          {sidebarOpen && (
            <div className="sidebar-mobile" style={{
              background: 'var(--bg2)', border: '1px solid var(--border)',
              borderRadius: 16, padding: 20, marginBottom: 16,
              gridColumn: '1 / -1',
            }}>
              <SidebarContent
                filters={filters} setFilter={setFilter}
                onReset={() => {
                  const reset = {
                    make:'', model:'', min_price:'', max_price:'', min_year:'',
                    max_year:'', max_km:'', fuel_type:'', body_type:'', country:'',
                    price_rating:'', sort_by:'date', page: 1,
                  }
                  setFilters(reset); doSearch(reset)
                }}
              />
            </div>
          )}

          {/* ── Results ── */}
          <div>
            {/* Results header */}
            <div style={{
              display: 'flex', justifyContent: 'space-between', alignItems: 'center',
              marginBottom: 20, flexWrap: 'wrap', gap: 10,
            }}>
              <div>
                <span style={{ color: 'var(--text)', fontSize: 15, fontWeight: 600 }}>
                  {loading ? '...' : `${results?.total?.toLocaleString() || 0} vozila`}
                </span>
                <span style={{ color: 'var(--text3)', fontSize: 13, marginLeft: 8 }}>
                  {!loading && results?.total > 0 && 'analiziranih AI-om'}
                </span>
              </div>
              <select value={filters.sort_by} onChange={e => setFilter('sort_by', e.target.value)}
                style={{
                  background: 'var(--bg2)', border: '1px solid var(--border)',
                  borderRadius: 8, padding: '8px 12px', color: 'var(--text)',
                  fontSize: 13, outline: 'none', cursor: 'pointer',
                }}>
                <option value="date">Najnoviji</option>
                <option value="best_deal">Najbolja ponuda</option>
                <option value="price_asc">Cena ↑</option>
                <option value="price_desc">Cena ↓</option>
                <option value="year_desc">Najmlađi</option>
              </select>
            </div>

            {/* Cards */}
            {loading ? (
              <div className="results-grid" style={{
                display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: 20,
              }}>
                {[...Array(6)].map((_, i) => (
                  <div key={i} className="skeleton" style={{ height: 360, borderRadius: 16 }} />
                ))}
              </div>
            ) : results?.results?.length ? (
              <>
                <div className="results-grid" style={{
                  display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: 20,
                }}>
                  {results.results.map((l: any) => <ListingCard key={l.id} listing={l} />)}
                </div>

                {results.pages > 1 && (
                  <div style={{ display: 'flex', justifyContent: 'center', gap: 8, marginTop: 40, flexWrap: 'wrap' }}>
                    {[...Array(Math.min(results.pages, 8))].map((_, i) => (
                      <button key={i} onClick={() => setFilter('page', i + 1)} style={{
                        width: 42, height: 42, borderRadius: 10,
                        border: '1px solid var(--border)',
                        background: filters.page === i + 1 ? 'var(--accent)' : 'var(--bg2)',
                        color: filters.page === i + 1 ? '#fff' : 'var(--text2)',
                        fontSize: 14, cursor: 'pointer', fontWeight: 600,
                      }}>{i + 1}</button>
                    ))}
                  </div>
                )}
              </>
            ) : (
              <div style={{
                textAlign: 'center', padding: '80px 20px',
                background: 'var(--bg2)', borderRadius: 16,
                border: '1px solid var(--border)',
              }}>
                <div style={{ fontSize: 52, marginBottom: 16 }}>🔍</div>
                <p style={{ fontSize: 17, fontWeight: 600, marginBottom: 8 }}>Nema rezultata</p>
                <p style={{ color: 'var(--text3)', fontSize: 14 }}>Pokušaj sa različitim filterima ili AI pretragom</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

// ── Listing Card ──────────────────────────────────────────────
function ListingCard({ listing }: { listing: any }) {
  const badge = AI_BADGES[listing.price_rating]
  const img = listing.images?.[0]
  const serbiaTotal = listing.price ? calcSerbiaImport(Number(listing.price)) : null
  const priceDelta = listing.price_delta_pct ? Number(listing.price_delta_pct) : null

  return (
    <a href={`/listing/${listing.id}`} className="card-hover" style={{
      display: 'block', background: 'var(--bg2)',
      border: '1px solid var(--border)',
      borderRadius: 16, overflow: 'hidden',
      textDecoration: 'none', position: 'relative',
    }}>
      {/* AI Badge Bar — full width, dominant */}
      {badge && (
        <div style={{
          background: badge.bg,
          borderBottom: `2px solid ${badge.color}`,
          padding: '8px 14px',
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        }}>
          <span style={{
            color: badge.color, fontSize: 12, fontWeight: 700, letterSpacing: '0.04em',
          }}>{badge.label}</span>
          {priceDelta !== null && (
            <span style={{
              color: priceDelta < 0 ? '#22C55E' : '#EF4444',
              fontSize: 12, fontWeight: 600,
            }}>
              {priceDelta > 0 ? '+' : ''}{priceDelta.toFixed(0)}% vs tržišta
            </span>
          )}
        </div>
      )}

      {/* Image */}
      <div style={{ height: 190, background: 'var(--bg3)', position: 'relative', overflow: 'hidden' }}>
        {img ? (
          <img src={img} alt={`${listing.make} ${listing.model}`}
            style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
        ) : (
          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            height: '100%', fontSize: 48, opacity: .4,
          }}>🚗</div>
        )}
        <span style={{
          position: 'absolute', bottom: 10, left: 10,
          background: 'rgba(0,0,0,.75)', borderRadius: 6, padding: '3px 8px',
          fontSize: 11, color: 'rgba(255,255,255,.7)', backdropFilter: 'blur(4px)',
        }}>{listing.source}</span>
      </div>

      {/* Info */}
      <div style={{ padding: '16px 18px 18px' }}>

        {/* Title */}
        <h3 style={{
          fontSize: 15, fontWeight: 600, margin: '0 0 12px',
          fontFamily: 'Syne, sans-serif', lineHeight: 1.3,
          color: 'var(--text)',
        }}>
          {listing.year && `${listing.year} `}{listing.make} {listing.model}
        </h3>

        {/* Price + Serbia total */}
        <div style={{ marginBottom: 14 }}>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, marginBottom: 6 }}>
            <span style={{ fontSize: 22, fontWeight: 700, color: 'var(--accent)' }}>
              {listing.price ? `${Number(listing.price).toLocaleString()} €` : 'Na upit'}
            </span>
            <span style={{ fontSize: 12, color: 'var(--text3)' }}>EU cena</span>
          </div>

          {serbiaTotal && (
            <div style={{
              background: 'rgba(255,107,0,.07)',
              border: '1px solid rgba(255,107,0,.2)',
              borderRadius: 8, padding: '8px 12px',
              display: 'flex', justifyContent: 'space-between', alignItems: 'center',
            }}>
              <div>
                <div style={{ fontSize: 11, color: 'var(--text3)', marginBottom: 2 }}>
                  🇷🇸 Ukupno za Srbiju
                </div>
                <div style={{ fontSize: 17, fontWeight: 700, color: 'var(--text)' }}>
                  {serbiaTotal.toLocaleString()} €
                </div>
              </div>
              <div style={{ fontSize: 11, color: 'var(--text3)', textAlign: 'right' }}>
                <div>carina + PDV</div>
                <div>+ transport</div>
              </div>
            </div>
          )}
        </div>

        {/* AI insight microcopy */}
        {badge && (
          <div style={{
            fontSize: 12, color: badge.color, marginBottom: 12,
            display: 'flex', alignItems: 'center', gap: 6,
          }}>
            <span style={{
              width: 6, height: 6, borderRadius: '50%',
              background: badge.color, display: 'inline-block', flexShrink: 0,
            }} />
            AI: {priceDelta !== null
              ? `${Math.abs(priceDelta).toFixed(0)}% ${priceDelta < 0 ? 'ispod' : 'iznad'} tržišne cene`
              : badge.insight
            }
          </div>
        )}

        {/* Specs row */}
        <div style={{
          display: 'flex', gap: 10, flexWrap: 'wrap',
          fontSize: 12, color: 'var(--text3)',
          paddingTop: 12, borderTop: '1px solid var(--border)',
        }}>
          {listing.mileage && (
            <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
              🛣 {Number(listing.mileage).toLocaleString()} km
            </span>
          )}
          {listing.fuel_type && (
            <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
              ⛽ {FUEL_LABELS[listing.fuel_type] || listing.fuel_type}
            </span>
          )}
          {listing.country && (
            <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
              📍 {listing.country}
            </span>
          )}
        </div>
      </div>
    </a>
  )
}

// ── Sidebar Content ───────────────────────────────────────────
function SidebarContent({ filters, setFilter, onReset }: any) {
  return (
    <>
      <h3 style={{
        fontSize: 12, marginBottom: 20, color: 'var(--text3)',
        letterSpacing: '0.1em', fontWeight: 600,
      }}>FILTERI</h3>

      <FilterSection label="Cena (EUR)">
        <div style={{ display: 'flex', gap: 6 }}>
          <input type="number" placeholder="Od" value={filters.min_price}
            onChange={e => setFilter('min_price', e.target.value)} style={inputStyle} />
          <input type="number" placeholder="Do" value={filters.max_price}
            onChange={e => setFilter('max_price', e.target.value)} style={inputStyle} />
        </div>
      </FilterSection>

      <FilterSection label="Godište">
        <div style={{ display: 'flex', gap: 6 }}>
          <input type="number" placeholder="Od" value={filters.min_year}
            onChange={e => setFilter('min_year', e.target.value)} style={inputStyle} />
          <input type="number" placeholder="Do" value={filters.max_year}
            onChange={e => setFilter('max_year', e.target.value)} style={inputStyle} />
        </div>
      </FilterSection>

      <FilterSection label="Max km">
        <input type="number" placeholder="npr. 150000" value={filters.max_km}
          onChange={e => setFilter('max_km', e.target.value)}
          style={{ ...inputStyle, width: '100%', boxSizing: 'border-box' }} />
      </FilterSection>

      <FilterSection label="Gorivo">
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
          {Object.entries(FUEL_LABELS).map(([val, label]) => (
            <FilterChip key={val} label={label} active={filters.fuel_type === val}
              onClick={() => setFilter('fuel_type', filters.fuel_type === val ? '' : val)} />
          ))}
        </div>
      </FilterSection>

      <FilterSection label="Karoserija">
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
          {Object.entries(BODY_LABELS).map(([val, label]) => (
            <FilterChip key={val} label={label} active={filters.body_type === val}
              onClick={() => setFilter('body_type', filters.body_type === val ? '' : val)} />
          ))}
        </div>
      </FilterSection>

      <FilterSection label="AI Ocjena">
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          {Object.entries(AI_BADGES).map(([val, { label, color }]) => (
            <FilterChip key={val} label={label} active={filters.price_rating === val}
              onClick={() => setFilter('price_rating', filters.price_rating === val ? '' : val)}
              color={color} fullWidth />
          ))}
        </div>
      </FilterSection>

      <button className="chip-btn" onClick={onReset} style={{
        width: '100%', padding: '11px', borderRadius: 10, marginTop: 4,
        background: 'transparent', border: '1px solid var(--border)',
        color: 'var(--text3)', fontSize: 13, cursor: 'pointer', fontWeight: 500,
      }}>Resetuj filtere</button>
    </>
  )
}

// ── Small components ──────────────────────────────────────────
function FilterSection({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div style={{ marginBottom: 22 }}>
      <div style={{
        fontSize: 11, color: 'var(--text3)', letterSpacing: '0.08em',
        marginBottom: 8, fontWeight: 600,
      }}>{label.toUpperCase()}</div>
      {children}
    </div>
  )
}

function FilterChip({ label, active, onClick, color, fullWidth }: {
  label: string; active: boolean; onClick: () => void; color?: string; fullWidth?: boolean
}) {
  return (
    <button className="chip-btn" onClick={onClick} style={{
      display: fullWidth ? 'block' : 'inline-block',
      width: fullWidth ? '100%' : 'auto',
      textAlign: fullWidth ? 'left' : 'center',
      margin: fullWidth ? '0' : '0',
      padding: fullWidth ? '7px 12px' : '5px 11px',
      borderRadius: fullWidth ? 8 : 20,
      fontSize: 12, fontWeight: active ? 600 : 400,
      background: active ? (color ? color + '20' : 'rgba(255,107,0,.15)') : 'transparent',
      border: `1px solid ${active ? (color || 'var(--accent)') : 'var(--border)'}`,
      color: active ? (color || 'var(--accent)') : 'var(--text3)',
      cursor: 'pointer', transition: 'all .15s',
    }}>{label}</button>
  )
}

const inputStyle: React.CSSProperties = {
  flex: 1, background: 'var(--bg3)', border: '1px solid var(--border)',
  borderRadius: 8, padding: '9px 11px', color: 'var(--text)',
  fontSize: 13, outline: 'none', minWidth: 0,
}
