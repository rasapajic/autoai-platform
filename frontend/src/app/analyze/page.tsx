'use client'
import { useState } from 'react'
import ContactModal from '@/components/ContactModal'

const AI_BADGES: Record<string, { label: string; color: string; bg: string }> = {
  great:      { label: '🟢 DOBRA KUPOVINA',  color: '#22C55E', bg: 'rgba(34,197,94,.13)'   },
  good:       { label: '🟡 FER CENA',         color: '#EAB308', bg: 'rgba(234,179,8,.13)'   },
  fair:       { label: '⚪ PROSEČNA CENA',    color: '#9CA3AF', bg: 'rgba(156,163,175,.10)' },
  high:       { label: '🟠 VISOKA CENA',      color: '#F97316', bg: 'rgba(249,115,22,.13)'  },
  overpriced: { label: '🔴 PREVISOKA CENA',   color: '#EF4444', bg: 'rgba(239,68,68,.13)'   },
}

const RECO_STYLE: Record<string, { color: string; bg: string }> = {
  KUPI:     { color: '#22C55E', bg: 'rgba(34,197,94,.12)'  },
  RAZMATRAJ:{ color: '#EAB308', bg: 'rgba(234,179,8,.12)'  },
  IZBEGNI:  { color: '#EF4444', bg: 'rgba(239,68,68,.12)'  },
}

const SUPPORTED = ['AutoScout24', 'Mobile.de', 'Willhaben', 'Polovni automobili', 'Kleinanzeigen', 'i drugi']

function calcBreakdown(price: number) {
  const carina = Math.round(price * 0.05)
  const pdv    = Math.round((price + carina) * 0.20)
  const transport = 420, reg = 280
  return { carina, pdv, transport, reg, total: price + carina + pdv + transport + reg }
}

type Step = 'idle' | 'fetching' | 'extracting' | 'analyzing' | 'done' | 'fallback' | 'error'

