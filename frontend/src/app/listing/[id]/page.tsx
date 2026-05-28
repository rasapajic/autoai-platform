'use client'
import { useEffect, useState, useRef } from 'react'
import { getListing, getPriceHistory, getSimilar, fraudCheck } from '@/lib/api'
import ContactModal from '@/components/ContactModal'
import VinChecker from '@/components/VinChecker'
import ModelChecklist from '@/components/ModelChecklist'

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'https://autoai-platform-production.up.railway.app/api/v1'

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
    label: 'Visoka verovatnoća uspešnog uvoza',
    sublabel: 'Električna vozila · 0% carine',
    reason: 'EV su oslobođeni carine. Potrebna COC dokumentacija i provera punjača.',
    tooltip: 'Električna vozila imaju povlašćen tretman pri uvozu u Srbiju.',
    warnings: ['Proveri kompatibilnost punjača (Tip 2 / CCS).', 'Pribavi COC dokument pre uvoza.'],
    confidence: 'high', carinaPct: 0,
  }
  if (age !== null && age >= 30) return {
    status: 'oldtimer', emoji: '🟣',
    label: 'Oldtimer — poseban režim uvoza',
    sublabel: 'Starije od 30 godina',
    reason: `Vozilo (${year}) starije od 30 god. — uvoz moguć uz posebne uslove.`,
    tooltip: 'Oldtimer vozila imaju poseban carinski tretman.',
    warnings: ['Registracija kao oldtimer zahteva poseban tehnički pregled.', 'Konsultuj carinskog agenta.'],
    confidence: 'medium', carinaPct: 5,
  }
  if (!year) return {
    status: 'needs_check', emoji: '🟠',
    label: 'Potrebna provera Euro norme',
    sublabel: 'Godište nepoznato',
    reason: 'Bez potvrđenog godišta nije moguće proceniti Euro normu.',
    tooltip: 'Zatraži datum prve registracije od prodavca.',
    warnings: ['Zatraži COC dokument i datum prve registracije.', 'Bez Euro norme moguć problem pri carinjenju.'],
    confidence: 'low', carinaPct: 5,
  }
  if (year >= 2015) return {
    status: 'eligible', emoji: '🟢',
    label: 'Visoka verovatnoća uspešnog uvoza',
    sublabel: `Euro 6 · ${year}. godište`,
    reason: `Vozilo (${year}) ispunjava Euro 6 — bez ograničenja pri uvozu.`,
    tooltip: 'Euro 6 vozila prolaze carinjenje bez problema.',
    warnings: ['Pribavi COC dokument.', ...(fuel === 'diesel' ? ['Proveri stanje DPF filtera.'] : [])],
    confidence: 'high', carinaPct: 5,
  }
  if (year >= 2011) return {
    status: 'eligible', emoji: '🟢',
    label: 'Verovatno uspešan uvoz',
    sublabel: `Euro 5 · ${year}. godište`,
    reason: `Vozilo (${year}) verovatno ispunjava Euro 5 normu.`,
    tooltip: 'Euro 5 vozila se mogu uvesti bez ograničenja.',
    warnings: ['Pribavi COC za potvrdu Euro 5.', ...(fuel === 'diesel' ? ['Dizel Euro 5 — proveri DPF filter.'] : [])],
    confidence: 'high', carinaPct: 5,
  }
  if (year >= 2006) return {
    status: 'eligible', emoji: fuel === 'diesel' ? '🟠' : '🟢',
    label: fuel === 'diesel' ? 'Potrebna provera Euro 4 norme' : 'Verovatno uspešan uvoz',
    sublabel: `Euro 4 · ${year}. godište`,
    reason: `Vozilo (${year}) — Euro 4 je minimalni uslov za uvoz.`,
    tooltip: 'Euro 4 je granica — obavezno proveri dokumentaciju.',
    warnings: ['Obavezno pribavi COC dokument.', ...(fuel === 'diesel' ? ['Dizel Euro 4 — rizik DPF i turbine.'] : [])],
    confidence: fuel === 'diesel' ? 'medium' : 'high', carinaPct: 5,
  }
  if (year >= 2001) return {
    status: 'needs_check', emoji: '🟠',
    label: 'Rizik pri uvozu — proveri Euro normu',
    sublabel: `Verovatno Euro 3 · ${year}. godište`,
    reason: `Vozilo (${year}) verovatno Euro 3 — uvoz moguć ali komplikovan.`,
    tooltip: 'Euro 3 može imati probleme pri tehničkom pregledu.',
    warnings: ['Konsultuj carinskog agenta pre kupovine.'],
    confidence: 'low', carinaPct: 5,
  }
  return {
    status: 'not_recommended', emoji: '🔴',
    label: 'Visok rizik pri uvozu',
    sublabel: `Prestara norma · ${year}. godište`,
    reason: `Vozilo (${year}) ne ispunjava minimalne standarde za uvoz u Srbiju.`,
    tooltip: 'Registracija u Srbiji verovatno nije moguća.',
    warnings: ['Stara vozila ne prolaze tehnički pregled u Srbiji.'],
    confidence: 'none', carinaPct: 5,
  }
}

