'use client'
import { useState } from 'react'

interface CheckItem {
  category: string
  item: string
  severity: 'critical' | 'important' | 'normal'
  tip: string
}

interface Props {
  make: string
  model?: string
  year?: number
  fuelType?: string
  transmission?: string
  onRequestVin?: () => void
}

// ✅ Model-specifična baza problema
const MODEL_KNOWN_ISSUES: Record<string, CheckItem[]> = {
  'bmw': [
    { category: 'Motor', item: 'Lanac razvoda — tipičan problem N47/N57', severity: 'critical', tip: 'BMW N47 dizel i N57 imaju poznate probleme sa lancem. Proveri da li je menjan.' },
    { category: 'Motor', item: 'Curenje ulja — bregasta osovina i poklopac', severity: 'important', tip: 'Čest problem na starijim BMW motorima. Provjeri vizuelno ispod haube.' },
    { category: 'Elektronika', item: 'iDrive sistem i ekran', severity: 'normal', tip: 'Stariji iDrive sistemi mogu imati kvarove. Testiraj sve funkcije.' },
    { category: 'Vešanje', item: 'Točkovi i vešanje — skupo za popravku', severity: 'important', tip: 'BMW vešanje je skupo. Provjeri amortizere, šrafove i ležajeve.' },
  ],
  'volkswagen': [
    { category: 'Menjač', item: 'DSG 7-stepeni (DQ200) — suvo kvačilo', severity: 'critical', tip: 'DQ200 (7-step DSG) poznat po problemima. Uvek pitaj za servisnu istoriju DSG-a.' },
    { category: 'Motor', item: 'Timing chain — TSI motori', severity: 'critical', tip: 'VW TSI 1.2 i 1.4 motori imaju probleme sa lancem. Provjeri zamjenu.' },
    { category: 'Motor', item: 'DPF filter — TDI motori', severity: 'important', tip: 'Provjeri da DPF nije uklonjen (ilegalno za uvoz). Regeneracija mora raditi.' },
    { category: 'Elektronika', item: 'MIL lampica — OBD dijagnostika', severity: 'important', tip: 'Uvek uradi OBD sken pre kupovine. Skrivene greške su česte.' },
  ],
  'vw': [
    { category: 'Menjač', item: 'DSG 7-stepeni (DQ200) — suvo kvačilo', severity: 'critical', tip: 'DQ200 (7-step DSG) poznat po problemima. Uvek pitaj za servisnu istoriju DSG-a.' },
    { category: 'Motor', item: 'Timing chain — TSI motori', severity: 'critical', tip: 'VW TSI 1.2 i 1.4 motori imaju probleme sa lancem. Provjeri zamjenu.' },
  ],
  'audi': [
    { category: 'Menjač', item: 'DSG/S-tronic servis', severity: 'critical', tip: 'S-tronic servis svakih 60k km. Provjeri kada je urađen i tip kvačila.' },
    { category: 'Motor', item: 'Curenje ulja — karakteristično za Audi', severity: 'important', tip: 'Mnogi Audi motori cure ulje sa bregaste osovine. Provjeri vizuelno.' },
    { category: 'Quattro', item: 'Haldex/Torsen — stanje pogona', severity: 'normal', tip: 'Quattro sistem zahteva redovnu zamjenu ulja. Pitaj za istoriju.' },
  ],
  'mercedes': [
    { category: 'Motor', item: 'Lanac razvoda — M271/M272/M273', severity: 'critical', tip: 'Mercedes benzinski motori imaju probleme sa lancem razvoda. Obavezno provjeri.' },
    { category: 'Vešanje', item: 'Airmatic / ABC vešanje', severity: 'critical', tip: 'Vazdušno vešanje može biti veoma skupo za popravku (2000-5000€).' },
    { category: 'Elektronika', item: 'COMAND sistem i navigacija', severity: 'normal', tip: 'Stariji COMAND sistemi su spori i imaju kvarove. Testiraj sve.' },
  ],
  'mercedes-benz': [
    { category: 'Motor', item: 'Lanac razvoda — M271/M272/M273', severity: 'critical', tip: 'Mercedes benzinski motori imaju probleme sa lancem razvoda. Obavezno provjeri.' },
    { category: 'Vešanje', item: 'Airmatic / ABC vešanje', severity: 'critical', tip: 'Vazdušno vešanje može biti veoma skupo za popravku (2000-5000€).' },
  ],
  'toyota': [
    { category: 'Hibrid', item: 'Hibridna baterija — stanje i garancija', severity: 'critical', tip: 'Toyota hibridne baterije su pouzdane ali skupo zamenljive. Provjeri SoH.' },
    { category: 'Hibrid', item: 'Inverter hlađenje — provjeri curenje', severity: 'important', tip: 'Stariji Toyota Prius ima probleme sa curjenjem rashladne tečnosti invertera.' },
    { category: 'Hibrid', item: 'eCVT — nema tradicionalnog kvačila', severity: 'normal', tip: 'eCVT je veoma pouzdan ali testiraj vožnju po punoj brzini.' },
  ],
  'tesla': [
    { category: 'Baterija', item: 'State of Health (SoH) — obavezno', severity: 'critical', tip: 'Zatraži Tesla diagnostiku baterije. Ispod 85% SoH = degradacija.' },
    { category: 'Punjač', item: 'CCS kompatibilnost za Srbiju', severity: 'critical', tip: 'Stariji Tesla Model S/X imaju Type 2 CCS adapter — provjeri kompatibilnost.' },
    { category: 'Karoserija', item: 'Panel gaps i farbanje', severity: 'important', tip: 'Tesla je poznata po nejednakim razmacima panela. Pažljivo provjeri.' },
    { category: 'Elektronika', item: 'MCU (Media Control Unit) — generacija', severity: 'important', tip: 'MCU1 (pre 2018) je sporiji i ne prima Autopilot update-ove.' },
  ],
  'peugeot': [
    { category: 'Elektronika', item: 'BSI modul — čest kvar', severity: 'critical', tip: 'BSI modul je Peugeot-ov poznat problem. Zamjena košta 300-800€.' },
    { category: 'Motor', item: 'EGR ventil — 1.6 HDi motori', severity: 'important', tip: 'Peugeot 1.6 HDi EGR je čest kvar. Provjeri stanje ili zamjenu.' },
  ],
  'renault': [
    { category: 'Menjač', item: 'EDC dvostruko kvačilo — problemi', severity: 'critical', tip: 'Renault EDC (posebno Energy TCe) je problematičan. Testiraj pažljivo.' },
    { category: 'Motor', item: 'Energy TCe 115/130 — pouzdanost', severity: 'important', tip: 'Raniji Energy TCe motori imaju probleme sa potrošnjom ulja.' },
  ],
  'ford': [
    { category: 'Menjač', item: 'PowerShift — automatski menjač', severity: 'critical', tip: 'Ford PowerShift je jedan od najproblematičnijih automenjača. Izbegavati.' },
    { category: 'Motor', item: 'EcoBoost 1.0 — pouzdanost', severity: 'important', tip: '1.0 EcoBoost može imati probleme sa hladnjakom i termično naprezanje.' },
  ],
  'opel': [
    { category: 'Automatik', item: 'Easytronic/AutoSA menjač', severity: 'critical', tip: 'Opel Easytronic je veoma nepouzdan. Provjeri istoriju servisa.' },
    { category: 'Motor', item: 'Corsa 1.3 CDTI — lanac razvoda', severity: 'important', tip: 'Poznat problem na manjim Opel dizel motorima.' },
  ],
  'skoda': [
    { category: 'Menjač', item: 'DSG 7-stepeni (DQ200) — servis', severity: 'critical', tip: 'Skoda koristi isti VW DQ200 DSG koji je problematičan. Provjeri servis.' },
    { category: 'Motor', item: 'Timing chain TSI — stanje', severity: 'important', tip: 'Skoda 1.2 i 1.4 TSI dijeli VW probleme sa lancem razvoda.' },
  ],
  'volvo': [
    { category: 'Motor', item: 'T5/T6 turbo — pouzdanost', severity: 'important', tip: 'Volvo turbo motori generalno pouzdani ali provjeri hladnjak i intercooler.' },
    { category: 'Elektronika', item: 'Sensus sistem — ažuriranja', severity: 'normal', tip: 'Stariji Sensus može biti spor. Provjeri da li prima update-ove.' },
  ],
  'hyundai': [
    { category: 'Motor', item: 'GDI motori — čađ na usisnoj', severity: 'important', tip: 'Hyundai GDI motori skupljaju čađ na usisnoj grani. Skupo čišćenje.' },
  ],
  'kia': [
    { category: 'Motor', item: 'GDI motori — čađ na usisnoj', severity: 'important', tip: 'Kia GDI motori isti problem kao Hyundai. Provjeri stanje usisne.' },
  ],
}

