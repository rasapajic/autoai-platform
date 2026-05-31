'use client'
import { useState, useEffect, useCallback } from 'react'
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

// ✅ Logo URL-ovi za marke — Clearbit / CarLogos
const MAKE_LOGOS: Record<string, string> = {
  'Volkswagen':    'https://logo.clearbit.com/vw.com',
  'BMW':           'https://logo.clearbit.com/bmw.com',
  'Mercedes-Benz': 'https://logo.clearbit.com/mercedes-benz.com',
  'Audi':          'https://logo.clearbit.com/audi.com',
  'Ford':          'https://logo.clearbit.com/ford.com',
  'Opel':          'https://logo.clearbit.com/opel.com',
  'Renault':       'https://logo.clearbit.com/renault.com',
  'Peugeot':       'https://logo.clearbit.com/peugeot.com',
  'Citroën':       'https://logo.clearbit.com/citroen.com',
  'Škoda':         'https://logo.clearbit.com/skoda-auto.com',
  'Toyota':        'https://logo.clearbit.com/toyota.com',
  'Hyundai':       'https://logo.clearbit.com/hyundai.com',
  'Kia':           'https://logo.clearbit.com/kia.com',
  'Volvo':         'https://logo.clearbit.com/volvocars.com',
  'SEAT':          'https://logo.clearbit.com/seat.com',
  'Fiat':          'https://logo.clearbit.com/fiat.com',
  'Nissan':        'https://logo.clearbit.com/nissan.com',
  'Mazda':         'https://logo.clearbit.com/mazda.com',
  'Honda':         'https://logo.clearbit.com/honda.com',
  'Tesla':         'https://logo.clearbit.com/tesla.com',
  'Porsche':       'https://logo.clearbit.com/porsche.com',
  'Mini':          'https://logo.clearbit.com/mini.com',
  'MINI':          'https://logo.clearbit.com/mini.com',
  'Mitsubishi':    'https://logo.clearbit.com/mitsubishi-motors.com',
  'Suzuki':        'https://logo.clearbit.com/suzuki.com',
  'Subaru':        'https://logo.clearbit.com/subaru.com',
  'Dacia':         'https://logo.clearbit.com/dacia.com',
  'Alfa Romeo':    'https://logo.clearbit.com/alfaromeo.com',
  'Jeep':          'https://logo.clearbit.com/jeep.com',
  'Land Rover':    'https://logo.clearbit.com/landrover.com',
  'Cupra':         'https://logo.clearbit.com/cupraofficial.com',
  'Lexus':         'https://logo.clearbit.com/lexus.com',
  'Dodge':         'https://logo.clearbit.com/dodge.com',
  'Chevrolet':     'https://logo.clearbit.com/chevrolet.com',
  'Bentley':       'https://logo.clearbit.com/bentleymotors.com',
  'Ferrari':       'https://logo.clearbit.com/ferrari.com',
  'Lamborghini':   'https://logo.clearbit.com/lamborghini.com',
  'Maserati':      'https://logo.clearbit.com/maserati.com',
  'Aston Martin':  'https://logo.clearbit.com/astonmartin.com',
}

// ✅ 19 najpopularnijih marki u Evropi — fiksni redosled za grid
const TOP_19_MAKES = [
  'Volkswagen', 'BMW', 'Mercedes-Benz', 'Audi', 'Ford',
  'Opel', 'Renault', 'Peugeot', 'Citroën', 'Škoda',
  'Toyota', 'Hyundai', 'Kia', 'Volvo', 'SEAT',
  'Fiat', 'Nissan', 'Mazda', 'Honda',
]

const ENGINE_SUFFIXES = /\s+(BlueHDI|BlueHDi|HDi|HDI|TDi|TDI|CDI|SDi|dCi|dci|TSI|TFSI|FSI|GTI|GTE|GTD|STI|MHEV|PHEV|HEV|EV|e-tron|4Motion|xDrive|sDrive|AWD|FWD|4WD|quattro|Hybrid|Electric)\b.*/i
const ENGINE_DISPLACEMENT = /\s+\d+[.,]\d+\s*(L|l|T|D)?\s*.*$/

function normalizeModel(model: string): string {
  if (!model) return model
  return model.replace(ENGINE_SUFFIXES, '').replace(ENGINE_DISPLACEMENT, '').trim()
}

function groupModels(raw: { model: string; count: number }[]): { model: string; count: number; raw: string[] }[] {
  const map = new Map<string, { count: number; raw: string[] }>()
  for (const { model, count } of raw) {
    const norm = normalizeModel(model)
    if (!norm) continue
    const existing = map.get(norm)
    if (existing) { existing.count += count; existing.raw.push(model) }
    else map.set(norm, { count, raw: [model] })
  }
  return Array.from(map.entries())
    .map(([model, { count, raw }]) => ({ model, count, raw }))
    .sort((a, b) => b.count - a.count)
}

const MAKE_CANONICAL: Record<string, string> = {
  'vw': 'Volkswagen', 'volkswagen': 'Volkswagen',
  'bmw': 'BMW',
  'mercedes': 'Mercedes-Benz', 'mercedes-benz': 'Mercedes-Benz', 'mercedes benz': 'Mercedes-Benz',
  'audi': 'Audi', 'ford': 'Ford', 'opel': 'Opel', 'renault': 'Renault',
  'peugeot': 'Peugeot', 'citroen': 'Citroën', 'skoda': 'Škoda',
  'toyota': 'Toyota', 'honda': 'Honda', 'mazda': 'Mazda', 'nissan': 'Nissan',
  'hyundai': 'Hyundai', 'kia': 'Kia', 'seat': 'SEAT', 'fiat': 'Fiat',
  'volvo': 'Volvo', 'mini': 'MINI', 'porsche': 'Porsche', 'jaguar': 'Jaguar',
  'land rover': 'Land Rover', 'landrover': 'Land Rover', 'jeep': 'Jeep',
  'subaru': 'Subaru', 'mitsubishi': 'Mitsubishi', 'suzuki': 'Suzuki',
  'tesla': 'Tesla', 'dacia': 'Dacia', 'alfa romeo': 'Alfa Romeo', 'alfa': 'Alfa Romeo',
  'cupra': 'Cupra', 'lexus': 'Lexus', 'dodge': 'Dodge', 'chevrolet': 'Chevrolet',
  'cadillac': 'Cadillac', 'bentley': 'Bentley', 'maserati': 'Maserati',
  'ferrari': 'Ferrari', 'lamborghini': 'Lamborghini', 'aston martin': 'Aston Martin',
  'rolls-royce': 'Rolls-Royce', 'rolls royce': 'Rolls-Royce', 'smart': 'Smart',
  'saab': 'Saab', 'ssangyong': 'SsangYong', 'lancia': 'Lancia',
}

function canonicalMake(make: string): string {
  const lower = make.toLowerCase().trim()
    .replace(/ë/g, 'e').replace(/é/g, 'e').replace(/è/g, 'e')
    .replace(/ä/g, 'a').replace(/ö/g, 'o').replace(/ü/g, 'u')
    .replace(/š/g, 's').replace(/č/g, 'c').replace(/ž/g, 'z')
  return MAKE_CANONICAL[lower] || make.trim()
}

