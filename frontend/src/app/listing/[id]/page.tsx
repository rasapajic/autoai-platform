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
]

const SOURCE_LABELS: Record<string, string> = {
  autoscout24:  'AutoScout24',
  willhaben:    'Willhaben',
  marktplaats:  'Marktplaats',
  '2dehands':   '2dehands',
  kleinanzeigen:'Kleinanzeigen',
  mobile_de:    'Mobile.de',
}

function getSerbiaEligibility(listing: any) {
  const year = listing.year ? Number(listing.year) : null
  const fuel = listing.fuel_type || null
  const age  = year ? (2026 - year) : null
  if (fuel === 'electric') return { status:'eligible', emoji:'🟢', label:'Visoka verovatnoća uvoza', sublabel:'EV · 0% carine', reason:'Električna vozila oslobođena carine.', warnings:['Proveri tip punjača (Tip 2 / CCS).'], confidence:'high', carinaPct:0 }
  if (age !== null && age >= 30) return { status:'oldtimer', emoji:'🟣', label:'Oldtimer — poseban režim', sublabel:'Starije od 30 god.', reason:`Poseban carinski tretman.`, warnings:['Konsultuj carinskog agenta.'], confidence:'medium', carinaPct:5 }
  if (!year) return { status:'needs_check', emoji:'🟠', label:'Proveriti detalje uvoza', sublabel:'Godište nepoznato', reason:'Bez potvrđenog godišta nije moguće proceniti Euro normu.', warnings:['Zatraži COC i datum prve registracije.'], confidence:'low', carinaPct:5 }
  if (year >= 2015) return { status:'eligible', emoji:'🟢', label:'Visoka verovatnoća uvoza', sublabel:`Euro 6 · ${year}.`, reason:`Euro 6 — bez ograničenja.`, warnings:['Pribavi COC.', ...(fuel==='diesel'?['Proveri DPF.']:[])] , confidence:'high', carinaPct:5 }
  if (year >= 2011) return { status:'eligible', emoji:'🟢', label:'Verovatno uspešan uvoz', sublabel:`Euro 5 · ${year}.`, reason:`Euro 5 — može se uvesti.`, warnings:['Pribavi COC.', ...(fuel==='diesel'?['Dizel Euro 5 — proveri DPF.']:[])] , confidence:'high', carinaPct:5 }
  if (year >= 2006) return { status:'eligible', emoji:fuel==='diesel'?'🟠':'🟢', label:fuel==='diesel'?'Proveriti Euro 4':'Verovatno uspešan uvoz', sublabel:`Euro 4 · ${year}.`, reason:`Euro 4 — minimalni uslov.`, warnings:['Obavezno pribavi COC.', ...(fuel==='diesel'?['Dizel Euro 4 — rizik DPF.']:[])] , confidence:fuel==='diesel'?'medium':'high', carinaPct:5 }
  if (year >= 2001) return { status:'needs_check', emoji:'🟠', label:'Proveriti detalje uvoza', sublabel:`Euro 3 · ${year}.`, reason:`Euro 3 — komplikovano, ali moguće.`, warnings:['Konsultuj carinskog agenta.'], confidence:'low', carinaPct:5 }
  return { status:'not_recommended', emoji:'🔴', label:'Visok rizik pri uvozu', sublabel:`Prestara norma · ${year}.`, reason:`Ne ispunjava standarde za uvoz.`, warnings:['Registracija u Srbiji verovatno nije moguća.'], confidence:'none', carinaPct:5 }
}

function calcTrustScore(listing: any, vinResult?: any) {
  let score = 0
  const explanations: {text:string; ok:boolean}[] = []
  const year    = listing.year ? Number(listing.year) : null
  const mileage = listing.mileage ? Number(listing.mileage) : null
  const delta   = listing.price_delta_pct ? Number(listing.price_delta_pct) : null
  const imgCount = (listing.images||[]).length

  if (imgCount >= 6)      { score += 10; explanations.push({text:`${imgCount} fotografija vozila`, ok:true}) }
  else if (imgCount >= 3) { score += 6 }
  else if (imgCount >= 1) { score += 2; explanations.push({text:'Malo fotografija vozila', ok:false}) }
  else                    { explanations.push({text:'Nema fotografija vozila', ok:false}) }

  if (year) { score += 10; explanations.push({text:`Godište potvrđeno (${year})`, ok:true}) }
  else { explanations.push({text:'Godište nije navedeno', ok:false}) }

  if (mileage) {
    const annual = year ? mileage/(2026-year) : null
    if (annual && annual > 40000) { score += 4; explanations.push({text:`Visoka godišnja kilometraža (~${Math.round(annual/1000)}k/god)`, ok:false}) }
    else { score += 10; explanations.push({text:`Kilometraža deluje realno (${mileage.toLocaleString()} km)`, ok:true}) }
  } else { explanations.push({text:'Kilometraža nije navedena', ok:false}) }

  if (listing.fuel_type) { score += 4; explanations.push({text:'Gorivo navedeno', ok:true}) }
  else explanations.push({text:'Gorivo nije navedeno', ok:false})
  if (listing.transmission) score += 4

  if (delta !== null) {
    if (delta < -25) { score += 6; explanations.push({text:`Cena ${Math.abs(delta).toFixed(0)}% ispod proseka — proveri razlog`, ok:false}) }
    else if (delta < -5) { score += 20; explanations.push({text:`Cena ispod tržišnog proseka za ${Math.abs(delta).toFixed(0)}%`, ok:true}) }
    else if (delta <= 10) { score += 15; explanations.push({text:'Cena odgovara tržišnom proseku', ok:true}) }
    else if (delta <= 20) { score += 8; explanations.push({text:`Cena iznad proseka za ${delta.toFixed(0)}%`, ok:false}) }
    else { score += 3; explanations.push({text:`Cena značajno iznad proseka (${delta.toFixed(0)}%)`, ok:false}) }
  } else if (listing.price) score += 8

  const descLen = (listing.description||'').length
  if (descLen > 100) { score += 8; explanations.push({text:'Detaljan opis vozila', ok:true}) }
  else if (descLen > 30) score += 4
  else explanations.push({text:'Kratak ili nedostaje opis', ok:false})

  const elig = getSerbiaEligibility(listing)
  if (elig.confidence==='high')   { score += 20; explanations.push({text:'Pogodan za uvoz u Srbiju', ok:true}) }
  else if (elig.confidence==='medium') { score += 10 }
  else if (elig.confidence==='low')    { score += 4; explanations.push({text:'Nesigurnost pri uvozu', ok:false}) }
  else explanations.push({text:'Problematičan uvoz', ok:false})

  if (vinResult) {
    const hasCritical = vinResult.mismatches?.some((m: any) => m.severity === 'critical')
    const hasWarning  = vinResult.mismatches?.some((m: any) => m.severity === 'warning')
    if (hasCritical) {
      score = Math.max(0, score - 55)
      const fields = vinResult.mismatches.filter((m: any) => m.severity === 'critical').map((m: any) => m.field).join(', ')
      explanations.push({text:`🚨 VIN neslaganje: ${fields}`, ok:false})
    } else if (hasWarning) {
      score = Math.max(0, score - 25)
      explanations.push({text:'⚠️ VIN delimično neslaganje', ok:false})
    } else if (vinResult.match_status === 'ok') {
      score = Math.min(100, score + 15)
      explanations.push({text:'✅ VIN potvrđuje sve podatke oglasa', ok:true})
    }
  } else {
    explanations.push({text:'VIN broj nije verifikovan', ok:false})
  }

  score = Math.min(100, Math.max(0, Math.round(score)))
  let label='', color=''
  const hasCriticalVin = vinResult?.mismatches?.some((m: any) => m.severity === 'critical')
  if (hasCriticalVin) {
    label = '🚨 Kritično neslaganje podataka'; color = '#EF4444'
  } else if (score>=85) { label='Veoma kvalitetan oglas'; color='#22C55E' }
  else if (score>=70)   { label='Dobar oglas'; color='#22C55E' }
  else if (score>=55)   { label='Delimično verifikovan'; color='#F97316' }
  else                  { label='Oglas nije potpuno verifikovan'; color='#EF4444' }

  return { score, label, color, explanations }
}

