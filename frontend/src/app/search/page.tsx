'use client'
import { useState, useEffect, useCallback } from 'react'
import { useSearchParams } from 'next/navigation'
import { searchListings, parseQuery } from '@/lib/api'
import ContactModal from '@/components/ContactModal'

const FUEL_LABELS: Record<string, string> = {
  diesel: 'Dizel', petrol: 'Benzin', electric: 'Električni',
  hybrid: 'Hibrid', lpg: 'Plin',
}
const BODY_LABELS: Record<string, string> = {
  sedan: 'Sedan', suv: 'SUV', hatchback: 'Hatchback',
  kombi: 'Kombi', coupe: 'Coupé', cabrio: 'Kabriolet',
}
const AI_BADGES: Record<string, { label: string; color: string; bg: string }> = {
  great:      { label: '🟢 DOBRA KUPOVINA',  color: '#22C55E', bg: 'rgba(34,197,94,.13)'   },
  good:       { label: '🟡 FER CENA',         color: '#EAB308', bg: 'rgba(234,179,8,.13)'   },
  fair:       { label: '⚪ PROSEČNA CENA',    color: '#9CA3AF', bg: 'rgba(156,163,175,.10)' },
  high:       { label: '🟠 VISOKA CENA',      color: '#F97316', bg: 'rgba(249,115,22,.13)'  },
  overpriced: { label: '🔴 PREVISOKA CENA',   color: '#EF4444', bg: 'rgba(239,68,68,.13)'   },
}

function calcBreakdown(price: number) {
  const carina    = Math.round(price * 0.05)
  const pdv       = Math.round((price + carina) * 0.20)
  const transport = 420
  const reg       = 280
  return { carina, pdv, transport, reg, total: price + carina + pdv + transport + reg }
}

function getInsight(listing: any): string | null {
  const delta = listing.price_delta_pct ? Number(listing.price_delta_pct) : null
  const km    = listing.mileage ? Number(listing.mileage) : null
  const year  = listing.year ? Number(listing.year) : null
  const now   = new Date().getFullYear()
  if (delta !== null) {
    if (delta < -10) return `${Math.abs(delta).toFixed(0)}% ispod tržišne cene`
    if (delta < -3)  return `Malo ispod tržišne vrednosti`
    if (delta > 15)  return `Cena znatno iznad tržišta`
    if (delta > 5)   return `Cena iznad proseka za godište`
  }
  if (year && now - year <= 2) return 'Mlado vozilo, niska amortizacija'
  if (km && km < 50000)        return 'Niska kilometraža za godište'
  if (km && km > 200000)       return 'Visoka kilometraža — pažljivo proveriti'
  if (listing.fuel_type === 'electric') return 'Električno — bez carine u Srbiji'
  return null
}

