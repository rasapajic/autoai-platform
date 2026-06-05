'use client'
export const dynamic = 'force-dynamic'
import { useState, useEffect, useCallback, useRef } from 'react'
import { useSearchParams } from 'next/navigation'
import { searchListings, parseQuery } from '@/lib/api'
import ContactModal from '@/components/ContactModal'

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'https://autoai-platform-production.up.railway.app/api/v1'

const FUEL_LABELS: Record<string, string> = {
  diesel: 'Dizel', petrol: 'Benzin', gasoline: 'Benzin',
  electric: 'Električni', hybrid: 'Hibrid', lpg: 'Plin',
}
const AI_BADGES: Record<string, { label: string; color: string; bg: string }> = {
  great:      { label: '🟢 DOBRA KUPOVINA', color: '#22C55E', bg: 'rgba(34,197,94,.13)'   },
  good:       { label: '🟡 FER CENA',        color: '#EAB308', bg: 'rgba(234,179,8,.13)'   },
  fair:       { label: '⚪ PROSEČNA CENA',   color: '#9CA3AF', bg: 'rgba(156,163,175,.10)' },
  high:       { label: '🟠 VISOKA CENA',     color: '#F97316', bg: 'rgba(249,115,22,.13)'  },
  overpriced: { label: '🔴 PREVISOKA CENA',  color: '#EF4444', bg: 'rgba(239,68,68,.13)'   },
}
const ELIGIBILITY_COLORS: Record<string, string> = {
  eligible: '#22C55E', needs_check: '#F97316',
  not_recommended: '#EF4444', oldtimer: '#A855F7',
}
const COUNTRIES = [
  { code:'AT', flag:'🇦🇹', label:'Austrija' },
  { code:'DE', flag:'🇩🇪', label:'Nemačka' },
  { code:'NL', flag:'🇳🇱', label:'Holandija' },
  { code:'BE', flag:'🇧🇪', label:'Belgija' },
  { code:'FR', flag:'🇫🇷', label:'Francuska' },
  { code:'IT', flag:'🇮🇹', label:'Italija' },
  { code:'CH', flag:'🇨🇭', label:'Švajcarska' },
  { code:'ES', flag:'🇪🇸', label:'Španija' },
  { code:'PL', flag:'🇵🇱', label:'Poljska' },
  { code:'DK', flag:'🇩🇰', label:'Danska' },
  { code:'SE', flag:'🇸🇪', label:'Švedska' },
]
const DEFAULT_FILTERS = {
  make: '', model: '', min_price: '', max_price: '',
  min_year: '', max_year: '', max_km: '', fuel_type: '',
  country: '', countries: [] as string[], price_rating: '', sort_by: 'date', page: 1,
}
const TOOLTIPS = {
  aiScore: `AI Score je automatska ocena oglasa od 0 do 100.`,
  uvozSrbija: `Ovaj indikator pokazuje da li vozilo može da se uveze u Srbiju bez problema. Srbija zahteva minimum Euro 4 emisijsku normu (za benzince godište 2006+, dizele treba posebno proveriti). Električna vozila su oslobođena carine i nemaju ograničenja.`,
  ukupnoSrbija: `Prikazuje procenu ukupnog troška kupovine vozila iz EU i dovoženja u Srbiju. Uključuje: EU cenu vozila, carinu (0-5% zavisno od tipa), PDV (20%), transport od prodavca do Srbije (~420€) i troškove registracije (~280€). Ovo je procena — tačan iznos može da varira.`,
  pronadi: `AutoAI prati nove oglase koji se pojave na svim portalima i šalje ti email čim pronađe vozilo koje odgovara tvojim kriterijumima. Ne moraš svakodnevno da pretražuješ ručno.`,
  kontaktirajProdavca: `AI automatski generiše profesionalnu poruku prodavcu na njegovom jeziku (nemački, holandski, francuski...). Poruka pita za sve važne detalje — VIN broj, servisnu istoriju, razlog prodaje i dostupnost za pregled. Ne moraš da znaš strani jezik.`,
}

function InfoIcon({ id, text }: { id: string; text: string }) {
  const [show, setShow] = useState(false)
  const [isMobile, setIsMobile] = useState(false)
  const [mounted, setMounted] = useState(false)
  const ref = useRef<HTMLSpanElement>(null)
  useEffect(() => {
    setMounted(true)
    const check = () => setIsMobile(window.innerWidth < 769)
    check(); window.addEventListener('resize', check)
    return () => window.removeEventListener('resize', check)
  }, [])
  useEffect(() => {
    if (!show || isMobile) return
    const handler = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setShow(false) }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [show, isMobile])
  const btnStyle: React.CSSProperties = {
    background: show ? 'rgba(239,68,68,.2)' : 'rgba(239,68,68,.1)',
    border: `1px solid ${show ? 'rgba(239,68,68,.6)' : 'rgba(239,68,68,.35)'}`,
    borderRadius: 20, width: 16, height: 16, cursor: 'pointer',
    fontSize: 10, color: '#EF4444', display: 'inline-flex', alignItems: 'center',
    justifyContent: 'center', fontWeight: 700, lineHeight: 1, flexShrink: 0, transition: 'all .15s',
  }
  if (!mounted) return <span style={{ display:'inline-flex', alignItems:'center', marginLeft:5 }}><span style={btnStyle}>ℹ</span></span>
  return (
    <span ref={ref} style={{ display:'inline-flex', alignItems:'center', marginLeft:5, position:'relative' }}>
      <button onMouseEnter={() => !isMobile && setShow(true)} onMouseLeave={() => !isMobile && setShow(false)}
        onClick={e => { e.stopPropagation(); setShow(v => !v) }} style={btnStyle} aria-label="Info">ℹ</button>
      {show && !isMobile && (
        <span style={{ position:'absolute', bottom:'calc(100% + 8px)', left:'50%', transform:'translateX(-50%)',
          background:'var(--bg2)', border:'1px solid var(--border)', borderRadius:10, padding:'10px 14px',
          fontSize:12, color:'var(--text2)', lineHeight:1.6, width:240, zIndex:1000, pointerEvents:'none',
          boxShadow:'0 8px 32px rgba(0,0,0,.5)' }}>
          {text}
          <span style={{ position:'absolute', top:'100%', left:'50%', transform:'translateX(-50%)',
            borderLeft:'6px solid transparent', borderRight:'6px solid transparent', borderTop:'6px solid var(--border)' }} />
        </span>
      )}
      {show && isMobile && (
        <span onClick={e => { e.stopPropagation(); setShow(false) }}
          style={{ position:'fixed', inset:0, zIndex:2000, display:'flex', alignItems:'center', justifyContent:'center',
            background:'rgba(0,0,0,.6)', backdropFilter:'blur(4px)' }}>
          <span onClick={e => e.stopPropagation()}
            style={{ background:'var(--bg2)', border:'1px solid rgba(255,107,0,.3)', borderRadius:16, padding:'20px 18px',
              fontSize:14, color:'var(--text2)', lineHeight:1.7, maxWidth:320, width:'88vw',
              boxShadow:'0 16px 48px rgba(0,0,0,.6)' }}>
            <div style={{ fontSize:11, color:'var(--accent)', fontWeight:700, marginBottom:8, letterSpacing:'.06em' }}>ℹ VIŠE INFO</div>
            {text}
            <div style={{ marginTop:14, textAlign:'right' }}>
              <button onClick={e => { e.stopPropagation(); setShow(false) }}
                style={{ background:'var(--accent)', border:'none', borderRadius:8, padding:'8px 18px', fontSize:13, color:'#fff', fontWeight:700, cursor:'pointer' }}>Zatvori</button>
            </div>
          </span>
        </span>
      )}
    </span>
  )
}