// Generičke provere po tipu goriva/menjača
function getGenericChecks(fuelType?: string, transmission?: string, year?: number): CheckItem[] {
  const checks: CheckItem[] = []
  const age = year ? 2026 - year : null

  // Dokumentacija — uvek
  checks.push({ category: 'Dokumentacija', item: 'COC dokument za uvoz u Srbiju', severity: 'critical', tip: 'Bez COC-a uvoz može biti problematičan. Obavezno zatraži od prodavca.' })
  checks.push({ category: 'Dokumentacija', item: 'Servisna knjiga / servisna istorija', severity: 'critical', tip: 'Redovan servis je ključan pokazatelj brige o vozilu.' })

  if (fuelType === 'diesel') {
    checks.push({ category: 'Motor', item: 'DPF filter — stanje i da nije uklonjen', severity: 'critical', tip: 'Bez DPF-a nije legalno uvesti vozilo. Zamjena košta 500-2000€.' })
    if (year && year >= 2015) {
      checks.push({ category: 'Motor', item: 'AdBlue / SCR sistem', severity: 'critical', tip: 'Euro 6 dizel mora imati funkcionalan AdBlue. Provjeri nivo i pumpu.' })
    }
    checks.push({ category: 'Motor', item: 'EGR ventil — stanje', severity: 'important', tip: 'Zapušen EGR je čest na dizel motorima. Skupo za popravku.' })
    checks.push({ category: 'Motor', item: 'Turbina — nema zujanja ni gubitka snage', severity: 'important', tip: 'Preslušaj motor na hladno i vruće. Zujanje = problemi.' })
  }

  if (fuelType === 'electric') {
    checks.push({ category: 'Baterija', item: 'SoH baterije — min 80%', severity: 'critical', tip: 'Zatraži dijagnostiku baterije. Ispod 80% = skupa zamjena.' })
    checks.push({ category: 'Punjač', item: 'Tip punjača — CCS / Tip 2 kompatibilnost sa Srbijom', severity: 'critical', tip: 'Srbija koristi Tip 2 (AC) i CCS (DC). Provjeri pre kupovine.' })
    checks.push({ category: 'Garancija', item: 'Ostatak garancije na bateriju', severity: 'important', tip: 'Većina marki daje 8 god / 160.000 km garanciju na bateriju.' })
  }

  if (fuelType === 'hybrid') {
    checks.push({ category: 'Baterija', item: 'Hibridna baterija — stanje', severity: 'critical', tip: 'Zamjena hibridne baterije košta 2000-8000€. Obavezno provjeri.' })
    checks.push({ category: 'Sistem', item: 'EV mod — funkcioniše li?', severity: 'important', tip: 'Testiraj električni mod zasebno tokom probe vožnje.' })
  }

  if (transmission === 'automatic') {
    checks.push({ category: 'Menjač', item: 'Servis automatskog menjača / DSG', severity: 'critical', tip: 'Pitaj kada je menjan ulje i filter. Svakih 60k km je standard.' })
    checks.push({ category: 'Menjač', item: 'Nema trzanja pri promjeni brzina', severity: 'important', tip: 'Trzanje = zapušen mechatronik ili staro ulje. Testiraj na putu.' })
  }

  if (age && age > 7) {
    checks.push({ category: 'Mehanika', item: 'Amortizeri i vešanje — dotrajalost', severity: 'important', tip: 'Vozila starija od 7 god. često imaju dotrajalo vešanje. Provjeri vizuelno.' })
    checks.push({ category: 'Karoserija', item: 'Korozija na pragu i šasiji', severity: 'important', tip: 'Pregledaj ispod vozila sa baterijskom lampom, posebno pragove.' })
  }

  checks.push({ category: 'Opšte', item: 'Probe vožnja min. 20 minuta', severity: 'critical', tip: 'Uključi autoput, naglo kočenje i parkiranje. Preslušaj sve zvuke.' })
  checks.push({ category: 'Opšte', item: 'OBD dijagnostika pre kupovine', severity: 'important', tip: 'OBD sken otkriva skrivene greške. Košta 20-50€ u servisu.' })

  return checks
}

