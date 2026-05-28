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
  model: string
  year?: number
  fuelType?: string
  transmission?: string
}

// Lokalna baza tipičnih problema po tipu vozila
function getBaseChecks(fuelType?: string, transmission?: string, year?: number): CheckItem[] {
  const checks: CheckItem[] = []
  const age = year ? 2026 - year : null

  // Opšte za svaki auto
  checks.push({ category: 'Dokumentacija', item: 'COC dokument (Certificate of Conformity)', severity: 'critical', tip: 'Bez COC-a uvoz u Srbiju može biti problem.' })
  checks.push({ category: 'Dokumentacija', item: 'Servisna knjiga', severity: 'critical', tip: 'Redovan servis je ključan za procenu stanja.' })
  checks.push({ category: 'Dokumentacija', item: 'Broj vlasnika', severity: 'important', tip: 'Više vlasnika = potencijalno više problema.' })

  // Diesel specifično
  if (fuelType === 'diesel') {
    checks.push({ category: 'Motor', item: 'DPF (filter čestica)', severity: 'critical', tip: 'Zamena DPF filtera košta 800–2000€. Proveri da nije uklonjen.' })
    checks.push({ category: 'Motor', item: 'EGR ventil', severity: 'important', tip: 'Česti kvarovi na dizel motorima. Pranje ili zamena.' })
    checks.push({ category: 'Motor', item: 'Turbina — stanje i curenje', severity: 'important', tip: 'Preslušaj motor na hladno. Zujanje = problem.' })
    if (year && year >= 2015) {
      checks.push({ category: 'Motor', item: 'AdBlue / SCR sistem', severity: 'critical', tip: 'Euro 6 dizel ima AdBlue. Proveri nivo i stanje pumpe.' })
    }
    checks.push({ category: 'Motor', item: 'Lanac ili zupčasti kaiš', severity: 'critical', tip: 'Pitaj o zameni. Pucanje = totalni kvar motora.' })
  }

  // Benzin specifično
  if (fuelType === 'petrol') {
    checks.push({ category: 'Motor', item: 'Svećice i šine gorivo injektora', severity: 'normal', tip: 'Redovan servis svake 30–60k km.' })
    checks.push({ category: 'Motor', item: 'Lanac ili zupčasti kaiš', severity: 'critical', tip: 'Obavezno pitaj o zameni.' })
  }

  // Električni
  if (fuelType === 'electric') {
    checks.push({ category: 'Baterija', item: 'State of Health (SoH) baterije', severity: 'critical', tip: 'Zatraži izveštaj o zdravlju baterije. Ispod 80% = problem.' })
    checks.push({ category: 'Baterija', item: 'Broj ciklusa punjenja', severity: 'important', tip: 'Više ciklusa = brže degradiranje kapaciteta.' })
    checks.push({ category: 'Punjač', item: 'Tip punjača (Tip 2 / CCS / CHAdeMO)', severity: 'critical', tip: 'Srbija koristi Tip 2 za AC i CCS za DC punjenje.' })
    checks.push({ category: 'Garancija', item: 'Garancija na bateriju', severity: 'important', tip: 'Većina proizvođača daje 8 god / 160.000 km.' })
  }

  // Hibrid
  if (fuelType === 'hybrid') {
    checks.push({ category: 'Baterija', item: 'Stanje hibridne baterije', severity: 'critical', tip: 'Zamena hibridne baterije košta 3000–8000€.' })
    checks.push({ category: 'Sistem', item: 'EV mod — funkcioniše?', severity: 'important', tip: 'Testiraj električni mod tokom probe vožnje.' })
  }

  // DSG / automatik
  if (transmission === 'automatic') {
    checks.push({ category: 'Menjač', item: 'DSG / automatik servis', severity: 'critical', tip: 'DSG servis svakih 60k km. Pitaj kada je urađen.' })
    checks.push({ category: 'Menjač', item: 'Tresenje pri menjanju brzina', severity: 'important', tip: 'Karakteristično za zapušen mechatronik ili staro ulje.' })
  }

  // Starost vozila
  if (age && age > 8) {
    checks.push({ category: 'Vešanje', item: 'Amortizeri i zglobovi', severity: 'important', tip: 'Vozila starija od 8 god. često imaju dotrajalо vešanje.' })
    checks.push({ category: 'Korozija', item: 'Korozija na šasiji i pragu', severity: 'important', tip: 'Pregledaj ispod vozila, posebno pragove.' })
  }

  // Opšte provere
  checks.push({ category: 'Karoserija', item: 'Tragovi udara ili lakiranja', severity: 'important', tip: 'Koristi paint meter za merenje debljine laka.' })
  checks.push({ category: 'Test vožnja', item: 'Probe vožnja min. 20 minuta', severity: 'critical', tip: 'Uključi autoput, zaustavljanja, parkiranje.' })
  checks.push({ category: 'Uvoz', item: 'Provera da vozilo nije ukradeno', severity: 'critical', tip: 'Proveri VIN u Interpol / EUCARIS bazi pre kupovine.' })

  return checks
}

