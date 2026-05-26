'use client'
import { useEffect, useState, useRef } from 'react'
import { getListing, getPriceHistory, getSimilar, fraudCheck, addFavorite } from '@/lib/api'
import ContactModal from '@/components/ContactModal'

const ELIGIBILITY_COLORS: Record<string, string> = {
  eligible: '#22C55E', needs_check: '#F97316', not_recommended: '#EF4444', oldtimer: '#A855F7',
}

const AI_SCAN_MESSAGES = [
  '🧠 AI proverava detalje oglasa...',
  '🧠 Provera Euro norme...',
  '🧠 Analiza kilometraže...',
  '🧠 Izračunavanje troška uvoza...',
  '🧠 Ažuriranje podataka sa originalnog portala...',
  '🧠 AI analizira uslove uvoza u Srbiju...',
]

function getSerbiaEligibility(listing: any) {
  const year = listing.year ? Number(listing.year) : null
  const fuel = listing.fuel_type || null
  const age  = year ? (2026 - year) : null

  if (fuel === 'electric') return {
    status: 'eligible', emoji: '🟢',
    label: 'Može uvoz u Srbiju',
    reason: 'Električna vozila se uvoze bez carine (0%). Potrebna COC dokumentacija.',
    tooltip: 'Električna vozila su oslobođena carine pri uvozu u Srbiju.',
    warnings: ['Proveri kompatibilnost punjača (Tip 2 / CCS).'],
    carinaPct: 0,
  }
  if (age !== null && age >= 30) return {
    status: 'oldtimer', emoji: '🟣',
    label: 'Oldtimer izuzetak',
    reason: `Vozilo (${year}) starije od 30 godina — poseban režim uvoza.`,
    tooltip: 'Oldtimer vozila mogu se uvesti pod posebnim uslovima.',
    warnings: ['Registracija kao oldtimer zahteva poseban tehnički pregled.'],
    carinaPct: 5,
  }
  if (!year) return {
    status: 'needs_check', emoji: '🟠',
    label: 'Nepoznato godište — Euro norma neprovjerljiva',
    reason: fuel === 'diesel'
      ? 'Dizel vozila zahtevaju posebnu proveru DPF filtera i Euro norme.'
      : 'Potrebno proveriti Euro normu pre uvoza.',
    tooltip: 'Kupovina je moguća, ali preporučujemo dodatnu proveru pre uvoza u Srbiju.',
    warnings: ['Zatraži od prodavca datum prve registracije i COC dokument.', 'Bez potvrde Euro norme može nastati problem pri carinjenju.'],
    carinaPct: 5,
  }
  if (year >= 2015) return {
    status: 'eligible', emoji: '🟢',
    label: 'Može uvoz u Srbiju',
    reason: `Vozilo (${year}) ispunjava Euro 6 normu — nema ograničenja za uvoz.`,
    tooltip: 'Euro 6 vozila bez problema prolaze carinjenje u Srbiji.',
    warnings: ['Pribavi COC dokument za potvrdu Euro norme.', ...(fuel === 'diesel' ? ['Proveri stanje DPF filtera — zamena je skupa.'] : [])],
    carinaPct: 5,
  }
  if (year >= 2011) return {
    status: 'eligible', emoji: '🟢',
    label: 'Može uvoz u Srbiju',
    reason: `Vozilo (${year}) verovatno ispunjava Euro 5 normu.`,
    tooltip: 'Euro 5 vozila se mogu uvesti u Srbiju bez ograničenja.',
    warnings: ['Pribavi COC dokument za potvrdu Euro 5 norme.', ...(fuel === 'diesel' ? ['Dizel Euro 5 — proveri DPF filter pre kupovine.'] : [])],
    carinaPct: 5,
  }
  if (year >= 2006) return {
    status: 'eligible', emoji: '🟢',
    label: fuel === 'diesel' ? 'Može uvoz — proveri Euro 4 normu' : 'Može uvoz u Srbiju',
    reason: `Vozilo (${year}) verovatno ispunjava Euro 4 normu — minimalni uslov za uvoz.`,
    tooltip: 'Euro 4 je minimalni standard za uvoz u Srbiju.',
    warnings: ['Euro 4 je granica — obavezno pribavi COC dokument.', ...(fuel === 'diesel' ? ['Dizel Euro 4 — proveri DPF i turbinu.'] : [])],
    carinaPct: 5,
  }
  if (year >= 2001) return {
    status: 'needs_check', emoji: '🟠',
    label: 'Potrebna provera Euro norme (verovatno Euro 3)',
    reason: `Vozilo (${year}) je verovatno Euro 3 norma — uvoz je moguć uz dodatnu dokumentaciju.`,
    tooltip: 'Kupovina je moguća, ali preporučujemo dodatnu proveru.',
    warnings: ['Euro 3 vozila mogu imati poteškoće pri tehničkom pregledu.', 'Konsultuj carinskog agenta pre uvoza.'],
    carinaPct: 5,
  }
  return {
    status: 'not_recommended', emoji: '🔴',
    label: 'Uvoz nije preporučljiv — staro vozilo',
    reason: `Vozilo (${year}) ne ispunjava minimalne emisione standarde za uvoz u Srbiju.`,
    tooltip: 'Ovo vozilo verovatno ne može biti registrovano u Srbiji.',
    warnings: ['Stara vozila ne prolaze tehnički pregled u Srbiji.'],
    carinaPct: 5,
  }
}