export default function AnalyzePage() {
  const [url,     setUrl]     = useState('')
  const [text,    setText]    = useState('')
  const [step,    setStep]    = useState<Step>('idle')
  const [result,  setResult]  = useState<any>(null)
  const [errMsg,  setErrMsg]  = useState('')
  const [showBd,  setShowBd]  = useState(false)
  const [contact, setContact] = useState(false)

  const analyze = async (useText = false) => {
    const payload = useText
      ? { text, url: url || undefined }
      : { url }

    if (!url && !text) return

    setStep(useText ? 'extracting' : 'fetching')
    setResult(null); setErrMsg('')

    try {
      if (!useText) setStep('fetching')
      const res = await fetch('/api/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      const data = await res.json()

      if (!data.success) {
        if (data.error === 'fetch_failed') {
          setStep('fallback')
          setErrMsg(data.message)
        } else {
          setStep('error')
          setErrMsg(data.message || 'Greška pri analizi.')
        }
        return
      }

      setResult(data)
      setStep('done')
    } catch {
      setStep('error')
      setErrMsg('Greška pri konekciji. Pokušaj ponovo.')
    }
  }

  const reset = () => { setStep('idle'); setResult(null); setUrl(''); setText(''); setErrMsg('') }

  const listing  = result?.listing  || {}
  const analysis = result?.analysis || {}
  const badge    = AI_BADGES[analysis.price_rating]
  const reco     = RECO_STYLE[analysis.recommendation]
  const price    = listing.price ? Number(listing.price) : null
  const bd       = price ? calcBreakdown(price) : null

  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg)', padding: '32px 16px 80px' }}>
      <style>{`
        @media(max-width:768px){.rg{grid-template-columns:1fr!important}}
        .cb:hover{opacity:.82!important}
        .inp:focus{border-color:var(--accent)!important;outline:none}
      `}</style>

      {contact && result && (
        <ContactModal
          listing={{ ...listing, id: 'external', url: result.url }}
          onClose={() => setContact(false)}
        />
      )}

      <div className="container" style={{ maxWidth: 740 }}>

        {/* ── Header ── */}
        <div style={{ marginBottom: 32, textAlign: 'center' }}>
          <div style={{
            display: 'inline-flex', alignItems: 'center', gap: 8,
            background: 'rgba(255,107,0,.1)', border: '1px solid rgba(255,107,0,.25)',
            borderRadius: 20, padding: '6px 14px', fontSize: 12, fontWeight: 600,
            color: 'var(--accent)', marginBottom: 16,
          }}>🤖 AI ANALIZA OGLASA</div>

          <h1 style={{ fontSize: 28, fontWeight: 800, margin: '0 0 10px', fontFamily: 'Syne,sans-serif', lineHeight: 1.2 }}>
            Proveri bilo koji auto oglas
          </h1>
          <p style={{ fontSize: 15, color: 'var(--text2)', margin: 0 }}>
            Nalepi link oglasa — AI analizira cenu, računica uvoza za Srbiju i otkriva rizike
          </p>
        </div>

        {step === 'idle' || step === 'fetching' || step === 'extracting' || step === 'analyzing' ? (
          <div style={{ background: 'var(--bg2)', border: '1px solid var(--border)', borderRadius: 20, padding: 28 }}>

            {/* URL input */}
            <div style={{ marginBottom: 16 }}>
              <label style={{ fontSize: 12, color: 'var(--text3)', fontWeight: 600, letterSpacing: '.07em', display: 'block', marginBottom: 8 }}>
                URL OGLASA
              </label>
              <input
                className="inp"
                value={url}
                onChange={e => setUrl(e.target.value)}
                placeholder="https://www.autoscout24.com/offers/... ili mobile.de, willhaben..."
                style={{
                  width: '100%', background: 'var(--bg3)',
                  border: '1px solid var(--border)', borderRadius: 12,
                  padding: '14px 16px', color: 'var(--text)', fontSize: 14,
                  boxSizing: 'border-box', transition: 'border-color .15s',
                }}
              />
            </div>

            {/* Supported sites */}
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 22 }}>
              {SUPPORTED.map(s => (
                <span key={s} style={{
                  fontSize: 11, padding: '4px 10px', borderRadius: 20,
                  background: 'var(--bg3)', border: '1px solid var(--border)',
                  color: 'var(--text3)',
                }}>{s}</span>
              ))}
            </div>

            {/* Analyze button */}
            <button
              className="cb"
              onClick={() => analyze(false)}
              disabled={!url.trim() || step !== 'idle'}
              style={{
                width: '100%', padding: '15px', borderRadius: 12, border: 'none',
                background: (!url.trim() || step !== 'idle') ? 'var(--bg3)' : 'var(--accent)',
                color: (!url.trim() || step !== 'idle') ? 'var(--text3)' : '#fff',
                fontSize: 16, fontWeight: 700,
                cursor: (!url.trim() || step !== 'idle') ? 'default' : 'pointer',
              }}
            >
              {step === 'fetching'   ? '⏳ Preuzimam oglas...'  :
               step === 'extracting' ? '🔍 Izvlačim podatke...' :
               step === 'analyzing'  ? '🤖 Analiziram...'       :
               '🔍 Analiziraj oglas'}
            </button>
          </div>
        ) : step === 'fallback' ? (

          /* ── Fallback: paste text ── */
          <div style={{ background: 'var(--bg2)', border: '1px solid rgba(249,115,22,.3)', borderRadius: 20, padding: 28 }}>
            <div style={{
              background: 'rgba(249,115,22,.1)', border: '1px solid rgba(249,115,22,.25)',
              borderRadius: 10, padding: '12px 16px', marginBottom: 20,
              display: 'flex', gap: 10, alignItems: 'flex-start',
            }}>
              <span style={{ fontSize: 18 }}>⚠️</span>
              <div>
                <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 4 }}>Sajt ne dozvoljava direktan pristup</div>
                <div style={{ fontSize: 13, color: 'var(--text2)' }}>{errMsg}</div>
              </div>
            </div>

            <label style={{ fontSize: 12, color: 'var(--text3)', fontWeight: 600, letterSpacing: '.07em', display: 'block', marginBottom: 8 }}>
              NALEPI TEKST OGLASA (Ctrl+A na stranici oglasa, pa Ctrl+C)
            </label>
            <textarea
              value={text}
              onChange={e => setText(e.target.value)}
              placeholder="Nalepi ovde kompletan tekst sa stranice oglasa..."
              rows={8}
              style={{
                width: '100%', background: 'var(--bg3)', border: '1px solid var(--border)',
                borderRadius: 12, padding: '14px', color: 'var(--text)', fontSize: 13,
                outline: 'none', resize: 'vertical', boxSizing: 'border-box',
                fontFamily: 'inherit', lineHeight: 1.6,
              }}
            />
            <div style={{ display: 'flex', gap: 10, marginTop: 14 }}>
              <button className="cb" onClick={() => analyze(true)} disabled={!text.trim()} style={{
                flex: 2, padding: '13px', borderRadius: 12, border: 'none',
                background: !text.trim() ? 'var(--bg3)' : 'var(--accent)',
                color: !text.trim() ? 'var(--text3)' : '#fff',
                fontSize: 14, fontWeight: 700, cursor: !text.trim() ? 'default' : 'pointer',
              }}>🤖 Analiziraj tekst</button>
              <button className="cb" onClick={reset} style={{
                flex: 1, padding: '13px', borderRadius: 12,
                background: 'transparent', border: '1px solid var(--border)',
                color: 'var(--text3)', fontSize: 14, cursor: 'pointer',
              }}>Nazad</button>
            </div>
          </div>

        ) : step === 'error' ? (

          <div style={{ textAlign: 'center', padding: '40px 20px', background: 'var(--bg2)', borderRadius: 20, border: '1px solid var(--border)' }}>
            <div style={{ fontSize: 48, marginBottom: 16 }}>❌</div>
            <p style={{ fontSize: 16, fontWeight: 600, marginBottom: 8 }}>Greška pri analizi</p>
            <p style={{ color: 'var(--text3)', fontSize: 14, marginBottom: 20 }}>{errMsg}</p>
            <button className="cb" onClick={reset} style={{
              padding: '11px 24px', borderRadius: 10,
              background: 'var(--accent)', color: '#fff',
              border: 'none', fontSize: 14, fontWeight: 600, cursor: 'pointer',
            }}>Pokušaj ponovo</button>
          </div>

        ) : (

          /* ── Results ── */
          <div>
            {/* AI Badge */}
            {badge && (
              <div style={{
                background: badge.bg, border: `2px solid ${badge.color}`,
                borderRadius: 16, padding: '16px 20px', marginBottom: 20,
                display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                flexWrap: 'wrap', gap: 10,
              }}>
                <div>
                  <div style={{ fontSize: 18, fontWeight: 800, color: badge.color, letterSpacing: '.03em' }}>
                    {badge.label}
                  </div>
                  {analysis.buying_insight && (
                    <div style={{ fontSize: 14, color: 'var(--text2)', marginTop: 4 }}>
                      {analysis.buying_insight}
                    </div>
                  )}
                </div>
                {reco && (
                  <div style={{
                    background: reco.bg, border: `1px solid ${reco.color}`,
                    borderRadius: 10, padding: '8px 16px',
                    fontSize: 14, fontWeight: 800, color: reco.color,
                  }}>
                    {analysis.recommendation}
                  </div>
                )}
              </div>
            )}

            {/* Car info + price */}
            <div style={{ background: 'var(--bg2)', border: '1px solid var(--border)', borderRadius: 16, padding: 24, marginBottom: 16 }}>
              <div style={{ marginBottom: 16 }}>
                <h2 style={{ fontSize: 20, fontWeight: 700, margin: '0 0 4px', fontFamily: 'Syne,sans-serif' }}>
                  {listing.title || `${listing.year || ''} ${listing.make || ''} ${listing.model || ''}`}
                </h2>
                {result.url && (
                  <a href={result.url} target="_blank" rel="noopener" style={{ fontSize: 12, color: 'var(--accent)', textDecoration: 'none' }}>
                    🔗 {new URL(result.url).hostname}
                  </a>
                )}
              </div>

              {/* Specs grid */}
              <div className="rg" style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 10, marginBottom: 20 }}>
                {[
                  { label: 'Godište',     value: listing.year },
                  { label: 'Kilometraža', value: listing.mileage ? `${Number(listing.mileage).toLocaleString()} km` : null },
                  { label: 'Gorivo',      value: listing.fuel_type },
                  { label: 'Menjač',      value: listing.transmission },
                  { label: 'Snaga',       value: listing.engine_power_kw ? `${listing.engine_power_kw} kW` : null },
                  { label: 'Zemlja',      value: listing.country },
                ].filter(s => s.value).map(s => (
                  <div key={s.label} style={{ background: 'var(--bg3)', borderRadius: 8, padding: '9px 12px' }}>
                    <div style={{ fontSize: 10, color: 'var(--text3)', marginBottom: 3, fontWeight: 600 }}>{s.label.toUpperCase()}</div>
                    <div style={{ fontSize: 13, fontWeight: 500 }}>{s.value}</div>
                  </div>
                ))}
              </div>

              {/* EU price */}
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
                <span style={{ fontSize: 13, color: 'var(--text3)' }}>EU cena:</span>
                <span style={{ fontSize: 24, fontWeight: 800, color: 'var(--text2)' }}>
                  {price ? `${price.toLocaleString()} €` : 'Nije pronađena'}
                </span>
                {analysis.price_delta_pct != null && (
                  <span style={{
                    fontSize: 13, fontWeight: 600,
                    color: analysis.price_delta_pct < 0 ? '#22C55E' : '#EF4444',
                    background: analysis.price_delta_pct < 0 ? 'rgba(34,197,94,.1)' : 'rgba(239,68,68,.1)',
                    padding: '3px 9px', borderRadius: 20,
                  }}>
                    {analysis.price_delta_pct > 0 ? '+' : ''}{Number(analysis.price_delta_pct).toFixed(0)}% vs tržišta
                  </span>
                )}
              </div>

              {/* Serbia cost */}
              {bd && (
                <div style={{ background: 'rgba(255,107,0,.07)', border: '1px solid rgba(255,107,0,.2)', borderRadius: 12, overflow: 'hidden' }}>
                  <button className="cb" onClick={() => setShowBd(!showBd)} style={{
                    width: '100%', background: 'none', border: 'none', cursor: 'pointer',
                    padding: '12px 16px', display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                  }}>
                    <div style={{ textAlign: 'left' }}>
                      <div style={{ fontSize: 11, color: 'var(--text3)', marginBottom: 2 }}>🇷🇸 Ukupno za Srbiju</div>
                      <div style={{ fontSize: 22, fontWeight: 800, color: 'var(--accent)' }}>{bd.total.toLocaleString()} €</div>
                    </div>
                    <span style={{ fontSize: 11, color: 'rgba(255,107,0,.6)' }}>{showBd ? '▲ sakrij' : '▼ detalji'}</span>
                  </button>
                  {showBd && (
                    <div style={{ padding: '0 16px 14px', borderTop: '1px solid rgba(255,107,0,.15)' }}>
                      <div style={{ fontSize: 11, color: 'var(--text3)', margin: '10px 0 8px', fontWeight: 600 }}>KAKO JE IZRAČUNATO:</div>
                      {[
                        { l: 'EU cena',          v: price!,      n: '' },
                        { l: 'Carina (5%)',       v: bd.carina,   n: 'srbija' },
                        { l: 'PDV (20%)',         v: bd.pdv,      n: 'srbija' },
                        { l: 'Transport EU→RS',   v: bd.transport,n: 'procena' },
                        { l: 'Registracija',      v: bd.reg,      n: 'procena' },
                      ].map(({ l, v, n }, i) => (
                        <div key={i} style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0', borderTop: i === 0 ? 'none' : '1px solid rgba(255,255,255,.04)' }}>
                          <span style={{ fontSize: 12, color: i === 0 ? 'var(--text2)' : 'var(--text3)' }}>
                            {i > 0 && '+ '}{l}{n && <span style={{ fontSize: 10, marginLeft: 4, opacity: .5 }}>({n})</span>}
                          </span>
                          <span style={{ fontSize: 12, fontWeight: 500, color: i === 0 ? 'var(--text2)' : '#fb923c' }}>
                            {i === 0 ? '' : '+'}{v.toLocaleString()} €
                          </span>
                        </div>
                      ))}
                      <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 8, paddingTop: 8, borderTop: '1px solid rgba(255,107,0,.25)' }}>
                        <span style={{ fontSize: 13, fontWeight: 700 }}>Ukupno Srbija</span>
                        <span style={{ fontSize: 16, fontWeight: 800, color: 'var(--accent)' }}>{bd.total.toLocaleString()} €</span>
                      </div>
                      <p style={{ fontSize: 10, color: 'var(--text3)', margin: '8px 0 0', lineHeight: 1.4 }}>
                        * Procena. Stvarni troškovi mogu varirati.
                      </p>
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* AI Notes + signals */}
            {(analysis.notes || analysis.risk_flags?.length > 0 || analysis.safe_signals?.length > 0) && (
              <div style={{ background: 'var(--bg2)', border: '1px solid var(--border)', borderRadius: 16, padding: 22, marginBottom: 16 }}>
                <h3 style={{ fontSize: 14, fontWeight: 600, margin: '0 0 14px', color: 'var(--text2)' }}>🤖 AI Analiza</h3>

                {analysis.notes && (
                  <p style={{ fontSize: 14, lineHeight: 1.7, color: 'var(--text2)', margin: '0 0 14px' }}>{analysis.notes}</p>
                )}

                {analysis.risk_flags?.length > 0 && (
                  <div style={{ marginBottom: 10 }}>
                    {analysis.risk_flags.map((f: string) => (
                      <div key={f} style={{ display: 'flex', gap: 8, alignItems: 'flex-start', marginBottom: 6 }}>
                        <span style={{ color: '#EF4444', fontSize: 14, flexShrink: 0 }}>⚠</span>
                        <span style={{ fontSize: 13, color: '#F87171' }}>{f}</span>
                      </div>
                    ))}
                  </div>
                )}

                {analysis.safe_signals?.length > 0 && (
                  <div>
                    {analysis.safe_signals.map((s: string) => (
                      <div key={s} style={{ display: 'flex', gap: 8, alignItems: 'flex-start', marginBottom: 6 }}>
                        <span style={{ color: '#22C55E', fontSize: 14, flexShrink: 0 }}>✓</span>
                        <span style={{ fontSize: 13, color: '#4ADE80' }}>{s}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Actions */}
            <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
              <button onClick={() => setContact(true)} className="cb" style={{
                flex: 2, padding: '13px', borderRadius: 12,
                background: 'rgba(99,102,241,.1)', border: '1px solid rgba(99,102,241,.35)',
                color: '#818CF8', fontSize: 14, fontWeight: 700, cursor: 'pointer', minWidth: 180,
              }}>
                🤖 Kontaktiraj prodavca
                <div style={{ fontSize: 11, fontWeight: 400, color: 'rgba(129,140,248,.7)', marginTop: 2 }}>
                  AI generiše poruku na jeziku prodavca
                </div>
              </button>
              <button onClick={reset} className="cb" style={{
                flex: 1, padding: '13px', borderRadius: 12,
                background: 'transparent', border: '1px solid var(--border)',
                color: 'var(--text3)', fontSize: 14, cursor: 'pointer', minWidth: 120,
              }}>🔍 Novi oglas</button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