const SEVERITY_COLORS = {
  critical: '#EF4444',
  important: '#F97316',
  normal: '#EAB308',
}

export default function ModelChecklist({ make, model, year, fuelType, transmission, onRequestVin }: Props) {
  const [expanded,  setExpanded]  = useState(false)
  const [aiChecks,  setAiChecks]  = useState<CheckItem[]>([])
  const [loading,   setLoading]   = useState(false)
  const [generated, setGenerated] = useState(false)

  const makeKey = (make || '').toLowerCase()
  const modelSpecific = MODEL_KNOWN_ISSUES[makeKey] || []
  const generic = getGenericChecks(fuelType, transmission, year)

  // Spoji i deduplikuj po kategoriji
  const allChecks = [...modelSpecific, ...aiChecks, ...generic]

  // Grupiši po severityju — kritični prvi
  const critical  = allChecks.filter(c => c.severity === 'critical')
  const important = allChecks.filter(c => c.severity === 'important')
  const normal    = allChecks.filter(c => c.severity === 'normal')

  const sorted = [...critical, ...important, ...normal]
  const visible = expanded ? sorted : sorted.slice(0, 4)

  const generateAiChecks = async () => {
    if (generated || loading || !make) return
    setLoading(true)
    try {
      const response = await fetch('https://api.anthropic.com/v1/messages', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          model: 'claude-sonnet-4-20250514',
          max_tokens: 800,
          messages: [{
            role: 'user',
            content: `Ekspert si za automobile. Nabroji 4 SPECIFIČNA tehnička problema za ${make}${model ? ' ' + model : ''}${year ? ' (' + year + ')' : ''} koja su dokumentovana na forumima i servisima.
Fokusiraj se na STVARNE poznate slabosti ovog konkretnog modela.
Odgovori SAMO JSON, bez ikakvih dodatnih reči:
[{"category":"Motor","item":"naziv problema","severity":"critical","tip":"konkretan savet"}]
severity: critical, important ili normal. Srpski jezik, ekavica.`
          }]
        })
      })
      const data = await response.json()
      const text  = data.content?.[0]?.text || ''
      const clean = text.replace(/```json|```/g, '').trim()
      const parsed = JSON.parse(clean)
      if (Array.isArray(parsed) && parsed.length > 0) {
        setAiChecks(parsed)
        setGenerated(true)
      }
    } catch {
      // Tiha greška — base checks ostaju
    }
    setLoading(false)
  }

  const hasModelSpecific = modelSpecific.length > 0

  return (
    <div>
      {/* Header */}
      <div style={{ display:'flex', justifyContent:'space-between', alignItems:'flex-start', marginBottom:12 }}>
        <div>
          <h2 style={{ fontSize:15, margin:'0 0 2px' }}>🔧 Šta proveriti kod ovog vozila?</h2>
          <p style={{ fontSize:12, color:'var(--text3)', margin:0 }}>
            {hasModelSpecific ? `Poznati problemi za ${make}` : 'Opšte preporuke za pregled vozila'}
          </p>
        </div>
        <div style={{ display:'flex', gap:5, flexShrink:0 }}>
          {critical.length > 0 && (
            <span style={{ fontSize:11, padding:'2px 8px', borderRadius:20, background:'rgba(239,68,68,.1)', border:'1px solid rgba(239,68,68,.2)', color:'#EF4444', fontWeight:700 }}>
              🔴 {critical.length}
            </span>
          )}
          {important.length > 0 && (
            <span style={{ fontSize:11, padding:'2px 8px', borderRadius:20, background:'rgba(249,115,22,.1)', border:'1px solid rgba(249,115,22,.2)', color:'#F97316', fontWeight:700 }}>
              🟠 {important.length}
            </span>
          )}
        </div>
      </div>

      {/* Model-specific badge */}
      {hasModelSpecific && (
        <div style={{ fontSize:12, color:'#818CF8', background:'rgba(99,102,241,.08)', border:'1px solid rgba(99,102,241,.15)', borderRadius:8, padding:'6px 10px', marginBottom:10 }}>
          ✓ AutoAI ima poznate probleme za {make} u bazi
        </div>
      )}

      {/* Lista provera */}
      <div style={{ display:'flex', flexDirection:'column', gap:6 }}>
        {visible.map((item, i) => (
          <div key={i} style={{
            background: 'var(--bg3)', borderRadius:10, padding:'10px 12px',
            borderLeft: `3px solid ${SEVERITY_COLORS[item.severity]}55`,
            display:'flex', gap:10, alignItems:'flex-start',
          }}>
            <span style={{ fontSize:14, flexShrink:0, marginTop:1 }}>
              {item.severity === 'critical' ? '🔴' : item.severity === 'important' ? '🟠' : '🟡'}
            </span>
            <div style={{ flex:1 }}>
              <div style={{ fontSize:13, fontWeight:600, color:'var(--text)', marginBottom:3 }}>
                {item.item}
                <span style={{ fontSize:10, color:'var(--text3)', fontWeight:400, marginLeft:6 }}>{item.category}</span>
              </div>
              <div style={{ fontSize:11, color:'var(--text3)', lineHeight:1.5 }}>{item.tip}</div>
            </div>
          </div>
        ))}
      </div>

      {/* Prikaži sve / AI generiši */}
      <div style={{ display:'flex', gap:8, marginTop:10 }}>
        {sorted.length > 4 && (
          <button onClick={() => setExpanded(v => !v)} style={{
            flex:1, padding:'8px', background:'transparent',
            border:'1px solid var(--border)', color:'var(--text3)',
            borderRadius:8, fontSize:12, cursor:'pointer',
          }}>
            {expanded ? '▲ Sakrij' : `▼ Prikaži sve (${sorted.length})`}
          </button>
        )}
        {!generated && make && (
          <button onClick={generateAiChecks} disabled={loading} style={{
            flex:1, padding:'8px', background:'rgba(99,102,241,.06)',
            border:'1px dashed rgba(99,102,241,.3)', color:'#818CF8',
            borderRadius:8, fontSize:12, fontWeight:600, cursor:loading?'default':'pointer',
          }}>
            {loading
              ? <span style={{ display:'flex', alignItems:'center', justifyContent:'center', gap:5 }}>
                  <span style={{ width:6, height:6, borderRadius:'50%', background:'#818CF8', display:'inline-block', animation:'pulse 1s infinite' }} />
                  AI analizira...
                </span>
              : `🤖 AI provere za ${make}`
            }
          </button>
        )}
      </div>

      {/* Legenda */}
      <div style={{ display:'flex', gap:12, marginTop:10 }}>
        {[['🔴', 'Kritično'], ['🟠', 'Važno'], ['🟡', 'Preporučeno']].map(([icon, label]) => (
          <span key={label} style={{ fontSize:11, color:'var(--text3)' }}>{icon} {label}</span>
        ))}
      </div>
    </div>
  )
}