// ✅ Poboljšan Trust Score — analitičan, ne optužujući
function calcTrustScore(listing: any): {
  score: number; label: string; color: string;
  positives: {text: string; weight: string}[];
  warnings: {text: string; severity: 'critical' | 'important' | 'minor'}[];
} {
  let score = 0
  const positives: {text: string; weight: string}[] = []
  const warnings: {text: string; severity: 'critical' | 'important' | 'minor'}[] = []

  const year    = listing.year ? Number(listing.year) : null
  const mileage = listing.mileage ? Number(listing.mileage) : null
  const price   = listing.price ? Number(listing.price) : null
  const delta   = listing.price_delta_pct ? Number(listing.price_delta_pct) : null
  const images  = listing.images || []
  const imgCount = images.length

  // Slike (0–20)
  if (imgCount >= 10)     { score += 20; positives.push({ text: `${imgCount} fotografija vozila`, weight: '+20' }) }
  else if (imgCount >= 6) { score += 15; positives.push({ text: `${imgCount} fotografija`, weight: '+15' }) }
  else if (imgCount >= 3) { score += 8;  warnings.push({ text: 'Manji broj fotografija vozila', severity: 'minor' }) }
  else if (imgCount >= 1) { score += 3;  warnings.push({ text: 'Premalo fotografija vozila', severity: 'important' }) }
  else                    { warnings.push({ text: 'Nema fotografija vozila', severity: 'critical' }) }

  // Godište (0–8)
  if (year) { score += 8; positives.push({ text: `Godište navedeno: ${year}`, weight: '+8' }) }
  else warnings.push({ text: 'Godište nije navedeno', severity: 'important' })

  // Kilometraža (0–8)
  if (mileage) {
    score += 6
    const annualKm = year ? mileage / (2026 - year) : null
    if (annualKm && annualKm > 35000) {
      score -= 3
      warnings.push({ text: `Visoka godišnja kilometraža (${Math.round(annualKm).toLocaleString()} km/god)`, severity: 'minor' })
    } else {
      positives.push({ text: `Kilometraža: ${mileage.toLocaleString()} km`, weight: '+6' })
    }
  } else warnings.push({ text: 'Kilometraža nije navedena', severity: 'important' })

  // Gorivo (0–5)
  if (listing.fuel_type) score += 5
  else warnings.push({ text: 'Vrsta goriva nije navedena', severity: 'minor' })

  // Menjač (0–4)
  if (listing.transmission) score += 4

  // Cena (0–18)
  if (delta !== null) {
    if (delta < -25) {
      score += 4
      warnings.push({ text: `Cena je ${Math.abs(delta).toFixed(0)}% ispod tržišnog proseka — proveri razlog`, severity: 'important' })
    } else if (delta < -5) {
      score += 18
      positives.push({ text: `Cena ispod tržišnog proseka za ${Math.abs(delta).toFixed(0)}% na osnovu sličnih oglasa`, weight: '+18' })
    } else if (delta <= 8) {
      score += 13
      positives.push({ text: 'Cena odgovara tržišnom proseku', weight: '+13' })
    } else if (delta <= 18) {
      score += 6
      warnings.push({ text: `Cena iznad tržišnog proseka za ${delta.toFixed(0)}% na osnovu sličnih oglasa`, severity: 'minor' })
    } else {
      score += 2
      warnings.push({ text: `Cena značajno iznad tržišnog proseka (${delta.toFixed(0)}%)`, severity: 'important' })
    }
  } else if (price) score += 8

  // Opis (0–7)
  if (listing.description && listing.description.length > 100) {
    score += 7; positives.push({ text: 'Detaljan opis vozila', weight: '+7' })
  } else if (listing.description && listing.description.length > 30) {
    score += 3
  } else {
    warnings.push({ text: 'Kratak ili nedostaje opis vozila', severity: 'minor' })
  }

  // Uvoz (0–20)
  const elig = getSerbiaEligibility(listing)
  if (elig.confidence === 'high') {
    score += 20; positives.push({ text: 'Pogodan za uvoz u Srbiju', weight: '+20' })
  } else if (elig.confidence === 'medium') {
    score += 10; warnings.push({ text: 'Potrebna dodatna provera za uvoz', severity: 'minor' })
  } else if (elig.confidence === 'low') {
    score += 3; warnings.push({ text: 'Nesigurnost pri uvozu u Srbiju', severity: 'important' })
  } else {
    warnings.push({ text: 'Problematičan uvoz u Srbiju', severity: 'critical' })
  }

  score = Math.min(100, Math.max(0, Math.round(score)))

  // ✅ Poboljšane kategorije — manje dramatične
  let label = '', color = ''
  if (score >= 85)      { label = 'Veoma kvalitetan oglas'; color = '#22C55E' }
  else if (score >= 70) { label = 'Dobar oglas'; color = '#22C55E' }
  else if (score >= 55) { label = 'Potrebna dodatna provera'; color = '#F97316' }
  else                  { label = 'Povećan rizik'; color = '#EF4444' }

  return { score, label, color, positives, warnings }
}