function calcImport(price: number, carinaPct: number) {
  const carina = Math.round(price * carinaPct/100)
  const pdv    = Math.round((price+carina)*0.20)
  return { carina, pdv, transport:420, reg:280, total:price+carina+pdv+420+280, carinaPct }
}

function fmt(n: any) { return Number(n).toLocaleString('de-DE') }
function fmtKm(km: any) {
  const n = Number(km)
  if (!n||n<1||n>999999) return null
  return n.toLocaleString('de-DE')+' km'
}
function fullImg(url: string) {
  if (!url) return url
  return url.replace(/\/\d+x\d+\.(webp|jpg|jpeg|png)/i, '/800x600.$1')
}

function BottomSheet({ open, onClose, title, children }: {open:boolean; onClose:()=>void; title:string; children:React.ReactNode}) {
  if (!open) return null
  return (
    <div style={{ position:'fixed', inset:0, zIndex:2000, display:'flex', flexDirection:'column', justifyContent:'flex-end' }}>
      <div onClick={onClose} style={{ flex:1, background:'rgba(0,0,0,.55)', backdropFilter:'blur(4px)' }} />
      <div style={{ background:'var(--bg2)', borderRadius:'20px 20px 0 0', padding:'0 0 env(safe-area-inset-bottom,16px)', maxHeight:'85vh', overflow:'hidden', display:'flex', flexDirection:'column', boxShadow:'0 -8px 40px rgba(0,0,0,.4)' }}>
        <div style={{ padding:'16px 20px 12px', borderBottom:'1px solid var(--border)', display:'flex', justifyContent:'space-between', alignItems:'center', flexShrink:0 }}>
          <h3 style={{ fontSize:16, fontWeight:700, margin:0 }}>{title}</h3>
          <button onClick={onClose} style={{ background:'none', border:'none', color:'var(--text3)', fontSize:20, cursor:'pointer', lineHeight:1 }}>✕</button>
        </div>
        <div style={{ overflowY:'auto', padding:'16px 20px 20px' }}>{children}</div>
      </div>
    </div>
  )
}

function Accordion({ title, icon, children, defaultOpen=false, badge }: {title:string; icon:string; children:React.ReactNode; defaultOpen?:boolean; badge?:string}) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <div style={{ background:'var(--bg2)', border:'1px solid var(--border)', borderRadius:14, overflow:'hidden', marginBottom:10 }}>
      <button onClick={() => setOpen(v=>!v)} style={{ width:'100%', background:'none', border:'none', cursor:'pointer', padding:'13px 16px', display:'flex', justifyContent:'space-between', alignItems:'center', color:'var(--text)' }}>
        <span style={{ display:'flex', alignItems:'center', gap:8, fontSize:14, fontWeight:600 }}>
          <span>{icon}</span>{title}
          {badge && <span style={{ fontSize:10, padding:'2px 7px', borderRadius:20, background:'rgba(239,68,68,.15)', color:'#EF4444', fontWeight:700 }}>{badge}</span>}
        </span>
        <span style={{ fontSize:12, color:'var(--text3)', transition:'transform .2s', transform:open?'rotate(180deg)':'none', display:'inline-block' }}>▼</span>
      </button>
      {open && <div style={{ borderTop:'1px solid var(--border)', padding:'14px 16px' }}>{children}</div>}
    </div>
  )
}