export default function SearchPage() {
  const searchParams = useSearchParams()
  const [results,     setResults]     = useState<any>(null)
  const [loading,     setLoading]     = useState(true)
  const [aiQuery,     setAiQuery]     = useState(searchParams.get('q') || '')
  const [aiLoading,   setAiLoading]   = useState(false)
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [contactListing, setContactListing] = useState<any>(null)

  const [filters, setFilters] = useState({
    make: searchParams.get('make') || '', model: searchParams.get('model') || '',
    min_price: searchParams.get('min_price') || '', max_price: searchParams.get('max_price') || '',
    min_year: searchParams.get('min_year') || '', max_year: searchParams.get('max_year') || '',
    max_km: searchParams.get('max_km') || '', fuel_type: searchParams.get('fuel_type') || '',
    body_type: searchParams.get('body_type') || '', country: searchParams.get('country') || '',
    price_rating: searchParams.get('price_rating') || '', sort_by: searchParams.get('sort_by') || 'date',
    page: 1,
  })

  const doSearch = useCallback(async (f = filters) => {
    setLoading(true)
    try   { const data = await searchListings(f); setResults(data) }
    catch { setResults(null) }
    finally { setLoading(false) }
  }, [filters])

  useEffect(() => { doSearch() }, [])

  const setFilter = (key: string, val: any) => {
    const next = { ...filters, [key]: val, page: key === 'page' ? val : 1 }
    setFilters(next); doSearch(next)
  }

  const handleAiSearch = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!aiQuery.trim()) return
    setAiLoading(true)
    try {
      const { filters: parsed } = await parseQuery(aiQuery)
      const next = { ...filters, ...parsed, page: 1 }
      setFilters(next); doSearch(next)
    } finally { setAiLoading(false) }
  }

  const activeCount = [
    filters.make, filters.model, filters.min_price, filters.max_price,
    filters.min_year, filters.max_year, filters.max_km,
    filters.fuel_type, filters.body_type, filters.price_rating,
  ].filter(Boolean).length

  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg)' }}>
      <style>{`
        @media(max-width:768px){.sg{grid-template-columns:1fr!important}.rg{grid-template-columns:1fr!important}.sd{display:none!important}.ht{font-size:18px!important}}
        @media(min-width:769px){.mfb{display:none!important}.sm{display:none!important}}
        .ch{transition:all .22s ease!important}
        .ch:hover{border-color:var(--accent)!important;transform:translateY(-3px)!important;box-shadow:0 14px 44px rgba(0,0,0,.45)!important}
        .cb:hover{opacity:.82!important}
      `}</style>

      {contactListing && (
        <ContactModal listing={contactListing} onClose={() => setContactListing(null)} />
      )}

      <div className="container" style={{ padding: '20px 16px 80px' }}>

        {/* Hero */}
        <div style={{
          background: 'linear-gradient(135deg,rgba(255,107,0,.09),rgba(255,107,0,.03))',
          border: '1px solid rgba(255,107,0,.22)', borderRadius: 16,
          padding: '18px 22px', marginBottom: 18,
          display: 'flex', gap: 16, alignItems: 'center', flexWrap: 'wrap',
        }}>
          <div style={{ flex: 1, minWidth: 180 }}>
            <p className="ht" style={{ fontSize: 21, fontWeight: 700, margin: 0, fontFamily: 'Syne,sans-serif', lineHeight: 1.3 }}>
              Ne kupuj auto iz EU naslepo
            </p>
            <p style={{ fontSize: 13, color: 'var(--text2)', margin: '5px 0 0' }}>
              AI analizira cene · Računa pravi trošak uvoza · Otkriva precenjene ponude
            </p>
          </div>
          <div style={{ display: 'flex', gap: 7, flexWrap: 'wrap' }}>
            {['🤖 AI analiza', '🛡 Zaštita od prevare', '🇷🇸 Trošak uvoza', '✉️ AI kontakt'].map(t => (
              <span key={t} style={{
                padding: '5px 11px', borderRadius: 20, fontSize: 12, fontWeight: 500,
                background: 'rgba(255,107,0,.1)', border: '1px solid rgba(255,107,0,.25)',
                color: 'var(--accent)', whiteSpace: 'nowrap',
              }}>{t}</span>
            ))}
          </div>
        </div>

        {/* Search */}
        <form onSubmit={handleAiSearch} style={{ marginBottom: 22 }}>
          <div style={{
            display: 'flex', gap: 8, background: 'var(--bg3)',
            border: '1px solid var(--border2)', borderRadius: 14, padding: 6,
            boxShadow: '0 4px 20px rgba(0,0,0,.2)',
          }}>
            <div style={{ flex: 1, display: 'flex', alignItems: 'center', gap: 10, padding: '4px 14px' }}>
              <span style={{ fontSize: 17 }}>🤖</span>
              <input value={aiQuery} onChange={e => setAiQuery(e.target.value)}
                placeholder='npr. "Golf diesel do 15000€, max 100000km, noviji od 2018"'
                style={{ flex: 1, background: 'none', border: 'none', outline: 'none', color: 'var(--text)', fontSize: 15 }} />
            </div>
            <button type="submit" disabled={aiLoading} style={{
              background: aiLoading ? 'var(--bg2)' : 'var(--accent)', color: aiLoading ? 'var(--text3)' : '#fff',
              border: 'none', borderRadius: 10, padding: '12px 22px', fontSize: 14, fontWeight: 700,
              cursor: aiLoading ? 'default' : 'pointer', whiteSpace: 'nowrap',
            }}>{aiLoading ? '⏳ Analiziram...' : '🔍 AI Pretraga'}</button>
          </div>
        </form>

        {/* Mobile filter */}
        <button className="mfb cb" onClick={() => setSidebarOpen(!sidebarOpen)} style={{
          display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
          padding: '11px 16px', borderRadius: 10, marginBottom: 16, width: '100%',
          background: activeCount > 0 ? 'rgba(255,107,0,.1)' : 'var(--bg2)',
          border: `1px solid ${activeCount > 0 ? 'var(--accent)' : 'var(--border)'}`,
          color: activeCount > 0 ? 'var(--accent)' : 'var(--text2)',
          fontSize: 14, fontWeight: 600, cursor: 'pointer',
        }}>⚙️ Filteri {activeCount > 0 && `(${activeCount})`} {sidebarOpen ? '▲' : '▼'}</button>

        <div className="sg" style={{ display: 'grid', gridTemplateColumns: '260px 1fr', gap: 24, alignItems: 'start' }}>

          <aside className="sd" style={{ background: 'var(--bg2)', border: '1px solid var(--border)', borderRadius: 16, padding: 20, position: 'sticky', top: 80 }}>
            <Sidebar filters={filters} setFilter={setFilter} onReset={() => {
              const r = { make:'',model:'',min_price:'',max_price:'',min_year:'',max_year:'',max_km:'',fuel_type:'',body_type:'',country:'',price_rating:'',sort_by:'date',page:1 }
              setFilters(r); doSearch(r)
            }} />
          </aside>

          {sidebarOpen && (
            <div className="sm" style={{ background: 'var(--bg2)', border: '1px solid var(--border)', borderRadius: 16, padding: 20, marginBottom: 16, gridColumn: '1/-1' }}>
              <Sidebar filters={filters} setFilter={setFilter} onReset={() => {
                const r = { make:'',model:'',min_price:'',max_price:'',min_year:'',max_year:'',max_km:'',fuel_type:'',body_type:'',country:'',price_rating:'',sort_by:'date',page:1 }
                setFilters(r); doSearch(r)
              }} />
            </div>
          )}

          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20, flexWrap: 'wrap', gap: 10 }}>
              <div>
                <span style={{ fontSize: 15, fontWeight: 600 }}>{loading ? '...' : `${results?.total?.toLocaleString() || 0} vozila`}</span>
                {!loading && results?.total > 0 && <span style={{ color: 'var(--text3)', fontSize: 13, marginLeft: 8 }}>analiziranih AI-om</span>}
              </div>
              <select value={filters.sort_by} onChange={e => setFilter('sort_by', e.target.value)}
                style={{ background: 'var(--bg2)', border: '1px solid var(--border)', borderRadius: 8, padding: '8px 12px', color: 'var(--text)', fontSize: 13, outline: 'none', cursor: 'pointer' }}>
                <option value="date">Najnoviji</option>
                <option value="best_deal">Najbolja ponuda</option>
                <option value="price_asc">Cena ↑</option>
                <option value="price_desc">Cena ↓</option>
                <option value="year_desc">Najmlađi</option>
              </select>
            </div>

            {loading ? (
              <div className="rg" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(300px,1fr))', gap: 20 }}>
                {[...Array(6)].map((_,i) => <div key={i} className="skeleton" style={{ height: 460, borderRadius: 16 }} />)}
              </div>
            ) : results?.results?.length ? (
              <>
                <div className="rg" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(300px,1fr))', gap: 20 }}>
                  {results.results.map((l: any) => (
                    <ListingCard key={l.id} listing={l} onContact={() => setContactListing(l)} />
                  ))}
                </div>
                {results.pages > 1 && (
                  <div style={{ display: 'flex', justifyContent: 'center', gap: 8, marginTop: 40, flexWrap: 'wrap' }}>
                    {[...Array(Math.min(results.pages, 8))].map((_,i) => (
                      <button key={i} onClick={() => setFilter('page', i+1)} style={{
                        width: 42, height: 42, borderRadius: 10, border: '1px solid var(--border)',
                        background: filters.page === i+1 ? 'var(--accent)' : 'var(--bg2)',
                        color: filters.page === i+1 ? '#fff' : 'var(--text2)',
                        fontSize: 14, cursor: 'pointer', fontWeight: 600,
                      }}>{i+1}</button>
                    ))}
                  </div>
                )}
              </>
            ) : (
              <div style={{ textAlign: 'center', padding: '80px 20px', background: 'var(--bg2)', borderRadius: 16, border: '1px solid var(--border)' }}>
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

function ListingCard({ listing, onContact }: { listing: any; onContact: () => void }) {
  const badge   = AI_BADGES[listing.price_rating]
  const insight = getInsight(listing)
  const img     = listing.images?.[0]
  const price   = listing.price ? Number(listing.price) : null
  const bd      = price ? calcBreakdown(price) : null
  const delta   = listing.price_delta_pct ? Number(listing.price_delta_pct) : null
  const [showBd, setShowBd] = useState(false)

  return (
    <div className="ch" style={{ background: 'var(--bg2)', border: '1px solid var(--border)', borderRadius: 16, overflow: 'hidden' }}>

      {/* AI Badge */}
      {badge ? (
        <div style={{ background: badge.bg, borderBottom: `2px solid ${badge.color}`, padding: '9px 16px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span style={{ color: badge.color, fontSize: 13, fontWeight: 800, letterSpacing: '.03em' }}>{badge.label}</span>
          {delta !== null && (
            <span style={{ color: delta < 0 ? '#22C55E' : '#EF4444', fontSize: 12, fontWeight: 600 }}>
              {delta > 0 ? '+' : ''}{delta.toFixed(0)}% vs tržišta
            </span>
          )}
        </div>
      ) : (
        <div style={{ background: 'rgba(99,102,241,.07)', borderBottom: '2px solid rgba(99,102,241,.2)', padding: '9px 16px' }}>
          <span style={{ color: '#818CF8', fontSize: 12, fontWeight: 700 }}>🤖 AI ANALIZA U TOKU</span>
        </div>
      )}

      {/* Image */}
      <a href={`/listing/${listing.id}`} style={{ display: 'block', textDecoration: 'none' }}>
        <div style={{ height: 185, background: 'var(--bg3)', position: 'relative', overflow: 'hidden' }}>
          {img
            ? <img src={img} alt={`${listing.make} ${listing.model}`} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
            : <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', fontSize: 48, opacity: .35 }}>🚗</div>
          }
          <span style={{ position: 'absolute', bottom: 10, left: 10, background: 'rgba(0,0,0,.75)', borderRadius: 6, padding: '3px 8px', fontSize: 11, color: 'rgba(255,255,255,.65)', backdropFilter: 'blur(4px)' }}>
            {listing.source}
          </span>
        </div>

        <div style={{ padding: '16px 18px 0' }}>
          <h3 style={{ fontSize: 15, fontWeight: 600, margin: '0 0 4px', fontFamily: 'Syne,sans-serif', lineHeight: 1.3, color: 'var(--text)' }}>
            {listing.year && `${listing.year} `}{listing.make} {listing.model}
          </h3>
          {insight && (
            <p style={{ fontSize: 12, color: badge?.color || '#818CF8', margin: '0 0 12px', display: 'flex', alignItems: 'center', gap: 5 }}>
              <span style={{ width: 5, height: 5, borderRadius: '50%', background: badge?.color || '#818CF8', display: 'inline-block', flexShrink: 0 }} />
              {insight}
            </p>
          )}
        </div>
      </a>

      <div style={{ padding: '0 18px 18px' }}>
        {/* EU price */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
          <span style={{ fontSize: 12, color: 'var(--text3)' }}>EU cena:</span>
          <span style={{ fontSize: 18, fontWeight: 700, color: 'var(--text2)' }}>
            {price ? `${price.toLocaleString()} €` : 'Na upit'}
          </span>
        </div>

        {/* Serbia cost */}
        {bd && (
          <div style={{ background: 'rgba(255,107,0,.07)', border: '1px solid rgba(255,107,0,.2)', borderRadius: 10, overflow: 'hidden', marginBottom: 12 }}>
            <button onClick={() => setShowBd(!showBd)} className="cb" style={{
              width: '100%', background: 'none', border: 'none', cursor: 'pointer',
              padding: '10px 14px', display: 'flex', justifyContent: 'space-between', alignItems: 'center',
            }}>
              <div style={{ textAlign: 'left' }}>
                <div style={{ fontSize: 11, color: 'var(--text3)', marginBottom: 2 }}>🇷🇸 Ukupno za Srbiju</div>
                <div style={{ fontSize: 19, fontWeight: 800, color: 'var(--accent)' }}>{bd.total.toLocaleString()} €</div>
              </div>
              <span style={{ fontSize: 11, color: 'rgba(255,107,0,.6)' }}>{showBd ? '▲ sakrij' : '▼ detalji'}</span>
            </button>

            {showBd && (
              <div style={{ padding: '0 14px 12px', borderTop: '1px solid rgba(255,107,0,.15)' }}>
                <div style={{ fontSize: 11, color: 'var(--text3)', margin: '8px 0' }}>Kako je izračunato:</div>
                {[
                  { label: 'EU cena',         val: price!,      note: '' },
                  { label: 'Carina (5%)',      val: bd.carina,   note: 'srbija' },
                  { label: 'PDV (20%)',        val: bd.pdv,      note: 'srbija' },
                  { label: 'Transport EU→RS',  val: bd.transport,note: 'procena' },
                  { label: 'Registracija',     val: bd.reg,      note: 'procena' },
                ].map(({ label, val, note }, i) => (
                  <div key={i} style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0', borderTop: i === 0 ? 'none' : '1px solid rgba(255,255,255,.04)' }}>
                    <span style={{ fontSize: 12, color: i === 0 ? 'var(--text2)' : 'var(--text3)' }}>
                      {i > 0 && '+ '}{label}
                      {note && <span style={{ fontSize: 10, marginLeft: 4, opacity: .5 }}>({note})</span>}
                    </span>
                    <span style={{ fontSize: 12, fontWeight: 500, color: i === 0 ? 'var(--text2)' : '#fb923c' }}>
                      {i === 0 ? '' : '+'}{val.toLocaleString()} €
                    </span>
                  </div>
                ))}
                <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 8, paddingTop: 8, borderTop: '1px solid rgba(255,107,0,.25)' }}>
                  <span style={{ fontSize: 13, fontWeight: 700 }}>Ukupno Srbija</span>
                  <span style={{ fontSize: 15, fontWeight: 800, color: 'var(--accent)' }}>{bd.total.toLocaleString()} €</span>
                </div>
                <p style={{ fontSize: 10, color: 'var(--text3)', margin: '8px 0 0', lineHeight: 1.4 }}>
                  * Procena na osnovu standardnih stopa. Stvarni troškovi mogu varirati.
                </p>
              </div>
            )}
          </div>
        )}

        {/* Specs */}
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', fontSize: 12, color: 'var(--text3)', paddingBottom: 12, borderBottom: '1px solid var(--border)' }}>
          {listing.mileage && <span>🛣 {Number(listing.mileage).toLocaleString()} km</span>}
          {listing.fuel_type && <span>⛽ {FUEL_LABELS[listing.fuel_type] || listing.fuel_type}</span>}
          {listing.country && <span>📍 {listing.country}</span>}
        </div>

        {/* Contact button */}
        <button onClick={onContact} className="cb" style={{
          width: '100%', marginTop: 12, padding: '11px',
          background: 'rgba(99,102,241,.1)', border: '1px solid rgba(99,102,241,.3)',
          color: '#818CF8', borderRadius: 10,
          fontSize: 13, fontWeight: 600, cursor: 'pointer',
        }}>
          🤖 Kontaktiraj prodavca
        </button>
      </div>
    </div>
  )
}

function Sidebar({ filters, setFilter, onReset }: any) {
  return (
    <>
      <h3 style={{ fontSize: 11, marginBottom: 20, color: 'var(--text3)', letterSpacing: '.1em', fontWeight: 600 }}>FILTERI</h3>
      <FS label="Cena (EUR)">
        <div style={{ display: 'flex', gap: 6 }}>
          <input type="number" placeholder="Od" value={filters.min_price} onChange={e => setFilter('min_price', e.target.value)} style={IS} />
          <input type="number" placeholder="Do" value={filters.max_price} onChange={e => setFilter('max_price', e.target.value)} style={IS} />
        </div>
      </FS>
      <FS label="Godište">
        <div style={{ display: 'flex', gap: 6 }}>
          <input type="number" placeholder="Od" value={filters.min_year} onChange={e => setFilter('min_year', e.target.value)} style={IS} />
          <input type="number" placeholder="Do" value={filters.max_year} onChange={e => setFilter('max_year', e.target.value)} style={IS} />
        </div>
      </FS>
      <FS label="Max km">
        <input type="number" placeholder="npr. 150000" value={filters.max_km} onChange={e => setFilter('max_km', e.target.value)} style={{ ...IS, width: '100%', boxSizing: 'border-box' as any }} />
      </FS>
      <FS label="Gorivo">
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
          {Object.entries(FUEL_LABELS).map(([v,l]) => <FC key={v} label={l} active={filters.fuel_type===v} onClick={()=>setFilter('fuel_type',filters.fuel_type===v?'':v)} />)}
        </div>
      </FS>
      <FS label="Karoserija">
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
          {Object.entries(BODY_LABELS).map(([v,l]) => <FC key={v} label={l} active={filters.body_type===v} onClick={()=>setFilter('body_type',filters.body_type===v?'':v)} />)}
        </div>
      </FS>
      <FS label="AI Ocjena">
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          {Object.entries(AI_BADGES).map(([v,{label,color}]) => <FC key={v} label={label} active={filters.price_rating===v} onClick={()=>setFilter('price_rating',filters.price_rating===v?'':v)} color={color} full />)}
        </div>
      </FS>
      <button className="cb" onClick={onReset} style={{ width: '100%', padding: 11, borderRadius: 10, marginTop: 4, background: 'transparent', border: '1px solid var(--border)', color: 'var(--text3)', fontSize: 13, cursor: 'pointer', fontWeight: 500 }}>
        Resetuj filtere
      </button>
    </>
  )
}

function FS({ label, children }: any) {
  return (
    <div style={{ marginBottom: 22 }}>
      <div style={{ fontSize: 11, color: 'var(--text3)', letterSpacing: '.08em', marginBottom: 8, fontWeight: 600 }}>{label.toUpperCase()}</div>
      {children}
    </div>
  )
}

function FC({ label, active, onClick, color, full }: any) {
  return (
    <button className="cb" onClick={onClick} style={{
      display: full ? 'block' : 'inline-block', width: full ? '100%' : 'auto',
      textAlign: full ? 'left' : 'center', padding: full ? '7px 12px' : '5px 11px',
      borderRadius: full ? 8 : 20, fontSize: 12, fontWeight: active ? 600 : 400,
      background: active ? (color ? color+'20' : 'rgba(255,107,0,.15)') : 'transparent',
      border: `1px solid ${active ? (color||'var(--accent)') : 'var(--border)'}`,
      color: active ? (color||'var(--accent)') : 'var(--text3)',
      cursor: 'pointer', transition: 'all .15s',
    }}>{label}</button>
  )
}

const IS: React.CSSProperties = {
  flex: 1, background: 'var(--bg3)', border: '1px solid var(--border)',
  borderRadius: 8, padding: '9px 11px', color: 'var(--text)',
  fontSize: 13, outline: 'none', minWidth: 0,
}
