'use client'
import { useState, useEffect } from 'react'

const FUEL_LABELS: Record<string, string> = {
  diesel: 'Dizel', petrol: 'Benzin', gasoline: 'Benzin',
  electric: 'Električni', hybrid: 'Hibrid', lpg: 'Plin',
}

function calcImport(price: number, year: number | null, fuel: string | null) {
  const carinaPct = fuel === 'electric' ? 0 : 5
  const carina    = Math.round(price * carinaPct / 100)
  const pdv       = Math.round((price + carina) * 0.20)
  return { total: price + carina + pdv + 420 + 280, carinaPct }
}

function fullImg(url: string): string {
  if (!url) return url
  return url.replace(/\/\d+x\d+\.(webp|jpg|jpeg|png)/i, '/800x600.$1')
}

export default function ComparePage() {
  const [listings, setListings] = useState<any[]>([])
  const [loading,  setLoading]  = useState(true)
  const [aiAnalysis, setAiAnalysis] = useState('')
  const [aiLoading,  setAiLoading]  = useState(false)

  const apiBase = process.env.NEXT_PUBLIC_API_URL || 'https://autoai-platform-production.up.railway.app/api/v1'

  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const ids    = params.get('ids')?.split(',') || []
    if (ids.length < 2) { window.location.href = '/search'; return }

    Promise.all(ids.map(id =>
      fetch(`${apiBase}/listings/${id}`).then(r => r.json())
    )).then(data => {
      setListings(data.filter(Boolean))
      setLoading(false)
    }).catch(() => setLoading(false))
  }, [])

  const generateAiAnalysis = async () => {
    setAiLoading(true)
    try {
      const apiBase2 = process.env.NEXT_PUBLIC_API_URL || 'https://autoai-platform-production.up.railway.app/api/v1'
      const res = await fetch(`${apiBase2}/ai/parse-query`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: `Uporedi ova vozila za uvoz u Srbiju i preporuči koje je bolje kupiti: ${
            listings.map(l => `${l.year} ${l.make} ${l.model} za ${l.price}€, ${l.mileage}km, ${l.fuel_type}`).join(' | ')
          }. Daj kratak savet koji je bolji izbor i zašto.`
        })
      })
      const data = await res.json()
      setAiAnalysis(data.advice || data.message || 'AI analiza nije dostupna.')
    } catch {
      setAiAnalysis('Greška pri AI analizi.')
    }
    setAiLoading(false)
  }

  if (loading) return (
    <div style={{ padding:'60px 0', textAlign:'center', color:'var(--text3)' }}>
      Učitavam oglase...
    </div>
  )

  const rows = [
    { label: 'Godište',      key: (l: any) => l.year || '—' },
    { label: 'Kilometraža',  key: (l: any) => l.mileage ? `${Number(l.mileage).toLocaleString('de-DE')} km` : '—' },
    { label: 'Gorivo',       key: (l: any) => FUEL_LABELS[l.fuel_type] || l.fuel_type || '—' },
    { label: 'Snaga',        key: (l: any) => l.engine_power_kw ? `${l.engine_power_kw} kW` : '—' },
    { label: 'Menjač',       key: (l: any) => l.transmission === 'automatic' ? 'Automatik' : l.transmission === 'manual' ? 'Manuel' : l.transmission || '—' },
    { label: 'Zemlja',       key: (l: any) => l.country || '—' },
    { label: 'EU cena',      key: (l: any) => l.price ? `${Number(l.price).toLocaleString('de-DE')} €` : '—', highlight: true },
    { label: 'Ukupno RS',    key: (l: any) => l.price ? `${calcImport(Number(l.price), l.year, l.fuel_type).total.toLocaleString('de-DE')} €` : '—', highlight: true },
   { label: 'AI ocena', key: (l: any) => l.price_rating ? ({ great:'🟢 Dobra', good:'🟡 Fer', fair:'⚪ Prosek', high:'🟠 Visoka', overpriced:'🔴 Previsoka' } as Record<string,string>)[l.price_rating] || '—' : '—' },
  ]

  return (
    <div style={{ minHeight:'100vh', padding:'32px 0 80px' }}>
      <div className="container">

        <div style={{ marginBottom:24 }}>
          <a href="/search" style={{ fontSize:13, color:'var(--text3)', textDecoration:'none' }}>← Nazad na pretragu</a>
          <h1 style={{ fontSize:26, fontFamily:'Syne,sans-serif', margin:'12px 0 4px' }}>⚖️ Poređenje automobila</h1>
          <p style={{ color:'var(--text3)', fontSize:14 }}>{listings.length} vozila</p>
        </div>

        {/* Slike i naslovi */}
        <div style={{ display:'grid', gridTemplateColumns:`repeat(${listings.length}, 1fr)`, gap:16, marginBottom:24 }}>
          {listings.map(l => (
            <div key={l.id} style={{ background:'var(--bg2)', border:'1px solid var(--border)', borderRadius:14, overflow:'hidden' }}>
              <div style={{ height:160, background:'var(--bg3)', overflow:'hidden' }}>
                {l.images?.[0]
                  ? <img src={fullImg(l.images[0])} alt="" style={{ width:'100%', height:'100%', objectFit:'cover' }}
                      onError={e => { (e.target as HTMLImageElement).src = l.images[0] }} />
                  : <div style={{ height:'100%', display:'flex', alignItems:'center', justifyContent:'center', fontSize:36 }}>🚗</div>
                }
              </div>
              <div style={{ padding:'12px 14px' }}>
                <div style={{ fontSize:14, fontWeight:700, marginBottom:4 }}>{l.year} {l.make} {l.model}</div>
                <a href={`/listing/${l.id}`} style={{ fontSize:12, color:'var(--accent)', textDecoration:'none' }}>Pogledaj oglas →</a>
              </div>
            </div>
          ))}
        </div>

        {/* Tabela poređenja */}
        <div style={{ background:'var(--bg2)', border:'1px solid var(--border)', borderRadius:14, overflow:'hidden', marginBottom:24 }}>
          {rows.map((row, ri) => (
            <div key={ri} style={{
              display:'grid', gridTemplateColumns:`180px repeat(${listings.length}, 1fr)`,
              borderBottom: ri < rows.length - 1 ? '1px solid var(--border)' : 'none',
              background: row.highlight ? 'rgba(255,107,0,.04)' : 'transparent',
            }}>
              <div style={{ padding:'12px 16px', fontSize:12, color:'var(--text3)', fontWeight:600, letterSpacing:'.06em', borderRight:'1px solid var(--border)' }}>
                {row.label.toUpperCase()}
              </div>
              {listings.map(l => (
                <div key={l.id} style={{
                  padding:'12px 16px', fontSize:14,
                  fontWeight: row.highlight ? 700 : 400,
                  color: row.highlight ? 'var(--accent)' : 'var(--text)',
                  borderRight:'1px solid var(--border)',
                }}>
                  {row.key(l)}
                </div>
              ))}
            </div>
          ))}
        </div>

        {/* AI analiza */}
        <div style={{ background:'rgba(99,102,241,.06)', border:'1px solid rgba(99,102,241,.25)', borderRadius:14, padding:24 }}>
          <h2 style={{ fontSize:16, marginBottom:12 }}>🤖 AI Preporuka za uvoz u Srbiju</h2>
          {aiAnalysis ? (
            <p style={{ fontSize:14, color:'var(--text2)', lineHeight:1.8, whiteSpace:'pre-wrap' }}>{aiAnalysis}</p>
          ) : (
            <button onClick={generateAiAnalysis} disabled={aiLoading} style={{
              padding:'12px 24px', borderRadius:10, fontSize:14, fontWeight:700,
              background: aiLoading ? 'var(--bg3)' : 'var(--accent)',
              color: aiLoading ? 'var(--text3)' : '#fff',
              border:'none', cursor: aiLoading ? 'default' : 'pointer',
            }}>
              {aiLoading ? '⏳ AI analizira...' : '🤖 Generiši AI preporuku'}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