function groupMakes(raw: { make: string; count: number }[]): { make: string; count: number }[] {
  const map = new Map<string, number>()
  for (const { make, count } of raw) {
    if (!make || !make.trim()) continue
    const canon = canonicalMake(make)
    map.set(canon, (map.get(canon) || 0) + count)
  }
  return Array.from(map.entries())
    .map(([make, count]) => ({ make, count }))
    .sort((a, b) => a.make.localeCompare(b.make))
}

function calcBreakdown(price: number, carinaPct: number) {
  const carina = Math.round(price * (carinaPct / 100))
  const pdv    = Math.round((price + carina) * 0.20)
  return { carina, pdv, transport: 420, reg: 280, total: price + carina + pdv + 420 + 280, carinaPct }
}

function getInsight(listing: any): string | null {
  const delta = listing.price_delta_pct ? Number(listing.price_delta_pct) : null
  const km    = listing.mileage ? Number(listing.mileage) : null
  const year  = listing.year ? Number(listing.year) : null
  if (delta !== null) {
    if (delta < -10) return `${Math.abs(delta).toFixed(0)}% ispod tržišne cene`
    if (delta < -3)  return 'Malo ispod tržišne vrednosti'
    if (delta > 15)  return 'Cena znatno iznad tržišta'
    if (delta > 5)   return 'Cena iznad proseka za godište'
  }
  if (year && 2026 - year <= 2) return 'Mlado vozilo, niska amortizacija'
  if (km && km < 50000)         return 'Niska kilometraža za godište'
  if (km && km > 200000)        return 'Visoka kilometraža — pažljivo proveriti'
  if (listing.fuel_type === 'electric') return 'Električno — bez carine u Srbiji'
  return null
}

function formatMileage(raw: any): string | null {
  const km = Number(raw)
  if (!km || km < 1 || km > 999999) return null
  return km.toLocaleString('de-DE') + ' km'
}

function fullImg(url: string): string {
  if (!url) return url
  return url.replace(/\/\d+x\d+\.(webp|jpg|jpeg|png)/i, '/800x600.$1')
}

function getSerbiaEligibility(listing: any) {
  const year = listing.year ? Number(listing.year) : null
  const fuel = listing.fuel_type || null
  const age  = year ? (2026 - year) : null
  if (fuel === 'electric') return { status:'eligible', emoji:'🟢', label:'Može uvoz u Srbiju', tooltip:'Električna vozila su oslobođena carine.', carinaPct:0 }
  if (age !== null && age >= 30) return { status:'oldtimer', emoji:'🟣', label:'Oldtimer izuzetak', tooltip:'Poseban režim uvoza.', carinaPct:5 }
  if (!year) return null
  if (year >= 2015) return { status:'eligible', emoji:'🟢', label:'Može uvoz u Srbiju', tooltip:'Euro 6 — bez ograničenja.', carinaPct:5 }
  if (year >= 2011) return { status:'eligible', emoji:'🟢', label:'Može uvoz u Srbiju', tooltip:'Euro 5 — može se uvesti.', carinaPct:5 }
  if (year >= 2006) return { status:'eligible', emoji:'🟢', label: fuel==='diesel' ? 'Može uvoz — proveri Euro 4' : 'Može uvoz u Srbiju', tooltip:'Euro 4 je minimalni standard.', carinaPct:5 }
  if (year >= 2001) return { status:'needs_check', emoji:'🟠', label:'Potrebna provera Euro norme', tooltip:'Moguće uz dodatnu dokumentaciju.', carinaPct:5 }
  return { status:'not_recommended', emoji:'🔴', label:'Uvoz nije preporučljiv', tooltip:'Stara emisiona norma.', carinaPct:5 }
}

// ✅ Komponenta jednog polja u Make Gridu
function MakeTile({ makeName, count, isSelected, onClick, logoFailed, onLogoError }: {
  makeName: string; count: number; isSelected: boolean;
  onClick: () => void; logoFailed: boolean; onLogoError: () => void
}) {
  const logoUrl = MAKE_LOGOS[makeName]
  const initials = makeName.split(' ').map(w => w[0]).join('').slice(0,2).toUpperCase()

  return (
    <button
      onClick={onClick}
      style={{
        display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
        gap: 6, padding: '12px 6px', borderRadius: 14, cursor: 'pointer',
        background: isSelected ? 'rgba(255,107,0,.15)' : 'var(--bg2)',
        border: `2px solid ${isSelected ? 'var(--accent)' : 'var(--border)'}`,
        transition: 'all .15s', minHeight: 80,
      }}
    >
      {/* Logo ili inicijali */}
      <div style={{
        width: 36, height: 36, borderRadius: 8, overflow: 'hidden',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        background: isSelected ? 'rgba(255,107,0,.1)' : 'rgba(255,255,255,.06)',
        flexShrink: 0,
      }}>
        {logoUrl && !logoFailed ? (
          <img
            src={logoUrl}
            alt={makeName}
            style={{ width: 28, height: 28, objectFit: 'contain', filter: 'brightness(0) invert(1)', opacity: isSelected ? 1 : 0.7 }}
            onError={onLogoError}
          />
        ) : (
          <span style={{ fontSize: 13, fontWeight: 700, color: isSelected ? 'var(--accent)' : 'var(--text3)' }}>{initials}</span>
        )}
      </div>
      {/* Naziv */}
      <div style={{
        fontSize: 11, fontWeight: 600, color: isSelected ? 'var(--accent)' : 'var(--text2)',
        textAlign: 'center', lineHeight: 1.2,
        overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
        maxWidth: '100%', paddingLeft: 2, paddingRight: 2,
      }}>{makeName}</div>
      {/* Broj */}
      <div style={{ fontSize: 10, color: 'var(--text3)', opacity: .7 }}>{count}</div>
    </button>
  )
}

