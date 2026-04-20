'use client'
import { useEffect, useState } from 'react'
import { getListing, getPriceHistory, getSimilar, fraudCheck, addFavorite } from '@/lib/api'

export default function ListingPage({ params }: { params: { id: string } }) {
  const [listing, setListing]   = useState<any>(null)
  const [history, setHistory]   = useState<any[]>([])
  const [similar, setSimilar]   = useState<any[]>([])
  const [fraud, setFraud]       = useState<any>(null)
  const [activeImg, setActiveImg] = useState(0)
  const [favorited, setFavorited] = useState(false)
  const [loading, setLoading]   = useState(true)

  useEffect(() => {
    Promise.all([
      getListing(params.id),
      getPriceHistory(params.id),
      getSimilar(params.id),
      fraudCheck(params.id),
    ]).then(([l, h, s, f]) => {
      setListing(l); setHistory(h); setSimilar(s); setFraud(f)
    }).catch(console.error)
    .finally(() => setLoading(false))
  }, [params.id])

  if (loading) return <PageSkeleton />
  if (!listing) return <div style={{textAlign:'center',padding:'80px 0',color:'var(--text3)'}}>Oglas nije pronađen.</div>

  const images = listing.images || []
  const priceRating = listing.price_rating
  const deltaGood = listing.price_delta_pct && Number(listing.price_delta_pct) < 0

  return (
    <div style={{ padding: '32px 0 80px' }}>
      <div className="container">
        {/* Breadcrumb */}
        <div style={{ fontSize: 13, color: 'var(--text3)', marginBottom: 20 }}>
          <a href="/" style={{ color: 'var(--text3)' }}>Početna</a> →{' '}
          <a href="/search" style={{ color: 'var(--text3)' }}>Pretraga</a> →{' '}
          <span style={{ color: 'var(--text)' }}>{listing.make} {listing.model}</span>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 340px', gap: 28, alignItems: 'start' }}>
          {/* Left column */}
          <div>
            {/* Gallery */}
            <div style={{ marginBottom: 24 }}>
              <div style={{
                height: 380, background: 'var(--bg3)', borderRadius: 'var(--radius)',
                overflow: 'hidden', marginBottom: 8, position: 'relative',
              }}>
                {images[activeImg] ? (
                  <img src={images[activeImg]} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                ) : (
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', fontSize: 60 }}>🚗</div>
                )}
              </div>
              {images.length > 1 && (
                <div style={{ display: 'flex', gap: 8, overflowX: 'auto' }}>
                  {images.slice(0, 10).map((img: string, i: number) => (
                    <div key={i} onClick={() => setActiveImg(i)} style={{
                      width: 72, height: 52, flexShrink: 0, borderRadius: 8,
                      overflow: 'hidden', cursor: 'pointer',
                      border: `2px solid ${activeImg === i ? 'var(--accent)' : 'transparent'}`,
                    }}>
                      <img src={img} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Specs grid */}
            <div style={{ background: 'var(--bg2)', border: '1px solid var(--border)', borderRadius: 'var(--radius)', padding: 24, marginBottom: 20 }}>
              <h2 style={{ fontSize: 16, marginBottom: 16 }}>Specifikacije</h2>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12 }}>
                {[
                  { label: 'Godište', value: listing.year },
                  { label: 'Kilometraža', value: listing.mileage ? `${Number(listing.mileage).toLocaleString()} km` : null },
                  { label: 'Gorivo', value: listing.fuel_type },
                  { label: 'Menjač', value: listing.transmission === 'automatic' ? 'Automatik' : listing.transmission === 'manual' ? 'Manuel' : listing.transmission },
                  { label: 'Snaga', value: listing.engine_power_kw ? `${listing.engine_power_kw} kW` : null },
                  { label: 'Karoserija', value: listing.body_type },
                  { label: 'Zemlja', value: listing.country },
                  { label: 'Grad', value: listing.city },
                  { label: 'Stanje', value: listing.accident_free ? '✅ Bez udesa' : null },
                ].filter(s => s.value).map(s => (
                  <div key={s.label} style={{ background: 'var(--bg3)', borderRadius: 8, padding: '10px 14px' }}>
                    <div style={{ fontSize: 11, color: 'var(--text3)', marginBottom: 3 }}>{s.label}</div>
                    <div style={{ fontSize: 14, fontWeight: 500 }}>{s.value}</div>
                  </div>
                ))}
              </div>
            </div>

            {/* Description */}
            {listing.description && (
              <div style={{ background: 'var(--bg2)', border: '1px solid var(--border)', borderRadius: 'var(--radius)', padding: 24, marginBottom: 20 }}>
                <h2 style={{ fontSize: 16, marginBottom: 12 }}>Opis</h2>
                <p style={{ color: 'var(--text2)', lineHeight: 1.8, fontSize: 14, whiteSpace: 'pre-line' }}>{listing.description}</p>
              </div>
            )}

            {/* Features */}
            {listing.features?.length > 0 && (
              <div style={{ background: 'var(--bg2)', border: '1px solid var(--border)', borderRadius: 'var(--radius)', padding: 24, marginBottom: 20 }}>
                <h2 style={{ fontSize: 16, marginBottom: 16 }}>Oprema ({listing.features.length})</h2>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                  {listing.features.map((f: string) => (
                    <span key={f} style={{ background: 'var(--bg3)', border: '1px solid var(--border)', borderRadius: 20, padding: '4px 12px', fontSize: 12, color: 'var(--text2)' }}>{f}</span>
                  ))}
                </div>
              </div>
            )}

            {/* Price history */}
            {history.length > 1 && (
              <div style={{ background: 'var(--bg2)', border: '1px solid var(--border)', borderRadius: 'var(--radius)', padding: 24, marginBottom: 20 }}>
                <h2 style={{ fontSize: 16, marginBottom: 16 }}>Istorija cene</h2>
                <PriceChart history={history} />
              </div>
            )}

            {/* Similar */}
            {similar.length > 0 && (
              <div>
                <h2 style={{ fontSize: 16, marginBottom: 16 }}>Slični oglasi</h2>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 12 }}>
                  {similar.slice(0, 4).map((s: any) => (
                    <a key={s.id} href={`/listing/${s.id}`} style={{
                      background: 'var(--bg2)', border: '1px solid var(--border)', borderRadius: 'var(--radius)',
                      overflow: 'hidden', display: 'block', transition: 'border-color .15s',
                    }}
                    onMouseEnter={e => ((e.currentTarget as HTMLElement).style.borderColor = 'var(--accent)')}
                    onMouseLeave={e => ((e.currentTarget as HTMLElement).style.borderColor = 'var(--border)')}
                    >
                      <div style={{ height: 120, background: 'var(--bg3)', overflow: 'hidden' }}>
                        {s.images?.[0] ? <img src={s.images[0]} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover' }} /> : <div style={{height:'100%',display:'flex',alignItems:'center',justifyContent:'center',fontSize:28}}>🚗</div>}
                      </div>
                      <div style={{ padding: 12 }}>
                        <div style={{ fontSize: 13, fontWeight: 600 }}>{s.year} {s.make} {s.model}</div>
                        <div style={{ fontSize: 14, color: 'var(--accent)', fontWeight: 700, marginTop: 4 }}>{s.price ? `${Number(s.price).toLocaleString()} €` : '—'}</div>
                      </div>
                    </a>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Right sidebar */}
          <div style={{ position: 'sticky', top: 80 }}>
            {/* Price card */}
            <div style={{ background: 'var(--bg2)', border: '1px solid var(--border)', borderRadius: 'var(--radius)', padding: 24, marginBottom: 16 }}>
              <h1 style={{ fontSize: 22, marginBottom: 4 }}>{listing.year} {listing.make} {listing.model}</h1>
              {listing.variant && <div style={{ color: 'var(--text2)', fontSize: 14, marginBottom: 16 }}>{listing.variant}</div>}

              <div style={{ fontSize: 32, fontWeight: 800, color: 'var(--accent)', marginBottom: 8 }}>
                {listing.price ? `${Number(listing.price).toLocaleString()} €` : 'Cena na upit'}
              </div>

              {listing.price_estimated && (
                <div style={{
                  background: deltaGood ? '#16A34A15' : '#78716C15',
                  border: `1px solid ${deltaGood ? '#22C55E40' : '#78716C40'}`,
                  borderRadius: 8, padding: '10px 14px', marginBottom: 16,
                }}>
                  <div style={{ fontSize: 12, color: 'var(--text3)', marginBottom: 2 }}>AI procena tržišne vrednosti</div>
                  <div style={{ fontWeight: 600 }}>{Number(listing.price_estimated).toLocaleString()} €</div>
                  <div style={{ fontSize: 12, color: deltaGood ? '#22C55E' : '#F87171', marginTop: 2 }}>
                    {deltaGood ? '✅ Ispod tržišne vrednosti' : '⚠️ Iznad tržišne vrednosti'}
                    {' '}{Math.abs(Number(listing.price_delta_pct)).toFixed(0)}%
                  </div>
                </div>
              )}

              <a href={listing.url} target="_blank" rel="noopener" style={{
                display: 'block', width: '100%', padding: '13px', textAlign: 'center',
                background: 'var(--accent)', color: '#fff', borderRadius: 10,
                fontWeight: 600, fontSize: 15, marginBottom: 8, transition: 'opacity .15s',
              }}
              onMouseEnter={e => ((e.target as HTMLElement).style.opacity = '0.85')}
              onMouseLeave={e => ((e.target as HTMLElement).style.opacity = '1')}
              >Pogledaj oglas →</a>

              <button onClick={async () => { await addFavorite(listing.id); setFavorited(true) }} style={{
                width: '100%', padding: '11px', background: 'transparent',
                border: `1px solid ${favorited ? 'var(--accent)' : 'var(--border)'}`,
                color: favorited ? 'var(--accent)' : 'var(--text2)',
                borderRadius: 10, fontSize: 14, cursor: 'pointer', transition: 'all .15s',
              }}>{favorited ? '❤️ U favoritima' : '🤍 Sačuvaj oglas'}</button>
            </div>

            {/* Fraud check */}
            {fraud && (
              <div style={{
                background: 'var(--bg2)', border: `1px solid ${fraud.badge?.color + '40' || 'var(--border)'}`,
                borderRadius: 'var(--radius)', padding: 20, marginBottom: 16,
              }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
                  <h3 style={{ fontSize: 14 }}>Provjera prevare</h3>
                  <span style={{
                    fontSize: 12, padding: '3px 10px', borderRadius: 20,
                    background: fraud.badge?.color + '20',
                    color: fraud.badge?.color,
                    border: `1px solid ${fraud.badge?.color + '40'}`,
                  }}>{fraud.badge?.text}</span>
                </div>

                {fraud.red_flags?.length > 0 && (
                  <div>
                    {fraud.red_flags.map((f: string) => (
                      <div key={f} style={{ fontSize: 12, color: '#F87171', display: 'flex', gap: 6, marginBottom: 4 }}>
                        <span>⚠</span><span>{f}</span>
                      </div>
                    ))}
                  </div>
                )}
                {fraud.safe_signals?.length > 0 && (
                  <div style={{ marginTop: 8 }}>
                    {fraud.safe_signals.map((s: string) => (
                      <div key={s} style={{ fontSize: 12, color: '#22C55E', display: 'flex', gap: 6, marginBottom: 4 }}>
                        <span>✓</span><span>{s}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Import calculator link */}
            <a href={`/import-calculator?price=${listing.price || ''}&year=${listing.year || ''}&cc=${listing.engine_cc || ''}&fuel=${listing.fuel_type || ''}&from=${listing.country || 'DE'}`}
              style={{
                display: 'flex', alignItems: 'center', gap: 10, padding: 16,
                background: 'var(--bg2)', border: '1px solid var(--border)',
                borderRadius: 'var(--radius)', transition: 'border-color .15s',
              }}
              onMouseEnter={e => ((e.currentTarget as HTMLElement).style.borderColor = 'var(--accent)')}
              onMouseLeave={e => ((e.currentTarget as HTMLElement).style.borderColor = 'var(--border)')}
            >
              <span style={{ fontSize: 24 }}>✈️</span>
              <div>
                <div style={{ fontSize: 14, fontWeight: 600 }}>Kalkulator uvoza</div>
                <div style={{ fontSize: 12, color: 'var(--text3)' }}>Koliko košta uvoz u Srbiju?</div>
              </div>
              <span style={{ marginLeft: 'auto', color: 'var(--text3)' }}>→</span>
            </a>
          </div>
        </div>
      </div>
    </div>
  )
}

function PriceChart({ history }: { history: any[] }) {
  const prices = history.map(h => Number(h.price))
  const min = Math.min(...prices)
  const max = Math.max(...prices)
  const range = max - min || 1
  const W = 500, H = 100, PAD = 10

  const points = history.map((h, i) => ({
    x: PAD + (i / (history.length - 1)) * (W - PAD * 2),
    y: H - PAD - ((Number(h.price) - min) / range) * (H - PAD * 2),
    price: Number(h.price),
    date: new Date(h.recorded_at).toLocaleDateString('sr'),
  }))

  const path = points.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x} ${p.y}`).join(' ')

  return (
    <div style={{ overflowX: 'auto' }}>
      <svg viewBox={`0 0 ${W} ${H}`} style={{ width: '100%', maxWidth: W }}>
        <defs>
          <linearGradient id="grad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#F97316" stopOpacity="0.3" />
            <stop offset="100%" stopColor="#F97316" stopOpacity="0" />
          </linearGradient>
        </defs>
        <path d={`${path} L ${points[points.length-1].x} ${H} L ${points[0].x} ${H} Z`}
          fill="url(#grad)" />
        <path d={path} fill="none" stroke="#F97316" strokeWidth="2" strokeLinecap="round" />
        {points.map((p, i) => (
          <circle key={i} cx={p.x} cy={p.y} r="3" fill="#F97316" />
        ))}
      </svg>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: 'var(--text3)', marginTop: 4 }}>
        <span>{points[0].date}: {points[0].price.toLocaleString()} €</span>
        <span>{points[points.length-1].date}: {points[points.length-1].price.toLocaleString()} €</span>
      </div>
    </div>
  )
}

function PageSkeleton() {
  return (
    <div style={{ padding: '32px 0' }}>
      <div className="container" style={{ display: 'grid', gridTemplateColumns: '1fr 340px', gap: 28 }}>
        <div>
          <div className="skeleton" style={{ height: 380, borderRadius: 12, marginBottom: 8 }} />
          <div className="skeleton" style={{ height: 200, borderRadius: 12, marginTop: 16 }} />
        </div>
        <div>
          <div className="skeleton" style={{ height: 280, borderRadius: 12 }} />
        </div>
      </div>
    </div>
  )
}
