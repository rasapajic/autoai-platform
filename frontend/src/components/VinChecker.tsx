'use client'
import { useState } from 'react'

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'https://autoai-platform-production.up.railway.app/api/v1'

const FUEL_LABELS: Record<string, string> = {
  diesel: 'Dizel', petrol: 'Benzin', electric: 'Električni',
  hybrid: 'Hibrid', lpg: 'Plin',
}

const ELIG_COLORS: Record<string, string> = {
  eligible: '#22C55E', needs_check: '#F97316',
  not_eligible: '#EF4444', oldtimer: '#A855F7',
}

interface Props {
  listing?: any
  compact?: boolean
}

export default function VinChecker({ listing, compact = false }: Props) {
  const [vin,     setVin]     = useState('')
  const [loading, setLoading] = useState(false)
  const [result,  setResult]  = useState<any>(null)
  const [error,   setError]   = useState('')
  const [copied,  setCopied]  = useState(false)
  const [showHow, setShowHow] = useState(false)

  const vinClean   = vin.toUpperCase().replace(/[^A-HJ-NPR-Z0-9]/g, '')
  const vinLen     = vinClean.length
  const vinComplete = vinLen === 17

  const decode = async () => {
    if (!vinComplete) return
    setLoading(true); setResult(null); setError('')
    try {
      const res = await fetch(`${API_BASE}/vin/decode`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ vin: vinClean, listing: listing || null }),
      })
      const data = await res.json()
      if (!data.success) setError(data.error || 'Greška pri dekodiranju VIN-a.')
      else setResult(data)
    } catch {
      setError('Nije moguće povezati se sa serverom.')
    }
    setLoading(false)
  }

  const eligColor = result ? (ELIG_COLORS[result.serbia_eligibility?.status] || '#F97316') : '#F97316'

  return (
    <div style={{ fontFamily: 'inherit' }}>
      <style>{`
        .vin-btn-active:hover {
          box-shadow: 0 0 20px rgba(255,107,0,.35) !important;
          transform: translateY(-1px) !important;
        }
        .vin-input:focus {
          border-color: rgba(255,107,0,.6) !important;
          box-shadow: 0 0 0 3px rgba(255,107,0,.1) !important;
        }
        .vin-how:hover { color: var(--text2) !important; }
      `}</style>

      {/* ✅ Benefiti — edukacija korisnika */}
      {!result && (
        <div style={{
          background: 'rgba(99,102,241,.06)',
          border: '1px solid rgba(99,102,241,.18)',
          borderRadius: 10, padding: '11px 14px', marginBottom: 14,
        }}>
          <div style={{ fontSize: 11, color: '#818CF8', fontWeight: 700, letterSpacing: '.06em', marginBottom: 6 }}>
            🛡️ ZAŠTO JE VIN VAŽAN?
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '3px 12px' }}>
            {[
              '✓ Stvarno godište vozila',
              '✓ Euro norma (za uvoz)',
              '✓ Podudaranje sa oglasom',
              '✓ Uslovi uvoza u Srbiju',
              '✓ Originalna oprema',
              '✓ Zemlja proizvodnje',
            ].map((b, i) => (
              <div key={i} style={{ fontSize: 12, color: 'var(--text3)', lineHeight: 1.6 }}>{b}</div>
            ))}
          </div>
        </div>
      )}

      {/* ✅ VIN input kartica */}
      <div style={{
        background: 'linear-gradient(135deg, rgba(15,15,20,1), rgba(20,20,28,1))',
        border: `2px solid ${vinComplete ? 'rgba(255,107,0,.5)' : result ? 'rgba(34,197,94,.4)' : 'rgba(99,102,241,.25)'}`,
        borderRadius: 14,
        padding: compact ? '14px' : '18px',
        boxShadow: vinComplete
          ? '0 0 24px rgba(255,107,0,.08), inset 0 1px 0 rgba(255,255,255,.04)'
          : '0 0 20px rgba(99,102,241,.06), inset 0 1px 0 rgba(255,255,255,.03)',
        transition: 'border-color .2s, box-shadow .2s',
        marginBottom: 0,
      }}>

        {/* Input red */}
        <div style={{ position: 'relative', marginBottom: 10 }}>
          <input
            className="vin-input"
            value={vin}
            onChange={e => { setVin(e.target.value.toUpperCase()); setError('') }}
            onKeyDown={e => e.key === 'Enter' && vinComplete && decode()}
            placeholder="Unesi VIN broj (17 znakova)"
            maxLength={20}
            style={{
              width: '100%', boxSizing: 'border-box',
              background: 'rgba(255,255,255,.04)',
              border: `1px solid ${vinComplete ? 'rgba(255,107,0,.4)' : 'rgba(255,255,255,.1)'}`,
              borderRadius: 10,
              padding: '12px 52px 12px 14px',
              color: 'var(--text)', fontSize: 15,
              fontFamily: 'monospace', letterSpacing: '0.08em',
              outline: 'none', transition: 'border-color .2s, box-shadow .2s',
            }}
          />
          {/* Brojač znakova */}
          <div style={{
            position: 'absolute', right: 12, top: '50%', transform: 'translateY(-50%)',
            fontSize: 12, fontWeight: 700, lineHeight: 1,
            color: vinComplete ? '#22C55E' : vinLen > 0 ? 'var(--accent)' : 'var(--text3)',
          }}>
            {vinLen}/17
          </div>
        </div>

        {/* Progress */}
        <div style={{ height: 2, background: 'rgba(255,255,255,.05)', borderRadius: 4, marginBottom: 12, overflow: 'hidden' }}>
          <div style={{
            height: '100%', borderRadius: 4,
            width: `${(Math.min(vinLen, 17) / 17) * 100}%`,
            background: vinComplete ? '#22C55E' : 'var(--accent)',
            transition: 'width .15s, background .2s',
          }} />
        </div>

        {/* VIN segmenti */}
        {vinLen > 0 && (
          <div style={{ display: 'flex', gap: 4, marginBottom: 12 }}>
            <div style={{ flex: 3, background: 'rgba(99,102,241,.12)', borderRadius: 6, padding: '5px 7px', textAlign: 'center' }}>
              <div style={{ fontFamily: 'monospace', fontWeight: 700, color: '#818CF8', fontSize: 12, letterSpacing: '0.1em' }}>
                {vinClean.slice(0, 3) || '···'}
              </div>
              <div style={{ fontSize: 9, color: 'var(--text3)', marginTop: 1 }}>Proizvođač</div>
            </div>
            <div style={{ flex: 6, background: 'rgba(255,107,0,.08)', borderRadius: 6, padding: '5px 7px', textAlign: 'center' }}>
              <div style={{ fontFamily: 'monospace', fontWeight: 700, color: 'var(--accent)', fontSize: 12, letterSpacing: '0.1em' }}>
                {vinClean.slice(3, 9) || '······'}
              </div>
              <div style={{ fontSize: 9, color: 'var(--text3)', marginTop: 1 }}>Vozilo</div>
            </div>
            <div style={{ flex: 8, background: 'rgba(34,197,94,.07)', borderRadius: 6, padding: '5px 7px', textAlign: 'center' }}>
              <div style={{ fontFamily: 'monospace', fontWeight: 700, color: '#22C55E', fontSize: 12, letterSpacing: '0.1em' }}>
                {vinClean.slice(9) || '········'}
              </div>
              <div style={{ fontSize: 9, color: 'var(--text3)', marginTop: 1 }}>Serijski br.</div>
            </div>
          </div>
        )}

        {/* ✅ CTA dugme */}
        <button
          className={vinComplete && !loading ? 'vin-btn-active' : ''}
          onClick={decode}
          disabled={!vinComplete || loading}
          style={{
            width: '100%', padding: '13px', borderRadius: 10, border: 'none',
            fontSize: 14, fontWeight: 800, cursor: vinComplete && !loading ? 'pointer' : 'default',
            transition: 'all .2s',
            background: loading
              ? 'rgba(255,255,255,.05)'
              : vinComplete
              ? 'linear-gradient(135deg, #FF6B00, #FF8C00)'
              : 'rgba(255,255,255,.04)',
            color: vinComplete && !loading ? '#fff' : 'var(--text3)',
            letterSpacing: vinComplete ? '.03em' : 'normal',
          }}
        >
          {loading
            ? <span style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8 }}>
                <span style={{ width: 8, height: 8, borderRadius: '50%', background: '#818CF8', display: 'inline-block', animation: 'pulse 1s infinite' }} />
                Verifikacija u toku...
              </span>
            : vinComplete
            ? '🔐 Pokreni VIN verifikaciju'
            : `Unesi još ${17 - vinLen} znaka...`
          }
        </button>

        {/* ✅ Gde naći VIN */}
        <button
          className="vin-how"
          onClick={() => setShowHow(v => !v)}
          style={{
            width: '100%', background: 'none', border: 'none', cursor: 'pointer',
            fontSize: 11, color: 'var(--text3)', marginTop: 10, textAlign: 'center',
            padding: '4px 0', transition: 'color .15s',
          }}
        >
          {showHow ? '▲ Sakrij' : '▼ Gde pronaći VIN broj?'}
        </button>

        {showHow && (
          <div style={{
            marginTop: 8, padding: '10px 12px',
            background: 'rgba(255,255,255,.03)',
            border: '1px solid rgba(255,255,255,.06)',
            borderRadius: 8,
          }}>
            <div style={{ fontSize: 11, color: 'var(--text3)', fontWeight: 600, marginBottom: 6 }}>
              VIN broj se nalazi na:
            </div>
            {[
              '🔲  Tableici vozila (donja strana šoferšajbne)',
              '📄  Saobraćajnoj dozvoli vozila',
              '🚪  Unutrašnjosti vrata vozača',
              '🔧  Motoru (ponekad)',
            ].map((item, i) => (
              <div key={i} style={{ fontSize: 12, color: 'var(--text3)', lineHeight: 1.7 }}>{item}</div>
            ))}
            <div style={{ fontSize: 11, color: 'rgba(255,107,0,.7)', marginTop: 6, fontStyle: 'italic' }}>
              💡 Zatraži ga od prodavca koristeći "Kontaktiraj prodavca" dugme.
            </div>
          </div>
        )}
      </div>

      {/* Greška */}
      {error && (
        <div style={{
          background: 'rgba(239,68,68,.08)', border: '1px solid rgba(239,68,68,.25)',
          borderRadius: 10, padding: '12px 14px', marginTop: 12,
          color: '#EF4444', fontSize: 13,
        }}>⚠️ {error}</div>
      )}

      {/* ✅ Rezultati */}
      {result && (
        <div style={{ marginTop: 14, display: 'flex', flexDirection: 'column', gap: 10 }}>

          {/* Match status */}
          {listing && result.match_status !== 'no_listing' && (
            <div style={{
              background: result.match_status === 'ok'
                ? 'rgba(34,197,94,.07)' : result.match_status === 'warning'
                ? 'rgba(249,115,22,.07)' : 'rgba(239,68,68,.07)',
              border: `2px solid ${result.match_status === 'ok' ? 'rgba(34,197,94,.3)' : result.match_status === 'warning' ? 'rgba(249,115,22,.3)' : 'rgba(239,68,68,.3)'}`,
              borderRadius: 12, padding: '12px 14px',
            }}>
              <div style={{ fontSize: 15, fontWeight: 800, marginBottom: 4 }}>{result.match_label}</div>
              {result.mismatches.length === 0 ? (
                <p style={{ fontSize: 13, color: 'var(--text2)', margin: 0 }}>
                  VIN potvrđuje sve podatke iz oglasa.
                </p>
              ) : (
                result.mismatches.map((m: any, i: number) => (
                  <div key={i} style={{
                    marginTop: i === 0 ? 4 : 6, padding: '8px 10px',
                    background: m.severity === 'critical' ? 'rgba(239,68,68,.1)' : 'rgba(249,115,22,.1)',
                    borderRadius: 8, borderLeft: `3px solid ${m.severity === 'critical' ? '#EF4444' : '#F97316'}`,
                  }}>
                    <div style={{ fontSize: 12, fontWeight: 700, color: m.severity === 'critical' ? '#EF4444' : '#F97316' }}>
                      ⚠ {m.field}
                    </div>
                    <div style={{ fontSize: 12, color: 'var(--text2)', marginTop: 2 }}>{m.message}</div>
                  </div>
                ))
              )}
            </div>
          )}

          {/* Dekodovani podaci */}
          <div style={{ background: 'var(--bg2)', border: '1px solid var(--border)', borderRadius: 12, padding: '12px 14px' }}>
            <div style={{ fontSize: 11, color: 'var(--text3)', fontWeight: 600, letterSpacing: '.07em', marginBottom: 10 }}>
              📋 DEKODOVANI PODACI
            </div>
            {result.nhtsa_error_text?.includes('11') && (
              <div style={{ background: 'rgba(249,115,22,.07)', border: '1px solid rgba(249,115,22,.2)', borderRadius: 7, padding: '7px 10px', marginBottom: 10, fontSize: 11, color: '#F97316' }}>
                ℹ️ EU vozila mogu imati nepotpune podatke u NHTSA bazi — godište i marka se detektuju lokalno.
              </div>
            )}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 7 }}>
              {[
                { label: 'Marka',       value: result.make },
                { label: 'Model',       value: result.model },
                { label: 'Godište',     value: result.year },
                { label: 'Gorivo',      value: result.fuel_type ? (FUEL_LABELS[result.fuel_type] || result.fuel_type) : null },
                { label: 'Karoserija',  value: result.body_type },
                { label: 'Motor (L)',   value: result.engine_displacement },
                { label: 'Cilindri',    value: result.engine_cylinders },
                { label: 'Pogon',       value: result.drive_type },
                { label: 'Zemlja pr.', value: result.plant_country },
              ].filter(f => f.value).map(({ label, value }) => (
                <div key={label} style={{ background: 'var(--bg3)', borderRadius: 7, padding: '7px 10px' }}>
                  <div style={{ fontSize: 10, color: 'var(--text3)', marginBottom: 2 }}>{label}</div>
                  <div style={{ fontSize: 13, fontWeight: 600 }}>{String(value)}</div>
                </div>
              ))}
            </div>
            {/* VIN segmenti */}
            <div style={{ marginTop: 10, padding: '7px 10px', background: 'var(--bg3)', borderRadius: 7 }}>
              <div style={{ fontSize: 10, color: 'var(--text3)', marginBottom: 3 }}>VIN</div>
              <div style={{ fontFamily: 'monospace', fontSize: 13, letterSpacing: '0.08em' }}>
                <span style={{ color: '#818CF8' }}>{result.vin.slice(0, 3)}</span>
                <span style={{ color: 'var(--accent)' }}>{result.vin.slice(3, 9)}</span>
                <span style={{ color: '#22C55E' }}>{result.vin.slice(9)}</span>
              </div>
            </div>
          </div>

          {/* Serbia eligibility */}
          <div style={{
            background: `${eligColor}0d`,
            border: `1px solid ${eligColor}33`,
            borderRadius: 12, padding: '12px 14px',
          }}>
            <div style={{ fontSize: 10, color: 'var(--text3)', fontWeight: 600, letterSpacing: '.07em', marginBottom: 5 }}>UVOZ U SRBIJU</div>
            <div style={{ fontSize: 14, fontWeight: 800, color: eligColor, marginBottom: 3 }}>
              {result.serbia_eligibility.emoji} {result.serbia_eligibility.label}
            </div>
            <p style={{ fontSize: 12, color: 'var(--text2)', margin: '0 0 4px', lineHeight: 1.5 }}>
              {result.serbia_eligibility.reason}
            </p>
            <div style={{ fontSize: 12, color: 'var(--text3)' }}>
              Carina: <strong style={{ color: eligColor }}>{result.serbia_eligibility.carina_pct}%</strong>
              {result.serbia_eligibility.carina_pct === 0 && ' (oslobođeno)'}
            </div>
          </div>

          {/* Budući provajderi */}
          <div style={{
            background: 'rgba(255,255,255,.02)', border: '1px dashed rgba(255,255,255,.08)',
            borderRadius: 10, padding: '10px 14px',
          }}>
            <div style={{ fontSize: 11, color: 'var(--text3)', fontWeight: 600, marginBottom: 5 }}>🔮 Detaljna istorija — uskoro</div>
            <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap' }}>
              {['CarVertical', 'AutoDNA', 'CARFAX'].map(p => (
                <span key={p} style={{ fontSize: 11, padding: '2px 8px', borderRadius: 20, background: 'var(--bg3)', border: '1px solid var(--border)', color: 'var(--text3)' }}>{p}</span>
              ))}
            </div>
          </div>

          {/* Kopiraj VIN */}
          <button
            onClick={() => { navigator.clipboard.writeText(result.vin); setCopied(true); setTimeout(() => setCopied(false), 2000) }}
            style={{
              width: '100%', padding: '9px', borderRadius: 9,
              background: copied ? 'rgba(34,197,94,.08)' : 'transparent',
              border: `1px solid ${copied ? '#22C55E44' : 'var(--border)'}`,
              color: copied ? '#22C55E' : 'var(--text3)',
              fontSize: 12, fontWeight: 600, cursor: 'pointer', transition: 'all .15s',
            }}
          >
            {copied ? '✓ VIN kopiran!' : `📋 Kopiraj VIN: ${result.vin}`}
          </button>
        </div>
      )}
    </div>
  )
}