export default function SearchPage() {
  const searchParams = useSearchParams()

  const getInitialFilters = () => {
    if (typeof window !== 'undefined') {
      try {
        const saved = sessionStorage.getItem('autoai_filters')
        const fromListing = sessionStorage.getItem('autoai_from_listing')
        if (saved && fromListing === '1') {
          sessionStorage.removeItem('autoai_from_listing')
          return JSON.parse(saved)
        }
      } catch {}
    }
    return {
      ...DEFAULT_FILTERS,
      make:         searchParams.get('make')         || '',
      model:        searchParams.get('model')        || '',
      min_price:    searchParams.get('min_price')    || '',
      max_price:    searchParams.get('max_price')    || '',
      min_year:     searchParams.get('min_year')     || '',
      max_year:     searchParams.get('max_year')     || '',
      max_km:       searchParams.get('max_km')       || '',
      fuel_type:    searchParams.get('fuel_type')    || '',
      country:      searchParams.get('country')      || '',
      countries:    [],
      price_rating: searchParams.get('price_rating') || '',
      sort_by:      searchParams.get('sort_by')      || 'date',
    }
  }

  const [results,        setResults]        = useState<any>(null)
  const [loading,        setLoading]        = useState(true)
  const [aiQuery,        setAiQuery]        = useState(searchParams.get('q') || '')
  const [aiLoading,      setAiLoading]      = useState(false)
  const [sidebarOpen,    setSidebarOpen]    = useState(false)
  const [contactListing, setContactListing] = useState<any>(null)
  const [showSaveModal,  setShowSaveModal]  = useState(false)
  const [showMakeModal,  setShowMakeModal]  = useState(false)
  const [saveName,       setSaveName]       = useState('')
  const [saving,         setSaving]         = useState(false)
  const [saveSuccess,    setSaveSuccess]    = useState(false)
  const [searchHistory,  setSearchHistory]  = useState<string[]>([])
  const [compareList,    setCompareList]    = useState<any[]>([])
  const [makes,          setMakes]          = useState<{make: string; count: number}[]>([])
  const [rawModels,      setRawModels]      = useState<{model: string; count: number}[]>([])
  const [makesLoading,   setMakesLoading]   = useState(false)
  const [modelSearch,    setModelSearch]    = useState('')
  const [filters,        setFilters]        = useState(getInitialFilters)
  // ✅ Praćenje grešaka logoa
  const [logoErrors,     setLogoErrors]     = useState<Record<string, boolean>>({})

  useEffect(() => {
    setMakesLoading(true)
    fetch(`${API_BASE}/search/makes`)
      .then(r => r.json())
      .then(data => {
        const filtered = (data || []).filter((m: any) => m.make && m.make.trim())
        setMakes(groupMakes(filtered))
      })
      .catch(() => {})
      .finally(() => setMakesLoading(false))
  }, [])

  useEffect(() => {
    if (!filters.make) { setRawModels([]); return }
    fetch(`${API_BASE}/search/models?make=${encodeURIComponent(filters.make)}`)
      .then(r => r.json())
      .then(data => setRawModels((data || []).filter((m: any) => m.model && m.model.trim())))
      .catch(() => setRawModels([]))
  }, [filters.make])

  const groupedModels = groupModels(rawModels)
  const filteredModels = groupedModels.filter(m =>
    !modelSearch || m.model.toLowerCase().includes(modelSearch.toLowerCase())
  )

  const doSearch = useCallback(async (f = filters) => {
    setLoading(true)
    try {
      sessionStorage.setItem('autoai_filters', JSON.stringify(f))
      sessionStorage.setItem('autoai_search_url', window.location.href)
    } catch {}
    try   { const fSend = { ...f, countries: (f.countries || []).join(',') }; const data = await searchListings(fSend); setResults(data) }
    catch { setResults(null) }
    finally { setLoading(false) }
  }, [filters])

  useEffect(() => { doSearch() }, [])

  useEffect(() => {
    const h = localStorage.getItem('autoai_search_history')
    if (h) setSearchHistory(JSON.parse(h))
  }, [])

  const setFilter = (key: string, val: any) => {
    const normalized = key === 'make' && val ? canonicalMake(val) : val
    const next: any = { ...filters, [key]: normalized, page: key === 'page' ? val : 1 }
    if (key === 'make') next.model = ''
    setFilters(next)
    doSearch(next)
  }

  const handleModelSelect = (normalizedModel: string, rawVariants: string[]) => {
    const isDeselect = filters.model === normalizedModel
    const next: any = { ...filters, model: isDeselect ? '' : normalizedModel, page: 1 }
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
      setFilters(next); doSearch(next)
      const newHistory = [aiQuery, ...searchHistory.filter(h => h !== aiQuery)].slice(0, 5)
      setSearchHistory(newHistory)
      localStorage.setItem('autoai_search_history', JSON.stringify(newHistory))
    } finally { setAiLoading(false) }
  }

  const handleSaveSearch = async () => {
    const token = localStorage.getItem('autoai_token')
    if (!token) { window.location.href = '/login'; return }
    setSaving(true)
    try {
      const res = await fetch(`${API_BASE}/alerts/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
        body: JSON.stringify({ name: saveName || 'Moja pretraga', filters, frequency: 'daily' }),
      })
      if (res.ok) { setSaveSuccess(true); setShowSaveModal(false); setSaveName('') }
    } catch {}
    finally { setSaving(false) }
  }

  const handleListingClick = () => {
    try {
      sessionStorage.setItem('autoai_from_listing', '1')
      sessionStorage.setItem('autoai_filters', JSON.stringify(filters))
    } catch {}
  }

  const activeCount = [
    filters.make, filters.model, filters.min_price, filters.max_price,
    filters.min_year, filters.max_year, filters.max_km, filters.fuel_type, filters.price_rating,
    ...(filters.countries || []),
  ].filter(Boolean).length

  // ✅ Gradi 4x5 grid: 19 najpopularnijih + "Sve marke"
  // Uzima fiksnih TOP_19 ako postoje u bazi, inače prvih 19 po popularnosti
  const makesCountMap = new Map(makes.map(m => [m.make, m.count]))
  const gridMakes: { make: string; count: number }[] = TOP_19_MAKES
    .filter(m => makesCountMap.has(m))
    .map(m => ({ make: m, count: makesCountMap.get(m)! }))

  // Ako nekih nema u bazi, dopuni iz baze po popularnosti
  const inGrid = new Set(gridMakes.map(m => m.make))
  const fallback = makes
    .sort((a, b) => b.count - a.count)
    .filter(m => !inGrid.has(m.make))
  while (gridMakes.length < 19 && fallback.length > 0) {
    gridMakes.push(fallback.shift()!)
  }

  return (
    <div style={{ minHeight:'100vh', background:'var(--bg)' }}>
      <style dangerouslySetInnerHTML={{__html: `
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
      `}} />

      {contactListing && <ContactModal listing={contactListing} onClose={() => setContactListing(null)} />}

      {/* Save modal */}
      {showSaveModal && (
        <div style={{ position:'fixed', inset:0, background:'rgba(0,0,0,.7)', display:'flex', alignItems:'center', justifyContent:'center', zIndex:1000 }}
          onClick={() => setShowSaveModal(false)}>
          <div style={{ background:'var(--bg2)', border:'1px solid var(--border)', borderRadius:16, padding:28, width:380, maxWidth:'90vw' }}
            onClick={e => e.stopPropagation()}>
            <h3 style={{ margin:'0 0 8px', fontSize:17 }}>🔔 Sačuvaj pretragu</h3>
            <p style={{ fontSize:13, color:'var(--text3)', margin:'0 0 16px' }}>Dobijaš email čim se pojavi novi oglas koji odgovara ovim filterima.</p>
            <input placeholder="Naziv pretrage (npr. BMW 3 do 10k)" value={saveName} onChange={e => setSaveName(e.target.value)}
              style={{ width:'100%', boxSizing:'border-box' as any, background:'var(--bg3)', border:'1px solid var(--border)', borderRadius:8, padding:'10px 14px', color:'var(--text)', fontSize:14, outline:'none', marginBottom:14 }} />
            <button onClick={handleSaveSearch} disabled={saving} style={{ width:'100%', padding:'12px', borderRadius:10, background:'var(--accent)', color:'#fff', border:'none', fontSize:14, fontWeight:700, cursor:'pointer' }}>
              {saving ? 'Čuvam...' : '✅ Sačuvaj i aktiviraj alert'}
            </button>
          </div>
        </div>
      )}

      {/* Make modal — sve marke abecedno */}
      {showMakeModal && (
        <div style={{ position:'fixed', inset:0, background:'rgba(0,0,0,.75)', zIndex:1000, display:'flex', alignItems:'flex-end' }}
          onClick={() => setShowMakeModal(false)}>
          <div style={{ background:'var(--bg2)', borderRadius:'20px 20px 0 0', padding:'20px 16px 40px', width:'100%', border:'1px solid var(--border)', maxHeight:'80vh', overflowY:'auto' }}
            onClick={e => e.stopPropagation()}>
            <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:16 }}>
              <div>
                <h3 style={{ fontSize:16, margin:0 }}>Sve marke</h3>
                <p style={{ fontSize:12, color:'var(--text3)', margin:'4px 0 0' }}>{makes.length} marki — sortirano abecedno</p>
              </div>
              <button onClick={() => setShowMakeModal(false)} style={{ background:'none', border:'none', color:'var(--text3)', fontSize:20, cursor:'pointer' }}>✕</button>
            </div>
            <div style={{ display:'grid', gridTemplateColumns:'repeat(4,1fr)', gap:8 }}>
              {makes.map(({ make: mkName, count: mkCount }) => (
                <MakeTile
                  key={mkName}
                  makeName={mkName}
                  count={mkCount}
                  isSelected={filters.make === mkName}
                  logoFailed={!!logoErrors[mkName]}
                  onLogoError={() => setLogoErrors(prev => ({ ...prev, [mkName]: true }))}
                  onClick={() => {
                    setFilter('make', filters.make === mkName ? '' : mkName)
                    setShowMakeModal(false)
                  }}
                />
              ))}
            </div>
          </div>
        </div>
      )}

      <div className="container" style={{ padding:'16px 16px 80px' }}>

        {/* Hero */}
        <div className="hero" style={{
          background:'linear-gradient(135deg,rgba(255,107,0,.09),rgba(255,107,0,.03))',
          border:'1px solid rgba(255,107,0,.22)', borderRadius:16,
          padding:'18px 22px', marginBottom:18,
          display:'flex', gap:16, alignItems:'center', flexWrap:'wrap',
        }}>
          <div style={{ flex:1, minWidth:180 }}>
            <p style={{ fontSize:21, fontWeight:700, margin:0, fontFamily:'Syne,sans-serif', lineHeight:1.3 }}>
              AI pomoćnik za uvoz automobila iz EU u Srbiju
            </p>
            <p style={{ fontSize:13, color:'var(--text2)', margin:'5px 0 0' }}>
              Analizira cene · Računa realni trošak uvoza · Proverava podobnost uvoza
            </p>
          </div>
          <div style={{ display:'flex', gap:7, flexWrap:'wrap' }}>
            {['🤖 AI analiza','🛡 Zaštita od prevare','🇷🇸 Trošak uvoza','✉️ AI kontakt'].map(t => (
              <span key={t} style={{ padding:'5px 11px', borderRadius:20, fontSize:12, fontWeight:500, background:'rgba(255,107,0,.1)', border:'1px solid rgba(255,107,0,.25)', color:'var(--accent)', whiteSpace:'nowrap' }}>{t}</span>
            ))}
          </div>
        </div>

        {/* AI Search */}
        <form onSubmit={handleAiSearch} style={{ marginBottom:12 }}>
          <div className="ai-form-inner" style={{ display:'flex', background:'var(--bg3)', border:'1px solid var(--border2)', borderRadius:14, padding:6, boxShadow:'0 4px 20px rgba(0,0,0,.2)', gap:6 }}>
            <div style={{ flex:1, display:'flex', alignItems:'center', gap:10, padding:'4px 14px' }}>
              <span style={{ fontSize:17 }}>🤖</span>
              <input value={aiQuery} onChange={e => setAiQuery(e.target.value)}
                placeholder='npr. "Golf dizel do 15000€, max 100000km"'
                style={{ flex:1, background:'none', border:'none', outline:'none', color:'var(--text)', fontSize:15 }} />
            </div>
            <button className="ai-btn" type="submit" disabled={aiLoading} style={{
              background: aiLoading ? 'var(--bg2)' : 'var(--accent)',
              color: aiLoading ? 'var(--text3)' : '#fff',
              border:'none', borderRadius:10, padding:'12px 18px', fontSize:14, fontWeight:700,
              cursor: aiLoading ? 'default' : 'pointer', whiteSpace:'nowrap',
            }}>{aiLoading ? '⏳ Analiziram...' : '🔍 AI Pretraga'}</button>
          </div>
        </form>

        {/* Istorija */}
        {searchHistory.length > 0 && !aiQuery && (
          <div style={{ marginBottom:12 }}>
            <div style={{ fontSize:11, color:'var(--text3)', fontWeight:600, letterSpacing:'.07em', marginBottom:8 }}>NEDAVNE PRETRAGE</div>
            <div style={{ display:'flex', gap:6, flexWrap:'wrap' }}>
              {searchHistory.map((h, i) => (
                <button key={i} onClick={() => { setAiQuery(h); handleAiSearch({ preventDefault: () => {} } as any) }}
                  style={{ padding:'6px 12px', borderRadius:20, fontSize:12, background:'var(--bg2)', border:'1px solid var(--border)', color:'var(--text3)', cursor:'pointer' }}>🕐 {h}</button>
              ))}
              <button onClick={() => { setSearchHistory([]); localStorage.removeItem('autoai_search_history') }}
                style={{ padding:'6px 12px', borderRadius:20, fontSize:12, background:'transparent', border:'none', color:'var(--text3)', cursor:'pointer', opacity:.6 }}>✕ Obriši</button>
            </div>
          </div>
        )}

        {/* Aktivni filteri */}
        {activeCount > 0 && (
          <div style={{ display:'flex', gap:6, flexWrap:'wrap', marginBottom:10, alignItems:'center' }}>
            <span style={{ fontSize:11, color:'var(--text3)' }}>Prikazujem:</span>
            {filters.make && <span style={{ padding:'4px 10px', borderRadius:20, fontSize:12, background:'rgba(255,107,0,.1)', border:'1px solid rgba(255,107,0,.3)', color:'var(--accent)' }}>{filters.make}</span>}
            {filters.model && <span style={{ padding:'4px 10px', borderRadius:20, fontSize:12, background:'rgba(255,107,0,.1)', border:'1px solid rgba(255,107,0,.3)', color:'var(--accent)' }}>{filters.model}</span>}
            {filters.fuel_type && <span style={{ padding:'4px 10px', borderRadius:20, fontSize:12, background:'rgba(255,107,0,.1)', border:'1px solid rgba(255,107,0,.3)', color:'var(--accent)' }}>{FUEL_LABELS[filters.fuel_type] || filters.fuel_type}</span>}
            {filters.min_price && <span style={{ padding:'4px 10px', borderRadius:20, fontSize:12, background:'rgba(255,107,0,.1)', border:'1px solid rgba(255,107,0,.3)', color:'var(--accent)' }}>od {Number(filters.min_price).toLocaleString()} €</span>}
            {filters.max_price && <span style={{ padding:'4px 10px', borderRadius:20, fontSize:12, background:'rgba(255,107,0,.1)', border:'1px solid rgba(255,107,0,.3)', color:'var(--accent)' }}>do {Number(filters.max_price).toLocaleString()} €</span>}
            {filters.min_year && <span style={{ padding:'4px 10px', borderRadius:20, fontSize:12, background:'rgba(255,107,0,.1)', border:'1px solid rgba(255,107,0,.3)', color:'var(--accent)' }}>od {filters.min_year}.</span>}
            {filters.max_year && <span style={{ padding:'4px 10px', borderRadius:20, fontSize:12, background:'rgba(255,107,0,.1)', border:'1px solid rgba(255,107,0,.3)', color:'var(--accent)' }}>do {filters.max_year}.</span>}
            <button onClick={() => { const r = {...DEFAULT_FILTERS}; setFilters(r); doSearch(r) }}
              style={{ padding:'4px 10px', borderRadius:20, fontSize:12, background:'transparent', border:'1px solid var(--border)', color:'var(--text3)', cursor:'pointer' }}>✕ Ukloni sve</button>
          </div>
        )}

        {/* ✅ MAKE GRID — 4x5, amblemi marki */}
        <div style={{ marginBottom:12 }}>
          <div style={{ fontSize:11, color:'var(--text3)', fontWeight:600, letterSpacing:'.07em', marginBottom:10 }}>
            MARKA {makesLoading && <span style={{ opacity:.5 }}>učitavam...</span>}
          </div>

          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(4, 1fr)',
            gap: 8,
          }}>
            {/* 19 najpopularnijih marki */}
            {gridMakes.map(({ make: mkName, count: mkCount }) => (
              <MakeTile
                key={mkName}
                makeName={mkName}
                count={mkCount}
                isSelected={filters.make === mkName}
                logoFailed={!!logoErrors[mkName]}
                onLogoError={() => setLogoErrors(prev => ({ ...prev, [mkName]: true }))}
                onClick={() => setFilter('make', filters.make === mkName ? '' : mkName)}
              />
            ))}

            {/* 20. polje — "Sve marke" */}
            <button
              onClick={() => setShowMakeModal(true)}
              className="make-tile"
              style={{
                display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
                gap: 6, padding: '12px 6px', borderRadius: 14, cursor: 'pointer',
                background: 'var(--bg2)',
                border: '2px dashed var(--border)',
                minHeight: 80,
              }}
            >
              <div style={{
                width: 36, height: 36, borderRadius: 8,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                background: 'rgba(255,107,0,.08)', fontSize: 18,
              }}>
                🔍
              </div>
              <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text3)', textAlign: 'center', lineHeight: 1.2 }}>
                Sve marke
              </div>
              <div style={{ fontSize: 10, color: 'var(--text3)', opacity: .6 }}>
                +{Math.max(0, makes.length - 19)} više
              </div>
            </button>
          </div>

          {/* Modeli */}
          {filters.make && (
            <div style={{ marginTop:10, padding:'12px 14px', background:'var(--bg2)', borderRadius:12, border:'1px solid var(--border)' }}>
              <div style={{ fontSize:11, color:'var(--text3)', fontWeight:600, letterSpacing:'.07em', marginBottom:8 }}>
                MODEL — {filters.make.toUpperCase()}
                {groupedModels.length > 0 && <span style={{ fontWeight:400, opacity:.6, marginLeft:6 }}>({groupedModels.length} modela)</span>}
              </div>
              {rawModels.length > 0 ? (
                <>
                  {groupedModels.length > 10 && (
                    <input placeholder="Traži model..." value={modelSearch} onChange={e => setModelSearch(e.target.value)}
                      style={{ width:'100%', boxSizing:'border-box' as any, background:'var(--bg3)', border:'1px solid var(--border)', borderRadius:8, padding:'7px 12px', color:'var(--text)', fontSize:13, outline:'none', marginBottom:8 }} />
                  )}
                  <div style={{ display:'flex', flexWrap:'wrap', gap:5 }}>
                    <button className="mkbtn cb" onClick={() => setFilter('model', '')} style={{
                      padding:'5px 11px', borderRadius:20, fontSize:13, cursor:'pointer',
                      background: !filters.model ? 'rgba(255,107,0,.15)' : 'transparent',
                      border: `1px solid ${!filters.model ? 'var(--accent)' : 'var(--border)'}`,
                      color: !filters.model ? 'var(--accent)' : 'var(--text)',
                    }}>Svi</button>
                    {filteredModels.slice(0, 40).map(({ model: mdName, count: mdCount, raw }) => (
                      <button key={mdName} className="mkbtn cb"
                        onClick={() => handleModelSelect(mdName, raw)}
                        style={{
                          padding:'5px 11px', borderRadius:20, fontSize:13, cursor:'pointer',
                          background: filters.model === mdName ? 'rgba(255,107,0,.15)' : 'transparent',
                          border: `1px solid ${filters.model === mdName ? 'var(--accent)' : 'var(--border)'}`,
                          color: filters.model === mdName ? 'var(--accent)' : 'var(--text)',
                          display:'flex', gap:4, alignItems:'center',
                        }}>
                        {mdName}
                        <span style={{ fontSize:10, opacity:.6 }}>{mdCount}</span>
                      </button>
                    ))}
                  </div>
                </>
              ) : (
                <p style={{ fontSize:12, color:'var(--text3)', margin:0 }}>Učitavam modele...</p>
              )}
              <button onClick={() => setFilter('make', '')} style={{ marginTop:8, background:'none', border:'none', color:'var(--text2)', fontSize:13, cursor:'pointer' }}>
                ✕ Ukloni {filters.make}
              </button>
            </div>
          )}
        </div>

        {/* Sačuvaj */}
        <div style={{ display:'flex', justifyContent:'flex-end', alignItems:'center', gap:10, marginBottom:12 }}>
          {saveSuccess && <span style={{ fontSize:13, color:'#22C55E', fontWeight:600 }}>✅ Pretraga sačuvana!</span>}
          <button onClick={() => setShowSaveModal(true)} style={{
            padding:'9px 16px', borderRadius:10, fontSize:13, fontWeight:600,
            background:'rgba(99,102,241,.12)', border:'1px solid rgba(99,102,241,.35)',
            color:'#818CF8', cursor:'pointer',
          }}>🔔 Sačuvaj pretragu</button>
        </div>

        {/* Mobile filter toggle */}
        <button className="mfb cb" onClick={() => setSidebarOpen(!sidebarOpen)} style={{
          display:'flex', alignItems:'center', justifyContent:'center', gap:8,
          padding:'11px 16px', borderRadius:10, marginBottom:16, width:'100%',
          background: activeCount > 0 ? 'rgba(255,107,0,.1)' : 'var(--bg2)',
          border: `1px solid ${activeCount > 0 ? 'var(--accent)' : 'var(--border)'}`,
          color: activeCount > 0 ? 'var(--accent)' : 'var(--text2)',
          fontSize:14, fontWeight:600, cursor:'pointer',
        }}>⚙️ Filteri {activeCount > 0 && `(${activeCount})`} {sidebarOpen ? '▲' : '▼'}</button>

        <div className="sg" style={{ display:'grid', gridTemplateColumns:'260px 1fr', gap:24, alignItems:'start' }}>
          <aside className="sd" style={{ background:'var(--bg2)', border:'1px solid var(--border)', borderRadius:16, padding:20, position:'sticky', top:80 }}>
            <Sidebar filters={filters} setFilter={setFilter} onReset={() => { const r={...DEFAULT_FILTERS}; setFilters(r); doSearch(r) }} />
          </aside>

          {sidebarOpen && (
            <div className="sm" style={{ background:'var(--bg2)', border:'1px solid var(--border)', borderRadius:16, padding:20, marginBottom:16, gridColumn:'1/-1' }}>
              <Sidebar filters={filters} setFilter={setFilter} onReset={() => { const r={...DEFAULT_FILTERS}; setFilters(r); doSearch(r) }} />
            </div>
          )}

          <div>
            <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:16, flexWrap:'wrap', gap:8 }}>
              <span style={{ fontSize:15, fontWeight:600 }}>
                {loading ? '...' : `${results?.total?.toLocaleString() || 0} vozila`}
                {!loading && results?.total > 0 && <span style={{ color:'var(--text3)', fontSize:13, marginLeft:8 }}>analiziranih AI-om</span>}
              </span>
              <select value={filters.sort_by} onChange={e => setFilter('sort_by', e.target.value)}
                style={{ background:'var(--bg2)', border:'1px solid var(--border)', borderRadius:8, padding:'8px 12px', color:'var(--text)', fontSize:13, outline:'none', cursor:'pointer' }}>
                <option value="date">Najnoviji</option>
                <option value="best_deal">Najbolja ponuda</option>
                <option value="price_asc">Cena ↑</option>
                <option value="price_desc">Cena ↓</option>
                <option value="year_desc">Najmlađi</option>
              </select>
            </div>

            {(filters.countries?.length > 0) && (
              <div style={{ display:'flex', gap:6, flexWrap:'wrap', marginBottom:12 }}>
                <span style={{ fontSize:12, color:'var(--text3)', alignSelf:'center' }}>📍</span>
                {(filters.countries || []).map((code: string) => {
                  const c = COUNTRIES.find(x => x.code === code)
                  return c ? (
                    <span key={code} style={{ fontSize:12, padding:'3px 9px', borderRadius:20, background:'rgba(255,107,0,.1)', border:'1px solid rgba(255,107,0,.3)', color:'var(--accent)' }}>
                      {c.flag} {c.label}
                      <button onClick={() => setFilter('countries', (filters.countries || []).filter((x: string) => x !== code))}
                        style={{ background:'none', border:'none', color:'var(--accent)', cursor:'pointer', marginLeft:4, fontSize:13 }}>✕</button>
                    </span>
                  ) : null
                })}
              </div>
            )}

            {!loading && results?.pages > 1 && <Pagination pages={results.pages} current={filters.page} onPage={p => { setFilter('page', p); window.scrollTo({top:0,behavior:'smooth'}) }} />}

            {loading ? (
              <div className="rg" style={{ display:'grid', gridTemplateColumns:'repeat(auto-fill,minmax(300px,1fr))', gap:20 }}>
                {[...Array(6)].map((_,i) => <div key={i} className="skeleton" style={{ height:520, borderRadius:16 }} />)}
              </div>
            ) : results?.results?.length ? (
              <>
                <div className="rg" style={{ display:'grid', gridTemplateColumns:'repeat(auto-fill,minmax(300px,1fr))', gap:20 }}>
                  {results.results.map((l: any) => (
                    <ListingCard key={l.id} listing={l}
                      onContact={() => setContactListing(l)}
                      onListingClick={handleListingClick}
                      onCompare={() => setCompareList(prev =>
                        prev.find(c => c.id === l.id) ? prev.filter(c => c.id !== l.id)
                        : prev.length < 3 ? [...prev, l] : prev
                      )}
                      inCompare={!!compareList.find(c => c.id === l.id)}
                    />
                  ))}
                </div>
                {results.pages > 1 && (
                  <div style={{ marginTop:32 }}>
                    <Pagination pages={results.pages} current={filters.page} onPage={p => { setFilter('page', p); window.scrollTo({top:0,behavior:'smooth'}) }} />
                    <div className="pagination-mobile" style={{ display:'none', flexDirection:'column', alignItems:'center', gap:12, marginTop:16 }}>
                      {filters.page < results.pages && (
                        <button onClick={() => setFilter('page', filters.page + 1)} style={{ width:'100%', padding:'14px', borderRadius:12, background:'var(--bg2)', border:'1px solid var(--border)', color:'var(--text2)', fontSize:15, fontWeight:600, cursor:'pointer' }}>⬇️ Učitaj još oglasa</button>
                      )}
                      <span style={{ fontSize:12, color:'var(--text3)' }}>Strana {filters.page} od {results.pages}</span>
                    </div>
                  </div>
                )}
              </>
            ) : (
              <div style={{ textAlign:'center', padding:'80px 20px', background:'var(--bg2)', borderRadius:16, border:'1px solid var(--border)' }}>
                <div style={{ fontSize:52, marginBottom:16 }}>🔍</div>
                <p style={{ fontSize:17, fontWeight:600, marginBottom:8 }}>Nema rezultata</p>
                <p style={{ color:'var(--text3)', fontSize:14 }}>Pokušaj sa različitim filterima ili AI pretragom</p>
              </div>
            )}
          </div>
        </div>
      </div>

      {compareList.length > 0 && (
        <div style={{ position:'fixed', bottom:0, left:0, right:0, zIndex:200, background:'rgba(17,17,20,.97)', borderTop:'1px solid rgba(99,102,241,.4)', backdropFilter:'blur(12px)', padding:'12px 16px' }}>
          <div className="container" style={{ display:'flex', alignItems:'center', gap:12, flexWrap:'wrap' }}>
            <span style={{ fontSize:13, color:'var(--text3)', fontWeight:600 }}>⚖️ Poređenje ({compareList.length}/3):</span>
            <div style={{ display:'flex', gap:8, flex:1, flexWrap:'wrap' }}>
              {compareList.map(c => (
                <div key={c.id} style={{ background:'var(--bg3)', border:'1px solid rgba(99,102,241,.3)', borderRadius:8, padding:'5px 10px', fontSize:12, display:'flex', alignItems:'center', gap:6 }}>
                  <span style={{ color:'var(--text2)' }}>{c.year} {c.make} {c.model}</span>
                  <button onClick={() => setCompareList(prev => prev.filter(x => x.id !== c.id))} style={{ background:'none', border:'none', color:'var(--text3)', cursor:'pointer', fontSize:14 }}>✕</button>
                </div>
              ))}
            </div>
            <div style={{ display:'flex', gap:8 }}>
              <button onClick={() => setCompareList([])} style={{ padding:'8px 14px', borderRadius:8, fontSize:13, background:'transparent', border:'1px solid var(--border)', color:'var(--text3)', cursor:'pointer' }}>Otkaži</button>
              {compareList.length >= 2 && (
                <button onClick={() => { window.location.href = `/compare?ids=${compareList.map(c => c.id).join(',')}` }}
                  style={{ padding:'8px 20px', borderRadius:8, fontSize:13, fontWeight:700, background:'var(--accent)', color:'#fff', border:'none', cursor:'pointer' }}>Uporedi →</button>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function Pagination({ pages, current, onPage }: { pages: number; current: number; onPage: (p: number) => void }) {
  const total = Math.min(pages, 74)
  const pageNums: number[] = []
  if (total <= 7) {
    for (let i = 1; i <= total; i++) pageNums.push(i)
  } else {
    pageNums.push(1)
    if (current > 3) pageNums.push(-1)
    for (let i = Math.max(2, current-1); i <= Math.min(total-1, current+1); i++) pageNums.push(i)
    if (current < total - 2) pageNums.push(-2)
    pageNums.push(total)
  }
  return (
    <div className="pagination-desktop" style={{ display:'flex', justifyContent:'center', gap:6, flexWrap:'wrap', marginBottom:16 }}>
      {current > 1 && <button onClick={() => onPage(current-1)} style={{ width:38, height:38, borderRadius:10, border:'1px solid var(--border)', background:'var(--bg2)', color:'var(--text2)', fontSize:14, cursor:'pointer' }}>‹</button>}
      {pageNums.map((p, i) => p < 0
        ? <span key={p} style={{ width:38, height:38, display:'flex', alignItems:'center', justifyContent:'center', color:'var(--text3)' }}>…</span>
        : <button key={p} onClick={() => onPage(p)} style={{ width:38, height:38, borderRadius:10, border:'1px solid var(--border)', background:current===p?'var(--accent)':'var(--bg2)', color:current===p?'#fff':'var(--text2)', fontSize:13, cursor:'pointer', fontWeight:600 }}>{p}</button>
      )}
      {current < total && <button onClick={() => onPage(current+1)} style={{ width:38, height:38, borderRadius:10, border:'1px solid var(--border)', background:'var(--bg2)', color:'var(--text2)', fontSize:14, cursor:'pointer' }}>›</button>}
    </div>
  )
}

function ListingCard({ listing, onContact, onCompare, inCompare, onListingClick }: {
  listing: any; onContact: () => void; onCompare: () => void; inCompare: boolean; onListingClick: () => void
}) {
  const badge       = AI_BADGES[listing.price_rating]
  const insight     = getInsight(listing)
  const img         = listing.images?.[0]
  const price       = listing.price ? Number(listing.price) : null
  const eligibility = getSerbiaEligibility(listing)
  const bd          = price && eligibility ? calcBreakdown(price, eligibility.carinaPct) : null
  const delta       = listing.price_delta_pct ? Number(listing.price_delta_pct) : null
  const mileage     = formatMileage(listing.mileage)
  const eligColor   = eligibility ? ELIGIBILITY_COLORS[eligibility.status] : null
  const [showBd, setShowBd] = useState(false)

  return (
    <div className="ch" style={{ background:'var(--bg2)', border:'1px solid var(--border)', borderRadius:16, overflow:'hidden' }}>
      {badge ? (
        <div style={{ background:badge.bg, borderBottom:`2px solid ${badge.color}`, padding:'9px 16px', display:'flex', justifyContent:'space-between', alignItems:'center' }}>
          <span style={{ color:badge.color, fontSize:13, fontWeight:800, letterSpacing:'.03em' }}>{badge.label}</span>
          {delta !== null && <span style={{ color: delta < 0 ? '#22C55E' : '#EF4444', fontSize:12, fontWeight:600 }}>{delta > 0 ? '+' : ''}{delta.toFixed(0)}% vs tržišta</span>}
        </div>
      ) : (
        <div style={{ background:'rgba(99,102,241,.07)', borderBottom:'2px solid rgba(99,102,241,.2)', padding:'9px 16px' }}>
          <span style={{ color:'#818CF8', fontSize:12, fontWeight:700 }}>🤖 AI ANALIZA U TOKU</span>
        </div>
      )}

      <a href={`/listing/${listing.id}`} onClick={onListingClick} style={{ display:'block', textDecoration:'none' }}>
        <div style={{ height:200, background:'var(--bg3)', position:'relative', overflow:'hidden' }}>
          {img
            ? <img src={fullImg(img)} alt={`${listing.make} ${listing.model}`} style={{ width:'100%', height:'100%', objectFit:'cover' }} onError={e => { (e.target as HTMLImageElement).src = img }} />
            : <div style={{ display:'flex', alignItems:'center', justifyContent:'center', height:'100%', fontSize:48, opacity:.35 }}>🚗</div>
          }
          <span style={{ position:'absolute', bottom:10, left:10, background:'rgba(0,0,0,.75)', borderRadius:6, padding:'3px 8px', fontSize:11, color:'rgba(255,255,255,.65)', backdropFilter:'blur(4px)' }}>{listing.source}</span>
        </div>
        <div style={{ padding:'14px 18px 0' }}>
          <h3 style={{ fontSize:15, fontWeight:600, margin:'0 0 4px', fontFamily:'Syne,sans-serif', lineHeight:1.3, color:'var(--text)' }}>
            {listing.year && `${listing.year} `}{listing.make} {listing.model}
          </h3>
          {insight && (
            <p style={{ fontSize:12, color:badge?.color||'#818CF8', margin:'0 0 10px', display:'flex', alignItems:'center', gap:5 }}>
              <span style={{ width:5, height:5, borderRadius:'50%', background:badge?.color||'#818CF8', display:'inline-block', flexShrink:0 }} />{insight}
            </p>
          )}
        </div>
      </a>

      <div style={{ padding:'0 18px 18px' }}>
        {eligibility && eligColor && (
          <div style={{ background:`${eligColor}11`, border:`1px solid ${eligColor}44`, borderRadius:10, padding:'9px 12px', marginBottom:10 }}>
            <div style={{ fontSize:10, color:'var(--text3)', marginBottom:2, letterSpacing:'.06em', fontWeight:600 }}>UVOZ U SRBIJU</div>
            <div style={{ fontSize:12, fontWeight:700, color:eligColor }}>{eligibility.emoji} {eligibility.label}</div>
            {eligibility.tooltip && <div style={{ fontSize:10, color:'var(--text3)', marginTop:2, lineHeight:1.4 }}>{eligibility.tooltip}</div>}
          </div>
        )}
        <div style={{ display:'flex', alignItems:'center', gap:8, marginBottom:10 }}>
          <span style={{ fontSize:12, color:'var(--text3)' }}>EU cena:</span>
          <span style={{ fontSize:18, fontWeight:700, color:'var(--text2)' }}>{price ? `${price.toLocaleString('de-DE')} €` : 'Na upit'}</span>
        </div>
        {bd && (
          <div style={{ background:'rgba(255,107,0,.07)', border:'1px solid rgba(255,107,0,.2)', borderRadius:10, overflow:'hidden', marginBottom:12 }}>
            <button onClick={() => setShowBd(!showBd)} className="cb" style={{ width:'100%', background:'none', border:'none', cursor:'pointer', padding:'10px 14px', display:'flex', justifyContent:'space-between', alignItems:'center' }}>
              <div style={{ textAlign:'left' }}>
                <div style={{ fontSize:11, color:'var(--text3)', marginBottom:2 }}>🇷🇸 Ukupno za Srbiju</div>
                <div style={{ fontSize:19, fontWeight:800, color:'var(--accent)' }}>{bd.total.toLocaleString('de-DE')} €</div>
              </div>
              <span style={{ fontSize:11, color:'rgba(255,107,0,.6)' }}>{showBd ? '▲ sakrij' : '▼ detalji'}</span>
            </button>
            {showBd && (
              <div style={{ padding:'0 14px 12px', borderTop:'1px solid rgba(255,107,0,.15)' }}>
                {[
                  { label:'EU cena', val:price!, note:'' },
                  { label:`Carina (${bd.carinaPct}%)`, val:bd.carina, note: bd.carinaPct===0?'oslobođeno':'srbija' },
                  { label:'PDV (20%)', val:bd.pdv, note:'srbija' },
                  { label:'Transport EU→RS', val:bd.transport, note:'procena' },
                  { label:'Registracija', val:bd.reg, note:'procena' },
                ].map(({ label, val, note }, i) => (
                  <div key={i} style={{ display:'flex', justifyContent:'space-between', padding:'4px 0', borderTop: i===0?'none':'1px solid rgba(255,255,255,.04)', marginTop: i===0?8:0 }}>
                    <span style={{ fontSize:12, color: i===0?'var(--text2)':'var(--text3)' }}>{i>0&&'+ '}{label}{note&&<span style={{ fontSize:10, marginLeft:4, opacity:.5 }}>({note})</span>}</span>
                    <span style={{ fontSize:12, fontWeight:500, color: i===0?'var(--text2)':'#fb923c' }}>{i===0?'':'+'}{val.toLocaleString('de-DE')} €</span>
                  </div>
                ))}
                <div style={{ display:'flex', justifyContent:'space-between', marginTop:8, paddingTop:8, borderTop:'1px solid rgba(255,107,0,.25)' }}>
                  <span style={{ fontSize:13, fontWeight:700 }}>Ukupno za Srbiju</span>
                  <span style={{ fontSize:15, fontWeight:800, color:'var(--accent)' }}>{bd.total.toLocaleString('de-DE')} €</span>
                </div>
              </div>
            )}
          </div>
        )}
        <div style={{ display:'flex', gap:10, flexWrap:'wrap', fontSize:12, color:'var(--text3)', paddingBottom:10, borderBottom:'1px solid var(--border)' }}>
          {mileage && <span>🛣 {mileage}</span>}
          {listing.fuel_type && <span>⛽ {FUEL_LABELS[listing.fuel_type] || listing.fuel_type}</span>}
          {listing.country && <span>📍 {listing.country}</span>}
        </div>
        <p style={{ fontSize:10, color:'var(--text3)', margin:'8px 0 10px', lineHeight:1.5, opacity:.7 }}>
          * Procena je informativna. Pre kupovine obavezno proveriti dokumentaciju i važeće propise.
        </p>
        <button onClick={onCompare} style={{
          width:'100%', padding:'9px', marginBottom:8,
          background: inCompare ? 'rgba(99,102,241,.15)' : 'transparent',
          border: `1px solid ${inCompare ? 'rgba(99,102,241,.5)' : 'var(--border)'}`,
          color: inCompare ? '#818CF8' : 'var(--text3)',
          borderRadius:10, fontSize:13, cursor:'pointer', fontWeight:500,
        }}>{inCompare ? '✓ Dodato za poređenje' : '⚖️ Uporedi'}</button>
        <button onClick={onContact} className="cb" style={{ width:'100%', padding:'11px', background:'rgba(99,102,241,.1)', border:'1px solid rgba(99,102,241,.3)', color:'#818CF8', borderRadius:10, fontSize:13, fontWeight:600, cursor:'pointer' }}>
          🤖 Kontaktiraj prodavca
        </button>
      </div>
    </div>
  )
}

function Sidebar({ filters, setFilter, onReset }: any) {
  return (
    <>
      <h3 style={{ fontSize:11, marginBottom:20, color:'var(--text3)', letterSpacing:'.1em', fontWeight:600 }}>FILTERI</h3>
      <FS label="Cena (EUR)">
        <div style={{ display:'flex', gap:6 }}>
          <input type="number" placeholder="Od" value={filters.min_price} onChange={e => setFilter('min_price', e.target.value)} style={IS} />
          <input type="number" placeholder="Do" value={filters.max_price} onChange={e => setFilter('max_price', e.target.value)} style={IS} />
        </div>
      </FS>
      <FS label="Godište">
        <div style={{ display:'flex', gap:6 }}>
          <input type="number" placeholder="Od" value={filters.min_year} onChange={e => setFilter('min_year', e.target.value)} style={IS} />
          <input type="number" placeholder="Do" value={filters.max_year} onChange={e => setFilter('max_year', e.target.value)} style={IS} />
        </div>
      </FS>
      <FS label="Max km">
        <input type="number" placeholder="npr. 150000" value={filters.max_km} onChange={e => setFilter('max_km', e.target.value)} style={{ ...IS, width:'100%', boxSizing:'border-box' as any }} />
      </FS>
      <FS label="Gorivo">
        <div style={{ display:'flex', flexWrap:'wrap', gap:4 }}>
          {[['diesel','Dizel'],['petrol','Benzin'],['electric','Električni'],['hybrid','Hibrid'],['lpg','Plin']].map(([v,l]) => (
            <FC key={v} label={l} active={filters.fuel_type===v} onClick={() => setFilter('fuel_type', filters.fuel_type===v?'':v)} />
          ))}
        </div>
      </FS>
      <FS label="AI Ocena">
        <div style={{ display:'flex', flexDirection:'column', gap:4 }}>
          {Object.entries(AI_BADGES).map(([v,{label,color}]) => (
            <FC key={v} label={label} active={filters.price_rating===v} onClick={() => setFilter('price_rating', filters.price_rating===v?'':v)} color={color} full />
          ))}
        </div>
      </FS>
      <FS label="Lokacija vozila">
        <div style={{ display:'flex', flexWrap:'wrap', gap:4 }}>
          {COUNTRIES.map(({ code, flag, label }) => {
            const active = (filters.countries || []).includes(code)
            return (
              <button key={code} className="cb" onClick={() => {
                const cur = filters.countries || []
                setFilter('countries', active ? cur.filter((c: string) => c !== code) : [...cur, code])
              }} style={{
                padding:'4px 9px', borderRadius:20, fontSize:12, cursor:'pointer', transition:'all .15s',
                background: active ? 'rgba(255,107,0,.15)' : 'transparent',
                border: `1px solid ${active ? 'var(--accent)' : 'var(--border)'}`,
                color: active ? 'var(--accent)' : 'var(--text3)',
              }}>{flag} {label}</button>
            )
          })}
        </div>
      </FS>
      <button className="cb" onClick={onReset} style={{ width:'100%', padding:11, borderRadius:10, marginTop:4, background:'transparent', border:'1px solid var(--border)', color:'var(--text3)', fontSize:13, cursor:'pointer', fontWeight:500 }}>
        Resetuj filtere
      </button>
    </>
  )
}

function FS({ label, children }: any) {
  return (
    <div style={{ marginBottom:22 }}>
      <div style={{ fontSize:11, color:'var(--text3)', letterSpacing:'.08em', marginBottom:8, fontWeight:600 }}>{label.toUpperCase()}</div>
      {children}
    </div>
  )
}

function FC({ label, active, onClick, color, full }: any) {
  return (
    <button className="cb" onClick={onClick} style={{
      display: full?'block':'inline-block', width: full?'100%':'auto',
      textAlign: full?'left':'center', padding: full?'7px 12px':'5px 11px',
      borderRadius: full?8:20, fontSize:12, fontWeight: active?600:400,
      background: active ? (color ? color+'20' : 'rgba(255,107,0,.15)') : 'transparent',
      border: `1px solid ${active ? (color||'var(--accent)') : 'var(--border)'}`,
      color: active ? (color||'var(--accent)') : 'var(--text3)',
      cursor:'pointer', transition:'all .15s',
    }}>{label}</button>
  )
}

const IS: React.CSSProperties = {
  flex:1, background:'var(--bg3)', border:'1px solid var(--border)',
  borderRadius:8, padding:'9px 11px', color:'var(--text)',
  fontSize:13, outline:'none', minWidth:0,
}