const SEVERITY_COLORS = { critical: '#EF4444', important: '#F97316', normal: '#EAB308' }
const SEVERITY_LABELS = { critical: '🔴 Kritično', important: '🟠 Važno', normal: '🟡 Preporučeno' }

export default function ModelChecklist({ make, model, year, fuelType, transmission }: Props) {
  const [expanded, setExpanded] = useState(false)
  const [aiChecks, setAiChecks] = useState<CheckItem[]>([])
  const [loading, setLoading] = useState(false)
  const [generated, setGenerated] = useState(false)

  const baseChecks = getBaseChecks(fuelType, transmission, year)

  // Grupiši po kategoriji
  const allChecks = [...aiChecks, ...baseChecks]
  const grouped = allChecks.reduce((acc, item) => {
    if (!acc[item.category]) acc[item.category] = []
    acc[item.category].push(item)
    return acc
  }, {} as Record<string, CheckItem[]>)

  const criticalCount  = allChecks.filter(c => c.severity === 'critical').length
  const importantCount = allChecks.filter(c => c.severity === 'important').length

  const generateAiChecks = async () => {
    if (generated || loading) return
    setLoading(true)
    try {
      const response = await fetch('https://api.anthropic.com/v1/messages', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          model: 'claude-sonnet-4-20250514',
          max_tokens: 1000,
          messages: [{
            role: 'user',
            content: `Ti si ekspert za automobile. Generiši listu od 4-6 specifičnih tehničkih problema karakterističnih za ${make} ${model}${year ? ` (${year})` : ''}.
Fokusiraj se na poznate slabosti ovog modela.
Odgovori SAMO u JSON formatu, bez preamble, tačno ovako:
[{"category":"Motor","item":"naziv problema","severity":"critical","tip":"kratak savet"}]
severity može biti: critical, important, normal
Sve na srpskom jeziku (ekavica). Kratko i konkretno.`
          }]
        })
      })
      const data = await response.json()
      const text = data.content?.[0]?.text || ''
      const clean = text.replace(/```json|```/g, '').trim()
      const parsed = JSON.parse(clean)
      if (Array.isArray(parsed)) {
        setAiChecks(parsed)
        setGenerated(true)
      }
    } catch (e) {
      // Fallback — tiha greška, base checks ostaju
    }
    setLoading(false)
  }

  return (
    <div>
      {/* Header sa summary */}
      <div style={{ display:'flex', justifyContent:'space-between', alignItems:'flex-start', marginBottom:14 }}>
        <div>
          <h2 style={{ fontSize:15, margin:'0 0 3px' }}>🔧 Šta proveriti kod ovog vozila?</h2>
          <p style={{ fontSize:12, color:'var(--text3)', margin:0 }}>
            AI lista specifičnih provera za {make} {model}
          </p>
        </div>
        <div style={{ display:'flex', gap:6, flexShrink:0 }}>
          <span style={{ fontSize:11, padding:'3px 9px', borderRadius:20, background:'rgba(239,68,68,.1)', border:'1px solid rgba(239,68,68,.2)', color:'#EF4444', fontWeight:700 }}>{criticalCount} kritično</span>
          <span style={{ fontSize:11, padding:'3px 9px', borderRadius:20, background:'rgba(249,115,22,.1)', border:'1px solid rgba(249,115,22,.2)', color:'#F97316', fontWeight:700 }}>{importantCount} važno</span>
        </div>
      </div>

      {/* AI generisanje dugme */}
      {!generated && (
        <button onClick={generateAiChecks} disabled={loading} style={{
          width:'100%', padding:'10px', borderRadius:9, border:'1px dashed rgba(99,102,241,.4)',
          background:'rgba(99,102,241,.06)', color:'#818CF8',
          fontSize:13, fontWeight:600, cursor:loading?'default':'pointer', marginBottom:14,
          transition:'all .15s',
        }}>
          {loading
            ? <span style={{ display:'flex', alignItems:'center', justifyContent:'center', gap:7 }}>
                <span style={{ width:7, height:7, borderRadius:'50%', background:'#818CF8', display:'inline-block', animation:'pulse 1s infinite' }} />
                AI analizira model...
              </span>
            : `🤖 Dodaj AI provere za ${make} ${model}`
          }
        </button>
      )}
      {generated && (
        <div style={{ fontSize:12, color:'#22C55E', marginBottom:12, display:'flex', alignItems:'center', gap:5 }}>
          <span style={{ width:6, height:6, borderRadius:'50%', background:'#22C55E', display:'inline-block' }} />
          AI dodao specifične provere za {make} {model}
        </div>
      )}

      {/* Lista provera */}
      <div style={{ display:'flex', flexDirection:'column', gap:6 }}>
        {Object.entries(grouped).slice(0, expanded ? undefined : 4).map(([category, items]) => (
          <div key={category} style={{ background:'var(--bg3)', borderRadius:10, overflow:'hidden' }}>
            <div style={{ padding:'8px 12px', borderBottom:'1px solid rgba(255,255,255,.04)', fontSize:11, color:'var(--text3)', fontWeight:600, letterSpacing:'.06em' }}>
              {category.toUpperCase()}
            </div>
            {items.map((item, i) => (
              <div key={i} style={{ padding:'9px 12px', borderTop: i===0?'none':'1px solid rgba(255,255,255,.04)', display:'flex', gap:10, alignItems:'flex-start' }}>
                <span style={{ fontSize:11, padding:'2px 7px', borderRadius:20, flexShrink:0, marginTop:1,
                  background: item.severity==='critical'?'rgba(239,68,68,.1)':item.severity==='important'?'rgba(249,115,22,.1)':'rgba(234,179,8,.1)',
                  color: SEVERITY_COLORS[item.severity], border:`1px solid ${SEVERITY_COLORS[item.severity]}33`,
                  fontWeight:700,
                }}>
                  {item.severity==='critical'?'🔴':item.severity==='important'?'🟠':'🟡'}
                </span>
                <div style={{ flex:1 }}>
                  <div style={{ fontSize:13, fontWeight:600, color:'var(--text)', marginBottom:2 }}>{item.item}</div>
                  <div style={{ fontSize:11, color:'var(--text3)', lineHeight:1.5 }}>{item.tip}</div>
                </div>
              </div>
            ))}
          </div>
        ))}
      </div>

      {Object.keys(grouped).length > 4 && (
        <button onClick={() => setExpanded(v => !v)} style={{
          width:'100%', marginTop:8, padding:'8px', background:'transparent',
          border:'1px solid var(--border)', color:'var(--text3)',
          borderRadius:8, fontSize:12, cursor:'pointer',
        }}>
          {expanded ? '▲ Sakrij' : `▼ Prikaži sve (${allChecks.length} provera)`}
        </button>
      )}

      {/* Legenda */}
      <div style={{ display:'flex', gap:10, marginTop:12, flexWrap:'wrap' }}>
        {Object.entries(SEVERITY_LABELS).map(([sev, label]) => (
          <span key={sev} style={{ fontSize:11, color:'var(--text3)' }}>{label}</span>
        ))}
      </div>
    </div>
  )
}