const CDN = 'https://raw.githubusercontent.com/filippofilip95/car-logos-dataset/master/logos/thumb'
const MAKE_LOGOS: Record<string, string> = {
  'Volkswagen':`${CDN}/volkswagen.png`,'BMW':`${CDN}/bmw.png`,'Mercedes-Benz':`${CDN}/mercedes-benz.png`,
  'Audi':`${CDN}/audi.png`,'Ford':`${CDN}/ford.png`,'Opel':`${CDN}/opel.png`,'Renault':`${CDN}/renault.png`,
  'Peugeot':`${CDN}/peugeot.png`,'Citroën':`${CDN}/citroen.png`,'Škoda':`${CDN}/skoda.png`,
  'Toyota':`${CDN}/toyota.png`,'Hyundai':`${CDN}/hyundai.png`,'Kia':`${CDN}/kia.png`,
  'Volvo':`${CDN}/volvo.png`,'SEAT':`${CDN}/seat.png`,'Fiat':`${CDN}/fiat.png`,
  'Nissan':`${CDN}/nissan.png`,'Mazda':`${CDN}/mazda.png`,'Honda':`${CDN}/honda.png`,
  'Tesla':`${CDN}/tesla.png`,'Porsche':`${CDN}/porsche.png`,'MINI':`${CDN}/mini.png`,'Mini':`${CDN}/mini.png`,
  'Mitsubishi':`${CDN}/mitsubishi.png`,'Suzuki':`${CDN}/suzuki.png`,'Subaru':`${CDN}/subaru.png`,
  'Dacia':`${CDN}/dacia.png`,'Alfa Romeo':`${CDN}/alfa-romeo.png`,'Jeep':`${CDN}/jeep.png`,
  'Land Rover':`${CDN}/land-rover.png`,'Cupra':`${CDN}/cupra.png`,'Lexus':`${CDN}/lexus.png`,
  'Dodge':`${CDN}/dodge.png`,'Chevrolet':`${CDN}/chevrolet.png`,'Bentley':`${CDN}/bentley.png`,
  'Ferrari':`${CDN}/ferrari.png`,'Lamborghini':`${CDN}/lamborghini.png`,'Maserati':`${CDN}/maserati.png`,
  'Aston Martin':`${CDN}/aston-martin.png`,'Cadillac':`${CDN}/cadillac.png`,'Rolls-Royce':`${CDN}/rolls-royce.png`,
  'Smart':`${CDN}/smart.png`,'Saab':`${CDN}/saab.png`,'SsangYong':`${CDN}/ssangyong.png`,
  'Lancia':`${CDN}/lancia.png`,'Jaguar':`${CDN}/jaguar.png`,'BYD':`${CDN}/byd.png`,
  'DS':`${CDN}/ds.png`,'Polestar':`${CDN}/polestar.png`,'MG':`${CDN}/mg.png`,
}
const TOP_19_MAKES = [
  'Volkswagen','BMW','Mercedes-Benz','Audi','Ford',
  'Opel','Renault','Peugeot','Citroën','Škoda',
  'Toyota','Hyundai','Kia','Volvo','SEAT',
  'Fiat','Nissan','Mazda','Honda',
]
const ENGINE_SUFFIXES = /\s+(BlueHDI|BlueHDi|HDi|HDI|TDi|TDI|CDI|SDi|dCi|dci|TSI|TFSI|FSI|GTI|GTE|GTD|STI|MHEV|PHEV|HEV|EV|e-tron|4Motion|xDrive|sDrive|AWD|FWD|4WD|quattro|Hybrid|Electric)\b.*/i
const ENGINE_DISPLACEMENT = /\s+\d+[.,]\d+\s*(L|l|T|D)?\s*.*$/
function normalizeModel(model: string): string {
  if (!model) return model
  return model.replace(ENGINE_SUFFIXES,'').replace(ENGINE_DISPLACEMENT,'').trim()
}
function groupModels(raw: {model:string;count:number}[]): {model:string;count:number;raw:string[]}[] {
  const map = new Map<string,{count:number;raw:string[]}>()
  for (const {model,count} of raw) {
    const norm = normalizeModel(model); if (!norm) continue
    const ex = map.get(norm)
    if (ex) { ex.count+=count; ex.raw.push(model) } else map.set(norm,{count,raw:[model]})
  }
  return Array.from(map.entries()).map(([model,{count,raw}])=>({model,count,raw})).sort((a,b)=>b.count-a.count)
}
const MAKE_CANONICAL: Record<string,string> = {
  'vw':'Volkswagen','volkswagen':'Volkswagen','bmw':'BMW',
  'mercedes':'Mercedes-Benz','mercedes-benz':'Mercedes-Benz','mercedes benz':'Mercedes-Benz',
  'audi':'Audi','ford':'Ford','opel':'Opel','renault':'Renault','peugeot':'Peugeot',
  'citroen':'Citroën','skoda':'Škoda','toyota':'Toyota','honda':'Honda','mazda':'Mazda',
  'nissan':'Nissan','hyundai':'Hyundai','kia':'Kia','seat':'SEAT','fiat':'Fiat',
  'volvo':'Volvo','mini':'MINI','porsche':'Porsche','jaguar':'Jaguar',
  'land rover':'Land Rover','landrover':'Land Rover','jeep':'Jeep',
  'subaru':'Subaru','mitsubishi':'Mitsubishi','suzuki':'Suzuki','tesla':'Tesla',
  'dacia':'Dacia','alfa romeo':'Alfa Romeo','alfa':'Alfa Romeo','cupra':'Cupra',
  'lexus':'Lexus','dodge':'Dodge','chevrolet':'Chevrolet','cadillac':'Cadillac',
  'bentley':'Bentley','maserati':'Maserati','ferrari':'Ferrari','lamborghini':'Lamborghini',
  'aston martin':'Aston Martin','rolls-royce':'Rolls-Royce','rolls royce':'Rolls-Royce',
  'smart':'Smart','saab':'Saab','ssangyong':'SsangYong','lancia':'Lancia',
}
function canonicalMake(make: string): string {
  const lower = make.toLowerCase().trim()
    .replace(/ë/g,'e').replace(/é/g,'e').replace(/è/g,'e')
    .replace(/ä/g,'a').replace(/ö/g,'o').replace(/ü/g,'u')
    .replace(/š/g,'s').replace(/č/g,'c').replace(/ž/g,'z')
  return MAKE_CANONICAL[lower] || make.trim()
}
function groupMakes(raw:{make:string;count:number}[]): {make:string;count:number}[] {
  const map = new Map<string,number>()
  for (const {make,count} of raw) {
    if (!make||!make.trim()) continue
    const canon = canonicalMake(make)
    map.set(canon,(map.get(canon)||0)+count)
  }
  return Array.from(map.entries()).map(([make,count])=>({make,count})).sort((a,b)=>a.make.localeCompare(b.make))
}
function calcBreakdown(price: number, carinaPct: number) {
  const carina = Math.round(price*(carinaPct/100))
  const pdv = Math.round((price+carina)*0.20)
  return {carina,pdv,transport:420,reg:280,total:price+carina+pdv+420+280,carinaPct}
}
function getInsight(listing: any): string|null {
  const delta = listing.price_delta_pct ? Number(listing.price_delta_pct) : null
  const km = listing.mileage ? Number(listing.mileage) : null
  const year = listing.year ? Number(listing.year) : null
  if (delta!==null) {
    if (delta<-10) return `${Math.abs(delta).toFixed(0)}% ispod tržišne cene`
    if (delta<-3) return 'Malo ispod tržišne vrednosti'
    if (delta>15) return 'Cena znatno iznad tržišta'
    if (delta>5) return 'Cena iznad proseka za godište'
  }
  if (year&&2026-year<=2) return 'Mlado vozilo, niska amortizacija'
  if (km&&km<50000) return 'Niska kilometraža za godište'
  if (km&&km>200000) return 'Visoka kilometraža — pažljivo proveriti'
  if (listing.fuel_type==='electric') return 'Električno — bez carine u Srbiji'
  return null
}
function formatMileage(raw: any): string|null {
  const km = Number(raw)
  if (!km||km<1||km>999999) return null
  return km.toLocaleString('de-DE')+' km'
}
function fullImg(url: string): string {
  if (!url) return url
  if (url.includes('img.kleinanzeigen.de')) return url.replace(/rule=\$_\w+/, 'rule=$_57.AUTO')
  return url.replace(/\/\d+x\d+\.(webp|jpg|jpeg|png)/i,'/800x600.$1')
}
function getSerbiaEligibility(listing: any) {
  const year = listing.year ? Number(listing.year) : null
  const fuel = listing.fuel_type || null
  const age = year ? (2026-year) : null
  if (fuel==='electric') return {status:'eligible',emoji:'🟢',label:'Može uvoz u Srbiju',tooltip:'Električna vozila su oslobođena carine.',carinaPct:0}
  if (age!==null&&age>=30) return {status:'oldtimer',emoji:'🟣',label:'Oldtimer izuzetak',tooltip:'Poseban režim uvoza.',carinaPct:5}
  if (!year) return null
  if (year>=2015) return {status:'eligible',emoji:'🟢',label:'Može uvoz u Srbiju',tooltip:'Euro 6 — bez ograničenja.',carinaPct:5}
  if (year>=2011) return {status:'eligible',emoji:'🟢',label:'Može uvoz u Srbiju',tooltip:'Euro 5 — može se uvesti.',carinaPct:5}
  if (year>=2006) return {status:'eligible',emoji:'🟢',label:fuel==='diesel'?'Može uvoz — proveri Euro 4':'Može uvoz u Srbiju',tooltip:'Euro 4 je minimalni standard.',carinaPct:5}
  if (year>=2001) return {status:'needs_check',emoji:'🟠',label:'Potrebna provera Euro norme',tooltip:'Moguće uz dodatnu dokumentaciju.',carinaPct:5}
  return {status:'not_recommended',emoji:'🔴',label:'Uvoz nije preporučljiv',tooltip:'Stara emisiona norma.',carinaPct:5}
}

function MakeTile({ makeName, count, isSelected, onClick, logoFailed, onLogoError }: {
  makeName:string;count:number;isSelected:boolean;onClick:()=>void;logoFailed:boolean;onLogoError:()=>void
}) {
  const logoUrl = MAKE_LOGOS[makeName]
  const initials = makeName.split(' ').map((w:string)=>w[0]).join('').slice(0,2).toUpperCase()
  const hasBgLogo = logoUrl && !logoFailed
  return (
    <button onClick={onClick} className="make-tile" style={{
      display:'flex',flexDirection:'column',alignItems:'center',justifyContent:'center',
      gap:4,padding:'10px 4px 8px',borderRadius:14,cursor:'pointer',
      background:isSelected?'rgba(255,107,0,.12)':'var(--bg2)',
      border:`2px solid ${isSelected?'var(--accent)':'var(--border)'}`,
      transition:'all .15s',height:100,width:'100%',boxSizing:'border-box' as any,
    }}>
      <div style={{
        width:48,height:48,flexShrink:0,display:'flex',alignItems:'center',justifyContent:'center',
        borderRadius:10,overflow:'hidden',
        background:hasBgLogo?'rgba(255,255,255,.97)':(isSelected?'rgba(255,107,0,.18)':'rgba(255,255,255,.07)'),
        padding:hasBgLogo?4:0,boxSizing:'border-box' as any,
      }}>
        {hasBgLogo
          ? <img src={logoUrl} alt={makeName} style={{width:40,height:40,objectFit:'contain'}} onError={onLogoError} />
          : <span style={{fontSize:15,fontWeight:800,color:isSelected?'var(--accent)':'var(--text3)',lineHeight:1}}>{initials}</span>
        }
      </div>
      <div style={{
        fontSize:10,fontWeight:600,lineHeight:1.25,
        color:isSelected?'var(--accent)':'var(--text2)',
        textAlign:'center',width:'100%',
        display:'-webkit-box',WebkitLineClamp:2,WebkitBoxOrient:'vertical' as any,
        overflow:'hidden',paddingLeft:3,paddingRight:3,minHeight:24,
      }}>{makeName}</div>
      <div style={{fontSize:9,color:'var(--text3)',opacity:.6,lineHeight:1}}>{count}</div>
    </button>
  )
}

