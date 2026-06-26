'use client'
import { useEffect, useState } from 'react'
import { getListing, getPriceHistory, getSimilar, fraudCheck, addFavorite, getProfile, importCost } from '@/lib/api'

export default function ListingPage({ params }: { params: { id: string } }) {
  const [listing, setListing]   = useState<any>(null)
  const [history, setHistory]   = useState<any[]>([])
  const [similar, setSimilar]   = useState<any[]>([])
  const [fraud, setFraud]       = useState<any>(null)
  const [user, setUser]         = useState<any>(null)
  const [importResult, setImportResult] = useState<any>(null)
  const [importLoading, setImportLoading] = useState(false)
  const [activeImg, setActiveImg] = useState(0)
  const [favorited, setFavorited] = useState(false)
  const [premiumModalOpen, setPremiumModalOpen] = useState(false)
  const [loading, setLoading]   = useState(true)

  useEffect(() => {
    setLoading(true)
    setActiveImg(0)
    setImportResult(null)
    setImportLoading(false)
    const profilePromise = localStorage.getItem('token')
      ? getProfile().catch(() => null)
      : Promise.resolve(null)

    Promise.all([
      getListing(params.id),
      getPriceHistory(params.id),
      getSimilar(params.id),
      fraudCheck(params.id),
      profilePromise,
    ]).then(([l, h, s, f, profile]) => {
      setListing(l); setHistory(h); setSimilar(s); setFraud(f); setUser(profile)
      if (l?.price && l?.year) {
        setImportLoading(true)
        importCost({
          price_eur: Number(l.price),
          year: Number(l.year),
          engine_cc: l.engine_cc ? Number(l.engine_cc) : null,
          fuel_type: l.fuel_type || null,
          from_country: l.country || 'DE',
          to_country: 'RS',
        })
          .then(setImportResult)
          .catch(() => setImportResult(null))
          .finally(() => setImportLoading(false))
      }
    }).catch(console.error)
    .finally(() => setLoading(false))
  }, [params.id])

  if (loading) return <PageSkeleton />
  if (!listing) return <div style={{textAlign:'center',padding:'80px 0',color:'var(--text3)'}}>Oglas nije pronađen.</div>

  const images = listing.images || []
  const deltaGood = listing.price_delta_pct && Number(listing.price_delta_pct) < 0
  const locationText = [listing.city, listing.country].filter(Boolean).join(', ')
  const mapsUrl = locationText ? `https://maps.google.com/?q=${encodeURIComponent(locationText)}` : ''
  const isPremium = Boolean(user?.is_premium)
  const openSellerContact = () => {
    if (isPremium && listing.url) {
      window.open(listing.url, '_blank', 'noopener,noreferrer')
      return
    }
    setPremiumModalOpen(true)
  }

  return (
    <div className="listing-detail-page" style={{ padding: '32px 0 80px' }}>
      <div className="container">
        {/* Breadcrumb */}
        <div className="listing-breadcrumb" style={{ fontSize: 13, color: 'var(--text3)', marginBottom: 20 }}>
          <a href="/" style={{ color: 'var(--text3)' }}>Početna</a> →{' '}
          <a href="/search" style={{ color: 'var(--text3)' }}>Pretraga</a> →{' '}
          <span style={{ color: 'var(--text)' }}>{listing.make} {listing.model}</span>
        </div>

        <div className="listing-detail-grid">
          {/* Left column */}
          <div className="listing-main-column">
            {/* Gallery */}
            <div className="listing-gallery-wrap">
              <ListingGallery images={images} activeImg={activeImg} setActiveImg={setActiveImg} />
            </div>

            <div className="listing-mobile-summary">
              <ListingSummaryCard
                listing={listing}
                locationText={locationText}
                mapsUrl={mapsUrl}
                deltaGood={deltaGood}
                importResult={importResult}
                importLoading={importLoading}
                isPremium={isPremium}
                favorited={favorited}
                setFavorited={setFavorited}
                onContact={openSellerContact}
              />
            </div>

            {/* Specs grid */}
            <div style={{ background: 'var(--bg2)', border: '1px solid var(--border)', borderRadius: 'var(--radius)', padding: 24, marginBottom: 20 }}>
              <h2 style={{ fontSize: 16, marginBottom: 16 }}>Specifikacije</h2>
              <div className="listing-specs-grid">
                {[
                  { label: 'Godište', value: listing.year },
                  { label: 'Kilometraža', value: listing.mileage ? `${Number(listing.mileage).toLocaleString()} km` : null },
                  { label: 'Gorivo', value: listing.fuel_type },
                  { label: 'Menjač', value: listing.transmission === 'automatic' ? 'Automatik' : listing.transmission === 'manual' ? 'Manuel' : listing.transmission },
                  { label: 'Snaga', value: listing.engine_power_kw ? `${listing.engine_power_kw} kW` : null },
                  { label: 'Karoserija', value: listing.body_type },
                  { label: 'Lokacija', value: locationText },
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
          <div className="listing-sidebar">
            {/* Price card */}
            <div className="listing-desktop-summary" style={{ background: 'var(--bg2)', border: '1px solid var(--border)', borderRadius: 'var(--radius)', padding: 24, marginBottom: 16 }}>
              <h1 style={{ fontSize: 22, marginBottom: 4 }}>{listing.year} {listing.make} {listing.model}</h1>
              {listing.variant && <div style={{ color: 'var(--text2)', fontSize: 14, marginBottom: 16 }}>{listing.variant}</div>}
              <VerifiedSourceBadge />
              {locationText && (
                <a href={mapsUrl} target="_blank" rel="noopener noreferrer" style={{
                  display: 'inline-flex', alignItems: 'center', gap: 6,
                  color: 'var(--text2)', fontSize: 13, marginBottom: 12,
                }}>
                  <span>📍</span>
                  <span>{locationText}</span>
                </a>
              )}
              {listing.special_vehicle && (
                <div style={{
                  display: 'inline-block', background: 'rgba(245, 158, 11, .16)',
                  border: '1px solid rgba(245, 158, 11, .45)', color: '#FBBF24',
                  borderRadius: 20, padding: '5px 11px', fontSize: 12,
                  fontWeight: 700, marginBottom: 14,
                }}>⚠️ Specijalno vozilo</div>
              )}

              <div style={{ fontSize: 32, fontWeight: 800, color: 'var(--accent)', marginBottom: 8 }}>
                {listing.price ? `${Number(listing.price).toLocaleString()} €` : 'Cena na upit'}
              </div>

              {listing.purchase_rating ? (
                <PurchaseRatingCard rating={listing.purchase_rating} />
              ) : listing.price_estimated && (
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

              <ImportSerbiaSummary listing={listing} importResult={importResult} importLoading={importLoading} />

              <button type="button" onClick={openSellerContact} style={{
                display: 'block', width: '100%', padding: '13px', textAlign: 'center',
                background: 'var(--accent)', color: '#fff', borderRadius: 10,
                border: 'none', fontWeight: 600, fontSize: 15, marginBottom: 8,
              }}>Kontaktiraj prodavca</button>

              {isPremium && (
                <a href={listing.url} target="_blank" rel="noopener noreferrer" style={{
                  display: 'block', width: '100%', padding: '11px', textAlign: 'center',
                  background: 'transparent', color: 'var(--text2)', borderRadius: 10,
                  border: '1px solid var(--border)', fontWeight: 600, fontSize: 14,
                  marginBottom: 8,
                }}>Pogledaj originalni oglas</a>
              )}

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
      {premiumModalOpen && <PremiumContactModal onClose={() => setPremiumModalOpen(false)} />}
    </div>
  )
}

function ListingGallery({ images, activeImg, setActiveImg }: { images: string[], activeImg: number, setActiveImg: (index: number) => void }) {
  const [touchStart, setTouchStart] = useState<number | null>(null)
  const total = images.length
  const hasImages = total > 0
  const safeIndex = hasImages ? Math.min(activeImg, total - 1) : 0

  const go = (direction: number) => {
    if (total <= 1) return
    setActiveImg((safeIndex + direction + total) % total)
  }

  return (
    <div>
      <div
        className="listing-gallery-main"
        onTouchStart={e => setTouchStart(e.touches[0].clientX)}
        onTouchEnd={e => {
          if (touchStart === null) return
          const delta = touchStart - e.changedTouches[0].clientX
          if (Math.abs(delta) > 40) go(delta > 0 ? 1 : -1)
          setTouchStart(null)
        }}
      >
        {images[safeIndex] ? (
          <img src={images[safeIndex]} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
        ) : (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', fontSize: 60 }}>🚗</div>
        )}

        <VerifiedSourceBadge compact />

        {hasImages && (
          <span style={{
            position: 'absolute', right: 12, bottom: 12,
            background: 'rgba(0,0,0,.72)', color: '#fff',
            borderRadius: 20, padding: '4px 10px', fontSize: 12,
            backdropFilter: 'blur(4px)',
          }}>{safeIndex + 1}/{total}</span>
        )}

        {total > 1 && (
          <>
            <button type="button" aria-label="Prethodna slika" onClick={() => go(-1)} className="listing-gallery-arrow listing-gallery-prev">‹</button>
            <button type="button" aria-label="Sledeća slika" onClick={() => go(1)} className="listing-gallery-arrow listing-gallery-next">›</button>
          </>
        )}
      </div>

      {total > 1 && (
        <div className="listing-gallery-thumbs">
          {images.slice(0, 10).map((img: string, i: number) => (
            <div key={i} onClick={() => setActiveImg(i)} style={{
              width: 72, height: 52, flexShrink: 0, borderRadius: 8,
              overflow: 'hidden', cursor: 'pointer',
              border: `2px solid ${safeIndex === i ? 'var(--accent)' : 'transparent'}`,
            }}>
              <img src={img} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function ListingSummaryCard({
  listing,
  locationText,
  mapsUrl,
  deltaGood,
  importResult,
  importLoading,
  isPremium,
  favorited,
  setFavorited,
  onContact,
}: {
  listing: any
  locationText: string
  mapsUrl: string
  deltaGood: any
  importResult: any
  importLoading: boolean
  isPremium: boolean
  favorited: boolean
  setFavorited: (value: boolean) => void
  onContact: () => void
}) {
  return (
    <div style={{ background: 'var(--bg2)', border: '1px solid var(--border)', borderRadius: 'var(--radius)', padding: 24, marginBottom: 16 }}>
      <h1 style={{ fontSize: 22, marginBottom: 4 }}>{listing.year} {listing.make} {listing.model}</h1>
      {listing.variant && <div style={{ color: 'var(--text2)', fontSize: 14, marginBottom: 12 }}>{listing.variant}</div>}
      <VerifiedSourceBadge />
      {locationText && (
        <a href={mapsUrl} target="_blank" rel="noopener noreferrer" style={{
          display: 'inline-flex', alignItems: 'center', gap: 6,
          color: 'var(--text2)', fontSize: 13, marginBottom: 12,
        }}>
          <span>📍</span>
          <span>{locationText}</span>
        </a>
      )}
      {listing.special_vehicle && (
        <div style={{
          display: 'inline-block', background: 'rgba(245, 158, 11, .16)',
          border: '1px solid rgba(245, 158, 11, .45)', color: '#FBBF24',
          borderRadius: 20, padding: '5px 11px', fontSize: 12,
          fontWeight: 700, marginBottom: 14,
        }}>⚠️ Specijalno vozilo</div>
      )}

      {listing.purchase_rating ? (
        <PurchaseRatingCard rating={listing.purchase_rating} />
      ) : listing.price_estimated && (
        <FallbackAiEstimate listing={listing} deltaGood={deltaGood} />
      )}

      <div style={{ fontSize: 32, fontWeight: 800, color: 'var(--accent)', marginBottom: 8 }}>
        {listing.price ? `${Number(listing.price).toLocaleString()} €` : 'Cena na upit'}
      </div>

      <ImportSerbiaSummary listing={listing} importResult={importResult} importLoading={importLoading} />

      <button type="button" onClick={onContact} style={{
        display: 'block', width: '100%', padding: '13px', textAlign: 'center',
        background: 'var(--accent)', color: '#fff', borderRadius: 10,
        border: 'none', fontWeight: 600, fontSize: 15, marginBottom: 8,
      }}>Kontaktiraj prodavca</button>

      {isPremium && (
        <a href={listing.url} target="_blank" rel="noopener noreferrer" style={{
          display: 'block', width: '100%', padding: '11px', textAlign: 'center',
          background: 'transparent', color: 'var(--text2)', borderRadius: 10,
          border: '1px solid var(--border)', fontWeight: 600, fontSize: 14,
          marginBottom: 8,
        }}>Pogledaj originalni oglas</a>
      )}

      <button onClick={async () => { await addFavorite(listing.id); setFavorited(true) }} style={{
        width: '100%', padding: '11px', background: 'transparent',
        border: `1px solid ${favorited ? 'var(--accent)' : 'var(--border)'}`,
        color: favorited ? 'var(--accent)' : 'var(--text2)',
        borderRadius: 10, fontSize: 14, cursor: 'pointer', transition: 'all .15s',
      }}>{favorited ? '❤️ U favoritima' : '🤍 Sačuvaj oglas'}</button>
    </div>
  )
}

function VerifiedSourceBadge({ compact = false }: { compact?: boolean }) {
  return (
    <span style={{
      display: 'inline-flex',
      alignItems: 'center',
      gap: 5,
      position: compact ? 'absolute' : undefined,
      left: compact ? 12 : undefined,
      bottom: compact ? 12 : undefined,
      background: compact ? 'rgba(0,0,0,.72)' : 'rgba(34, 197, 94, .12)',
      border: compact ? '1px solid rgba(255,255,255,.16)' : '1px solid rgba(34, 197, 94, .35)',
      borderRadius: 20,
      padding: compact ? '4px 10px' : '4px 9px',
      color: compact ? '#fff' : '#4ADE80',
      fontSize: 12,
      marginBottom: compact ? 0 : 12,
      backdropFilter: compact ? 'blur(4px)' : undefined,
    }}>
      <span>✓</span>
      <span>Verifikovan izvor</span>
    </span>
  )
}

function ImportSerbiaSummary({ listing, importResult, importLoading }: { listing: any, importResult: any, importLoading: boolean }) {
  const vehiclePrice = Number(listing.price || 0)
  const totalSerbia = importResult?.total_cost_eur !== undefined ? Number(importResult.total_cost_eur) : null
  const importOnly = totalSerbia !== null && vehiclePrice ? Math.max(0, totalSerbia - vehiclePrice) : null

  return (
    <div style={{
      background: 'var(--bg3)', border: '1px solid var(--border)',
      borderRadius: 10, padding: 14, marginBottom: 12,
    }}>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
        <div>
          <div style={{ fontSize: 11, color: 'var(--text3)', marginBottom: 3 }}>Uvoz u Srbiju</div>
          <div style={{ fontSize: 16, fontWeight: 800 }}>
            {importLoading ? 'Računam...' : importOnly !== null ? money(importOnly) : 'Nije dostupno'}
          </div>
        </div>
        <div>
          <div style={{ fontSize: 11, color: 'var(--text3)', marginBottom: 3 }}>Ukupno za Srbiju</div>
          <div style={{ fontSize: 16, fontWeight: 800, color: 'var(--accent)' }}>
            {importLoading ? 'Računam...' : totalSerbia !== null ? money(totalSerbia) : 'Nije dostupno'}
          </div>
        </div>
      </div>
      {importResult?.total_cost_rsd && (
        <div style={{ fontSize: 11, color: 'var(--text3)', marginTop: 8 }}>
          Približno {Number(importResult.total_cost_rsd).toLocaleString()} RSD
        </div>
      )}
    </div>
  )
}

function FallbackAiEstimate({ listing, deltaGood }: { listing: any, deltaGood: any }) {
  return (
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
  )
}

function PremiumContactModal({ onClose }: { onClose: () => void }) {
  return (
    <div role="dialog" aria-modal="true" style={{
      position: 'fixed', inset: 0, zIndex: 50,
      background: 'rgba(0,0,0,.72)', display: 'flex',
      alignItems: 'center', justifyContent: 'center', padding: 20,
    }}>
      <div style={{
        width: '100%', maxWidth: 420, background: 'var(--bg2)',
        border: '1px solid var(--border)', borderRadius: 'var(--radius)',
        padding: 24, boxShadow: 'var(--shadow)',
      }}>
        <h2 style={{ fontSize: 20, marginBottom: 12 }}>Kontakt prodavca je Premium funkcija.</h2>
        <p style={{ color: 'var(--text2)', fontSize: 14, lineHeight: 1.7, marginBottom: 18 }}>
          AutoAI ti prikazuje analizu oglasa, cenu i procenu uvoza.
          Za originalni oglas i kontakt prodavca potrebna je pretplata.
        </p>
        <a href="/account" style={{
          display: 'block', textAlign: 'center', padding: 12,
          borderRadius: 10, background: 'var(--accent)', color: '#fff',
          fontWeight: 800, marginBottom: 10,
        }}>Aktiviraj Premium</a>
        <button type="button" onClick={onClose} style={{
          width: '100%', padding: 10, borderRadius: 10,
          background: 'transparent', border: '1px solid var(--border)',
          color: 'var(--text2)',
        }}>Zatvori</button>
      </div>
    </div>
  )
}

function PurchaseRatingCard({ rating }: { rating: any }) {
  const labelStyle = purchaseRatingStyle(rating.rating)
  const saving = Number(rating.potential_saving || 0)
  const hasEstimate = rating.estimated_market_value !== null && rating.estimated_market_value !== undefined
  const hasReliableEnoughData = rating.rating !== 'INSUFFICIENT_DATA'

  return (
    <div style={{
      background: labelStyle.bg,
      border: `1px solid ${labelStyle.border}`,
      borderRadius: 10,
      padding: '12px 14px',
      marginBottom: 16,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
        <span style={{ fontSize: 18 }}>{labelStyle.icon}</span>
        <div style={{ fontSize: 15, fontWeight: 800, color: labelStyle.color }}>{rating.label}</div>
      </div>

      <RatingRow label="Tražena cena" value={money(rating.asking_price)} />
      {hasReliableEnoughData && (
        <>
          <RatingRow label="Tržišna vrednost" value={hasEstimate ? money(rating.estimated_market_value) : '—'} />
          <RatingRow
            label={saving >= 0 ? 'Ušteda' : 'Preplata'}
            value={hasEstimate ? money(Math.abs(saving)) : '—'}
            valueColor={saving >= 0 ? '#22C55E' : '#F87171'}
          />
        </>
      )}
      <RatingRow label="Pouzdanost" value={`${Number(rating.confidence_percent || 0)}%`} />
      <div style={{ fontSize: 12, color: 'var(--text3)', marginTop: 8 }}>
        Na osnovu {Number(rating.comparable_count || 0).toLocaleString()} sličnih vozila.
      </div>
      <div style={{ fontSize: 11, color: 'var(--text3)', marginTop: 6 }}>
        Procena će biti pouzdanija kada baza pređe 50.000+ vozila.
      </div>
      {hasReliableEnoughData && hasEstimate && rating.market_low && rating.market_high && (
        <div style={{
          borderTop: '1px solid var(--border)', marginTop: 10, paddingTop: 10,
          display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8,
        }}>
          <div>
            <div style={{ fontSize: 11, color: 'var(--text3)' }}>Tržišni raspon od</div>
            <div style={{ fontSize: 13, fontWeight: 700 }}>{money(rating.market_low)}</div>
          </div>
          <div>
            <div style={{ fontSize: 11, color: 'var(--text3)' }}>do</div>
            <div style={{ fontSize: 13, fontWeight: 700 }}>{money(rating.market_high)}</div>
          </div>
        </div>
      )}
      {(rating.comparable_year_range?.min || rating.comparable_mileage_range?.min) && (
        <div style={{ fontSize: 11, color: 'var(--text3)', marginTop: 8 }}>
          {rating.comparable_year_range?.min && rating.comparable_year_range?.max && (
            <div>Godine za poređenje: {rating.comparable_year_range.min} - {rating.comparable_year_range.max}</div>
          )}
          {rating.comparable_mileage_range?.min && rating.comparable_mileage_range?.max && (
            <div>Kilometraža za poređenje: {Number(rating.comparable_mileage_range.min).toLocaleString()} - {Number(rating.comparable_mileage_range.max).toLocaleString()} km</div>
          )}
        </div>
      )}
      {rating.explanations?.length > 0 && (
        <div style={{ marginTop: 10 }}>
          {rating.explanations.slice(0, 4).map((item: string) => (
            <div key={item} style={{ fontSize: 11, color: 'var(--text3)', marginTop: 4 }}>
              {item}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function RatingRow({ label, value, valueColor }: { label: string, value: string, valueColor?: string }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, fontSize: 12, marginBottom: 6 }}>
      <span style={{ color: 'var(--text3)' }}>{label}</span>
      <span style={{ color: valueColor || 'var(--text)', fontWeight: 700, textAlign: 'right' }}>{value}</span>
    </div>
  )
}

function purchaseRatingStyle(rating: string) {
  if (rating === 'VERY_GOOD_BUY') return { icon: '🟢', color: '#22C55E', bg: '#16A34A14', border: '#22C55E40' }
  if (rating === 'GOOD_BUY') return { icon: '🟡', color: '#EAB308', bg: '#EAB30814', border: '#EAB30840' }
  if (rating === 'EXPENSIVE') return { icon: '🔴', color: '#F87171', bg: '#EF444414', border: '#EF444440' }
  if (rating === 'ROUGH_ESTIMATE') return { icon: '🟡', color: '#EAB308', bg: '#EAB30814', border: '#EAB30840' }
  if (rating === 'INSUFFICIENT_DATA') return { icon: '⚪', color: 'var(--text2)', bg: '#78716C15', border: '#78716C40' }
  return { icon: '⚪', color: '#D8B4FE', bg: '#78716C15', border: '#78716C40' }
}

function money(value: any) {
  if (value === null || value === undefined || value === '') return '—'
  return `${Number(value).toLocaleString()} €`
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