function calcImport(price: number, carinaPct: number) {
  const carina = Math.round(price * carinaPct / 100)
  const pdv    = Math.round((price + carina) * 0.20)
  return { carina, pdv, transport: 420, reg: 280, total: price + carina + pdv + 420 + 280, carinaPct }
}

function fmt(n: any) { return Number(n).toLocaleString('de-DE') }

function fmtKm(km: any): string | null {
  const n = Number(km)
  if (!n || n < 1 || n > 999999) return null
  return n.toLocaleString('de-DE') + ' km'
}

function fullImg(url: string): string {
  if (!url) return url
  return url.replace(/\/\d+x\d+\.(webp|jpg|jpeg|png)/i, '/800x600.$1')
}

export default function ListingPage({ params }: { params: { id: string } }) {
  const [listing,     setListing]     = useState<any>(null)
  const [history,     setHistory]     = useState<any[]>([])
  const [similar,     setSimilar]     = useState<any[]>([])
  const [fraud,       setFraud]       = useState<any>(null)
  const [activeImg,   setActiveImg]   = useState(0)
  const [favorited,   setFavorited]   = useState(false)
  const [loading,     setLoading]     = useState(true)
  const [showContact, setShowContact] = useState(false)
  const [showBd,      setShowBd]      = useState(false)
  const [enriching,   setEnriching]   = useState(false)
  const [enriched,    setEnriched]    = useState(false)
  const [scanMsg,     setScanMsg]     = useState(AI_SCAN_MESSAGES[0])
  const scanInterval = useRef<any>(null)

  useEffect(() => {
    Promise.allSettled([
      getListing(params.id),
      getPriceHistory(params.id),
      getSimilar(params.id),
      fraudCheck(params.id),
    ]).then(([l, h, s, f]) => {
      if (l.status === 'fulfilled') {
        const data = l.value
        setListing(data)
        if (data?.url && (!data.year || !data.mileage)) {
          autoEnrich(data.url)
        }
      }
      if (h.status === 'fulfilled') setHistory(h.value)
      if (s.status === 'fulfilled') setSimilar(s.value)
      if (f.status === 'fulfilled') setFraud(f.value)
    }).finally(() => setLoading(false))
  }, [params.id])

  const startScanMessages = () => {
    let i = 0
    setScanMsg(AI_SCAN_MESSAGES[0])
    scanInterval.current = setInterval(() => {
      i = (i + 1) % AI_SCAN_MESSAGES.length
      setScanMsg(AI_SCAN_MESSAGES[i])
    }, 1800)
  }

  const stopScanMessages = () => {
    if (scanInterval.current) clearInterval(scanInterval.current)
  }

  const autoEnrich = async (url: string) => {
    if (enriching || enriched) return
    setEnriching(true)
    startScanMessages()
    try {
      const apiBase = process.env.NEXT_PUBLIC_API_URL || 'https://autoai-platform-production.up.railway.app/api/v1'
      const res  = await fetch(`${apiBase}/analyze/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url }),
      })
      const data = await res.json()
      if (data.scrape_success) {
        setListing((prev: any) => ({
          ...prev,
          year:            data.year            || prev.year,
          mileage:         data.mileage          || prev.mileage,
          fuel_type:       data.fuel_type        || prev.fuel_type,
          engine_power_kw: data.engine_power_kw  || prev.engine_power_kw,
          country:         data.country          || prev.country,
          city:            data.city             || prev.city,
          transmission:    data.transmission     || prev.transmission,
          images:          (data.images?.length || 0) > (prev.images?.length || 0) ? data.images : prev.images,
        }))
        setEnriched(true)
      }
    } catch {}
    stopScanMessages()
    setEnriching(false)
  }

  const manualRefresh = async () => {
    if (!listing?.url || enriching) return
    setEnriched(false)
    await autoEnrich(listing.url)
  }

  if (loading) return <PageSkeleton />
  if (!listing) return <div style={{ textAlign:'center', padding:'80px 0', color:'var(--text3)' }}>Oglas nije pronađen.</div>

  const images    = listing.images || []
  const elig      = getSerbiaEligibility(listing)
  const eligColor = ELIGIBILITY_COLORS[elig.status] || '#F97316'
  const price     = listing.price ? Number(listing.price) : null
  const bd        = price ? calcImport(price, elig.carinaPct) : null
  const deltaGood = listing.price_delta_pct && Number(listing.price_delta_pct) < 0

  const specs = [
    { label: 'Godište',     value: listing.year },
    { label: 'Kilometraža', value: fmtKm(listing.mileage) },
    { label: 'Gorivo', value: listing.fuel_type ? ({
  diesel: 'Dizel', petrol: 'Benzin', electric: 'Električni',
  hybrid: 'Hibrid', lpg: 'Plin', gasoline: 'Benzin',
} as any)[listing.fuel_type] || listing.fuel_type : null },
    { label: 'Menjač',      value: listing.transmission === 'automatic' ? 'Automatik' : listing.transmission === 'manual' ? 'Manuel' : listing.transmission },
    { label: 'Snaga',       value: listing.engine_power_kw ? `${listing.engine_power_kw} kW` : null },
    { label: 'Karoserija',  value: listing.body_type },
    { label: 'Zemlja',      value: listing.country },
    { label: 'Grad', value: listing.city ? listing.city.split(' - ')[0] : null },
  ].filter(s => s.value)

  return (
    <div style={{ padding: '32px 0 80px' }}>
      {showContact && <ContactModal listing={listing} onClose={() => setShowContact(false)} />}
      <style>{`
        @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.3} }
        @keyframes shimmer { 0%{background-position:-200% 0} 100%{background-position:200% 0} }
      `}</style>

      <div className="container">

        <div style={{ fontSize: 13, color: 'var(--text3)', marginBottom: 20 }}>
          <a href="/" style={{ color: 'var(--text3)' }}>Početna</a> →{' '}
          <a href="/search" style={{ color: 'var(--text3)' }}>Pretraga</a> →{' '}
          <span style={{ color: 'var(--text)' }}>{listing.make} {listing.model}</span>
        </div>

        {/* AI Enrichment scanning banner */}
        {enriching && (
          <div style={{
            background: 'rgba(99,102,241,.08)', border: '1px solid rgba(99,102,241,.3)',
            borderRadius: 12, padding: '14px 20px', marginBottom: 20,
            display: 'flex', alignItems: 'center', gap: 12,
          }}>
            <div style={{ width: 10, height: 10, borderRadius: '50%', background: '#818CF8', animation: 'pulse 1s infinite' }} />
            <span style={{ fontSize: 14, color: '#818CF8', fontWeight: 600 }}>{scanMsg}</span>
          </div>
        )}

        {enriched && !enriching && (
          <div style={{
            background: 'rgba(34,197,94,.08)', border: '1px solid rgba(34,197,94,.25)',
            borderRadius: 12, padding: '12px 16px', marginBottom: 20,
            fontSize: 13, color: '#22C55E', fontWeight: 600,
          }}>
            ✅ AutoAI je automatski analizirao ovaj oglas.
          </div>
        )}

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 340px', gap: 28, alignItems: 'start' }}>

          {/* Leva kolona */}
          <div>
            {/* Galerija */}
            <div style={{ marginBottom: 24 }}>
              <div style={{ height: 420, background: 'var(--bg3)', borderRadius: 'var(--radius)', overflow: 'hidden', marginBottom: 8 }}>
                {enriching && images.length === 0
                  ? <div className="skeleton" style={{ width: '100%', height: '100%' }} />
                  : images[activeImg]
                    ? <img src={fullImg(images[activeImg])} alt={`${listing.make} ${listing.model}`}
                        style={{ width:'100%', height:'100%', objectFit:'cover' }}
                        onError={e => { (e.target as HTMLImageElement).src = images[activeImg] }} />
                    : <div style={{ display:'flex', alignItems:'center', justifyContent:'center', height:'100%', fontSize:60 }}>🚗</div>
                }
              </div>
              {images.length > 1 && (
                <div style={{ display:'flex', gap:8, overflowX:'auto' }}>
                  {images.slice(0, 10).map((img: string, i: number) => (
                    <div key={i} onClick={() => setActiveImg(i)} style={{
                      width:80, height:58, flexShrink:0, borderRadius:8, overflow:'hidden', cursor:'pointer',
                      border: `2px solid ${activeImg === i ? 'var(--accent)' : 'transparent'}`,
                    }}>
                      <img src={img} alt="" style={{ width:'100%', height:'100%', objectFit:'cover' }} />
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Specifikacije */}
            <div style={{ background:'var(--bg2)', border:'1px solid var(--border)', borderRadius:'var(--radius)', padding:24, marginBottom:20 }}>
              <h2 style={{ fontSize:16, marginBottom:16 }}>Specifikacije</h2>
              {enriching && specs.length === 0 ? (
                <div style={{ display:'grid', gridTemplateColumns:'repeat(3,1fr)', gap:12 }}>
                  {[...Array(3)].map((_,i) => <div key={i} className="skeleton" style={{ height:52, borderRadius:8 }} />)}
                </div>
              ) : specs.length > 0 ? (
                <div style={{ display:'grid', gridTemplateColumns:'repeat(3,1fr)', gap:12 }}>
                  {specs.map(s => (
                    <div key={s.label} style={{ background:'var(--bg3)', borderRadius:8, padding:'10px 14px' }}>
                      <div style={{ fontSize:11, color:'var(--text3)', marginBottom:3 }}>{s.label}</div>
                      <div style={{ fontSize:14, fontWeight:500, display:'flex', alignItems:'center', gap:6 }}>
                        {s.value}
                        {s.label === 'Grad' && s.value && (
                          <a href={`https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(String(s.value))}`}
                            target="_blank" rel="noopener noreferrer" title="Otvori na Google Maps"
                            style={{ fontSize:16, textDecoration:'none', lineHeight:1 }}>🗺️</a>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p style={{ color:'var(--text3)', fontSize:13, margin:0 }}>Specifikacije se učitavaju...</p>
              )}
            </div>

            {listing.description && (
              <div style={{ background:'var(--bg2)', border:'1px solid var(--border)', borderRadius:'var(--radius)', padding:24, marginBottom:20 }}>
                <h2 style={{ fontSize:16, marginBottom:12 }}>Opis</h2>
                <p style={{ color:'var(--text2)', lineHeight:1.8, fontSize:14, whiteSpace:'pre-line' }}>{listing.description}</p>
              </div>
            )}

            {listing.features?.length > 0 && (
              <div style={{ background:'var(--bg2)', border:'1px solid var(--border)', borderRadius:'var(--radius)', padding:24, marginBottom:20 }}>
                <h2 style={{ fontSize:16, marginBottom:16 }}>Oprema ({listing.features.length})</h2>
                <div style={{ display:'flex', flexWrap:'wrap', gap:8 }}>
                  {listing.features.map((f: string) => (
                    <span key={f} style={{ background:'var(--bg3)', border:'1px solid var(--border)', borderRadius:20, padding:'4px 12px', fontSize:12, color:'var(--text2)' }}>{f}</span>
                  ))}
                </div>
              </div>
            )}

            {history.length > 1 && (
              <div style={{ background:'var(--bg2)', border:'1px solid var(--border)', borderRadius:'var(--radius)', padding:24, marginBottom:20 }}>
                <h2 style={{ fontSize:16, marginBottom:16 }}>Istorija cene</h2>
                <PriceChart history={history} />
              </div>
            )}

            {similar.length > 0 && (
              <div style={{ marginBottom: 20 }}>
                <h2 style={{ fontSize:16, marginBottom:16 }}>Slični oglasi</h2>
                <div style={{ display:'grid', gridTemplateColumns:'repeat(auto-fill,minmax(200px,1fr))', gap:12 }}>
                  {similar.slice(0, 4).map((s: any) => (
                    <a key={s.id} href={`/listing/${s.id}`} style={{
                      background:'var(--bg2)', border:'1px solid var(--border)', borderRadius:'var(--radius)',
                      overflow:'hidden', display:'block', textDecoration:'none',
                    }}>
                      <div style={{ height:130, background:'var(--bg3)', overflow:'hidden' }}>
                        {s.images?.[0]
                          ? <img src={fullImg(s.images[0])} alt="" style={{ width:'100%', height:'100%', objectFit:'cover' }} onError={e => { (e.target as HTMLImageElement).src = s.images[0] }} />
                          : <div style={{ height:'100%', display:'flex', alignItems:'center', justifyContent:'center', fontSize:28 }}>🚗</div>
                        }
                      </div>
                      <div style={{ padding:12 }}>
                        <div style={{ fontSize:13, fontWeight:600, color:'var(--text)' }}>{s.year} {s.make} {s.model}</div>
                        <div style={{ fontSize:14, color:'var(--accent)', fontWeight:700, marginTop:4 }}>{s.price ? `${fmt(s.price)} €` : '—'}</div>
                        {fmtKm(s.mileage) && <div style={{ fontSize:11, color:'var(--text3)', marginTop:2 }}>🛣 {fmtKm(s.mileage)}</div>}
                      </div>
                    </a>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Desna kolona — sidebar */}
          <div style={{ position:'sticky', top:80, display:'flex', flexDirection:'column', gap:14 }}>

            <div style={{ background:'var(--bg2)', border:'1px solid var(--border)', borderRadius:'var(--radius)', padding:22 }}>
              <h1 style={{ fontSize:20, marginBottom:4, fontFamily:'Syne,sans-serif' }}>{listing.make} {listing.model}</h1>
              {listing.year && <div style={{ color:'var(--text3)', fontSize:13, marginBottom:10 }}>Godište: {listing.year}</div>}

              <div style={{ fontSize:30, fontWeight:800, color:'var(--accent)', marginBottom:12 }}>
                {price ? `${fmt(price)} €` : 'Cena na upit'}
              </div>

              {listing.price_estimated && (
                <div style={{
                  background: deltaGood ? '#16A34A15' : '#78716C15',
                  border: `1px solid ${deltaGood ? '#22C55E40' : '#78716C40'}`,
                  borderRadius:8, padding:'10px 14px', marginBottom:12,
                }}>
                  <div style={{ fontSize:11, color:'var(--text3)', marginBottom:2 }}>AI procena tržišne vrednosti</div>
                  <div style={{ fontWeight:600 }}>{fmt(listing.price_estimated)} €</div>
                  <div style={{ fontSize:12, color: deltaGood ? '#22C55E' : '#F87171', marginTop:2 }}>
                    {deltaGood ? '✅ Ispod tržišne vrednosti' : '⚠️ Iznad tržišne vrednosti'}{' '}
                    {Math.abs(Number(listing.price_delta_pct)).toFixed(0)}%
                  </div>
                </div>
              )}

              {/* Pogledaj oglas — primarno */}
              <a href={listing.url} target="_blank" rel="noopener" style={{
                display:'block', width:'100%', padding:'13px', textAlign:'center',
                background:'var(--accent)', color:'#fff', borderRadius:10,
                fontWeight:700, fontSize:15, marginBottom:10, textDecoration:'none',
              }}>Pogledaj oglas →</a>

              {/* Kontaktiraj prodavca */}
              <button onClick={() => setShowContact(true)} style={{
                width:'100%', padding:'12px', marginBottom:10,
                background:'rgba(99,102,241,.1)', border:'1px solid rgba(99,102,241,.35)',
                color:'#818CF8', borderRadius:10, fontSize:14, fontWeight:700, cursor:'pointer',
              }}>
                🤖 Kontaktiraj prodavca
                <div style={{ fontSize:11, fontWeight:400, color:'rgba(129,140,248,.7)', marginTop:2 }}>
                  AI generiše poruku na jeziku prodavca
                </div>
              </button>

              {/* VELIKO AZURIRAJ DUGME — primarna akcija */}
              <button
                onClick={manualRefresh}
                disabled={enriching || enriched}
                style={{
                  width:'100%', padding:'14px', marginBottom:10,
                  background: enriched
                    ? 'rgba(34,197,94,.1)'
                    : enriching
                    ? 'var(--bg3)'
                    : 'linear-gradient(135deg, rgba(99,102,241,.15), rgba(99,102,241,.08))',
                  border: `2px solid ${enriched ? '#22C55E' : enriching ? 'var(--border)' : 'rgba(99,102,241,.5)'}`,
                  color: enriched ? '#22C55E' : enriching ? 'var(--text3)' : '#818CF8',
                  borderRadius:12, fontSize:14, fontWeight:700,
                  cursor: (enriching || enriched) ? 'default' : 'pointer',
                  transition:'all .2s',
                }}
              >
                {enriching ? (
                  <div style={{ display:'flex', alignItems:'center', justifyContent:'center', gap:8 }}>
                    <div style={{ width:8, height:8, borderRadius:'50%', background:'#818CF8', animation:'pulse 1s infinite' }} />
                    AI analizira oglas...
                  </div>
                ) : enriched ? (
                  '✅ Oglas analiziran'
                ) : (
                  <div>
                    🔍 Analiziraj oglas sa AI
                    <div style={{ fontSize:11, fontWeight:400, color:'rgba(129,140,248,.7)', marginTop:3 }}>
                      Učitaj godište, km, slike i Euro normu
                    </div>
                  </div>
                )}
              </button>

              {/* Sačuvaj oglas */}
              {/* Share dugme */}
              <button onClick={() => {
                const url = window.location.href
                if (navigator.share) {
                  navigator.share({
                    title: `${listing.year} ${listing.make} ${listing.model}`,
                    text: `Pogledaj ovaj oglas na AutoAI — ${listing.year} ${listing.make} ${listing.model} za ${listing.price ? Number(listing.price).toLocaleString() + ' €' : 'na upit'}`,
                    url,
                  })
                } else {
                  navigator.clipboard.writeText(url)
                  alert('Link kopiran!')
                }
              }} style={{
                width:'100%', padding:'10px', marginBottom:10,
                background:'transparent',
                border:'1px solid var(--border)',
                color:'var(--text2)',
                borderRadius:10, fontSize:13, cursor:'pointer',
                display:'flex', alignItems:'center', justifyContent:'center', gap:6,
              }}>
                🔗 Podeli oglas
              </button>
              <button onClick={async () => {
                const token = localStorage.getItem('autoai_token')
                if (!token) { window.location.href = '/login'; return }
                try {
                  const apiBase = process.env.NEXT_PUBLIC_API_URL || 'https://autoai-platform-production.up.railway.app/api/v1'
                  const res = await fetch(`${apiBase}/users/me/favorites`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
                    body: JSON.stringify({ listing_id: listing.id }),
                  })
                  if (res.ok) setFavorited(true)
                } catch {}
              }} style={{
                width:'100%', padding:'10px', background:'transparent',
                border: `1px solid ${favorited ? 'var(--accent)' : 'var(--border)'}`,
                color: favorited ? 'var(--accent)' : 'var(--text2)',
                borderRadius:10, fontSize:13, cursor:'pointer',
              }}>
                {favorited ? '❤️ U favoritima' : '🤍 Sačuvaj oglas'}
              </button>
            </div>

            {/* Uvoz u Srbiju */}
            <div style={{ background:`${eligColor}11`, border:`1px solid ${eligColor}33`, borderRadius:'var(--radius)', padding:18 }}>
              <div style={{ fontSize:11, color:'var(--text3)', letterSpacing:'.07em', fontWeight:600, marginBottom:6 }}>UVOZ U SRBIJU</div>
              {enriching && !listing.year ? (
                <>
                  <div className="skeleton" style={{ height:20, borderRadius:6, marginBottom:8, width:'70%' }} />
                  <div className="skeleton" style={{ height:14, borderRadius:6, width:'90%' }} />
                </>
              ) : (
                <>
                  <div style={{ fontSize:14, fontWeight:800, color:eligColor, marginBottom:4 }}>{elig.emoji} {elig.label}</div>
                  {elig.tooltip && <div style={{ fontSize:11, color:'var(--text3)', marginBottom:8, lineHeight:1.4 }}>{elig.tooltip}</div>}
                  <p style={{ fontSize:12, color:'var(--text2)', margin:'0 0 8px', lineHeight:1.5 }}>{elig.reason}</p>
                  {elig.warnings.map((w: string, i: number) => (
                    <div key={i} style={{ fontSize:11, color:'var(--text3)', paddingLeft:10, borderLeft:`2px solid ${eligColor}55`, marginBottom:3, lineHeight:1.4 }}>{w}</div>
                  ))}
                </>
              )}
            </div>

            {/* Troškovi uvoza */}
            {bd && (
              <div style={{ background:'rgba(255,107,0,.07)', border:'1px solid rgba(255,107,0,.2)', borderRadius:'var(--radius)', overflow:'hidden' }}>
                <button onClick={() => setShowBd(!showBd)} style={{
                  width:'100%', background:'none', border:'none', cursor:'pointer',
                  padding:'14px 16px', display:'flex', justifyContent:'space-between', alignItems:'center',
                }}>
                  <div style={{ textAlign:'left' }}>
                    <div style={{ fontSize:11, color:'var(--text3)', marginBottom:2 }}>🇷🇸 Ukupno za Srbiju</div>
                    <div style={{ fontSize:22, fontWeight:800, color:'var(--accent)' }}>{fmt(bd.total)} €</div>
                  </div>
                  <span style={{ fontSize:11, color:'rgba(255,107,0,.6)' }}>{showBd ? '▲' : '▼ detalji'}</span>
                </button>
                {showBd && (
                  <div style={{ padding:'0 16px 14px', borderTop:'1px solid rgba(255,107,0,.15)' }}>
                    {[
                      { label:'EU cena',         val: price!,       note:'' },
                      { label:`Carina (${bd.carinaPct}%)`, val: bd.carina, note: bd.carinaPct===0?'oslobođeno':'srbija' },
                      { label:'PDV (20%)',        val: bd.pdv,       note:'srbija' },
                      { label:'Transport EU→RS',  val: bd.transport, note:'procena' },
                      { label:'Registracija',     val: bd.reg,       note:'procena' },
                    ].map(({ label, val, note }, i) => (
                      <div key={i} style={{ display:'flex', justifyContent:'space-between', padding:'5px 0', borderTop: i===0?'none':'1px solid rgba(255,255,255,.04)', marginTop: i===0?8:0 }}>
                        <span style={{ fontSize:12, color: i===0?'var(--text2)':'var(--text3)' }}>
                          {i>0&&'+ '}{label}{note&&<span style={{ fontSize:10, marginLeft:5, opacity:.5 }}>({note})</span>}
                        </span>
                        <span style={{ fontSize:12, fontWeight:600, color: i===0?'var(--text2)':'#fb923c' }}>
                          {i===0?'':'+'}{fmt(val)} €
                        </span>
                      </div>
                    ))}
                    <div style={{ display:'flex', justifyContent:'space-between', marginTop:10, paddingTop:10, borderTop:'1px solid rgba(255,107,0,.25)' }}>
                      <span style={{ fontSize:13, fontWeight:700 }}>Ukupno za Srbiju</span>
                      <span style={{ fontSize:14, fontWeight:800, color:'var(--accent)' }}>{fmt(bd.total)} €</span>
                    </div>
                    <p style={{ fontSize:10, color:'var(--text3)', margin:'8px 0 0', lineHeight:1.4 }}>
                      * Procena je informativna. Stvarni troškovi mogu varirati.
                    </p>
                  </div>
                )}
              </div>
            )}

            {/* Provera prevare */}
            {fraud && (
              <div style={{
                background:'var(--bg2)', border:`1px solid ${fraud.badge?.color+'40'||'var(--border)'}`,
                borderRadius:'var(--radius)', padding:18,
              }}>
                <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between', marginBottom:10 }}>
                  <h3 style={{ fontSize:13, fontWeight:600 }}>Provera prevare</h3>
                  <span style={{
                    fontSize:11, padding:'3px 10px', borderRadius:20,
                    background: fraud.badge?.color+'20', color: fraud.badge?.color,
                    border: `1px solid ${fraud.badge?.color+'40'}`,
                  }}>{fraud.badge?.text}</span>
                </div>
                {fraud.red_flags?.map((f: string) => (
                  <div key={f} style={{ fontSize:12, color:'#F87171', display:'flex', gap:6, marginBottom:3 }}>⚠ {f}</div>
                ))}
                {fraud.safe_signals?.map((s: string) => (
                  <div key={s} style={{ fontSize:12, color:'#22C55E', display:'flex', gap:6, marginBottom:3 }}>✓ {s}</div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

function PriceChart({ history }: { history: any[] }) {
  const prices = history.map(h => Number(h.price))
  const min = Math.min(...prices), max = Math.max(...prices)
  const range = max - min || 1
  const W = 500, H = 100, PAD = 10
  const points = history.map((h, i) => ({
    x: PAD + (i / (history.length - 1)) * (W - PAD * 2),
    y: H - PAD - ((Number(h.price) - min) / range) * (H - PAD * 2),
    price: Number(h.price),
    date: new Date(h.recorded_at).toLocaleDateString('sr'),
  }))
  const path = points.map((p, i) => `${i===0?'M':'L'} ${p.x} ${p.y}`).join(' ')
  return (
    <div style={{ overflowX:'auto' }}>
      <svg viewBox={`0 0 ${W} ${H}`} style={{ width:'100%', maxWidth:W }}>
        <defs>
          <linearGradient id="grad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#F97316" stopOpacity="0.3" />
            <stop offset="100%" stopColor="#F97316" stopOpacity="0" />
          </linearGradient>
        </defs>
        <path d={`${path} L ${points[points.length-1].x} ${H} L ${points[0].x} ${H} Z`} fill="url(#grad)" />
        <path d={path} fill="none" stroke="#F97316" strokeWidth="2" strokeLinecap="round" />
        {points.map((p, i) => <circle key={i} cx={p.x} cy={p.y} r="3" fill="#F97316" />)}
      </svg>
      <div style={{ display:'flex', justifyContent:'space-between', fontSize:11, color:'var(--text3)', marginTop:4 }}>
        <span>{points[0].date}: {points[0].price.toLocaleString()} €</span>
        <span>{points[points.length-1].date}: {points[points.length-1].price.toLocaleString()} €</span>
      </div>
    </div>
  )
}

function PageSkeleton() {
  return (
    <div style={{ padding:'32px 0' }}>
      <div className="container" style={{ display:'grid', gridTemplateColumns:'1fr 340px', gap:28 }}>
        <div>
          <div className="skeleton" style={{ height:420, borderRadius:12, marginBottom:8 }} />
          <div className="skeleton" style={{ height:200, borderRadius:12, marginTop:16 }} />
        </div>
        <div><div className="skeleton" style={{ height:400, borderRadius:12 }} /></div>
      </div>
    </div>
  )
}