export default function ListingPage({ params }: { params: { id: string } }) {
  const [listing,        setListing]        = useState<any>(null)
  const [history,        setHistory]        = useState<any[]>([])
  const [similar,        setSimilar]        = useState<any[]>([])
  const [fraud,          setFraud]          = useState<any>(null)
  const [activeImg,      setActiveImg]      = useState(0)
  const [favorited,      setFavorited]      = useState(false)
  const [vinResult,      setVinResult]      = useState<any>(null)
  const [loading,        setLoading]        = useState(true)
  const [showContact,    setShowContact]    = useState(false)
  const [showBd,         setShowBd]         = useState(false)
  const [enriching,      setEnriching]      = useState(false)
  const [enriched,       setEnriched]       = useState(false)
  const [scanMsg,        setScanMsg]        = useState(AI_SCAN_MESSAGES[0])
  const [backUrl,        setBackUrl]        = useState('/search')
  const [showScoreSheet, setShowScoreSheet] = useState(false)
  const [showBdSheet,    setShowBdSheet]    = useState(false)
  const scanInterval = useRef<any>(null)

  useEffect(() => {
    const prev = sessionStorage.getItem('autoai_search_url')
    if (prev) setBackUrl(prev)
  }, [])

  useEffect(() => {
    Promise.allSettled([getListing(params.id), getPriceHistory(params.id), getSimilar(params.id), fraudCheck(params.id)])
      .then(([l,h,s,f]) => {
        if (l.status==='fulfilled') { const d=l.value; setListing(d); if (d?.url&&(!d.year||!d.mileage)) autoEnrich(d.url) }
        if (h.status==='fulfilled') setHistory(h.value)
        if (s.status==='fulfilled') setSimilar(s.value)
        if (f.status==='fulfilled') setFraud(f.value)
      }).finally(() => setLoading(false))
  }, [params.id])

  const startScanMessages = () => {
    let i=0; setScanMsg(AI_SCAN_MESSAGES[0])
    scanInterval.current = setInterval(() => { i=(i+1)%AI_SCAN_MESSAGES.length; setScanMsg(AI_SCAN_MESSAGES[i]) }, 1800)
  }
  const stopScanMessages = () => { if (scanInterval.current) clearInterval(scanInterval.current) }

  const autoEnrich = async (url: string) => {
    if (enriching||enriched) return
    setEnriching(true); startScanMessages()
    try {
      const res  = await fetch(`${API_BASE}/analyze/`, { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({url}) })
      const data = await res.json()
      if (data.scrape_success) {
        setListing((prev: any) => ({...prev, year:data.year||prev.year, mileage:data.mileage||prev.mileage, fuel_type:data.fuel_type||prev.fuel_type, engine_power_kw:data.engine_power_kw||prev.engine_power_kw, country:data.country||prev.country, city:data.city||prev.city, transmission:data.transmission||prev.transmission, images:(data.images?.length||0)>(prev.images?.length||0)?data.images:prev.images}))
        setEnriched(true)
      }
    } catch {}
    stopScanMessages(); setEnriching(false)
  }

  if (loading) return <PageSkeleton />
  if (!listing) return <div style={{textAlign:'center',padding:'80px 0',color:'var(--text3)'}}>Oglas nije pronađen.</div>

  const images    = listing.images||[]
  const elig      = getSerbiaEligibility(listing)
  const eligColor = ELIGIBILITY_COLORS[elig.status]||'#F97316'
  const price     = listing.price ? Number(listing.price) : null
  const bd        = price ? calcImport(price, elig.carinaPct) : null
  const deltaGood = listing.price_delta_pct && Number(listing.price_delta_pct) < 0
  const trust     = calcTrustScore(listing, vinResult)
  const portalName = SOURCE_LABELS[listing.source] || listing.source || 'Portal'

  const fuelLabel = (f: string) => ({diesel:'Dizel',petrol:'Benzin',electric:'Električni',hybrid:'Hibrid',lpg:'Plin',gasoline:'Benzin'} as any)[f]||f

  const specs = [
    {label:'Godište',    value:listing.year},
    {label:'Km',         value:fmtKm(listing.mileage)},
    {label:'Gorivo',     value:listing.fuel_type?fuelLabel(listing.fuel_type):null},
    {label:'Menjač',     value:listing.transmission==='automatic'?'Automatik':listing.transmission==='manual'?'Manuel':listing.transmission},
    {label:'Snaga',      value:listing.engine_power_kw?`${listing.engine_power_kw} kW`:null},
    {label:'Karoserija', value:listing.body_type},
    {label:'Zemlja',     value:listing.country},
    {label:'Grad',       value:listing.city?listing.city.split(' - ')[0]:null},
  ].filter(s=>s.value)

  const handleSave = async () => {
    const t = localStorage.getItem('autoai_token')
    if (!t) { window.location.href='/login'; return }
    try {
      const r = await fetch(`${API_BASE}/users/me/favorites`, {
        method:'POST',
        headers:{'Content-Type':'application/json','Authorization':`Bearer ${t}`},
        body:JSON.stringify({listing_id:listing.id})
      })
      if (r.ok) setFavorited(true)
    } catch {}
  }

  return (
    <div style={{paddingBottom:20}}>
      {showContact && <ContactModal listing={listing} onClose={() => setShowContact(false)} />}

      {/* AI Score Bottom Sheet */}
      <BottomSheet open={showScoreSheet} onClose={() => setShowScoreSheet(false)} title={`AI procena: ${trust.score}/100`}>
        <div style={{marginBottom:16}}>
          <div style={{height:8, background:'rgba(255,255,255,.06)', borderRadius:4, overflow:'hidden', marginBottom:8}}>
            <div style={{height:'100%', borderRadius:4, width:`${trust.score}%`, background:trust.color, transition:'width .6s'}} />
          </div>
          <div style={{fontSize:15, fontWeight:700, color:trust.color}}>{trust.label}</div>
        </div>
        <div style={{display:'flex', flexDirection:'column', gap:8}}>
          {trust.explanations.map((e,i) => (
            <div key={i} style={{display:'flex', alignItems:'flex-start', gap:10, padding:'9px 12px', background:'var(--bg3)', borderRadius:10}}>
              <span style={{fontSize:15, flexShrink:0}}>{e.ok ? '✅' : '⚠️'}</span>
              <span style={{fontSize:13, color:e.ok?'var(--text2)':'var(--text3)'}}>{e.text}</span>
            </div>
          ))}
        </div>
        <p style={{fontSize:11, color:'var(--text3)', marginTop:14, lineHeight:1.6, opacity:.7}}>
          Score se poboljšava sa VIN verifikacijom i kompletnim podacima.
        </p>
      </BottomSheet>

      {/* Uvoz troškovi Bottom Sheet */}
      <BottomSheet open={showBdSheet} onClose={() => setShowBdSheet(false)} title="🇷🇸 Trošak uvoza u Srbiju">
        {bd && (
          <div>
            <div className="mob-import-total" style={{fontSize:28, fontWeight:800, color:'var(--accent)', marginBottom:16}}>{fmt(bd.total)} €</div>
            {[
              {label:'EU cena', val:price!, note:''},
              {label:`Carina (${bd.carinaPct}%)`, val:bd.carina, note:bd.carinaPct===0?'oslobođeno':'srbija'},
              {label:'PDV (20%)', val:bd.pdv, note:'srbija'},
              {label:'Transport EU→RS', val:bd.transport, note:'procena'},
              {label:'Registracija', val:bd.reg, note:'procena'},
            ].map(({label,val,note},i) => (
              <div key={i} style={{display:'flex',justifyContent:'space-between',padding:'11px 0',borderBottom:'1px solid var(--border)'}}>
                <span style={{fontSize:14,color:i===0?'var(--text)':'var(--text2)'}}>{i>0&&'+ '}{label}{note&&<span style={{fontSize:11,marginLeft:5,opacity:.6}}>({note})</span>}</span>
                <span style={{fontSize:14,fontWeight:600,color:i===0?'var(--text)':'var(--accent)'}}>{fmt(val)} €</span>
              </div>
            ))}
            <div style={{display:'flex',justifyContent:'space-between',marginTop:14,paddingTop:14,borderTop:'2px solid rgba(255,107,0,.25)'}}>
              <span style={{fontSize:16,fontWeight:700}}>Ukupno za Srbiju</span>
              <span style={{fontSize:18,fontWeight:800,color:'var(--accent)'}}>{fmt(bd.total)} €</span>
            </div>
            <p style={{fontSize:11,color:'var(--text3)',marginTop:10,lineHeight:1.5,opacity:.7}}>* Procena je informativna. Provjeri sa carinskim agentom.</p>
          </div>
        )}
      </BottomSheet>

      <style>{`
        @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.3} }
        @media(max-width:768px){
          .listing-grid { grid-template-columns:1fr !important; }
          .desktop-sidebar { display:none !important; }
          .desktop-section { display:none !important; }
        }
        @media(min-width:769px){
          .mobile-stack { display:none !important; }
        }
        .mobile-stack { display:block; }
        .trust-bar { transition:width .6s ease; }

        @media(max-width:768px){
          .mob-title    { font-size:20px !important; font-weight:700 !important; }
          .mob-price    { font-size:38px !important; font-weight:800 !important; line-height:1 !important; }
          .mob-price-rs { font-size:22px !important; font-weight:700 !important; }
          .mob-status   { font-size:16px !important; font-weight:700 !important; }
          .mob-status-sub { font-size:13px !important; }
          .mob-spec-label { font-size:12px !important; }
          .mob-spec-value { font-size:17px !important; font-weight:600 !important; }
          .mob-ai-score { font-size:32px !important; font-weight:800 !important; }
          .mob-ai-label { font-size:17px !important; font-weight:700 !important; }
          .mob-ai-sub   { font-size:15px !important; }
          .mob-section-title { font-size:16px !important; font-weight:700 !important; }
          .mob-body-text { font-size:14px !important; line-height:1.7 !important; }
          .mob-badge    { font-size:14px !important; font-weight:700 !important; }
          .mob-btn      { font-size:16px !important; font-weight:700 !important; padding:16px !important; }
          .mob-import-total { font-size:26px !important; font-weight:800 !important; }
          .mob-import-row { font-size:14px !important; }
          .mob-source-badge { font-size:13px !important; }
          .mob-tiny { font-size:12px !important; }
        }
        .score-btn:active { opacity:.7; transform:scale(.97); }
        .action-btn:active { opacity:.8; transform:scale(.97); }
      `}</style>

      <div className="container" style={{padding:'12px 12px 0'}}>
        {/* Breadcrumb */}
        <div style={{fontSize:12,color:'var(--text3)',marginBottom:10,display:'flex',alignItems:'center',gap:5}}>
          <a href={backUrl} style={{color:'var(--text3)',textDecoration:'none'}}>← Pretraga</a>
          <span>·</span>
          <span style={{color:'var(--text)',overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}}>{listing.make} {listing.model}</span>
        </div>

        {enriching && (
          <div style={{background:'rgba(99,102,241,.08)',border:'1px solid rgba(99,102,241,.25)',borderRadius:10,padding:'9px 14px',marginBottom:10,display:'flex',alignItems:'center',gap:8}}>
            <div style={{width:7,height:7,borderRadius:'50%',background:'#818CF8',animation:'pulse 1s infinite',flexShrink:0}} />
            <span style={{fontSize:12,color:'#818CF8',fontWeight:600}}>{scanMsg}</span>
          </div>
        )}

        {/* VIN KRITIČNI ALERT */}
        {vinResult?.mismatches?.some((m: any) => m.severity === 'critical') && (
          <div style={{
            background:'rgba(239,68,68,.08)', border:'2px solid rgba(239,68,68,.5)',
            borderRadius:14, padding:'14px 16px', marginBottom:12,
            boxShadow:'0 0 30px rgba(239,68,68,.15)',
          }}>
            <div style={{fontSize:16, fontWeight:800, color:'#EF4444', marginBottom:10, display:'flex', alignItems:'center', gap:8}}>
              🚨 VIN SE NE POKLAPA SA OGLASOM
            </div>
            <div style={{display:'grid', gridTemplateColumns:'1fr 1fr', gap:8, marginBottom:10}}>
              <div style={{background:'rgba(239,68,68,.08)', borderRadius:10, padding:'10px 12px'}}>
                <div style={{fontSize:10, color:'#EF4444', fontWeight:700, marginBottom:6, letterSpacing:'.06em'}}>📋 VIN PODACI</div>
                {[
                  {label:'Marka', value: vinResult.make},
                  {label:'Model', value: vinResult.model},
                  {label:'Godište', value: vinResult.year},
                ].filter(f => f.value).map(({label, value}) => (
                  <div key={label} style={{fontSize:12, marginBottom:3}}>
                    <span style={{color:'var(--text3)'}}>{label}: </span>
                    <span style={{color:'#EF4444', fontWeight:700}}>{String(value)}</span>
                  </div>
                ))}
              </div>
              <div style={{background:'rgba(255,255,255,.04)', borderRadius:10, padding:'10px 12px'}}>
                <div style={{fontSize:10, color:'var(--text3)', fontWeight:700, marginBottom:6, letterSpacing:'.06em'}}>📝 OGLAS NAVODI</div>
                {[
                  {label:'Marka', value: listing.make},
                  {label:'Model', value: listing.model},
                  {label:'Godište', value: listing.year},
                ].filter(f => f.value).map(({label, value}) => (
                  <div key={label} style={{fontSize:12, marginBottom:3}}>
                    <span style={{color:'var(--text3)'}}>{label}: </span>
                    <span style={{fontWeight:600}}>{String(value)}</span>
                  </div>
                ))}
              </div>
            </div>
            {vinResult.mismatches.filter((m: any) => m.severity === 'critical').map((m: any, i: number) => (
              <div key={i} style={{
                background:'rgba(239,68,68,.1)', borderLeft:'3px solid #EF4444',
                borderRadius:'0 8px 8px 0', padding:'8px 12px', marginBottom:6,
              }}>
                <div style={{fontSize:12, fontWeight:700, color:'#EF4444'}}>⚠ {m.field}</div>
                <div style={{fontSize:12, color:'var(--text2)', marginTop:2}}>{m.message}</div>
              </div>
            ))}
            <div style={{
              background:'rgba(239,68,68,.06)', borderRadius:8, padding:'10px 12px',
              marginTop:8, fontSize:12, color:'var(--text2)', lineHeight:1.6,
            }}>
              ⛔ <strong style={{color:'#EF4444'}}>Ne preporučujemo kupovinu</strong> dok prodavac ne objasni neslaganje podataka ili dostavi ispravnu dokumentaciju.
            </div>
          </div>
        )}

        <div className="listing-grid" style={{display:'grid',gridTemplateColumns:'1fr 340px',gap:24,alignItems:'start'}}>

          {/* MOBILE STACK */}
          <div className="mobile-stack">

            {/* Slika */}
            <div style={{marginBottom:8,borderRadius:14,overflow:'hidden',position:'relative',height:220,background:'var(--bg3)'}}>
              {images[activeImg]
                ? <img src={fullImg(images[activeImg])} alt={`${listing.make} ${listing.model}`} style={{width:'100%',height:'100%',objectFit:'cover'}} onError={e=>{(e.target as HTMLImageElement).src=images[activeImg]}} />
                : <div style={{display:'flex',alignItems:'center',justifyContent:'center',height:'100%',fontSize:50}}>🚗</div>
              }
              <span style={{position:'absolute',bottom:8,left:8,background:'rgba(0,0,0,.75)',borderRadius:6,padding:'2px 8px',fontSize:11,color:'rgba(255,255,255,.7)'}}>{portalName}</span>
              {images.length > 1 && (
                <span style={{position:'absolute',bottom:8,right:8,background:'rgba(0,0,0,.75)',borderRadius:6,padding:'2px 8px',fontSize:11,color:'rgba(255,255,255,.7)'}}>
                  {activeImg+1}/{images.length}
                </span>
              )}
            </div>
            {images.length > 1 && (
              <div style={{display:'flex',gap:5,overflowX:'auto',marginBottom:8,paddingBottom:2}}>
                {images.slice(0,8).map((img:string,i:number) => (
                  <div key={i} onClick={() => setActiveImg(i)} style={{width:54,height:40,flexShrink:0,borderRadius:7,overflow:'hidden',cursor:'pointer',border:`2px solid ${activeImg===i?'var(--accent)':'transparent'}`}}>
                    <img src={img} alt="" style={{width:'100%',height:'100%',objectFit:'cover'}} />
                  </div>
                ))}
              </div>
            )}

            {/* Naziv + Cena */}
            <div style={{marginBottom:8}}>
              <div className="mob-title" style={{fontSize:16,color:'var(--text)',fontWeight:700,marginBottom:2}}>{listing.make} {listing.model}{listing.year?` · ${listing.year}`:''}</div>
              <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-end'}}>
                <div className="mob-price" style={{fontSize:32,fontWeight:800,color:'var(--accent)',lineHeight:1}}>{price?`${fmt(price)} €`:'Na upit'}</div>
                {listing.price_estimated && (
                  <div style={{fontSize:12,color:deltaGood?'#22C55E':'#F87171',textAlign:'right'}}>
                    {deltaGood?'↓ ispod':'↑ iznad'} proseka za {Math.abs(Number(listing.price_delta_pct)).toFixed(0)}%
                  </div>
                )}
              </div>
            </div>

            {/* TAB navigacija */}
            <MobileTabs listing={listing} elig={elig} eligColor={eligColor} bd={bd} trust={trust}
              specs={specs} similar={similar} price={price} deltaGood={deltaGood}
              onContact={() => setShowContact(true)} onShowScore={() => setShowScoreSheet(true)}
              onShowBd={() => setShowBdSheet(true)} enriching={enriching} enriched={enriched}
              scanMsg={scanMsg} onEnrich={() => autoEnrich(listing.url)} fraud={fraud}
              onVinResult={setVinResult} vinResult={vinResult}
              portalName={portalName}
              saved={favorited}
              onSave={handleSave}
            />
          </div>

          {/* DESKTOP LEVA KOLONA */}
          <div className="desktop-section" style={{display:'block'}}>
            <div style={{height:380,background:'var(--bg3)',borderRadius:'var(--radius)',overflow:'hidden',marginBottom:8,position:'relative'}}>
              {images[activeImg]
                ? <img src={fullImg(images[activeImg])} alt={`${listing.make} ${listing.model}`} style={{width:'100%',height:'100%',objectFit:'cover'}} onError={e=>{(e.target as HTMLImageElement).src=images[activeImg]}} />
                : <div style={{display:'flex',alignItems:'center',justifyContent:'center',height:'100%',fontSize:60}}>🚗</div>
              }
              <span style={{position:'absolute',bottom:8,left:8,background:'rgba(0,0,0,.75)',borderRadius:6,padding:'3px 9px',fontSize:11,color:'rgba(255,255,255,.7)'}}>{portalName}</span>
            </div>
            {images.length > 1 && (
              <div style={{display:'flex',gap:5,overflowX:'auto',marginBottom:16}}>
                {images.slice(0,10).map((img:string,i:number) => (
                  <div key={i} onClick={() => setActiveImg(i)} style={{width:70,height:50,flexShrink:0,borderRadius:7,overflow:'hidden',cursor:'pointer',border:`2px solid ${activeImg===i?'var(--accent)':'transparent'}`}}>
                    <img src={img} alt="" style={{width:'100%',height:'100%',objectFit:'cover'}} />
                  </div>
                ))}
              </div>
            )}
            <div style={{background:'var(--bg2)',border:`2px solid ${trust.color}22`,borderRadius:'var(--radius)',padding:20,marginBottom:16,cursor:'pointer'}} onClick={() => setShowScoreSheet(true)}>
              <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start',marginBottom:10}}>
                <div>
                  <h2 style={{fontSize:15,margin:'0 0 2px'}}>🤖 AI procena oglasa</h2>
                  <div style={{fontSize:12,color:'var(--text3)'}}>Klikni za detalje</div>
                </div>
                <div style={{textAlign:'right',flexShrink:0}}>
                  <div className="mob-ai-score" style={{fontSize:24,fontWeight:800,color:trust.color,lineHeight:1}}>{trust.score}</div>
                  <div style={{fontSize:10,color:'var(--text3)'}}>/100</div>
                </div>
              </div>
              <div style={{height:5,background:'rgba(255,255,255,.06)',borderRadius:4,overflow:'hidden',marginBottom:6}}>
                <div className="trust-bar" style={{height:'100%',borderRadius:4,width:`${trust.score}%`,background:trust.color}} />
              </div>
              <div style={{fontSize:13,fontWeight:700,color:trust.color}}>{trust.label}</div>
            </div>
            <div style={{background:'var(--bg2)',border:'1px solid var(--border)',borderRadius:'var(--radius)',padding:20,marginBottom:16}}>
              <h2 style={{fontSize:15,marginBottom:14}}>Specifikacije</h2>
              <div style={{display:'grid',gridTemplateColumns:'repeat(3,1fr)',gap:10}}>
                {specs.map(s => (
                  <div key={s.label} style={{background:'var(--bg3)',borderRadius:8,padding:'9px 12px'}}>
                    <div style={{fontSize:10,color:'var(--text3)',marginBottom:2}}>{s.label}</div>
                    <div style={{fontSize:13,fontWeight:500}}>{s.value}</div>
                  </div>
                ))}
              </div>
            </div>
            {listing.make && (
              <div style={{background:'var(--bg2)',border:'1px solid var(--border)',borderRadius:'var(--radius)',padding:20,marginBottom:16}}>
                <ModelChecklist make={listing.make} model={listing.model} year={listing.year} fuelType={listing.fuel_type} transmission={listing.transmission} />
              </div>
            )}
            <div style={{background:'var(--bg2)',border:'1px solid var(--border)',borderRadius:'var(--radius)',padding:20,marginBottom:16}}>
              <h2 style={{fontSize:15,margin:'0 0 4px'}}>🔐 VIN Provera vozila</h2>
              <p style={{fontSize:12,color:'var(--text3)',margin:'0 0 14px',lineHeight:1.5}}>
                Zatraži VIN od prodavca koristeći{' '}
                <button onClick={() => setShowContact(true)} style={{background:'none',border:'none',color:'var(--accent)',cursor:'pointer',fontSize:12,fontWeight:600,padding:0,textDecoration:'underline'}}>Kontaktiraj prodavca</button>
                {' '}— AI automatski dodaje pitanje na jeziku prodavca.
              </p>
              <VinChecker listing={listing} onVinResult={setVinResult} />
            </div>
            {listing.description && (
              <div style={{background:'var(--bg2)',border:'1px solid var(--border)',borderRadius:'var(--radius)',padding:20,marginBottom:16}}>
                <h2 style={{fontSize:15,marginBottom:10}}>Opis</h2>
                <p style={{color:'var(--text2)',lineHeight:1.8,fontSize:14,whiteSpace:'pre-line',margin:0}}>{listing.description}</p>
              </div>
            )}
            {listing.features?.length > 0 && (
              <div style={{background:'var(--bg2)',border:'1px solid var(--border)',borderRadius:'var(--radius)',padding:20,marginBottom:16}}>
                <h2 style={{fontSize:15,marginBottom:12}}>Oprema ({listing.features.length})</h2>
                <div style={{display:'flex',flexWrap:'wrap',gap:5}}>
                  {listing.features.map((f:string) => <span key={f} style={{background:'var(--bg3)',border:'1px solid var(--border)',borderRadius:20,padding:'3px 11px',fontSize:11,color:'var(--text2)'}}>{f}</span>)}
                </div>
              </div>
            )}
            {similar.length > 0 && (
              <div>
                <h2 style={{fontSize:15,marginBottom:12}}>Slični oglasi</h2>
                <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fill,minmax(185px,1fr))',gap:10}}>
                  {similar.slice(0,4).map((s:any) => (
                    <a key={s.id} href={`/listing/${s.id}`} style={{background:'var(--bg2)',border:'1px solid var(--border)',borderRadius:'var(--radius)',overflow:'hidden',display:'block',textDecoration:'none'}}>
                      <div style={{height:110,background:'var(--bg3)',overflow:'hidden'}}>
                        {s.images?.[0] ? <img src={fullImg(s.images[0])} alt="" style={{width:'100%',height:'100%',objectFit:'cover'}} /> : <div style={{height:'100%',display:'flex',alignItems:'center',justifyContent:'center',fontSize:24}}>🚗</div>}
                      </div>
                      <div style={{padding:9}}>
                        <div style={{fontSize:12,fontWeight:600,color:'var(--text)'}}>{s.year} {s.make} {s.model}</div>
                        <div style={{fontSize:13,color:'var(--accent)',fontWeight:700,marginTop:2}}>{s.price?`${fmt(s.price)} €`:'—'}</div>
                      </div>
                    </a>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* DESKTOP SIDEBAR */}
          <div className="desktop-sidebar" style={{position:'sticky',top:80,display:'flex',flexDirection:'column',gap:12}}>
            <div style={{background:'var(--bg2)',border:'1px solid var(--border)',borderRadius:'var(--radius)',padding:20}}>
              <h1 style={{fontSize:17,marginBottom:3,fontFamily:'Syne,sans-serif'}}>{listing.make} {listing.model}</h1>
              {listing.year && <div style={{color:'var(--text3)',fontSize:12,marginBottom:8}}>Godište: {listing.year}</div>}
              <div style={{fontSize:26,fontWeight:800,color:'var(--accent)',marginBottom:10}}>{price?`${fmt(price)} €`:'Na upit'}</div>
              {listing.price_estimated && (
                <div style={{background:deltaGood?'#16A34A15':'#78716C15',border:`1px solid ${deltaGood?'#22C55E40':'#78716C40'}`,borderRadius:8,padding:'9px 12px',marginBottom:12}}>
                  <div style={{fontSize:11,color:'var(--text3)',marginBottom:2}}>AI procena tržišne vrednosti</div>
                  <div style={{fontWeight:600,fontSize:13}}>{fmt(listing.price_estimated)} €</div>
                  <div style={{fontSize:12,color:deltaGood?'#22C55E':'#F87171',marginTop:2}}>
                    {deltaGood?'✅ Ispod':'⚠️ Iznad'} proseka za {Math.abs(Number(listing.price_delta_pct)).toFixed(0)}%
                  </div>
                </div>
              )}
              <a href={listing.url} target="_blank" rel="noopener" style={{display:'block',width:'100%',padding:'12px',textAlign:'center',background:'var(--accent)',color:'#fff',borderRadius:10,fontWeight:700,fontSize:14,marginBottom:8,textDecoration:'none'}}>
                Pogledaj na {portalName} →
              </a>
              <button onClick={() => setShowContact(true)} style={{width:'100%',padding:'11px',marginBottom:8,background:'rgba(99,102,241,.1)',border:'1px solid rgba(99,102,241,.35)',color:'#818CF8',borderRadius:10,fontSize:13,fontWeight:700,cursor:'pointer'}}>
                🤖 Kontaktiraj prodavca
                <div style={{fontSize:11,fontWeight:400,color:'rgba(129,140,248,.7)',marginTop:2}}>AI generiše poruku na jeziku prodavca</div>
              </button>
              {enriched ? (
                <div style={{display:'flex',alignItems:'center',gap:8,background:'rgba(34,197,94,.08)',border:'1px solid rgba(34,197,94,.2)',borderRadius:10,padding:'9px 12px',marginBottom:8}}>
                  <span>✅</span>
                  <div>
                    <div style={{fontSize:12,fontWeight:600,color:'#22C55E'}}>Podaci provereni</div>
                    <div style={{fontSize:11,color:'var(--text3)'}}>AutoAI ažurirao podatke</div>
                  </div>
                </div>
              ) : (
                <button onClick={() => autoEnrich(listing.url)} disabled={enriching} style={{width:'100%',padding:'11px',marginBottom:8,background:enriching?'var(--bg3)':'linear-gradient(135deg,rgba(99,102,241,.15),rgba(99,102,241,.08))',border:`2px solid ${enriching?'var(--border)':'rgba(99,102,241,.4)'}`,color:enriching?'var(--text3)':'#818CF8',borderRadius:10,fontSize:13,fontWeight:700,cursor:enriching?'default':'pointer'}}>
                  {enriching ? <span style={{display:'flex',alignItems:'center',justifyContent:'center',gap:6}}><span style={{width:7,height:7,borderRadius:'50%',background:'#818CF8',display:'inline-block',animation:'pulse 1s infinite'}} />Proveravam...</span>
                  : <div>🔍 Proveri podatke oglasa<div style={{fontSize:11,fontWeight:400,color:'rgba(129,140,248,.7)',marginTop:2}}>Godište · km · Euro norma</div></div>}
                </button>
              )}
              <div style={{display:'flex',gap:6}}>
                <button onClick={() => { const u=window.location.href; if(navigator.share) navigator.share({title:`${listing.year} ${listing.make} ${listing.model}`,url:u}); else { navigator.clipboard.writeText(u); alert('Link kopiran!') } }} style={{flex:1,padding:'8px',background:'transparent',border:'1px solid var(--border)',color:'var(--text2)',borderRadius:9,fontSize:12,cursor:'pointer'}}>🔗 Podeli</button>
                <button onClick={handleSave} style={{flex:1,padding:'8px',background:'transparent',border:`1px solid ${favorited?'var(--accent)':'var(--border)'}`,color:favorited?'var(--accent)':'var(--text2)',borderRadius:9,fontSize:12,cursor:'pointer'}}>
                  {favorited?'❤️ Sačuvano':'🤍 Sačuvaj'}
                </button>
              </div>
            </div>
            <div style={{background:`${trust.color}0d`,border:`1px solid ${trust.color}33`,borderRadius:'var(--radius)',padding:14,cursor:'pointer'}} onClick={() => setShowScoreSheet(true)}>
              <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:7}}>
                <span style={{fontSize:11,color:'var(--text3)',fontWeight:600,letterSpacing:'.07em'}}>AI PROCENA</span>
                <span style={{fontSize:19,fontWeight:800,color:trust.color}}>{trust.score}/100</span>
              </div>
              <div style={{height:4,background:'rgba(255,255,255,.06)',borderRadius:4,overflow:'hidden',marginBottom:5}}>
                <div className="trust-bar" style={{height:'100%',borderRadius:4,width:`${trust.score}%`,background:trust.color}} />
              </div>
              <div style={{fontSize:12,fontWeight:700,color:trust.color}}>{trust.label}</div>
            </div>
            <div style={{background:`${eligColor}0d`,border:`1px solid ${eligColor}33`,borderRadius:'var(--radius)',padding:14}}>
              <div style={{fontSize:10,color:'var(--text3)',letterSpacing:'.07em',fontWeight:600,marginBottom:5}}>UVOZ U SRBIJU</div>
              <div style={{fontSize:13,fontWeight:800,color:eligColor,marginBottom:2}}>{elig.emoji} {elig.label}</div>
              {elig.sublabel && <div style={{fontSize:11,color:'var(--text3)',marginBottom:5}}>{elig.sublabel}</div>}
              <p style={{fontSize:12,color:'var(--text2)',margin:'0 0 5px',lineHeight:1.5}}>{elig.reason}</p>
              {elig.warnings.slice(0,2).map((w:string,i:number) => (
                <div key={i} style={{fontSize:11,color:'var(--text3)',paddingLeft:8,borderLeft:`2px solid ${eligColor}55`,marginBottom:2,lineHeight:1.4}}>{w}</div>
              ))}
            </div>
            <div style={{background:'rgba(255,107,0,.07)',border:'1px solid rgba(255,107,0,.2)',borderRadius:'var(--radius)',overflow:'hidden'}}>
              <button onClick={() => setShowBd(!showBd)} style={{width:'100%',background:'none',border:'none',cursor:'pointer',padding:'12px 14px',display:'flex',justifyContent:'space-between',alignItems:'center'}}>
                <div style={{textAlign:'left'}}>
                  <div style={{fontSize:11,color:'var(--text3)',marginBottom:1}}>🇷🇸 Ukupno za Srbiju</div>
                  {bd && <div style={{fontSize:20,fontWeight:800,color:'var(--accent)'}}>{fmt(bd.total)} €</div>}
                </div>
                <span style={{fontSize:11,color:'rgba(255,107,0,.6)'}}>{showBd?'▲':'▼ detalji'}</span>
              </button>
              {showBd && bd && (
                <div style={{padding:'0 14px 12px',borderTop:'1px solid rgba(255,107,0,.15)'}}>
                  {[
                    {label:'EU cena',val:price!,note:''},
                    {label:`Carina (${bd.carinaPct}%)`,val:bd.carina,note:bd.carinaPct===0?'oslobođeno':'srbija'},
                    {label:'PDV (20%)',val:bd.pdv,note:'srbija'},
                    {label:'Transport EU→RS',val:bd.transport,note:'procena'},
                    {label:'Registracija',val:bd.reg,note:'procena'},
                  ].map(({label,val,note},i) => (
                    <div key={i} style={{display:'flex',justifyContent:'space-between',padding:'4px 0',borderTop:i===0?'none':'1px solid rgba(255,255,255,.04)',marginTop:i===0?6:0}}>
                      <span style={{fontSize:11,color:i===0?'var(--text2)':'var(--text3)'}}>{i>0&&'+ '}{label}{note&&<span style={{fontSize:10,marginLeft:4,opacity:.5}}>({note})</span>}</span>
                      <span style={{fontSize:11,fontWeight:600,color:i===0?'var(--text2)':'#fb923c'}}>{i===0?'':'+'}{fmt(val)} €</span>
                    </div>
                  ))}
                  <div style={{display:'flex',justifyContent:'space-between',marginTop:8,paddingTop:8,borderTop:'1px solid rgba(255,107,0,.25)'}}>
                    <span style={{fontSize:12,fontWeight:700}}>Ukupno</span>
                    <span style={{fontSize:13,fontWeight:800,color:'var(--accent)'}}>{fmt(bd.total)} €</span>
                  </div>
                </div>
              )}
            </div>
            {fraud && (
              <div style={{background:'var(--bg2)',border:`1px solid ${fraud.badge?.color+'40'||'var(--border)'}`,borderRadius:'var(--radius)',padding:14}}>
                <div style={{display:'flex',alignItems:'center',justifyContent:'space-between',marginBottom:8}}>
                  <h3 style={{fontSize:12,fontWeight:600,margin:0}}>🛡️ Bezbednosna provera</h3>
                  <span style={{fontSize:11,padding:'2px 8px',borderRadius:20,background:fraud.badge?.color+'20',color:fraud.badge?.color,border:`1px solid ${fraud.badge?.color+'40'}`}}>{fraud.badge?.text}</span>
                </div>
                {fraud.red_flags?.map((f:string) => <div key={f} style={{fontSize:12,color:'#F87171',marginBottom:3}}>⚠ {f}</div>)}
                {fraud.safe_signals?.map((s:string) => <div key={s} style={{fontSize:12,color:'#22C55E',marginBottom:3}}>✓ {s}</div>)}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

// MOBILE TAB KOMPONENTA
function MobileTabs({ listing, elig, eligColor, bd, trust, specs, similar, price, deltaGood,
  onContact, onShowScore, onShowBd, enriching, enriched, scanMsg, onEnrich, fraud, onVinResult, vinResult,
  onSave, saved, portalName }: any) {
  const [tab, setTab] = useState(0)

  const TABS = [
    { icon:'🚗', label:'Vozilo' },
    { icon:'🤖', label:'AI + Uvoz' },
    { icon:'🔐', label:'VIN + Docs' },
  ]

  const fmt = (n: any) => Number(n).toLocaleString('de-DE')

  return (
    <div style={{display:'flex', flexDirection:'column'}}>

      {/* Tab bar */}
      <div style={{display:'flex', gap:4, marginBottom:10, background:'var(--bg2)', borderRadius:12, padding:4, border:'1px solid var(--border)'}}>
        {TABS.map((t, i) => (
          <button key={i} onClick={() => setTab(i)} style={{
            flex:1, padding:'10px 6px', borderRadius:9, border:'none', cursor:'pointer',
            background: tab===i ? 'var(--accent)' : 'transparent',
            color: tab===i ? '#fff' : 'var(--text3)',
            fontSize:13, fontWeight:700, transition:'all .15s',
            display:'flex', flexDirection:'column', alignItems:'center', gap:2,
          }}>
            <span style={{fontSize:16}}>{t.icon}</span>
            <span style={{fontSize:11}}>{t.label}</span>
          </button>
        ))}
      </div>

      {/* Tab sadržaj */}
      <div>

        {/* TAB 0 — Vozilo */}
        {tab === 0 && (
          <div style={{display:'flex', flexDirection:'column', gap:8}}>

            {/* Uvoz status */}
            {elig && (
              <div style={{background:`${eligColor}0d`,border:`1px solid ${eligColor}33`,borderRadius:12,padding:'10px 14px'}}>
                <div className="mob-status" style={{fontSize:14,fontWeight:700,color:eligColor}}>{elig.emoji} {elig.label}</div>
                {elig.sublabel && <div style={{fontSize:12,color:'var(--text3)',marginTop:2}}>{elig.sublabel}</div>}
                {bd && (
                  <button onClick={onShowBd} style={{marginTop:6,background:'none',border:'none',cursor:'pointer',padding:0,textAlign:'left'}}>
                    <div style={{fontSize:11,color:'var(--text3)'}}>🇷🇸 za Srbiju</div>
                    <div style={{fontSize:20,fontWeight:800,color:'var(--accent)'}}>{fmt(bd.total)} €</div>
                  </button>
                )}
              </div>
            )}

            {/* Specs grid */}
            <div style={{background:'var(--bg2)',border:'1px solid var(--border)',borderRadius:12,padding:'12px 14px'}}>
              <div style={{fontSize:11,color:'var(--text3)',fontWeight:600,letterSpacing:'.06em',marginBottom:8}}>SPECIFIKACIJE</div>
              <div style={{display:'grid',gridTemplateColumns:'repeat(3,1fr)',gap:6}}>
                {specs.map((s: any) => (
                  <div key={s.label} style={{background:'var(--bg3)',borderRadius:8,padding:'8px 10px'}}>
                    <div className="mob-spec-label" style={{fontSize:10,color:'var(--text3)',marginBottom:2}}>{s.label.toUpperCase()}</div>
                    <div className="mob-spec-value" style={{fontSize:14,fontWeight:700}}>
                      {s.label === 'Grad' ? (
                        <a href={`https://maps.google.com/?q=${encodeURIComponent([listing.city, listing.country].filter(Boolean).join(', '))}`}
                          target="_blank" rel="noopener" style={{color:'inherit',textDecoration:'none'}}>
                          {s.value} 📍
                        </a>
                      ) : s.value}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Proveri podatke */}
            {enriched ? (
              <div style={{display:'flex',alignItems:'center',gap:8,background:'rgba(34,197,94,.08)',border:'1px solid rgba(34,197,94,.2)',borderRadius:10,padding:'10px 14px'}}>
                <span style={{fontSize:16}}>✅</span>
                <div>
                  <div style={{fontSize:14,fontWeight:600,color:'#22C55E'}}>Podaci provereni</div>
                  <div style={{fontSize:12,color:'var(--text3)'}}>AutoAI je ažurirao podatke</div>
                </div>
              </div>
            ) : !enriching && listing.url && (
              <button onClick={onEnrich} style={{width:'100%',padding:'11px 14px',background:'linear-gradient(135deg,rgba(99,102,241,.12),rgba(99,102,241,.06))',border:'1px solid rgba(99,102,241,.3)',color:'#818CF8',borderRadius:10,fontSize:14,fontWeight:600,cursor:'pointer',textAlign:'left'}}>
                🔍 Proveri podatke oglasa
                <span style={{fontSize:12,color:'rgba(129,140,248,.6)',display:'block',marginTop:1}}>Godište · km · Euro norma · uvoz</span>
              </button>
            )}
            {enriching && (
              <div style={{background:'rgba(99,102,241,.08)',border:'1px solid rgba(99,102,241,.25)',borderRadius:10,padding:'9px 14px',display:'flex',alignItems:'center',gap:8}}>
                <div style={{width:7,height:7,borderRadius:'50%',background:'#818CF8',animation:'pulse 1s infinite',flexShrink:0}} />
                <span style={{fontSize:13,color:'#818CF8',fontWeight:600}}>{scanMsg}</span>
              </div>
            )}

            {/* ===== AKCIONA DUGMAD — odmah ispod specifikacija, iznad sličnih oglasa ===== */}
            <div style={{display:'flex', gap:8, marginTop:4}}>
              {/* Kontaktiraj — najveće, najvažnije */}
              <button
                onClick={onContact}
                className="action-btn"
                style={{
                  flex:2, padding:'18px 8px',
                  background:'var(--accent)', border:'none',
                  color:'#fff', borderRadius:14,
                  fontSize:17, fontWeight:800, cursor:'pointer',
                  display:'flex', flexDirection:'column', alignItems:'center', gap:3,
                  boxShadow:'0 4px 20px rgba(255,107,0,.35)',
                }}
              >
                <span style={{fontSize:22}}>🤖</span>
                <span>Kontaktiraj</span>
              </button>

              {/* Sačuvaj */}
              <button
                onClick={onSave}
                className="action-btn"
                style={{
                  flex:1, padding:'18px 6px',
                  background: saved ? 'rgba(255,107,0,.15)' : 'var(--bg2)',
                  border: `2px solid ${saved ? 'var(--accent)' : 'var(--border)'}`,
                  color: saved ? 'var(--accent)' : 'var(--text2)',
                  borderRadius:14,
                  fontSize:14, fontWeight:700, cursor:'pointer',
                  display:'flex', flexDirection:'column', alignItems:'center', gap:3,
                }}
              >
                <span style={{fontSize:22}}>{saved ? '❤️' : '🤍'}</span>
                <span style={{fontSize:13}}>{saved ? 'Sačuvano' : 'Sačuvaj'}</span>
              </button>

              {/* Link na portal */}
              <a
                href={listing.url}
                target="_blank"
                rel="noopener"
                className="action-btn"
                style={{
                  flex:1, padding:'18px 6px',
                  background:'var(--bg2)',
                  border:'2px solid var(--border)',
                  color:'var(--text2)', borderRadius:14,
                  fontSize:13, fontWeight:700, textDecoration:'none',
                  display:'flex', flexDirection:'column', alignItems:'center', gap:3,
                }}
              >
                <span style={{fontSize:22}}>🔗</span>
                <span style={{fontSize:12}}>{portalName}</span>
              </a>
            </div>
            {/* ===== KRAJ AKCIONIH DUGMADI ===== */}

            {/* Slični oglasi */}
            {similar.length > 0 && (
              <div style={{marginTop:4}}>
                <div style={{fontSize:14,fontWeight:700,marginBottom:8,color:'var(--text)'}}>Slični oglasi</div>
                <div style={{display:'flex',gap:8,overflowX:'auto',paddingBottom:4}}>
                  {similar.slice(0,6).map((s:any) => (
                    <a key={s.id} href={`/listing/${s.id}`} style={{flexShrink:0,width:150,background:'var(--bg2)',border:'1px solid var(--border)',borderRadius:10,overflow:'hidden',display:'block',textDecoration:'none'}}>
                      <div style={{height:90,background:'var(--bg3)',overflow:'hidden'}}>
                        {s.images?.[0] ? <img src={s.images[0]} alt="" style={{width:'100%',height:'100%',objectFit:'cover'}} /> : <div style={{height:'100%',display:'flex',alignItems:'center',justifyContent:'center',fontSize:24}}>🚗</div>}
                      </div>
                      <div style={{padding:'7px 9px'}}>
                        <div style={{fontSize:12,fontWeight:600,color:'var(--text)',overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}}>{s.year} {s.make} {s.model}</div>
                        <div style={{fontSize:13,color:'var(--accent)',fontWeight:700,marginTop:2}}>{s.price?`${fmt(s.price)} €`:'—'}</div>
                      </div>
                    </a>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* TAB 1 — AI + Uvoz */}
        {tab === 1 && (
          <div style={{display:'flex', flexDirection:'column', gap:8}}>

            {/* AI Score */}
            <button onClick={onShowScore} style={{width:'100%',background:'var(--bg2)',border:`1px solid ${trust.color}33`,borderRadius:12,padding:'12px 14px',cursor:'pointer',textAlign:'left',display:'flex',justifyContent:'space-between',alignItems:'center'}}>
              <div style={{flex:1}}>
                <div style={{fontSize:12,color:'var(--text3)',fontWeight:600,letterSpacing:'.06em',marginBottom:5}}>AI PROCENA OGLASA</div>
                <div style={{height:6,background:'rgba(255,255,255,.06)',borderRadius:4,overflow:'hidden',marginBottom:6}}>
                  <div style={{height:'100%',borderRadius:4,width:`${trust.score}%`,background:trust.color,transition:'width .6s'}} />
                </div>
                <div className="mob-ai-label" style={{fontSize:14,fontWeight:700,color:trust.color}}>{trust.label}</div>
              </div>
              <div style={{textAlign:'right',marginLeft:12,flexShrink:0}}>
                <div className="mob-ai-score" style={{fontSize:28,fontWeight:800,color:trust.color,lineHeight:1}}>{trust.score}</div>
                <div style={{fontSize:11,color:'var(--text3)'}}>/ 100</div>
              </div>
            </button>

            {/* Uvoz kalkulator */}
            {bd && (
              <div style={{background:'rgba(255,107,0,.07)',border:'1px solid rgba(255,107,0,.2)',borderRadius:12,padding:'12px 14px'}}>
                <div style={{fontSize:11,color:'var(--text3)',fontWeight:600,letterSpacing:'.06em',marginBottom:6}}>🇷🇸 TROŠAK UVOZA U SRBIJU</div>
                <div style={{fontSize:26,fontWeight:800,color:'var(--accent)',marginBottom:10}}>{fmt(bd.total)} €</div>
                {[
                  {label:'EU cena', val:price!, note:''},
                  {label:`Carina (${bd.carinaPct}%)`, val:bd.carina, note:bd.carinaPct===0?'0%':'srbija'},
                  {label:'PDV (20%)', val:bd.pdv, note:'srbija'},
                  {label:'Transport EU→RS', val:bd.transport, note:'procena'},
                  {label:'Registracija', val:bd.reg, note:'procena'},
                ].map(({label,val,note},i) => (
                  <div key={i} style={{display:'flex',justifyContent:'space-between',padding:'5px 0',borderTop:i===0?'none':'1px solid rgba(255,255,255,.05)'}}>
                    <span style={{fontSize:13,color:i===0?'var(--text2)':'var(--text3)'}}>{i>0&&'+ '}{label}</span>
                    <span style={{fontSize:13,fontWeight:600,color:i===0?'var(--text2)':'#fb923c'}}>{fmt(val)} €</span>
                  </div>
                ))}
              </div>
            )}

            {/* Fraud check */}
            {fraud && (
              <div style={{background:'var(--bg2)',border:'1px solid var(--border)',borderRadius:12,padding:'12px 14px'}}>
                <div style={{fontSize:12,fontWeight:700,marginBottom:8}}>🛡️ Bezbednosna provera</div>
                {fraud.red_flags?.map((f:string) => <div key={f} style={{fontSize:13,color:'#F87171',marginBottom:4}}>⚠ {f}</div>)}
                {fraud.safe_signals?.map((s:string) => <div key={s} style={{fontSize:13,color:'#22C55E',marginBottom:4}}>✓ {s}</div>)}
              </div>
            )}

            {/* Opis */}
            {listing.description && (
              <div style={{background:'var(--bg2)',border:'1px solid var(--border)',borderRadius:12,padding:'12px 14px'}}>
                <div style={{fontSize:13,fontWeight:700,marginBottom:8}}>📄 Opis</div>
                <p style={{color:'var(--text2)',lineHeight:1.7,fontSize:13,whiteSpace:'pre-line',margin:0}}>{listing.description.slice(0,600)}{listing.description.length>600?'...':''}</p>
              </div>
            )}
          </div>
        )}

        {/* TAB 2 — VIN + Docs */}
        {tab === 2 && (
          <div style={{display:'flex', flexDirection:'column', gap:8}}>
            {listing.make && (
              <div style={{background:'var(--bg2)',border:'1px solid var(--border)',borderRadius:12,padding:'12px 14px'}}>
                <div style={{fontSize:14,fontWeight:700,marginBottom:10}}>🔧 Šta proveriti</div>
                <ModelChecklist make={listing.make} model={listing.model} year={listing.year} fuelType={listing.fuel_type} transmission={listing.transmission} />
              </div>
            )}
            <div style={{background:'var(--bg2)',border:'1px solid var(--border)',borderRadius:12,padding:'12px 14px'}}>
              <div style={{fontSize:14,fontWeight:700,marginBottom:10}}>🔐 VIN Provera vozila</div>
              <p style={{fontSize:13,color:'var(--text3)',margin:'0 0 12px',lineHeight:1.5}}>
                Zatraži VIN od prodavca koristeći{' '}
                <button onClick={onContact} style={{background:'none',border:'none',color:'var(--accent)',cursor:'pointer',fontSize:13,fontWeight:600,padding:0,textDecoration:'underline'}}>
                  Kontaktiraj prodavca
                </button>
              </p>
              <VinChecker listing={listing} compact onVinResult={onVinResult} />
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

function PageSkeleton() {
  return (
    <div style={{padding:'12px'}}>
      <div className="skeleton" style={{height:240,borderRadius:14,marginBottom:10}} />
      <div className="skeleton" style={{height:80,borderRadius:14,marginBottom:8}} />
      <div className="skeleton" style={{height:60,borderRadius:14,marginBottom:8}} />
      <div className="skeleton" style={{height:60,borderRadius:14}} />
    </div>
  )
}
