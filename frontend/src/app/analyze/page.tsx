'use client'
import { useState } from 'react'

const FUEL_LABELS: Record<string, string> = {
  diesel: 'Dizel', petrol: 'Benzin', electric: 'Električni', hybrid: 'Hibrid', lpg: 'Plin',
}
const ELIGIBILITY_COLORS: Record<string, string> = {
  eligible: '#22C55E', needs_check: '#F97316', not_recommended: '#EF4444', oldtimer: '#A855F7',
}
const QUICK_QUESTIONS = [
  'Da li je auto imao udes?', 'Da li postoji servisna istorija?',
  'Koja je poslednja cena?', 'Da li je moguć izvoz?',
  'Da li je auto još dostupan?', 'Koliko ima vlasnika?',
]

function fmt(n: number) { return n.toLocaleString('de-DE') }
function fmtKm(km: any): string | null {
  const n = Number(km)
  if (!n || n < 1 || n > 999999) return null
  return n.toLocaleString('de-DE') + ' km'
}

export default function AnalyzePage() {
  const [url,      setUrl]      = useState('')
  const [loading,  setLoading]  = useState(false)
  const [result,   setResult]   = useState<any>(null)
  const [error,    setError]    = useState('')
  const [selected, setSelected] = useState<string[]>([])
  const [custom,   setCustom]   = useState('')
  const [msgLoad,  setMsgLoad]  = useState(false)
  const [message,  setMessage]  = useState('')
  const [msgError, setMsgError] = useState('')
  const [copied,   setCopied]   = useState(false)

  async function analyze() {
    if (!url.trim()) return
    setLoading(true); setResult(null); setError('')
    setMessage(''); setSelected([]); setCustom('')
    const apiBase = process.env.NEXT_PUBLIC_API_URL || 'https://autoai-platform-production.up.railway.app/api/v1'
    try {
      const res  = await fetch(`${apiBase}/analyze/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: url.trim() }),
      })
      const data = await res.json()
      if (!res.ok) setError(data.detail || 'Greška pri analizi.')
      else setResult(data)
    } catch {
      setError('Nije moguće conectovati se sa serverom. Pokušaj ponovo.')
    }
    setLoading(false)
  }

  async function generateMessage() {
    if (!result || (!selected.length && !custom.trim())) return
    setMsgLoad(true); setMessage(''); setMsgError('')
    try {
      const res = await fetch('/api/contact-message', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          country:     result.country || 'DE',
          make:        result.title?.split(' ')[0] || '',
          model:       result.title?.split(' ').slice(1, 3).join(' ') || '',
          year:        result.year,
          price:       result.price,
          questions:   selected,
          custom_text: custom,
        }),
      })
      const data = await res.json()
      setMessage(data.message || '')
    } catch {
      setMsgError('Greška pri generisanju poruke.')
    }
    setMsgLoad(false)
  }

  function copyMsg() {
    navigator.clipboard.writeText(message)
    setCopied(true); setTimeout(() => setCopied(false), 2200)
  }

  function openGmail() {
    const sub  = encodeURIComponent(`Inquiry: ${result?.year || ''} ${result?.title || ''}`)
    const body = encodeURIComponent(message)
    window.open(`https://mail.google.com/mail/?view=cm&su=${sub}&body=${body}`, '_blank')
  }

  const bd        = result?.import_cost
  const elig      = result?.serbia_eligibility
  const eligColor = elig ? (ELIGIBILITY_COLORS[elig.eligible_status] || '#F97316') : '#F97316'
  const portalName = result?.source === 'autoscout24' ? 'AutoScout24' : 'Mobile.de'

  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg)', paddingBottom: 80 }}>
      <div className="container" style={{ maxWidth: 720, padding: '32px 16px 0' }}>

        <div style={{ marginBottom: 32, textAlign: 'center' }}>
          <div style={{ fontSize: 40, marginBottom: 12 }}>🔍</div>
          <h1 style={{ fontSize: 26, fontWeight: 800, fontFamily: 'Syne,sans-serif', margin: '0 0 10px', lineHeight: 1.2 }}>
            Proveri oglas pre kupovine
          </h1>
          <p style={{ fontSize: 15, color: 'var(--text2)', margin: 0, lineHeight: 1.6 }}>
            Ubaci link sa AutoScout24 ili Mobile.de i saznaj da li se auto isplati za uvoz u Srbiju.
          </p>
        </div>

        <div style={{ background: 'var(--bg2)', border: '1px solid var(--border)', borderRadius: 16, padding: 20, marginBottom: 24 }}>
          <div style={{ fontSize: 11, color: 'var(--text3)', letterSpacing: '.08em', fontWeight: 600, marginBottom: 8 }}>LINK OGLASA</div>
          <input
            value={url} onChange={e => setUrl(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && analyze()}
            placeholder="Zalepi link oglasa ovde…"
            style={{ width: '100%', background: 'var(--bg3)', border: '1px solid var(--border)', borderRadius: 10, padding: '13px 16px', color: 'var(--text)', fontSize: 14, outline: 'none', boxSizing: 'border-box', fontFamily: 'inherit', marginBottom: 6 }}
          />
          <p style={{ fontSize: 11, color: 'var(--text3)', margin: '0 0 14px' }}>Podržani portali: autoscout24.com · mobile.de</p>
          <button onClick={analyze} disabled={loading || !url.trim()} style={{
            width: '100%', padding: '14px', borderRadius: 12, border: 'none',
            background: (!url.trim() || loading) ? 'var(--bg3)' : 'var(--accent)',
            color: (!url.trim() || loading) ? 'var(--text3)' : '#fff',
            fontSize: 15, fontWeight: 700, cursor: (!url.trim() || loading) ? 'default' : 'pointer',
          }}>
            {loading ? '⏳ Analiziram oglas…' : '🔍 Analiziraj oglas'}
          </button>
        </div>

        {error && (
          <div style={{ background: 'rgba(239,68,68,.1)', border: '1px solid rgba(239,68,68,.3)', borderRadius: 12, padding: 16, marginBottom: 20, color: '#EF4444', fontSize: 14 }}>
            ⚠️ {error}
          </div>
        )}

        {result && !result.scrape_success && (
          <div style={{ background: 'rgba(249,115,22,.08)', border: '1px solid rgba(249,115,22,.25)', borderRadius: 12, padding: 20, textAlign: 'center' }}>
            <div style={{ fontSize: 32, marginBottom: 10 }}>😕</div>
            <p style={{ fontWeight: 600, marginBottom: 6 }}>Nismo uspeli da pročitamo oglas</p>
            <p style={{ fontSize: 13, color: 'var(--text3)', margin: 0, lineHeight: 1.6 }}>{result.error_message}</p>
          </div>
        )}

        {result && result.scrape_success && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

            <div style={{ background: 'var(--bg2)', border: '1px solid var(--border)', borderRadius: 16, overflow: 'hidden' }}>
              {result.images?.[0] && (
                <div style={{ height: 220, overflow: 'hidden', position: 'relative' }}>
                  <img src={result.images[0]} alt={result.title} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                  <span style={{ position: 'absolute', bottom: 10, left: 10, background: 'rgba(0,0,0,.7)', borderRadius: 6, padding: '3px 10px', fontSize: 11, color: 'rgba(255,255,255,.7)' }}>{result.source}</span>
                </div>
              )}
              <div style={{ padding: '16px 18px' }}>
                <h2 style={{ fontSize: 17, fontWeight: 700, margin: '0 0 8px', fontFamily: 'Syne,sans-serif', lineHeight: 1.3 }}>
                  {result.title || `${result.year || ''} vozilo`}
                </h2>
                <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', fontSize: 13, color: 'var(--text3)' }}>
                  {result.year            && <span>📅 {result.year}</span>}
                  {fmtKm(result.mileage)  && <span>🛣 {fmtKm(result.mileage)}</span>}
                  {result.fuel_type       && <span>⛽ {FUEL_LABELS[result.fuel_type] || result.fuel_type}</span>}
                  {result.engine_power_kw && <span>⚡ {result.engine_power_kw} kW</span>}
                  {result.country         && <span>📍 {result.city ? `${result.city}, ` : ''}{result.country}</span>}
                </div>
              </div>
            </div>

            <div style={{ background: 'var(--bg2)', border: '1px solid var(--border)', borderRadius: 16, padding: '16px 18px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontSize: 14, color: 'var(--text3)', fontWeight: 600 }}>EU cena</span>
              <span style={{ fontSize: 24, fontWeight: 800 }}>{result.price ? `${fmt(result.price)} €` : 'Na upit'}</span>
            </div>

            {elig && (
              <div style={{ background: `${eligColor}11`, border: `1px solid ${eligColor}33`, borderRadius: 16, padding: '16px 18px' }}>
                <div style={{ fontSize: 11, color: 'var(--text3)', letterSpacing: '.07em', fontWeight: 600, marginBottom: 8 }}>UVOZ U SRBIJU</div>
                <div style={{ fontSize: 16, fontWeight: 800, color: eligColor, marginBottom: 8 }}>{elig.emoji} {elig.label}</div>
                <p style={{ fontSize: 13, color: 'var(--text2)', margin: '0 0 10px', lineHeight: 1.6 }}>{elig.reason}</p>
                {elig.warnings?.length > 0 && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
                    {elig.warnings.map((w: string, i: number) => (
                      <div key={i} style={{ fontSize: 12, color: 'var(--text3)', lineHeight: 1.5, paddingLeft: 12, borderLeft: `2px solid ${eligColor}55` }}>{w}</div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {bd && (
              <div style={{ background: 'rgba(255,107,0,.07)', border: '1px solid rgba(255,107,0,.2)', borderRadius: 16, padding: '16px 18px' }}>
                <div style={{ fontSize: 11, color: 'var(--text3)', letterSpacing: '.07em', fontWeight: 600, marginBottom: 8 }}>🇷🇸 TROŠAK UVOZA U SRBIJU</div>
                <div style={{ fontSize: 26, fontWeight: 800, color: 'var(--accent)', marginBottom: 16 }}>{fmt(bd.total)} €</div>
                {[
                  { label: 'EU cena', val: bd.eu_price, note: '' },
                  { label: `Carina (${bd.carina_pct}%)`, val: bd.carina, note: bd.carina_pct === 0 ? 'oslobođeno' : 'srbija' },
                  { label: 'PDV (20%)', val: bd.pdv, note: 'srbija' },
                  { label: 'Transport EU→RS', val: bd.transport, note: 'procena' },
                  { label: 'Registracija', val: bd.registration, note: 'procena' },
                ].map(({ label, val, note }, i) => (
                  <div key={i} style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 0', borderTop: i === 0 ? 'none' : '1px solid rgba(255,255,255,.05)' }}>
                    <span style={{ fontSize: 13, color: i === 0 ? 'var(--text2)' : 'var(--text3)' }}>
                      {i > 0 && '+ '}{label}{note && <span style={{ fontSize: 10, marginLeft: 6, opacity: .5 }}>({note})</span>}
                    </span>
                    <span style={{ fontSize: 13, fontWeight: 600, color: i === 0 ? 'var(--text2)' : '#fb923c' }}>
                      {i === 0 ? '' : '+'}{fmt(val)} €
                    </span>
                  </div>
                ))}
                <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 12, paddingTop: 12, borderTop: '1px solid rgba(255,107,0,.25)' }}>
                  <span style={{ fontSize: 14, fontWeight: 700 }}>Ukupno za Srbiju</span>
                  <span style={{ fontSize: 16, fontWeight: 800, color: 'var(--accent)' }}>{fmt(bd.total)} €</span>
                </div>
              </div>
            )}

            {result.risk_warnings?.length > 0 && (
              <div style={{ background: 'rgba(239,68,68,.06)', border: '1px solid rgba(239,68,68,.2)', borderRadius: 16, padding: '16px 18px' }}>
                <div style={{ fontSize: 11, color: '#EF4444', letterSpacing: '.07em', fontWeight: 600, marginBottom: 10 }}>⚠️ RIZICI I UPOZORENJA</div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 7 }}>
                  {result.risk_warnings.map((w: string, i: number) => (
                    <div key={i} style={{ fontSize: 13, color: 'var(--text2)', lineHeight: 1.5, paddingLeft: 12, borderLeft: '2px solid rgba(239,68,68,.4)' }}>{w}</div>
                  ))}
                </div>
              </div>
            )}

            {result.features?.length > 0 && (
              <div style={{ background: 'var(--bg2)', border: '1px solid var(--border)', borderRadius: 16, padding: '16px 18px' }}>
                <div style={{ fontSize: 11, color: 'var(--text3)', letterSpacing: '.07em', fontWeight: 600, marginBottom: 12 }}>OPREMA ({result.features.length} stavki)</div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                  {result.features.slice(0, 20).map((f: string, i: number) => (
                    <span key={i} style={{ fontSize: 11, padding: '4px 10px', borderRadius: 20, background: 'var(--bg3)', border: '1px solid var(--border)', color: 'var(--text3)' }}>{f}</span>
                  ))}
                  {result.features.length > 20 && <span style={{ fontSize: 11, color: 'var(--text3)', padding: '4px 10px' }}>+{result.features.length - 20} više</span>}
                </div>
              </div>
            )}

            {/* Kontakt prodavca */}
            <div style={{ background: 'var(--bg2)', border: '1px solid var(--border)', borderRadius: 16, padding: '18px 18px' }}>
              <div style={{ fontSize: 11, color: 'var(--text3)', letterSpacing: '.07em', fontWeight: 600, marginBottom: 4 }}>🤖 KONTAKTIRAJ PRODAVCA</div>
              <p style={{ fontSize: 13, color: 'var(--text3)', margin: '0 0 14px', lineHeight: 1.5 }}>
                AI generiše poruku na jeziku prodavca ({result.seller_language || 'Deutsch'}).
              </p>

              <div style={{ fontSize: 11, color: 'var(--text3)', fontWeight: 600, letterSpacing: '.06em', marginBottom: 8 }}>BRZA PITANJA</div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 14 }}>
                {QUICK_QUESTIONS.map(q => (
                  <button key={q} onClick={() => setSelected(s => s.includes(q) ? s.filter(x => x !== q) : [...s, q])} style={{
                    padding: '6px 12px', borderRadius: 20, fontSize: 12,
                    background: selected.includes(q) ? 'rgba(255,107,0,.14)' : 'var(--bg3)',
                    border: `1px solid ${selected.includes(q) ? 'var(--accent)' : 'var(--border)'}`,
                    color: selected.includes(q) ? 'var(--accent)' : 'var(--text2)',
                    cursor: 'pointer',
                  }}>{q}</button>
                ))}
              </div>

              <div style={{ fontSize: 11, color: 'var(--text3)', fontWeight: 600, letterSpacing: '.06em', marginBottom: 6 }}>DODAJ VLASTITO PITANJE</div>
              <textarea
                value={custom} onChange={e => setCustom(e.target.value)}
                placeholder='npr. "Pitaj da li je moguć uvoz u Srbiju..."'
                rows={2}
                style={{ width: '100%', background: 'var(--bg3)', border: '1px solid var(--border)', borderRadius: 10, padding: '10px 14px', color: 'var(--text)', fontSize: 13, outline: 'none', resize: 'none', boxSizing: 'border-box', fontFamily: 'inherit', marginBottom: 12 }}
              />

              <button onClick={generateMessage} disabled={msgLoad || (!selected.length && !custom.trim())} style={{
                width: '100%', padding: '12px', borderRadius: 10, border: 'none',
                background: (!selected.length && !custom.trim()) || msgLoad ? 'var(--bg3)' : 'rgba(99,102,241,.2)',
                color: (!selected.length && !custom.trim()) || msgLoad ? 'var(--text3)' : '#818CF8',
                fontSize: 14, fontWeight: 700, cursor: 'pointer', marginBottom: 10,
              }}>
                {msgLoad ? '⏳ Generišem…' : '🤖 Generiši poruku'}
              </button>

              {msgError && <p style={{ color: '#EF4444', fontSize: 13, margin: '0 0 10px' }}>{msgError}</p>}

              {message && (
                <div>
                  <div style={{ background: 'var(--bg3)', border: '1px solid var(--border)', borderRadius: 10, padding: 14, fontSize: 13, lineHeight: 1.75, color: 'var(--text2)', whiteSpace: 'pre-wrap', marginBottom: 10 }}>
                    {message}
                  </div>
                  <div style={{ display: 'flex', gap: 8, marginBottom: 10 }}>
                    <button onClick={copyMsg} style={{
                      flex: 1, padding: '10px', borderRadius: 10,
                      background: copied ? 'rgba(34,197,94,.12)' : 'var(--bg3)',
                      border: `1px solid ${copied ? '#22C55E' : 'var(--border)'}`,
                      color: copied ? '#22C55E' : 'var(--text2)',
                      fontSize: 13, fontWeight: 600, cursor: 'pointer',
                    }}>{copied ? '✓ Kopirano!' : '📋 Kopiraj'}</button>
                    <button onClick={openGmail} style={{
                      flex: 1, padding: '10px', borderRadius: 10,
                      background: 'rgba(234,67,53,.1)', border: '1px solid rgba(234,67,53,.3)',
                      color: '#EA4335', fontSize: 13, fontWeight: 600, cursor: 'pointer',
                    }}>📧 Gmail</button>
                  </div>
                  <p style={{ fontSize: 11, color: 'var(--text3)', margin: '0 0 10px', textAlign: 'center' }}>
                    Poruka je generisana AI-om — preporučujemo da je pregledate pre slanja.
                  </p>
                </div>
              )}

              {/* Dugmad za kontakt na portalu */}
              <a href={result.url} target="_blank" rel="noopener noreferrer" style={{
                display: 'block', width: '100%', padding: '12px',
                background: 'rgba(99,102,241,.15)', border: '1px solid rgba(99,102,241,.4)',
                color: '#818CF8', borderRadius: 10, textAlign: 'center',
                fontSize: 13, fontWeight: 700, textDecoration: 'none', marginBottom: 8,
              }}>
                📩 Pošalji poruku na {portalName}
              </a>
              <a href={result.url} target="_blank" rel="noopener noreferrer" style={{
                display: 'block', width: '100%', padding: '10px',
                background: 'transparent', border: '1px solid var(--border)',
                color: 'var(--text3)', borderRadius: 10, textAlign: 'center',
                fontSize: 12, fontWeight: 500, textDecoration: 'none',
              }}>🔗 Otvori originalni oglas</a>
            </div>

            <p style={{ fontSize: 11, color: 'var(--text3)', textAlign: 'center', lineHeight: 1.6, opacity: .7 }}>
              * Procena je informativna. Pre kupovine obavezno proveriti dokumentaciju vozila, Euro normu i važeće propise u Srbiji.
            </p>

          </div>
        )}
      </div>
    </div>
  )
}