function calcImport(price: number, carinaPct: number) {
  const carina = Math.round(price * carinaPct / 100)
  const pdv    = Math.round((price + carina) * 0.20)
  return { carina, pdv, transport: 420, reg: 280, total: price + carina + pdv + 420 + 280, carinaPct }
}

function fmt(n: any)   { return Number(n).toLocaleString('de-DE') }
function fmtKm(km: any) {
  const n = Number(km)
  if (!n || n < 1 || n > 999999) return null
  return n.toLocaleString('de-DE') + ' km'
}
function fullImg(url: string) {
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
  const [backUrl,     setBackUrl]     = useState('/search')
  const scanInterval = useRef<any>(null)

  useEffect(() => {
    const prev = sessionStorage.getItem('autoai_search_url')
    if (prev) setBackUrl(prev)
  }, [])

  useEffect(() => {
    Promise.allSettled([
      getListing(params.id), getPriceHistory(params.id),
      getSimilar(params.id), fraudCheck(params.id),
    ]).then(([l, h, s, f]) => {
      if (l.status === 'fulfilled') {
        const data = l.value; setListing(data)
        if (data?.url && (!data.year || !data.mileage)) autoEnrich(data.url)
      }
      if (h.status === 'fulfilled') setHistory(h.value)
      if (s.status === 'fulfilled') setSimilar(s.value)
      if (f.status === 'fulfilled') setFraud(f.value)
    }).finally(() => setLoading(false))
  }, [params.id])

  const startScanMessages = () => {
    let i = 0; setScanMsg(AI_SCAN_MESSAGES[0])
    scanInterval.current = setInterval(() => { i = (i + 1) % AI_SCAN_MESSAGES.length; setScanMsg(AI_SCAN_MESSAGES[i]) }, 1800)
  }
  const stopScanMessages = () => { if (scanInterval.current) clearInterval(scanInterval.current) }

  const autoEnrich = async (url: string) => {
    if (enriching || enriched) return
    setEnriching(true); startScanMessages()
    try {
      const res  = await fetch(`${API_BASE}/analyze/`, { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ url }) })
      const data = await res.json()
      if (data.scrape_success) {
        setListing((prev: any) => ({
          ...prev,
          year: data.year||prev.year, mileage: data.mileage||prev.mileage,
          fuel_type: data.fuel_type||prev.fuel_type, engine_power_kw: data.engine_power_kw||prev.engine_power_kw,
          country: data.country||prev.country, city: data.city||prev.city,
          transmission: data.transmission||prev.transmission,
          images: (data.images?.length||0) > (prev.images?.length||0) ? data.images : prev.images,
        }))
        setEnriched(true)
      }
    } catch {}
    stopScanMessages(); setEnriching(false)
  }

  if (loading) return <PageSkeleton />
  if (!listing) return <div style={{ textAlign:'center', padding:'80px 0', color:'var(--text3)' }}>Oglas nije pronađen.</div>

  const images    = listing.images || []
  const elig      = getSerbiaEligibility(listing)
  const eligColor = ELIGIBILITY_COLORS[elig.status] || '#F97316'
  const price     = listing.price ? Number(listing.price) : null
  const bd        = price ? calcImport(price, elig.carinaPct) : null
  const deltaGood = listing.price_delta_pct && Number(listing.price_delta_pct) < 0
  const trust     = calcTrustScore(listing)

  const specs = [
    { label:'Godište',    value: listing.year },
    { label:'Kilometraža',value: fmtKm(listing.mileage) },
    { label:'Gorivo',     value: listing.fuel_type ? ({diesel:'Dizel',petrol:'Benzin',electric:'Električni',hybrid:'Hibrid',lpg:'Plin',gasoline:'Benzin'} as any)[listing.fuel_type]||listing.fuel_type : null },
    { label:'Menjač',     value: listing.transmission==='automatic'?'Automatik':listing.transmission==='manual'?'Manuel':listing.transmission },
    { label:'Snaga',      value: listing.engine_power_kw?`${listing.engine_power_kw} kW`:null },
    { label:'Karoserija', value: listing.body_type },
    { label:'Zemlja',     value: listing.country },
    { label:'Grad',       value: listing.city?listing.city.split(' - ')[0]:null },
  ].filter(s => s.value)

  return (
    <div style={{ padding:'24px 0 80px' }}>
      {showContact && <ContactModal listing={listing} onClose={() => setShowContact(false)} />}
      <style>{`
        @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.3} }
        .trust-bar { transition: width .6s ease; }
        @media(max-width:768px){
          .listing-grid { grid-template-columns:1fr !important; }
          .listing-sidebar { position:static !important; }
          .desktop-only { display:none !important; }
          .mobile-top { display:block !important; }
        }
        @media(min-width:769px){ .mobile-top { display:none !important; } }
        .mobile-top { display:none; }
      `}</style>

      <div className="container">

        {/* Breadcrumb */}
        <div style={{ fontSize:13, color:'var(--text3)', marginBottom:16, display:'flex', alignItems:'center', gap:6 }}>
          <a href="/" style={{ color:'var(--text3)', textDecoration:'none' }}>Početna</a>
          <span>→</span>
          <a href={backUrl} style={{ color:'var(--text3)', textDecoration:'none' }}>← Pretraga</a>
          <span>→</span>
          <span style={{ color:'var(--text)' }}>{listing.make} {listing.model}</span>
        </div>

        {/* MOBILE TOP */}
        <div className="mobile-top" style={{ marginBottom:14 }}>
          <div style={{ background:'var(--bg2)', border:'1px solid var(--border)', borderRadius:14, padding:'14px 16px', marginBottom:10 }}>
            <div style={{ fontSize:13, color:'var(--text3)', marginBottom:4 }}>{listing.make} {listing.model}{listing.year?` · ${listing.year}`:''}</div>
            <div style={{ fontSize:26, fontWeight:800, color:'var(--accent)' }}>{price?`${fmt(price)} €`:'Cena na upit'}</div>
            {bd && <div style={{ fontSize:13, color:'var(--text3)', marginTop:2 }}>🇷🇸 Ukupno: <strong style={{ color:'var(--text2)' }}>{fmt(bd.total)} €</strong></div>}
          </div>
          <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:8, marginBottom:10 }}>
            <div style={{ background:`${eligColor}11`, border:`1px solid ${eligColor}33`, borderRadius:12, padding:'10px 12px' }}>
              <div style={{ fontSize:12, fontWeight:700, color:eligColor }}>{elig.emoji} Uvoz</div>
              <div style={{ fontSize:11, color:'var(--text3)', marginTop:2 }}>{elig.sublabel || elig.label}</div>
            </div>
            <div style={{ background:`${trust.color}11`, border:`1px solid ${trust.color}33`, borderRadius:12, padding:'10px 12px' }}>
              <div style={{ fontSize:12, fontWeight:700, color:trust.color }}>AI procena</div>
              <div style={{ fontSize:18, fontWeight:800, color:trust.color }}>{trust.score}/100</div>
            </div>
          </div>
          <a href={listing.url} target="_blank" rel="noopener" style={{ display:'block', width:'100%', padding:'12px', textAlign:'center', background:'var(--accent)', color:'#fff', borderRadius:10, fontWeight:700, fontSize:14, marginBottom:8, textDecoration:'none', boxSizing:'border-box' as any }}>Pogledaj oglas →</a>
          <button onClick={() => setShowContact(true)} style={{ width:'100%', padding:'11px', background:'rgba(99,102,241,.1)', border:'1px solid rgba(99,102,241,.35)', color:'#818CF8', borderRadius:10, fontSize:13, fontWeight:700, cursor:'pointer' }}>🤖 Kontaktiraj prodavca</button>
        </div>

        {enriching && (
          <div style={{ background:'rgba(99,102,241,.08)', border:'1px solid rgba(99,102,241,.3)', borderRadius:12, padding:'11px 16px', marginBottom:14, display:'flex', alignItems:'center', gap:10 }}>
            <div style={{ width:8, height:8, borderRadius:'50%', background:'#818CF8', animation:'pulse 1s infinite', flexShrink:0 }} />
            <span style={{ fontSize:13, color:'#818CF8', fontWeight:600 }}>{scanMsg}</span>
          </div>
        )}
        {enriched && !enriching && (
          <div style={{ background:'rgba(34,197,94,.08)', border:'1px solid rgba(34,197,94,.25)', borderRadius:12, padding:'10px 16px', marginBottom:14, fontSize:13, color:'#22C55E', fontWeight:600 }}>
            ✅ Podaci oglasa su provereni i ažurirani.
          </div>
        )}

        <div className="listing-grid" style={{ display:'grid', gridTemplateColumns:'1fr 340px', gap:28, alignItems:'start' }}>

          {/* LEVA KOLONA */}
          <div>

            {/* Galerija */}
            <div style={{ marginBottom:20 }}>
              <div style={{ height:400, background:'var(--bg3)', borderRadius:'var(--radius)', overflow:'hidden', marginBottom:8, position:'relative' }}>
                {images[activeImg]
                  ? <img src={fullImg(images[activeImg])} alt={`${listing.make} ${listing.model}`} style={{ width:'100%', height:'100%', objectFit:'cover' }} onError={e => { (e.target as HTMLImageElement).src = images[activeImg] }} />
                  : <div style={{ display:'flex', alignItems:'center', justifyContent:'center', height:'100%', fontSize:60 }}>🚗</div>
                }
                <span style={{ position:'absolute', bottom:10, left:10, background:'rgba(0,0,0,.75)', borderRadius:6, padding:'3px 9px', fontSize:11, color:'rgba(255,255,255,.7)', backdropFilter:'blur(4px)' }}>{listing.source}</span>
              </div>
              {images.length > 1 && (
                <div style={{ display:'flex', gap:6, overflowX:'auto' }}>
                  {images.slice(0, 10).map((img: string, i: number) => (
                    <div key={i} onClick={() => setActiveImg(i)} style={{ width:74, height:52, flexShrink:0, borderRadius:7, overflow:'hidden', cursor:'pointer', border:`2px solid ${activeImg===i?'var(--accent)':'transparent'}` }}>
                      <img src={img} alt="" style={{ width:'100%', height:'100%', objectFit:'cover' }} />
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* ✅ AI Procena oglasa */}
            <div style={{ background:'var(--bg2)', border:`2px solid ${trust.color}22`, borderRadius:'var(--radius)', padding:20, marginBottom:20 }}>
              <div style={{ display:'flex', justifyContent:'space-between', alignItems:'flex-start', marginBottom:12 }}>
                <div>
                  <h2 style={{ fontSize:15, margin:'0 0 2px' }}>🤖 AI procena oglasa</h2>
                  <div style={{ fontSize:12, color:'var(--text3)' }}>Automatska analiza kvaliteta i potpunosti</div>
                </div>
                <div style={{ textAlign:'right', flexShrink:0 }}>
                  <div style={{ fontSize:26, fontWeight:800, color:trust.color, lineHeight:1 }}>{trust.score}</div>
                  <div style={{ fontSize:10, color:'var(--text3)' }}>/ 100</div>
                </div>
              </div>
              <div style={{ height:6, background:'rgba(255,255,255,.06)', borderRadius:4, overflow:'hidden', marginBottom:8 }}>
                <div className="trust-bar" style={{ height:'100%', borderRadius:4, width:`${trust.score}%`, background:`linear-gradient(90deg,${trust.color},${trust.color}bb)` }} />
              </div>
              <div style={{ fontSize:13, fontWeight:700, color:trust.color, marginBottom:12 }}>{trust.label}</div>

              <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:5 }}>
                {trust.positives.slice(0, 4).map((p, i) => (
                  <div key={i} style={{ fontSize:12, color:'#22C55E', display:'flex', gap:5, alignItems:'flex-start' }}>
                    <span style={{ marginTop:3, width:5, height:5, borderRadius:'50%', background:'#22C55E', flexShrink:0, display:'inline-block' }} />
                    {p.text}
                  </div>
                ))}
                {trust.warnings.map((w, i) => (
                  <div key={i} style={{ fontSize:12, display:'flex', gap:5, alignItems:'flex-start',
                    color: w.severity==='critical'?'#EF4444':w.severity==='important'?'#F97316':'#EAB308',
                  }}>
                    <span style={{ marginTop:3 }}>{w.severity==='critical'?'🔴':w.severity==='important'?'🟠':'🟡'}</span>
                    {w.text}
                  </div>
                ))}
              </div>
            </div>

            {/* Specifikacije */}
            <div style={{ background:'var(--bg2)', border:'1px solid var(--border)', borderRadius:'var(--radius)', padding:20, marginBottom:20 }}>
              <h2 style={{ fontSize:15, marginBottom:14 }}>Specifikacije</h2>
              {specs.length > 0 ? (
                <div style={{ display:'grid', gridTemplateColumns:'repeat(3,1fr)', gap:10 }}>
                  {specs.map(s => (
                    <div key={s.label} style={{ background:'var(--bg3)', borderRadius:8, padding:'9px 12px' }}>
                      <div style={{ fontSize:10, color:'var(--text3)', marginBottom:2 }}>{s.label}</div>
                      <div style={{ fontSize:13, fontWeight:500, display:'flex', alignItems:'center', gap:5 }}>
                        {s.value}
                        {s.label==='Grad' && s.value && (
                          <a href={`https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(String(s.value))}`} target="_blank" rel="noopener noreferrer" style={{ fontSize:14, textDecoration:'none' }}>🗺️</a>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              ) : <p style={{ color:'var(--text3)', fontSize:13, margin:0 }}>Specifikacije se učitavaju...</p>}
            </div>

            {/* ✅ Model Checklist */}
            {listing.make && (
              <div style={{ background:'var(--bg2)', border:'1px solid var(--border)', borderRadius:'var(--radius)', padding:20, marginBottom:20 }}>
                <ModelChecklist
                  make={listing.make}
                  model={listing.model}
                  year={listing.year}
                  fuelType={listing.fuel_type}
                  transmission={listing.transmission}
                />
              </div>
            )}

            {/* VIN Provera */}
            <div style={{ background:'var(--bg2)', border:'1px solid var(--border)', borderRadius:'var(--radius)', padding:20, marginBottom:20 }}>
              <div style={{ marginBottom:14 }}>
                <h2 style={{ fontSize:15, margin:'0 0 3px' }}>🔐 VIN Provera vozila</h2>
                <p style={{ fontSize:12, color:'var(--text3)', margin:0, lineHeight:1.5 }}>Zatraži VIN od prodavca i proveri da li podaci odgovaraju oglasu.</p>
              </div>
              <VinChecker listing={listing} />
            </div>

            {/* Opis */}
            {listing.description && (
              <div style={{ background:'var(--bg2)', border:'1px solid var(--border)', borderRadius:'var(--radius)', padding:20, marginBottom:20 }}>
                <h2 style={{ fontSize:15, marginBottom:10 }}>Opis</h2>
                <p style={{ color:'var(--text2)', lineHeight:1.8, fontSize:14, whiteSpace:'pre-line', margin:0 }}>{listing.description}</p>
              </div>
            )}

            {listing.features?.length > 0 && (
              <div style={{ background:'var(--bg2)', border:'1px solid var(--border)', borderRadius:'var(--radius)', padding:20, marginBottom:20 }}>
                <h2 style={{ fontSize:15, marginBottom:12 }}>Oprema ({listing.features.length})</h2>
                <div style={{ display:'flex', flexWrap:'wrap', gap:6 }}>
                  {listing.features.map((f: string) => (
                    <span key={f} style={{ background:'var(--bg3)', border:'1px solid var(--border)', borderRadius:20, padding:'3px 11px', fontSize:11, color:'var(--text2)' }}>{f}</span>
                  ))}
                </div>
              </div>
            )}

            {history.length > 1 && (
              <div style={{ background:'var(--bg2)', border:'1px solid var(--border)', borderRadius:'var(--radius)', padding:20, marginBottom:20 }}>
                <h2 style={{ fontSize:15, marginBottom:14 }}>Istorija cene</h2>
                <PriceChart history={history} />
              </div>
            )}

            {similar.length > 0 && (
              <div style={{ marginBottom:20 }}>
                <h2 style={{ fontSize:15, marginBottom:12 }}>Slični oglasi</h2>
                <div style={{ display:'grid', gridTemplateColumns:'repeat(auto-fill,minmax(190px,1fr))', gap:10 }}>
                  {similar.slice(0, 4).map((s: any) => (
                    <a key={s.id} href={`/listing/${s.id}`} style={{ background:'var(--bg2)', border:'1px solid var(--border)', borderRadius:'var(--radius)', overflow:'hidden', display:'block', textDecoration:'none' }}>
                      <div style={{ height:120, background:'var(--bg3)', overflow:'hidden' }}>
                        {s.images?.[0] ? <img src={fullImg(s.images[0])} alt="" style={{ width:'100%', height:'100%', objectFit:'cover' }} /> : <div style={{ height:'100%', display:'flex', alignItems:'center', justifyContent:'center', fontSize:26 }}>🚗</div>}
                      </div>
                      <div style={{ padding:10 }}>
                        <div style={{ fontSize:12, fontWeight:600, color:'var(--text)' }}>{s.year} {s.make} {s.model}</div>
                        <div style={{ fontSize:14, color:'var(--accent)', fontWeight:700, marginTop:3 }}>{s.price?`${fmt(s.price)} €`:'—'}</div>
                      </div>
                    </a>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* DESNA KOLONA */}
          <div className="listing-sidebar" style={{ position:'sticky', top:80, display:'flex', flexDirection:'column', gap:12 }}>

            <div style={{ background:'var(--bg2)', border:'1px solid var(--border)', borderRadius:'var(--radius)', padding:20 }}>
              <h1 style={{ fontSize:18, marginBottom:3, fontFamily:'Syne,sans-serif' }}>{listing.make} {listing.model}</h1>
              {listing.year && <div style={{ color:'var(--text3)', fontSize:12, marginBottom:10 }}>Godište: {listing.year}</div>}
              <div style={{ fontSize:26, fontWeight:800, color:'var(--accent)', marginBottom:10 }}>
                {price?`${fmt(price)} €`:'Cena na upit'}
              </div>

              {listing.price_estimated && (
                <div style={{ background:deltaGood?'#16A34A15':'#78716C15', border:`1px solid ${deltaGood?'#22C55E40':'#78716C40'}`, borderRadius:8, padding:'9px 12px', marginBottom:12 }}>
                  <div style={{ fontSize:11, color:'var(--text3)', marginBottom:2 }}>AI procena tržišne vrednosti</div>
                  <div style={{ fontWeight:600, fontSize:14 }}>{fmt(listing.price_estimated)} €</div>
                  <div style={{ fontSize:12, color:deltaGood?'#22C55E':'#F87171', marginTop:2 }}>
                    {deltaGood?'✅ Ispod':'⚠️ Iznad'} tržišne vrednosti za {Math.abs(Number(listing.price_delta_pct)).toFixed(0)}% na osnovu sličnih oglasa
                  </div>
                </div>
              )}

              <a href={listing.url} target="_blank" rel="noopener" style={{ display:'block', width:'100%', padding:'12px', textAlign:'center', background:'var(--accent)', color:'#fff', borderRadius:10, fontWeight:700, fontSize:14, marginBottom:8, textDecoration:'none' }}>Pogledaj oglas →</a>

              <button onClick={() => setShowContact(true)} style={{ width:'100%', padding:'11px', marginBottom:8, background:'rgba(99,102,241,.1)', border:'1px solid rgba(99,102,241,.35)', color:'#818CF8', borderRadius:10, fontSize:13, fontWeight:700, cursor:'pointer' }}>
                🤖 Kontaktiraj prodavca
                <div style={{ fontSize:11, fontWeight:400, color:'rgba(129,140,248,.7)', marginTop:2 }}>AI generiše poruku na jeziku prodavca</div>
              </button>

              <button onClick={() => { setEnriched(false); autoEnrich(listing.url) }} disabled={enriching || enriched} style={{
                width:'100%', padding:'11px', marginBottom:8,
                background: enriched?'rgba(34,197,94,.1)':enriching?'var(--bg3)':'linear-gradient(135deg,rgba(99,102,241,.15),rgba(99,102,241,.08))',
                border: `2px solid ${enriched?'#22C55E':enriching?'var(--border)':'rgba(99,102,241,.4)'}`,
                color: enriched?'#22C55E':enriching?'var(--text3)':'#818CF8',
                borderRadius:10, fontSize:13, fontWeight:700, cursor:(enriching||enriched)?'default':'pointer',
              }}>
                {enriching
                  ? <span style={{ display:'flex', alignItems:'center', justifyContent:'center', gap:6 }}><span style={{ width:7, height:7, borderRadius:'50%', background:'#818CF8', display:'inline-block', animation:'pulse 1s infinite' }} />Proveravam podatke...</span>
                  : enriched ? '✅ Podaci provereni'
                  : <div>🔍 Proveri podatke oglasa<div style={{ fontSize:11, fontWeight:400, color:'rgba(129,140,248,.7)', marginTop:2 }}>Godište · km · Euro norma · uvoz</div></div>
                }
              </button>

              <div style={{ display:'flex', gap:6 }}>
                <button onClick={() => { const url=window.location.href; if(navigator.share) navigator.share({title:`${listing.year} ${listing.make} ${listing.model}`,url}); else { navigator.clipboard.writeText(url); alert('Link kopiran!') } }} style={{ flex:1, padding:'8px', background:'transparent', border:'1px solid var(--border)', color:'var(--text2)', borderRadius:9, fontSize:12, cursor:'pointer' }}>🔗 Podeli</button>
                <button onClick={async () => {
                  const token = localStorage.getItem('autoai_token')
                  if (!token) { window.location.href='/login'; return }
                  try { const res = await fetch(`${API_BASE}/users/me/favorites`, { method:'POST', headers:{'Content-Type':'application/json','Authorization':`Bearer ${token}`}, body: JSON.stringify({listing_id:listing.id}) }); if (res.ok) setFavorited(true) } catch {}
                }} style={{ flex:1, padding:'8px', background:'transparent', border:`1px solid ${favorited?'var(--accent)':'var(--border)'}`, color:favorited?'var(--accent)':'var(--text2)', borderRadius:9, fontSize:12, cursor:'pointer' }}>
                  {favorited?'❤️ Sačuvano':'🤍 Sačuvaj'}
                </button>
              </div>
            </div>

            {/* AI Procena — sidebar */}
            <div style={{ background:'var(--bg2)', border:`1px solid ${trust.color}33`, borderRadius:'var(--radius)', padding:16 }}>
              <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:8 }}>
                <span style={{ fontSize:11, color:'var(--text3)', fontWeight:600, letterSpacing:'.07em' }}>AI PROCENA OGLASA</span>
                <span style={{ fontSize:20, fontWeight:800, color:trust.color }}>{trust.score}/100</span>
              </div>
              <div style={{ height:5, background:'rgba(255,255,255,.06)', borderRadius:4, overflow:'hidden', marginBottom:6 }}>
                <div className="trust-bar" style={{ height:'100%', borderRadius:4, width:`${trust.score}%`, background:trust.color }} />
              </div>
              <div style={{ fontSize:12, fontWeight:700, color:trust.color }}>{trust.label}</div>
            </div>

            {/* Uvoz u Srbiju */}
            <div style={{ background:`${eligColor}0d`, border:`1px solid ${eligColor}33`, borderRadius:'var(--radius)', padding:16 }}>
              <div style={{ fontSize:10, color:'var(--text3)', letterSpacing:'.07em', fontWeight:600, marginBottom:6 }}>UVOZ U SRBIJU</div>
              <div style={{ fontSize:13, fontWeight:800, color:eligColor, marginBottom:2 }}>{elig.emoji} {elig.label}</div>
              {elig.sublabel && <div style={{ fontSize:11, color:'var(--text3)', marginBottom:6 }}>{elig.sublabel}</div>}
              <p style={{ fontSize:12, color:'var(--text2)', margin:'0 0 6px', lineHeight:1.5 }}>{elig.reason}</p>
              {elig.warnings.slice(0, 2).map((w: string, i: number) => (
                <div key={i} style={{ fontSize:11, color:'var(--text3)', paddingLeft:8, borderLeft:`2px solid ${eligColor}55`, marginBottom:3, lineHeight:1.4 }}>{w}</div>
              ))}
            </div>

            {/* Troškovi */}
            {bd && (
              <div style={{ background:'rgba(255,107,0,.07)', border:'1px solid rgba(255,107,0,.2)', borderRadius:'var(--radius)', overflow:'hidden' }}>
                <button onClick={() => setShowBd(!showBd)} style={{ width:'100%', background:'none', border:'none', cursor:'pointer', padding:'12px 14px', display:'flex', justifyContent:'space-between', alignItems:'center' }}>
                  <div style={{ textAlign:'left' }}>
                    <div style={{ fontSize:11, color:'var(--text3)', marginBottom:1 }}>🇷🇸 Ukupno za Srbiju</div>
                    <div style={{ fontSize:20, fontWeight:800, color:'var(--accent)' }}>{fmt(bd.total)} €</div>
                  </div>
                  <span style={{ fontSize:11, color:'rgba(255,107,0,.6)' }}>{showBd?'▲':'▼ detalji'}</span>
                </button>
                {showBd && (
                  <div style={{ padding:'0 14px 12px', borderTop:'1px solid rgba(255,107,0,.15)' }}>
                    {[
                      { label:'EU cena', val:price!, note:'' },
                      { label:`Carina (${bd.carinaPct}%)`, val:bd.carina, note:bd.carinaPct===0?'oslobođeno':'srbija' },
                      { label:'PDV (20%)', val:bd.pdv, note:'srbija' },
                      { label:'Transport EU→RS', val:bd.transport, note:'procena' },
                      { label:'Registracija', val:bd.reg, note:'procena' },
                    ].map(({ label, val, note }, i) => (
                      <div key={i} style={{ display:'flex', justifyContent:'space-between', padding:'4px 0', borderTop:i===0?'none':'1px solid rgba(255,255,255,.04)', marginTop:i===0?6:0 }}>
                        <span style={{ fontSize:11, color:i===0?'var(--text2)':'var(--text3)' }}>{i>0&&'+ '}{label}{note&&<span style={{ fontSize:10, marginLeft:4, opacity:.5 }}>({note})</span>}</span>
                        <span style={{ fontSize:11, fontWeight:600, color:i===0?'var(--text2)':'#fb923c' }}>{i===0?'':'+'}{fmt(val)} €</span>
                      </div>
                    ))}
                    <div style={{ display:'flex', justifyContent:'space-between', marginTop:8, paddingTop:8, borderTop:'1px solid rgba(255,107,0,.25)' }}>
                      <span style={{ fontSize:12, fontWeight:700 }}>Ukupno</span>
                      <span style={{ fontSize:13, fontWeight:800, color:'var(--accent)' }}>{fmt(bd.total)} €</span>
                    </div>
                    <p style={{ fontSize:10, color:'var(--text3)', margin:'6px 0 0', lineHeight:1.4, opacity:.7 }}>* Procena je informativna.</p>
                  </div>
                )}
              </div>
            )}

            {/* Provera prevare */}
            {fraud && (
              <div style={{ background:'var(--bg2)', border:`1px solid ${fraud.badge?.color+'40'||'var(--border)'}`, borderRadius:'var(--radius)', padding:16 }}>
                <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between', marginBottom:8 }}>
                  <h3 style={{ fontSize:12, fontWeight:600, margin:0 }}>Provera prevare</h3>
                  <span style={{ fontSize:11, padding:'2px 8px', borderRadius:20, background:fraud.badge?.color+'20', color:fraud.badge?.color, border:`1px solid ${fraud.badge?.color+'40'}` }}>{fraud.badge?.text}</span>
                </div>
                {fraud.red_flags?.map((f: string) => <div key={f} style={{ fontSize:12, color:'#F87171', marginBottom:3 }}>⚠ {f}</div>)}
                {fraud.safe_signals?.map((s: string) => <div key={s} style={{ fontSize:12, color:'#22C55E', marginBottom:3 }}>✓ {s}</div>)}
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
  const min = Math.min(...prices), max = Math.max(...prices), range = max - min || 1
  const W = 500, H = 90, PAD = 10
  const points = history.map((h, i) => ({
    x: PAD + (i / (history.length - 1)) * (W - PAD * 2),
    y: H - PAD - ((Number(h.price) - min) / range) * (H - PAD * 2),
    price: Number(h.price), date: new Date(h.recorded_at).toLocaleDateString('sr'),
  }))
  const path = points.map((p, i) => `${i===0?'M':'L'} ${p.x} ${p.y}`).join(' ')
  return (
    <div style={{ overflowX:'auto' }}>
      <svg viewBox={`0 0 ${W} ${H}`} style={{ width:'100%', maxWidth:W }}>
        <defs><linearGradient id="grad" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#F97316" stopOpacity="0.3" /><stop offset="100%" stopColor="#F97316" stopOpacity="0" /></linearGradient></defs>
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
          <div className="skeleton" style={{ height:400, borderRadius:12, marginBottom:8 }} />
          <div className="skeleton" style={{ height:160, borderRadius:12, marginTop:12 }} />
        </div>
        <div><div className="skeleton" style={{ height:380, borderRadius:12 }} /></div>
      </div>
    </div>
  )
}