// ── PronadiModal ─────────────────────────────────────────────────
function PronadiModal({ onClose, filters }: { onClose: ()=>void; filters: any }) {
  const [aiText, setAiText] = useState('')
  const [aiParsing, setAiParsing] = useState(false)
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [showCountryPicker, setShowCountryPicker] = useState(false)
  const [showLogin, setShowLogin] = useState(false)
  const [saving, setSaving] = useState(false)
  const [success, setSuccess] = useState(false)
  const [form, setForm] = useState({
    name: filters.make ? `${filters.make}${filters.model?' '+filters.model:''}` : '',
    make: filters.make || '',
    model: filters.model || '',
    max_price: filters.max_price || '',
    max_km: filters.max_km || '',
    min_year: filters.min_year || '',
    fuel_type: filters.fuel_type || '',
    transmission: '',
    countries: filters.countries?.length ? filters.countries : [] as string[],
    min_ai_score: '',
  })

  const parseWithAI = async () => {
    if (!aiText.trim()) return
    setAiParsing(true)
    try {
      const res = await fetch(`${API_BASE}/ai/parse-query`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: aiText })
      })
      if (res.ok) {
        const data = await res.json()
        console.log('AI parse result:', JSON.stringify(data))
        const f = data.filters || data
        console.log('f:', JSON.stringify(f))
        setForm(prev => ({
          ...prev,
          make: f.make || prev.make,
          model: f.model || prev.model,
          max_price: f.max_price ? String(f.max_price) : prev.max_price,
          max_km: f.max_km ? String(f.max_km) : prev.max_km,
          min_year: f.min_year ? String(f.min_year) : prev.min_year,
          fuel_type: f.fuel_type || prev.fuel_type,
          transmission: f.transmission || prev.transmission,
          name: prev.name || (f.make ? `${f.make}${f.model?' '+f.model:''}` : ''),
        }))
        setShowAdvanced(true)
      }
    } catch {}
    setAiParsing(false)
  }

  const handleSubmit = async () => {
    const token = localStorage.getItem('autoai_token')
    if (!token) { setShowLogin(true); return }
    setSaving(true)
    try {
      const res = await fetch(`${API_BASE}/alerts/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
        body: JSON.stringify({
          name: form.name || `${form.make} ${form.model}`.trim() || 'Moja potraga',
          filters: { ...form, countries: form.countries.join(',') },
          frequency: 'daily'
        })
      })
      if (res.ok) setSuccess(true)
    } catch {}
    setSaving(false)
  }

  const IS2: React.CSSProperties = {
    width: '100%', boxSizing: 'border-box' as any,
    background: 'var(--bg3)', border: '1px solid var(--border)',
    borderRadius: 10, padding: '10px 14px',
    color: 'var(--text)', fontSize: 14, outline: 'none',
  }

  // Login gate
  if (showLogin) return (
    <div style={{position:'fixed',inset:0,background:'rgba(0,0,0,.8)',display:'flex',alignItems:'center',justifyContent:'center',zIndex:2000}} onClick={onClose}>
      <div style={{background:'var(--bg2)',border:'1px solid var(--border)',borderRadius:20,padding:'36px 28px',width:360,maxWidth:'92vw',textAlign:'center'}} onClick={e=>e.stopPropagation()}>
        <div style={{fontSize:48,marginBottom:16}}>🔐</div>
        <h3 style={{fontSize:18,fontWeight:800,margin:'0 0 10px'}}>Potrebna je registracija</h3>
        <p style={{fontSize:14,color:'var(--text3)',lineHeight:1.6,margin:'0 0 24px'}}>AutoAI čuva vaše potrage i javlja kada pronađe odgovarajuće vozilo.</p>
        <div style={{display:'flex',flexDirection:'column',gap:10}}>
          <a href="/register" style={{display:'block',padding:'13px',borderRadius:12,background:'var(--accent)',color:'#fff',textDecoration:'none',fontSize:15,fontWeight:700}}>Registruj se</a>
          <a href="/login" style={{display:'block',padding:'13px',borderRadius:12,background:'var(--bg3)',border:'1px solid var(--border)',color:'var(--text2)',textDecoration:'none',fontSize:15,fontWeight:600}}>Prijavi se</a>
        </div>
      </div>
    </div>
  )

  // Success
  if (success) return (
    <div style={{position:'fixed',inset:0,background:'rgba(0,0,0,.8)',display:'flex',alignItems:'center',justifyContent:'center',zIndex:2000}} onClick={onClose}>
      <div style={{background:'var(--bg2)',border:'1px solid rgba(34,197,94,.3)',borderRadius:20,padding:'40px 28px',width:400,maxWidth:'92vw',textAlign:'center'}} onClick={e=>e.stopPropagation()}>
        <div style={{fontSize:56,marginBottom:16}}>✅</div>
        <h3 style={{fontSize:20,fontWeight:800,margin:'0 0 10px'}}>Potraga aktivirana</h3>
        <p style={{fontSize:14,color:'var(--text3)',lineHeight:1.7,margin:'0 0 8px'}}>
          AutoAI će vas obavestiti emailom kada pronađe nova vozila.
        </p>
        <p style={{fontSize:13,color:'var(--text3)',margin:'0 0 28px',opacity:.7}}>
          Potrage možete pratiti u{' '}
          <a href="/profile" style={{color:'var(--accent)',textDecoration:'none',fontWeight:600}}>Moje potrage →</a>
        </p>
        <button onClick={onClose} style={{padding:'13px 36px',borderRadius:12,background:'var(--accent)',color:'#fff',border:'none',fontSize:15,fontWeight:700,cursor:'pointer',boxShadow:'0 4px 20px rgba(255,107,0,.35)'}}>
          Odlično!
        </button>
      </div>
    </div>
  )

  return (
    <div style={{position:'fixed',inset:0,background:'rgba(0,0,0,.8)',display:'flex',alignItems:'flex-end',justifyContent:'center',zIndex:2000}} onClick={onClose}>
      <div style={{background:'var(--bg2)',borderRadius:'20px 20px 0 0',padding:'24px 20px 40px',width:'100%',maxWidth:540,border:'1px solid var(--border)',maxHeight:'92vh',overflowY:'auto'}} onClick={e=>e.stopPropagation()}>

        {/* Header */}
        <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start',marginBottom:20}}>
          <div>
            <div style={{display:'flex',alignItems:'center',gap:8,marginBottom:4}}>
              <h3 style={{fontSize:19,fontWeight:800,margin:0}}>🔎 AutoAI traži za vas</h3>
              <span style={{fontSize:10,padding:'3px 8px',borderRadius:20,background:'rgba(255,107,0,.15)',color:'var(--accent)',fontWeight:800,letterSpacing:'.04em'}}>BETA</span>
            </div>
            <p style={{fontSize:12,color:'var(--text3)',margin:0}}>Opišite šta tražite — AI popunjava kriterijume</p>
          </div>
          <button onClick={onClose} style={{background:'none',border:'none',color:'var(--text3)',fontSize:22,cursor:'pointer',lineHeight:1,flexShrink:0}}>✕</button>
        </div>

        {/* AI unos */}
        <div style={{background:'linear-gradient(135deg,rgba(99,102,241,.1),rgba(99,102,241,.05))',border:'1px solid rgba(99,102,241,.3)',borderRadius:14,padding:16,marginBottom:16}}>
          <div style={{fontSize:11,color:'#818CF8',fontWeight:700,letterSpacing:'.06em',marginBottom:8}}>✨ OPIŠI KAKAV AUTO TRAŽIŠ</div>
          <textarea
            value={aiText}
            onChange={e=>setAiText(e.target.value)}
            placeholder={'npr.\nTražim BMW Seriju 3, automatik,\ndo 18.000€, ispod 150.000 km,\nbez velikih rizika.'}
            rows={3}
            style={{width:'100%',boxSizing:'border-box' as any,background:'rgba(0,0,0,.2)',border:'1px solid rgba(99,102,241,.25)',borderRadius:10,padding:'10px 14px',color:'var(--text)',fontSize:13,outline:'none',resize:'none',lineHeight:1.6,fontFamily:'inherit'}}
          />
          <button onClick={parseWithAI} disabled={aiParsing||!aiText.trim()}
            style={{width:'100%',marginTop:10,padding:'11px',borderRadius:10,
              background:aiParsing||!aiText.trim()?'rgba(99,102,241,.1)':'rgba(99,102,241,.2)',
              border:'1px solid rgba(99,102,241,.4)',color:aiParsing||!aiText.trim()?'rgba(129,140,248,.4)':'#818CF8',
              fontSize:13,fontWeight:700,cursor:aiParsing||!aiText.trim()?'default':'pointer',
              display:'flex',alignItems:'center',justifyContent:'center',gap:8}}>
            {aiParsing ? <><span style={{display:'inline-block',animation:'pulse 1s infinite',width:6,height:6,borderRadius:'50%',background:'#818CF8'}}/>Analiziram...</> : '✨ Popuni automatski'}
          </button>
        </div>

        {/* Obavezna polja */}
        <div style={{display:'flex',flexDirection:'column',gap:12,marginBottom:16}}>
          <div>
            <div style={{fontSize:11,color:'var(--text3)',fontWeight:600,letterSpacing:'.06em',marginBottom:6}}>NAZIV POTRAGE</div>
            <input placeholder="npr. BMW 3 do 18.000€" value={form.name} onChange={e=>setForm(p=>({...p,name:e.target.value}))} style={IS2} />
          </div>
          <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:10}}>
            <div>
              <div style={{fontSize:11,color:'var(--text3)',fontWeight:600,letterSpacing:'.06em',marginBottom:6}}>MARKA <span style={{color:'#EF4444'}}>*</span></div>
              <input placeholder="npr. BMW" value={form.make} onChange={e=>setForm(p=>({...p,make:e.target.value}))} style={IS2} />
            </div>
            <div>
              <div style={{fontSize:11,color:'var(--text3)',fontWeight:600,letterSpacing:'.06em',marginBottom:6}}>MODEL</div>
              <input placeholder="npr. Serija 3" value={form.model} onChange={e=>setForm(p=>({...p,model:e.target.value}))} style={IS2} />
            </div>
          </div>
          <div>
            <div style={{fontSize:11,color:'var(--text3)',fontWeight:600,letterSpacing:'.06em',marginBottom:6}}>MAKS. BUDŽET (€) <span style={{color:'#EF4444'}}>*</span></div>
            <input type="number" placeholder="npr. 18000" value={form.max_price} onChange={e=>setForm(p=>({...p,max_price:e.target.value}))} style={IS2} />
          </div>
        </div>

        {/* Opcioni kriterijumi */}
        <button onClick={()=>setShowAdvanced(!showAdvanced)}
          style={{width:'100%',background:'var(--bg3)',border:'1px solid var(--border)',borderRadius:10,padding:'10px 14px',
            color:'var(--text3)',fontSize:13,cursor:'pointer',textAlign:'left',display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:showAdvanced?12:16}}>
          <span>⚙️ Opcioni kriterijumi</span>
          <span style={{fontSize:11,transition:'transform .2s',display:'inline-block',transform:showAdvanced?'rotate(180deg)':'none'}}>▼</span>
        </button>

        {showAdvanced && (
          <div style={{display:'flex',flexDirection:'column',gap:12,marginBottom:16,padding:'14px',background:'var(--bg3)',borderRadius:12,border:'1px solid var(--border)'}}>
            <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:10}}>
              <div>
                <div style={{fontSize:11,color:'var(--text3)',fontWeight:600,letterSpacing:'.06em',marginBottom:6}}>MAKS. KM</div>
                <input type="number" placeholder="npr. 150000" value={form.max_km} onChange={e=>setForm(p=>({...p,max_km:e.target.value}))} style={IS2} />
              </div>
              <div>
                <div style={{fontSize:11,color:'var(--text3)',fontWeight:600,letterSpacing:'.06em',marginBottom:6}}>MIN. GODIŠTE</div>
                <input type="number" placeholder="npr. 2015" value={form.min_year} onChange={e=>setForm(p=>({...p,min_year:e.target.value}))} style={IS2} />
              </div>
            </div>

            <div>
              <div style={{fontSize:11,color:'var(--text3)',fontWeight:600,letterSpacing:'.06em',marginBottom:6}}>GORIVO</div>
              <div style={{display:'flex',gap:5,flexWrap:'wrap'}}>
                {[['','Sve'],['diesel','Dizel'],['petrol','Benzin'],['electric','Električni'],['hybrid','Hibrid']].map(([v,l])=>(
                  <button key={v} onClick={()=>setForm(p=>({...p,fuel_type:v}))}
                    style={{padding:'5px 11px',borderRadius:20,fontSize:12,cursor:'pointer',
                      background:form.fuel_type===v?'rgba(255,107,0,.15)':'transparent',
                      border:`1px solid ${form.fuel_type===v?'var(--accent)':'var(--border)'}`,
                      color:form.fuel_type===v?'var(--accent)':'var(--text3)'}}>
                    {l}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <div style={{fontSize:11,color:'var(--text3)',fontWeight:600,letterSpacing:'.06em',marginBottom:6}}>MENJAČ</div>
              <div style={{display:'flex',gap:5}}>
                {[['','Sve'],['automatic','Automatik'],['manual','Manuel']].map(([v,l])=>(
                  <button key={v} onClick={()=>setForm(p=>({...p,transmission:v}))}
                    style={{padding:'5px 11px',borderRadius:20,fontSize:12,cursor:'pointer',
                      background:form.transmission===v?'rgba(255,107,0,.15)':'transparent',
                      border:`1px solid ${form.transmission===v?'var(--accent)':'var(--border)'}`,
                      color:form.transmission===v?'var(--accent)':'var(--text3)'}}>
                    {l}
                  </button>
                ))}
              </div>
            </div>

            {/* Minimalni kvalitet */}
            <div>
              <div style={{fontSize:11,color:'var(--text3)',fontWeight:600,letterSpacing:'.06em',marginBottom:6}}>MINIMALNI KVALITET VOZILA</div>
              <input type="number" placeholder="npr. 70" min="0" max="100" value={form.min_ai_score}
                onChange={e=>setForm(p=>({...p,min_ai_score:e.target.value}))} style={IS2} />
              <div style={{display:'flex',gap:12,marginTop:6}}>
                {[['60','prihvatljivo'],['80','dobra kupovina'],['90','retka prilika']].map(([v,l])=>(
                  <button key={v} onClick={()=>setForm(p=>({...p,min_ai_score:v}))}
                    style={{fontSize:11,padding:'3px 8px',borderRadius:20,cursor:'pointer',
                      background:form.min_ai_score===v?'rgba(255,107,0,.15)':'transparent',
                      border:`1px solid ${form.min_ai_score===v?'var(--accent)':'var(--border)'}`,
                      color:form.min_ai_score===v?'var(--accent)':'var(--text3)'}}>
                    {v} = {l}
                  </button>
                ))}
              </div>
            </div>

            {/* Države */}
            <div>
              <div style={{fontSize:11,color:'var(--text3)',fontWeight:600,letterSpacing:'.06em',marginBottom:6}}>DRŽAVE</div>
              <button onClick={()=>setShowCountryPicker(!showCountryPicker)}
                style={{width:'100%',padding:'9px 14px',borderRadius:10,background:'var(--bg2)',border:'1px solid var(--border)',
                  color:'var(--text2)',fontSize:13,cursor:'pointer',textAlign:'left',display:'flex',justifyContent:'space-between',alignItems:'center'}}>
                <span>
                  {form.countries.length > 0
                    ? form.countries.map((c:string) => COUNTRIES.find(x=>x.code===c)?.flag+' '+c).join(' · ')
                    : 'Sve države'}
                </span>
                <span style={{fontSize:11,opacity:.6}}>▼</span>
              </button>
              {showCountryPicker && (
                <div style={{display:'grid',gridTemplateColumns:'repeat(3,1fr)',gap:4,marginTop:6}}>
                  {COUNTRIES.map(({code,flag,label})=>{
                    const active = form.countries.includes(code)
                    return (
                      <button key={code} onClick={()=>{
                        const next = active ? form.countries.filter((c:string)=>c!==code) : [...form.countries,code]
                        setForm(p=>({...p,countries:next}))
                      }} style={{padding:'5px 6px',borderRadius:8,fontSize:11,cursor:'pointer',
                        background:active?'rgba(255,107,0,.15)':'transparent',
                        border:`1px solid ${active?'var(--accent)':'var(--border)'}`,
                        color:active?'var(--accent)':'var(--text3)'}}>
                        {flag} {label}
                      </button>
                    )
                  })}
                </div>
              )}
            </div>
          </div>
        )}

        {/* Kako radi kartica */}
        <div style={{background:'rgba(255,255,255,.03)',border:'1px solid rgba(255,255,255,.08)',borderRadius:12,padding:'12px 14px',marginBottom:16}}>
          <div style={{fontSize:11,color:'var(--text3)',fontWeight:600,marginBottom:8}}>ⓘ Kako radi?</div>
          <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:4,marginBottom:10}}>
            {['✓ cenu','✓ kilometražu','✓ godište','✓ AI score','✓ mogućnost uvoza','✓ Euro normu'].map(t=>(
              <div key={t} style={{fontSize:12,color:'var(--text3)'}}>{t}</div>
            ))}
          </div>
          <div style={{fontSize:11,color:'var(--text3)',opacity:.6,paddingTop:8,borderTop:'1px solid rgba(255,255,255,.06)'}}>
            Stalno proveravamo nove oglase sa svih portala
          </div>
        </div>

        {/* Submit */}
        <button onClick={handleSubmit} disabled={saving||!form.make}
          style={{width:'100%',padding:'15px',borderRadius:14,
            background:saving||!form.make?'var(--bg3)':'var(--accent)',
            color:saving||!form.make?'var(--text3)':'#fff',
            border:'none',fontSize:16,fontWeight:800,
            cursor:saving||!form.make?'default':'pointer',
            boxShadow:saving||!form.make?'none':'0 4px 20px rgba(255,107,0,.35)'}}>
          {saving ? '⏳ Kreiramo potragu...' : '🔎 AutoAI traži za mene'}
        </button>
        <p style={{fontSize:11,color:'var(--text3)',textAlign:'center',marginTop:10,lineHeight:1.6,opacity:.7}}>
          AutoAI proverava nove oglase i šalje email kada pronađe odgovarajuće vozilo.<br/>
          Rezultati se otvaraju unutar AutoAI naloga.
        </p>
      </div>
    </div>
  )
}


export default function SearchPage() {
  const searchParams = useSearchParams()
  const getInitialFilters = () => {
    if (typeof window!=='undefined') {
      try {
        const saved = sessionStorage.getItem('autoai_filters')
        const fromListing = sessionStorage.getItem('autoai_from_listing')
        if (saved&&fromListing==='1') { sessionStorage.removeItem('autoai_from_listing'); return JSON.parse(saved) }
      } catch {}
    }
    return {
      ...DEFAULT_FILTERS,
      make:searchParams.get('make')||'',model:searchParams.get('model')||'',
      min_price:searchParams.get('min_price')||'',max_price:searchParams.get('max_price')||'',
      min_year:searchParams.get('min_year')||'',max_year:searchParams.get('max_year')||'',
      max_km:searchParams.get('max_km')||'',fuel_type:searchParams.get('fuel_type')||'',
      country:searchParams.get('country')||'',countries:[],
      price_rating:searchParams.get('price_rating')||'',sort_by:searchParams.get('sort_by')||'date',
    }
  }

  const [results,setResults]=useState<any>(null)
  const [loading,setLoading]=useState(true)
  const [aiQuery,setAiQuery]=useState(searchParams.get('q')||'')
  const [aiLoading,setAiLoading]=useState(false)
  const [sidebarOpen,setSidebarOpen]=useState(false)
  const [contactListing,setContactListing]=useState<any>(null)
  const [showPronadiModal,setShowPronadiModal]=useState(false)
  const [showMakeModal,setShowMakeModal]=useState(false)
  const [pronadiSuccess,setPronadiSuccess]=useState(false)
  const [searchHistory,setSearchHistory]=useState<string[]>([])
  const [compareList,setCompareList]=useState<any[]>([])
  const [makes,setMakes]=useState<{make:string;count:number}[]>([])
  const [rawModels,setRawModels]=useState<{model:string;count:number}[]>([])
  const [makesLoading,setMakesLoading]=useState(false)
  const [modelSearch,setModelSearch]=useState('')
  const [filters,setFilters]=useState(DEFAULT_FILTERS)
  const [logoErrors,setLogoErrors]=useState<Record<string,boolean>>({})

  useEffect(()=>{ setFilters(getInitialFilters()) },[])

  useEffect(()=>{
    setMakesLoading(true)
    fetch(`${API_BASE}/search/makes`).then(r=>r.json()).then(data=>{
      const filtered=(data||[]).filter((m:any)=>m.make&&m.make.trim())
      setMakes(groupMakes(filtered))
    }).catch(()=>{}).finally(()=>setMakesLoading(false))
  },[])

  useEffect(()=>{
    if (!filters.make){setRawModels([]);return}
    fetch(`${API_BASE}/search/models?make=${encodeURIComponent(filters.make)}`).then(r=>r.json()).then(data=>setRawModels((data||[]).filter((m:any)=>m.model&&m.model.trim()))).catch(()=>setRawModels([]))
  },[filters.make])

  const groupedModels = groupModels(rawModels)
  const filteredModels = groupedModels.filter(m=>!modelSearch||m.model.toLowerCase().includes(modelSearch.toLowerCase()))

  const doSearch = useCallback(async(f=filters)=>{
    setLoading(true)
    try{sessionStorage.setItem('autoai_filters',JSON.stringify(f));sessionStorage.setItem('autoai_search_url',window.location.href)}catch{}
    try{const fSend={...f,countries:(f.countries||[]).join(',')};const data=await searchListings(fSend);setResults(data)}
    catch{setResults(null)}
    finally{setLoading(false)}
  },[filters])

  useEffect(()=>{doSearch()},[])
  useEffect(()=>{const h=localStorage.getItem('autoai_search_history');if(h)setSearchHistory(JSON.parse(h))},[])

  const setFilter=(key:string,val:any)=>{
    const normalized=key==='make'&&val?canonicalMake(val):val
    const next:any={...filters,[key]:normalized,page:key==='page'?val:1}
    if(key==='make')next.model=''
    setFilters(next);doSearch(next)
  }
  const handleModelSelect=(normalizedModel:string,rawVariants:string[])=>{
    const isDeselect=filters.model===normalizedModel
    const next:any={...filters,model:isDeselect?'':normalizedModel,page:1}
    setFilters(next);doSearch(next)
  }
  const handleAiSearch=async(e:React.FormEvent)=>{
    e.preventDefault();if(!aiQuery.trim())return;setAiLoading(true)
    try{
      const{filters:parsed}=await parseQuery(aiQuery)
      const next={...filters,...parsed,page:1};setFilters(next);doSearch(next)
      const newHistory=[aiQuery,...searchHistory.filter(h=>h!==aiQuery)].slice(0,5)
      setSearchHistory(newHistory);localStorage.setItem('autoai_search_history',JSON.stringify(newHistory))
    }finally{setAiLoading(false)}
  }
  const handleListingClick=()=>{
    try{sessionStorage.setItem('autoai_from_listing','1');sessionStorage.setItem('autoai_filters',JSON.stringify(filters))}catch{}
  }

  const activeCount=[filters.make,filters.model,filters.min_price,filters.max_price,filters.min_year,filters.max_year,filters.max_km,filters.fuel_type,filters.price_rating,...(filters.countries||[])].filter(Boolean).length
  const makesCountMap=new Map(makes.map(m=>[m.make,m.count]))
  const gridMakes:{make:string;count:number}[]=TOP_19_MAKES.filter(m=>makesCountMap.has(m)).map(m=>({make:m,count:makesCountMap.get(m)!}))
  const inGrid=new Set(gridMakes.map(m=>m.make))
  const fallback=makes.sort((a,b)=>b.count-a.count).filter(m=>!inGrid.has(m.make))
  while(gridMakes.length<19&&fallback.length>0)gridMakes.push(fallback.shift()!)

  return (
    <div style={{minHeight:'100vh',background:'var(--bg)'}}>
      <style dangerouslySetInnerHTML={{__html:`
        @media(max-width:768px){
          .sg{display:block!important;width:100%!important}
          .rg{grid-template-columns:1fr!important}
          .sd{display:none!important}
          .hero{display:none!important}
          .ai-form-inner{flex-direction:column!important}
          .ai-btn{width:100%!important;margin-top:6px!important}
          .pagination-desktop{display:none!important}
          .pagination-mobile{display:flex!important}
        }
        @media(min-width:769px){
          .mfb{display:none!important}
          .sm{display:none!important}
          .ai-form-inner{flex-direction:row!important;align-items:center!important}
          .ai-btn{width:auto!important}
        }
        .ch{transition:all .22s ease!important}
        .ch:hover{border-color:var(--accent)!important;transform:translateY(-3px)!important;box-shadow:0 14px 44px rgba(0,0,0,.45)!important}
        .cb:hover{opacity:.82!important}
        .mkbtn{transition:all .15s!important}
        .mkbtn:hover{border-color:var(--accent)!important;color:var(--accent)!important}
        .make-tile:hover{border-color:var(--accent)!important;background:rgba(255,107,0,.08)!important;transform:translateY(-2px)!important;box-shadow:0 8px 24px rgba(0,0,0,.3)!important}
        .make-tile{transition:all .15s ease!important}
        .pronadi-btn{transition:all .2s!important}
        .pronadi-btn:hover{transform:translateY(-2px)!important;box-shadow:0 8px 28px rgba(255,107,0,.4)!important}
      `}} />

      {contactListing&&<ContactModal listing={contactListing} onClose={()=>setContactListing(null)} />}
      {showPronadiModal&&<PronadiModal onClose={()=>setShowPronadiModal(false)} filters={filters} />}

      {/* Make modal */}
      {showMakeModal&&(
        <div style={{position:'fixed',inset:0,background:'rgba(0,0,0,.75)',zIndex:1000,display:'flex',alignItems:'flex-end'}} onClick={()=>setShowMakeModal(false)}>
          <div style={{background:'var(--bg2)',borderRadius:'20px 20px 0 0',padding:'20px 16px 40px',width:'100%',border:'1px solid var(--border)',maxHeight:'80vh',overflowY:'auto'}} onClick={e=>e.stopPropagation()}>
            <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:16}}>
              <div><h3 style={{fontSize:16,margin:0}}>Sve marke</h3><p style={{fontSize:12,color:'var(--text3)',margin:'4px 0 0'}}>{makes.length} marki — sortirano abecedno</p></div>
              <button onClick={()=>setShowMakeModal(false)} style={{background:'none',border:'none',color:'var(--text3)',fontSize:20,cursor:'pointer'}}>✕</button>
            </div>
            <div style={{display:'grid',gridTemplateColumns:'repeat(4,1fr)',gap:6}}>
              {makes.map(({make:mkName,count:mkCount})=>(
                <MakeTile key={mkName} makeName={mkName} count={mkCount} isSelected={filters.make===mkName}
                  logoFailed={!!logoErrors[mkName]} onLogoError={()=>setLogoErrors(prev=>({...prev,[mkName]:true}))}
                  onClick={()=>{setFilter('make',filters.make===mkName?'':mkName);setShowMakeModal(false)}} />
              ))}
            </div>
          </div>
        </div>
      )}

      <div className="container" style={{padding:'16px 16px 80px'}}>
        {/* Hero */}
        <div className="hero" style={{background:'linear-gradient(135deg,rgba(255,107,0,.09),rgba(255,107,0,.03))',border:'1px solid rgba(255,107,0,.22)',borderRadius:16,padding:'18px 22px',marginBottom:18,display:'flex',gap:16,alignItems:'center',flexWrap:'wrap'}}>
          <div style={{flex:1,minWidth:180}}>
            <p style={{fontSize:21,fontWeight:700,margin:0,fontFamily:'Syne,sans-serif',lineHeight:1.3}}>AI pomoćnik za uvoz automobila iz EU u Srbiju</p>
            <p style={{fontSize:13,color:'var(--text2)',margin:'5px 0 0'}}>Analizira cene · Računa realni trošak uvoza · Proverava podobnost uvoza</p>
          </div>
          <div style={{display:'flex',gap:7,flexWrap:'wrap'}}>
            {['🤖 AI analiza','🛡 Zaštita od prevare','🇷🇸 Trošak uvoza','✉️ AI kontakt'].map(t=>(
              <span key={t} style={{padding:'5px 11px',borderRadius:20,fontSize:12,fontWeight:500,background:'rgba(255,107,0,.1)',border:'1px solid rgba(255,107,0,.25)',color:'var(--accent)',whiteSpace:'nowrap'}}>{t}</span>
            ))}
          </div>
        </div>

        {/* AI Search */}
        <form onSubmit={handleAiSearch} style={{marginBottom:12}}>
          <div className="ai-form-inner" style={{display:'flex',background:'var(--bg3)',border:'1px solid var(--border2)',borderRadius:14,padding:6,boxShadow:'0 4px 20px rgba(0,0,0,.2)',gap:6}}>
            <div style={{flex:1,display:'flex',alignItems:'center',gap:10,padding:'4px 14px'}}>
              <span style={{fontSize:17}}>🤖</span>
              <input value={aiQuery} onChange={e=>setAiQuery(e.target.value)} placeholder='npr. "Golf dizel do 15000€, max 100000km"'
                style={{flex:1,background:'none',border:'none',outline:'none',color:'var(--text)',fontSize:15}} />
            </div>
            <button className="ai-btn" type="submit" disabled={aiLoading} style={{background:aiLoading?'var(--bg2)':'var(--accent)',color:aiLoading?'var(--text3)':'#fff',border:'none',borderRadius:10,padding:'12px 18px',fontSize:14,fontWeight:700,cursor:aiLoading?'default':'pointer',whiteSpace:'nowrap'}}>
              {aiLoading?'⏳ Analiziram...':'🔍 AI Pretraga'}
            </button>
          </div>
        </form>

        {/* Istorija */}
        {searchHistory.length>0&&!aiQuery&&(
          <div style={{marginBottom:12}}>
            <div style={{fontSize:11,color:'var(--text3)',fontWeight:600,letterSpacing:'.07em',marginBottom:8}}>NEDAVNE PRETRAGE</div>
            <div style={{display:'flex',gap:6,flexWrap:'wrap'}}>
              {searchHistory.map((h,i)=>(
                <button key={i} onClick={()=>{setAiQuery(h);handleAiSearch({preventDefault:()=>{}} as any)}}
                  style={{padding:'6px 12px',borderRadius:20,fontSize:12,background:'var(--bg2)',border:'1px solid var(--border)',color:'var(--text3)',cursor:'pointer'}}>🕐 {h}</button>
              ))}
              <button onClick={()=>{setSearchHistory([]);localStorage.removeItem('autoai_search_history')}}
                style={{padding:'6px 12px',borderRadius:20,fontSize:12,background:'transparent',border:'none',color:'var(--text3)',cursor:'pointer',opacity:.6}}>✕ Obriši</button>
            </div>
          </div>
        )}

        {/* Aktivni filteri */}
        {activeCount>0&&(
          <div style={{display:'flex',gap:6,flexWrap:'wrap',marginBottom:10,alignItems:'center'}}>
            <span style={{fontSize:11,color:'var(--text3)'}}>Prikazujem:</span>
            {filters.make&&<span style={{padding:'4px 10px',borderRadius:20,fontSize:12,background:'rgba(255,107,0,.1)',border:'1px solid rgba(255,107,0,.3)',color:'var(--accent)'}}>{filters.make}</span>}
            {filters.model&&<span style={{padding:'4px 10px',borderRadius:20,fontSize:12,background:'rgba(255,107,0,.1)',border:'1px solid rgba(255,107,0,.3)',color:'var(--accent)'}}>{filters.model}</span>}
            {filters.fuel_type&&<span style={{padding:'4px 10px',borderRadius:20,fontSize:12,background:'rgba(255,107,0,.1)',border:'1px solid rgba(255,107,0,.3)',color:'var(--accent)'}}>{FUEL_LABELS[filters.fuel_type]||filters.fuel_type}</span>}
            {filters.min_price&&<span style={{padding:'4px 10px',borderRadius:20,fontSize:12,background:'rgba(255,107,0,.1)',border:'1px solid rgba(255,107,0,.3)',color:'var(--accent)'}}>od {Number(filters.min_price).toLocaleString()} €</span>}
            {filters.max_price&&<span style={{padding:'4px 10px',borderRadius:20,fontSize:12,background:'rgba(255,107,0,.1)',border:'1px solid rgba(255,107,0,.3)',color:'var(--accent)'}}>do {Number(filters.max_price).toLocaleString()} €</span>}
            {filters.min_year&&<span style={{padding:'4px 10px',borderRadius:20,fontSize:12,background:'rgba(255,107,0,.1)',border:'1px solid rgba(255,107,0,.3)',color:'var(--accent)'}}>od {filters.min_year}.</span>}
            {filters.max_year&&<span style={{padding:'4px 10px',borderRadius:20,fontSize:12,background:'rgba(255,107,0,.1)',border:'1px solid rgba(255,107,0,.3)',color:'var(--accent)'}}>do {filters.max_year}.</span>}
            <button onClick={()=>{const r={...DEFAULT_FILTERS};setFilters(r);doSearch(r)}}
              style={{padding:'4px 10px',borderRadius:20,fontSize:12,background:'transparent',border:'1px solid var(--border)',color:'var(--text3)',cursor:'pointer'}}>✕ Ukloni sve</button>
          </div>
        )}

        {/* MAKE GRID */}
        <div style={{marginBottom:12}}>
          <div style={{fontSize:11,color:'var(--text3)',fontWeight:600,letterSpacing:'.07em',marginBottom:10}}>
            MARKA {makesLoading&&<span style={{opacity:.5}}>učitavam...</span>}
          </div>
          <div style={{display:'grid',gridTemplateColumns:'repeat(4,1fr)',gap:6}}>
            {gridMakes.map(({make:mkName,count:mkCount})=>(
              <MakeTile key={mkName} makeName={mkName} count={mkCount} isSelected={filters.make===mkName}
                logoFailed={!!logoErrors[mkName]} onLogoError={()=>setLogoErrors(prev=>({...prev,[mkName]:true}))}
                onClick={()=>setFilter('make',filters.make===mkName?'':mkName)} />
            ))}
            <button onClick={()=>setShowMakeModal(true)} className="make-tile" style={{
              display:'flex',flexDirection:'column',alignItems:'center',justifyContent:'center',
              gap:4,padding:'10px 4px 8px',borderRadius:14,cursor:'pointer',
              background:'var(--bg2)',border:'2px dashed var(--border)',
              height:100,width:'100%',boxSizing:'border-box' as any,
            }}>
              <div style={{width:48,height:48,borderRadius:10,display:'flex',alignItems:'center',justifyContent:'center',background:'rgba(255,107,0,.08)',fontSize:22,flexShrink:0}}>🔍</div>
              <div style={{fontSize:10,fontWeight:600,color:'var(--text3)',textAlign:'center',lineHeight:1.25,minHeight:24}}>Sve marke</div>
              <div style={{fontSize:9,color:'var(--text3)',opacity:.6,lineHeight:1}}>+{Math.max(0,makes.length-19)}</div>
            </button>
          </div>

          {/* Modeli */}
          {filters.make&&(
            <div style={{marginTop:10,padding:'12px 14px',background:'var(--bg2)',borderRadius:12,border:'1px solid var(--border)'}}>
              <div style={{fontSize:11,color:'var(--text3)',fontWeight:600,letterSpacing:'.07em',marginBottom:8}}>
                MODEL — {filters.make.toUpperCase()}
                {groupedModels.length>0&&<span style={{fontWeight:400,opacity:.6,marginLeft:6}}>({groupedModels.length} modela)</span>}
              </div>
              {rawModels.length>0 ? (
                <>
                  {groupedModels.length>10&&(
                    <input placeholder="Traži model..." value={modelSearch} onChange={e=>setModelSearch(e.target.value)}
                      style={{width:'100%',boxSizing:'border-box' as any,background:'var(--bg3)',border:'1px solid var(--border)',borderRadius:8,padding:'7px 12px',color:'var(--text)',fontSize:13,outline:'none',marginBottom:8}} />
                  )}
                  <div style={{display:'flex',flexWrap:'wrap',gap:5}}>
                    <button className="mkbtn cb" onClick={()=>setFilter('model','')} style={{padding:'5px 11px',borderRadius:20,fontSize:13,cursor:'pointer',background:!filters.model?'rgba(255,107,0,.15)':'transparent',border:`1px solid ${!filters.model?'var(--accent)':'var(--border)'}`,color:!filters.model?'var(--accent)':'var(--text)'}}>Svi</button>
                    {filteredModels.slice(0,40).map(({model:mdName,count:mdCount,raw})=>(
                      <button key={mdName} className="mkbtn cb" onClick={()=>handleModelSelect(mdName,raw)}
                        style={{padding:'5px 11px',borderRadius:20,fontSize:13,cursor:'pointer',background:filters.model===mdName?'rgba(255,107,0,.15)':'transparent',border:`1px solid ${filters.model===mdName?'var(--accent)':'var(--border)'}`,color:filters.model===mdName?'var(--accent)':'var(--text)',display:'flex',gap:4,alignItems:'center'}}>
                        {mdName}<span style={{fontSize:10,opacity:.6}}>{mdCount}</span>
                      </button>
                    ))}
                  </div>
                </>
              ) : <p style={{fontSize:12,color:'var(--text3)',margin:0}}>Učitavam modele...</p>}
              <button onClick={()=>setFilter('make','')} style={{marginTop:8,background:'none',border:'none',color:'var(--text2)',fontSize:13,cursor:'pointer'}}>✕ Ukloni {filters.make}</button>
            </div>
          )}
        </div>

        {/* Pronađi mi ovakav auto dugme */}
        <div style={{display:'flex',justifyContent:'flex-end',alignItems:'center',gap:8,marginBottom:12}}>
          {pronadiSuccess&&<span style={{fontSize:13,color:'#22C55E',fontWeight:600}}>✅ AutoAI traži vozilo za vas!</span>}
          <div style={{display:'flex',alignItems:'center',gap:4}}>
            <button onClick={()=>setShowPronadiModal(true)} className="pronadi-btn"
              style={{padding:'10px 18px',borderRadius:12,fontSize:13,fontWeight:700,
                background:'linear-gradient(135deg,rgba(255,107,0,.15),rgba(255,107,0,.08))',
                border:'1px solid rgba(255,107,0,.4)',color:'var(--accent)',cursor:'pointer',
                display:'flex',alignItems:'center',gap:8}}>
              🔎 Pronađi mi ovakav auto
            </button>
            <InfoIcon id="pronadi" text={TOOLTIPS.pronadi} />
          </div>
        </div>

        {/* Mobile filter toggle */}
        <button className="mfb cb" onClick={()=>setSidebarOpen(!sidebarOpen)} style={{display:'flex',alignItems:'center',justifyContent:'center',gap:8,padding:'11px 16px',borderRadius:10,marginBottom:16,width:'100%',background:activeCount>0?'rgba(255,107,0,.1)':'var(--bg2)',border:`1px solid ${activeCount>0?'var(--accent)':'var(--border)'}`,color:activeCount>0?'var(--accent)':'var(--text2)',fontSize:14,fontWeight:600,cursor:'pointer'}}>
          ⚙️ Filteri {activeCount>0&&`(${activeCount})`} {sidebarOpen?'▲':'▼'}
        </button>

        <div className="sg" style={{display:'grid',gridTemplateColumns:'260px 1fr',gap:24,alignItems:'start'}}>
          <aside className="sd" style={{background:'var(--bg2)',border:'1px solid var(--border)',borderRadius:16,padding:20,position:'sticky',top:80,maxHeight:'calc(100vh - 100px)',overflowY:'auto'}}>
            <Sidebar filters={filters} setFilter={setFilter} onReset={()=>{const r={...DEFAULT_FILTERS};setFilters(r);doSearch(r)}} />
          </aside>
          {sidebarOpen&&(
            <div className="sm" style={{background:'var(--bg2)',border:'1px solid var(--border)',borderRadius:16,padding:20,marginBottom:16,gridColumn:'1/-1'}}>
              <Sidebar filters={filters} setFilter={setFilter} onReset={()=>{const r={...DEFAULT_FILTERS};setFilters(r);doSearch(r)}} />
            </div>
          )}
          <div>
            <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:16,flexWrap:'wrap',gap:8}}>
              <span style={{fontSize:15,fontWeight:600}}>
                {loading?'...':`${results?.total?.toLocaleString()||0} vozila`}
                {!loading&&results?.total>0&&<span style={{color:'var(--text3)',fontSize:13,marginLeft:8}}>analiziranih AI-om</span>}
              </span>
              <select value={filters.sort_by} onChange={e=>setFilter('sort_by',e.target.value)}
                style={{background:'var(--bg2)',border:'1px solid var(--border)',borderRadius:8,padding:'8px 12px',color:'var(--text)',fontSize:13,outline:'none',cursor:'pointer'}}>
                <option value="date">Najnoviji</option>
                <option value="best_deal">Najbolja ponuda</option>
                <option value="price_asc">Cena ↑</option>
                <option value="price_desc">Cena ↓</option>
                <option value="year_desc">Najmlađi</option>
              </select>
            </div>

            {(filters.countries?.length>0)&&(
              <div style={{display:'flex',gap:6,flexWrap:'wrap',marginBottom:12}}>
                <span style={{fontSize:12,color:'var(--text3)',alignSelf:'center'}}>📍</span>
                {(filters.countries||[]).map((code:string)=>{
                  const c=COUNTRIES.find(x=>x.code===code)
                  return c?(
                    <span key={code} style={{fontSize:12,padding:'3px 9px',borderRadius:20,background:'rgba(255,107,0,.1)',border:'1px solid rgba(255,107,0,.3)',color:'var(--accent)'}}>
                      {c.flag} {c.label}
                      <button onClick={()=>setFilter('countries',(filters.countries||[]).filter((x:string)=>x!==code))} style={{background:'none',border:'none',color:'var(--accent)',cursor:'pointer',marginLeft:4,fontSize:13}}>✕</button>
                    </span>
                  ):null
                })}
              </div>
            )}

            {!loading&&results?.pages>1&&<Pagination pages={results.pages} current={filters.page} onPage={p=>{setFilter('page',p);window.scrollTo({top:0,behavior:'smooth'})}} />}

            {loading ? (
              <div className="rg" style={{display:'grid',gridTemplateColumns:'repeat(auto-fill,minmax(300px,1fr))',gap:20}}>
                {[...Array(6)].map((_,i)=><div key={i} className="skeleton" style={{height:520,borderRadius:16}} />)}
              </div>
            ) : results?.results?.length ? (
              <>
                <div className="rg" style={{display:'grid',gridTemplateColumns:'repeat(auto-fill,minmax(300px,1fr))',gap:20}}>
                  {results.results.map((l:any)=>(
                    <ListingCard key={l.id} listing={l}
                      onContact={()=>setContactListing(l)}
                      onListingClick={handleListingClick}
                      onCompare={()=>setCompareList(prev=>prev.find(c=>c.id===l.id)?prev.filter(c=>c.id!==l.id):prev.length<3?[...prev,l]:prev)}
                      inCompare={!!compareList.find(c=>c.id===l.id)}
                    />
                  ))}
                </div>
                {results.pages>1&&(
                  <div style={{marginTop:32}}>
                    <Pagination pages={results.pages} current={filters.page} onPage={p=>{setFilter('page',p);window.scrollTo({top:0,behavior:'smooth'})}} />
                    <div className="pagination-mobile" style={{display:'none',flexDirection:'column',alignItems:'center',gap:12,marginTop:16}}>
                      {filters.page<results.pages&&(
                        <button onClick={()=>setFilter('page',filters.page+1)} style={{width:'100%',padding:'14px',borderRadius:12,background:'var(--bg2)',border:'1px solid var(--border)',color:'var(--text2)',fontSize:15,fontWeight:600,cursor:'pointer'}}>⬇️ Učitaj još oglasa</button>
                      )}
                      <span style={{fontSize:12,color:'var(--text3)'}}>Strana {filters.page} od {results.pages}</span>
                    </div>
                  </div>
                )}
              </>
            ) : (
              /* ── EMPTY STATE sa Pronađi CTA ── */
              <div style={{textAlign:'center',padding:'60px 20px 40px',background:'var(--bg2)',borderRadius:16,border:'1px solid var(--border)'}}>
                <div style={{fontSize:52,marginBottom:16}}>🔍</div>
                <p style={{fontSize:18,fontWeight:700,marginBottom:8}}>Nismo našli odgovarajuće vozilo</p>
                <p style={{color:'var(--text3)',fontSize:14,marginBottom:32,lineHeight:1.6}}>
                  Pokušaj sa različitim filterima ili AI pretragom.<br/>
                  AutoAI može da prati nove oglase i pronađe ga za vas.
                </p>
                <button onClick={()=>setShowPronadiModal(true)} className="pronadi-btn"
                  style={{padding:'16px 32px',borderRadius:16,fontSize:16,fontWeight:800,
                    background:'var(--accent)',color:'#fff',border:'none',cursor:'pointer',
                    boxShadow:'0 6px 24px rgba(255,107,0,.4)',display:'inline-flex',alignItems:'center',gap:10}}>
                  🔎 Pronađi mi ovakav auto
                </button>
                <p style={{fontSize:12,color:'var(--text3)',marginTop:14,opacity:.7}}>
                  Dobijate email čim se pojavi odgovarajući oglas
                </p>
              </div>
            )}
          </div>
        </div>
      </div>

      {compareList.length>0&&(
        <div style={{position:'fixed',bottom:0,left:0,right:0,zIndex:200,background:'rgba(17,17,20,.97)',borderTop:'1px solid rgba(99,102,241,.4)',backdropFilter:'blur(12px)',padding:'12px 16px'}}>
          <div className="container" style={{display:'flex',alignItems:'center',gap:12,flexWrap:'wrap'}}>
            <span style={{fontSize:13,color:'var(--text3)',fontWeight:600}}>⚖️ Poređenje ({compareList.length}/3):</span>
            <div style={{display:'flex',gap:8,flex:1,flexWrap:'wrap'}}>
              {compareList.map(c=>(
                <div key={c.id} style={{background:'var(--bg3)',border:'1px solid rgba(99,102,241,.3)',borderRadius:8,padding:'5px 10px',fontSize:12,display:'flex',alignItems:'center',gap:6}}>
                  <span style={{color:'var(--text2)'}}>{c.year} {c.make} {c.model}</span>
                  <button onClick={()=>setCompareList(prev=>prev.filter(x=>x.id!==c.id))} style={{background:'none',border:'none',color:'var(--text3)',cursor:'pointer',fontSize:14}}>✕</button>
                </div>
              ))}
            </div>
            <div style={{display:'flex',gap:8}}>
              <button onClick={()=>setCompareList([])} style={{padding:'8px 14px',borderRadius:8,fontSize:13,background:'transparent',border:'1px solid var(--border)',color:'var(--text3)',cursor:'pointer'}}>Otkaži</button>
              {compareList.length>=2&&(
                <button onClick={()=>{window.location.href=`/compare?ids=${compareList.map(c=>c.id).join(',')}`}}
                  style={{padding:'8px 20px',borderRadius:8,fontSize:13,fontWeight:700,background:'var(--accent)',color:'#fff',border:'none',cursor:'pointer'}}>Uporedi →</button>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function Pagination({pages,current,onPage}:{pages:number;current:number;onPage:(p:number)=>void}) {
  const total=Math.min(pages,74)
  const pageNums:number[]=[]
  if(total<=7){for(let i=1;i<=total;i++)pageNums.push(i)}
  else{
    pageNums.push(1)
    if(current>3)pageNums.push(-1)
    for(let i=Math.max(2,current-1);i<=Math.min(total-1,current+1);i++)pageNums.push(i)
    if(current<total-2)pageNums.push(-2)
    pageNums.push(total)
  }
  return (
    <div className="pagination-desktop" style={{display:'flex',justifyContent:'center',gap:6,flexWrap:'wrap',marginBottom:16}}>
      {current>1&&<button onClick={()=>onPage(current-1)} style={{width:38,height:38,borderRadius:10,border:'1px solid var(--border)',background:'var(--bg2)',color:'var(--text2)',fontSize:14,cursor:'pointer'}}>‹</button>}
      {pageNums.map((p,i)=>p<0
        ?<span key={p} style={{width:38,height:38,display:'flex',alignItems:'center',justifyContent:'center',color:'var(--text3)'}}>…</span>
        :<button key={p} onClick={()=>onPage(p)} style={{width:38,height:38,borderRadius:10,border:'1px solid var(--border)',background:current===p?'var(--accent)':'var(--bg2)',color:current===p?'#fff':'var(--text2)',fontSize:13,cursor:'pointer',fontWeight:600}}>{p}</button>
      )}
      {current<total&&<button onClick={()=>onPage(current+1)} style={{width:38,height:38,borderRadius:10,border:'1px solid var(--border)',background:'var(--bg2)',color:'var(--text2)',fontSize:14,cursor:'pointer'}}>›</button>}
    </div>
  )
}

function ListingCard({listing,onContact,onCompare,inCompare,onListingClick}:{listing:any;onContact:()=>void;onCompare:()=>void;inCompare:boolean;onListingClick:()=>void}) {
  const badge=AI_BADGES[listing.price_rating]
  const insight=getInsight(listing)
  const img=listing.images?.[0]
  const price=listing.price?Number(listing.price):null
  const eligibility=getSerbiaEligibility(listing)
  const bd=price&&eligibility?calcBreakdown(price,eligibility.carinaPct):null
  const delta=listing.price_delta_pct?Number(listing.price_delta_pct):null
  const mileage=formatMileage(listing.mileage)
  const eligColor=eligibility?ELIGIBILITY_COLORS[eligibility.status]:null
  const [showBd,setShowBd]=useState(false)
  return (
    <div className="ch" style={{background:'var(--bg2)',border:'1px solid var(--border)',borderRadius:16,overflow:'hidden'}}>
      {badge?(
        <div style={{background:badge.bg,borderBottom:`2px solid ${badge.color}`,padding:'9px 16px',display:'flex',justifyContent:'space-between',alignItems:'center'}}>
          <span style={{color:badge.color,fontSize:13,fontWeight:800,letterSpacing:'.03em'}}>{badge.label}</span>
          {delta!==null&&<span style={{color:delta<0?'#22C55E':'#EF4444',fontSize:12,fontWeight:600}}>{delta>0?'+':''}{delta.toFixed(0)}% vs tržišta</span>}
        </div>
      ):(
        <div style={{background:'rgba(99,102,241,.07)',borderBottom:'2px solid rgba(99,102,241,.2)',padding:'9px 16px'}}>
          <span style={{color:'#818CF8',fontSize:12,fontWeight:700}}>🤖 AI ANALIZA U TOKU</span>
        </div>
      )}
      <a href={`/listing/${listing.id}`} onClick={onListingClick} style={{display:'block',textDecoration:'none'}}>
        <div style={{height:220,background:'#0a0a0a',position:'relative',overflow:'hidden'}}>
          {img
            ?<img src={fullImg(img)} alt={`${listing.make} ${listing.model}`} style={{width:'100%',height:'100%',objectFit:'contain',background:'#0a0a0a'}} onError={e=>{(e.target as HTMLImageElement).src=img}} />
            :<div style={{display:'flex',alignItems:'center',justifyContent:'center',height:'100%',fontSize:48,opacity:.35}}>🚗</div>
          }
          <span style={{position:'absolute',bottom:10,left:10,background:'rgba(0,0,0,.75)',borderRadius:6,padding:'3px 8px',fontSize:11,color:'rgba(255,255,255,.85)',backdropFilter:'blur(4px)'}}>
            {listing.country==='DE'?'🇩🇪':listing.country==='AT'?'🇦🇹':listing.country==='NL'?'🇳🇱':listing.country==='BE'?'🇧🇪':listing.country==='FR'?'🇫🇷':listing.country==='IT'?'🇮🇹':listing.country==='CH'?'🇨🇭':listing.country==='ES'?'🇪🇸':listing.country==='PL'?'🇵🇱':listing.country==='DK'?'🇩🇰':listing.country==='SE'?'🇸🇪':'✓'} Verifikovan izvor
          </span>
        </div>
        <div style={{padding:'14px 18px 0'}}>
          <h3 style={{fontSize:15,fontWeight:600,margin:'0 0 4px',fontFamily:'Syne,sans-serif',lineHeight:1.3,color:'var(--text)'}}>
            {listing.year&&`${listing.year} `}{listing.make} {listing.model}
          </h3>
          {insight&&(
            <p style={{fontSize:12,color:badge?.color||'#818CF8',margin:'0 0 10px',display:'flex',alignItems:'center',gap:5}}>
              <span style={{width:5,height:5,borderRadius:'50%',background:badge?.color||'#818CF8',display:'inline-block',flexShrink:0}} />{insight}
            </p>
          )}
        </div>
      </a>
      <div style={{padding:'0 18px 18px'}}>
        {eligibility&&eligColor&&(
          <div style={{background:`${eligColor}11`,border:`1px solid ${eligColor}44`,borderRadius:10,padding:'9px 12px',marginBottom:10}}>
            <div style={{display:'flex',alignItems:'center',marginBottom:2}}>
              <div style={{fontSize:10,color:'var(--text3)',letterSpacing:'.06em',fontWeight:600}}>UVOZ U SRBIJU</div>
              <InfoIcon id="uvozSrbija" text={TOOLTIPS.uvozSrbija} />
            </div>
            <div style={{fontSize:12,fontWeight:700,color:eligColor}}>{eligibility.emoji} {eligibility.label}</div>
            {eligibility.tooltip&&<div style={{fontSize:10,color:'var(--text3)',marginTop:2,lineHeight:1.4}}>{eligibility.tooltip}</div>}
          </div>
        )}
        <div style={{display:'flex',alignItems:'center',gap:8,marginBottom:10}}>
          <span style={{fontSize:12,color:'var(--text3)'}}>EU cena:</span>
          <span style={{fontSize:18,fontWeight:700,color:'var(--text2)'}}>{price?`${price.toLocaleString('de-DE')} €`:'Na upit'}</span>
        </div>
        {bd&&(
          <div style={{background:'rgba(255,107,0,.07)',border:'1px solid rgba(255,107,0,.2)',borderRadius:10,overflow:'hidden',marginBottom:12}}>
            <button onClick={()=>setShowBd(!showBd)} className="cb" style={{width:'100%',background:'none',border:'none',cursor:'pointer',padding:'10px 14px',display:'flex',justifyContent:'space-between',alignItems:'center'}}>
              <div style={{textAlign:'left'}}>
                <div style={{display:'flex',alignItems:'center'}}>
                  <div style={{fontSize:11,color:'var(--text3)',marginBottom:2}}>🇷🇸 Ukupno za Srbiju</div>
                  <InfoIcon id="ukupnoSrbija" text={TOOLTIPS.ukupnoSrbija} />
                </div>
                <div style={{fontSize:19,fontWeight:800,color:'var(--accent)'}}>{bd.total.toLocaleString('de-DE')} €</div>
              </div>
              <span style={{fontSize:11,color:'rgba(255,107,0,.6)'}}>{showBd?'▲ sakrij':'▼ detalji'}</span>
            </button>
            {showBd&&(
              <div style={{padding:'0 14px 12px',borderTop:'1px solid rgba(255,107,0,.15)'}}>
                {[
                  {label:'EU cena',val:price!,note:''},
                  {label:`Carina (${bd.carinaPct}%)`,val:bd.carina,note:bd.carinaPct===0?'oslobođeno':'srbija'},
                  {label:'PDV (20%)',val:bd.pdv,note:'srbija'},
                  {label:'Transport EU→RS',val:bd.transport,note:'procena'},
                  {label:'Registracija',val:bd.reg,note:'procena'},
                ].map(({label,val,note},i)=>(
                  <div key={i} style={{display:'flex',justifyContent:'space-between',padding:'4px 0',borderTop:i===0?'none':'1px solid rgba(255,255,255,.04)',marginTop:i===0?8:0}}>
                    <span style={{fontSize:12,color:i===0?'var(--text2)':'var(--text3)'}}>{i>0&&'+ '}{label}{note&&<span style={{fontSize:10,marginLeft:4,opacity:.5}}>({note})</span>}</span>
                    <span style={{fontSize:12,fontWeight:500,color:i===0?'var(--text2)':'#fb923c'}}>{i===0?'':'+'}{val.toLocaleString('de-DE')} €</span>
                  </div>
                ))}
                <div style={{display:'flex',justifyContent:'space-between',marginTop:8,paddingTop:8,borderTop:'1px solid rgba(255,107,0,.25)'}}>
                  <span style={{fontSize:13,fontWeight:700}}>Ukupno za Srbiju</span>
                  <span style={{fontSize:15,fontWeight:800,color:'var(--accent)'}}>{bd.total.toLocaleString('de-DE')} €</span>
                </div>
              </div>
            )}
          </div>
        )}
        <div style={{display:'flex',gap:10,flexWrap:'wrap',fontSize:12,color:'var(--text3)',paddingBottom:10,borderBottom:'1px solid var(--border)'}}>
          {mileage&&<span>🛣 {mileage}</span>}
          {listing.fuel_type&&<span>⛽ {FUEL_LABELS[listing.fuel_type]||listing.fuel_type}</span>}
          {listing.country&&<span>📍 {listing.country}</span>}
        </div>
        <p style={{fontSize:10,color:'var(--text3)',margin:'8px 0 10px',lineHeight:1.5,opacity:.7}}>
          * Procena je informativna. Pre kupovine obavezno proveriti dokumentaciju i važeće propise.
        </p>
        <button onClick={onCompare} style={{width:'100%',padding:'9px',marginBottom:8,background:inCompare?'rgba(99,102,241,.15)':'transparent',border:`1px solid ${inCompare?'rgba(99,102,241,.5)':'var(--border)'}`,color:inCompare?'#818CF8':'var(--text3)',borderRadius:10,fontSize:13,cursor:'pointer',fontWeight:500}}>
          {inCompare?'✓ Dodato za poređenje':'⚖️ Uporedi'}
        </button>
        <div style={{display:'flex',alignItems:'center',gap:4}}>
          <button onClick={onContact} className="cb" style={{flex:1,padding:'11px',background:'rgba(99,102,241,.1)',border:'1px solid rgba(99,102,241,.3)',color:'#818CF8',borderRadius:10,fontSize:13,fontWeight:600,cursor:'pointer'}}>
            🤖 Kontaktiraj prodavca
          </button>
          <InfoIcon id="kontaktirajProdavca" text={TOOLTIPS.kontaktirajProdavca} />
        </div>
      </div>
    </div>
  )
}

function Sidebar({filters,setFilter,onReset}:any) {
  return (
    <>
      <h3 style={{fontSize:11,marginBottom:20,color:'var(--text3)',letterSpacing:'.1em',fontWeight:600}}>FILTERI</h3>
      <FS label="Cena (EUR)">
        <div style={{display:'flex',gap:6}}>
          <input type="number" placeholder="Od" value={filters.min_price} onChange={e=>setFilter('min_price',e.target.value)} style={IS} />
          <input type="number" placeholder="Do" value={filters.max_price} onChange={e=>setFilter('max_price',e.target.value)} style={IS} />
        </div>
      </FS>
      <FS label="Godište">
        <div style={{display:'flex',gap:6}}>
          <input type="number" placeholder="Od" value={filters.min_year} onChange={e=>setFilter('min_year',e.target.value)} style={IS} />
          <input type="number" placeholder="Do" value={filters.max_year} onChange={e=>setFilter('max_year',e.target.value)} style={IS} />
        </div>
      </FS>
      <FS label="Max km">
        <input type="number" placeholder="npr. 150000" value={filters.max_km} onChange={e=>setFilter('max_km',e.target.value)} style={{...IS,width:'100%',boxSizing:'border-box' as any}} />
      </FS>
      <FS label="Gorivo">
        <div style={{display:'flex',flexWrap:'wrap',gap:4}}>
          {[['diesel','Dizel'],['petrol','Benzin'],['electric','Električni'],['hybrid','Hibrid'],['lpg','Plin']].map(([v,l])=>(
            <FC key={v} label={l} active={filters.fuel_type===v} onClick={()=>setFilter('fuel_type',filters.fuel_type===v?'':v)} />
          ))}
        </div>
      </FS>
      <FS label="AI Ocena">
        <div style={{display:'flex',flexDirection:'column',gap:4}}>
          {Object.entries(AI_BADGES).map(([v,{label,color}])=>(
            <FC key={v} label={label} active={filters.price_rating===v} onClick={()=>setFilter('price_rating',filters.price_rating===v?'':v)} color={color} full />
          ))}
        </div>
      </FS>
      <FS label="Lokacija vozila">
        <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:4}}>
          {COUNTRIES.map(({code,flag,label})=>{
            const active=(filters.countries||[]).includes(code)
            return (
              <button key={code} className="cb" onClick={()=>{const cur=filters.countries||[];setFilter('countries',active?cur.filter((c:string)=>c!==code):[...cur,code])}}
                style={{padding:'5px 8px',borderRadius:8,fontSize:12,cursor:'pointer',transition:'all .15s',background:active?'rgba(255,107,0,.15)':'transparent',border:`1px solid ${active?'var(--accent)':'var(--border)'}`,color:active?'var(--accent)':'var(--text3)',textAlign:'left'}}>
                {flag} {label}
              </button>
            )
          })}
        </div>
      </FS>
      <button className="cb" onClick={onReset} style={{width:'100%',padding:11,borderRadius:10,marginTop:4,background:'transparent',border:'1px solid var(--border)',color:'var(--text3)',fontSize:13,cursor:'pointer',fontWeight:500}}>Resetuj filtere</button>
    </>
  )
}

function FS({label,children}:any) {
  return (
    <div style={{marginBottom:22}}>
      <div style={{fontSize:11,color:'var(--text3)',letterSpacing:'.08em',marginBottom:8,fontWeight:600}}>{label.toUpperCase()}</div>
      {children}
    </div>
  )
}
function FC({label,active,onClick,color,full}:any) {
  return (
    <button className="cb" onClick={onClick} style={{
      display:full?'block':'inline-block',width:full?'100%':'auto',
      textAlign:full?'left':'center',padding:full?'7px 12px':'5px 11px',
      borderRadius:full?8:20,fontSize:12,fontWeight:active?600:400,
      background:active?(color?color+'20':'rgba(255,107,0,.15)'):'transparent',
      border:`1px solid ${active?(color||'var(--accent)'):'var(--border)'}`,
      color:active?(color||'var(--accent)'):'var(--text3)',
      cursor:'pointer',transition:'all .15s',
    }}>{label}</button>
  )
}
const IS: React.CSSProperties = {
  flex:1,background:'var(--bg3)',border:'1px solid var(--border)',
  borderRadius:8,padding:'9px 11px',color:'var(--text)',fontSize:13,outline:'none',minWidth:0,
}
