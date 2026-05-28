'use client'
import { useState } from 'react'

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'https://autoai-platform-production.up.railway.app/api/v1'

const FUEL_LABELS: Record<string, string> = {
  diesel: 'Dizel', petrol: 'Benzin', electric: 'Električni',
  hybrid: 'Hibrid', lpg: 'Plin',
}

interface VinResult {
  success: boolean
  vin: string
  make?: string
  model?: string
  year?: number
  fuel_type?: string
  body_type?: string
  engine_displacement?: string
  engine_cylinders?: string
  drive_type?: string
  plant_country?: string
  manufacturer?: string
  serbia_eligibility: {
    status: string
    emoji: string
    label: string
    reason: string
    carina_pct: number
  }
  mismatches: Array<{
    field: string
    severity: string
    vin_value: string
    listing_value: string
    message: string
  }>
  match_status: string
  match_label: string
  history_providers: any
  error?: string
  nhtsa_error_text?: string
}

const ELIG_COLORS: Record<string, string> = {
  eligible: '#22C55E', needs_check: '#F97316',
  not_eligible: '#EF4444', oldtimer: '#A855F7',
}

interface Props {
  listing?: any  // Opcionalno — za poređenje
  compact?: boolean
}

export default function VinChecker({ listing, compact = false }: Props) {
  const [vin,      setVin]      = useState('')
  const [loading,  setLoading]  = useState(false)
  const [result,   setResult]   = useState<VinResult | null>(null)
  const [error,    setError]    = useState('')
  const [copied,   setCopied]   = useState(false)

  const vinClean = vin.toUpperCase().replace(/[^A-HJ-NPR-Z0-9]/g, '')

  const decode = async () => {
    if (vinClean.length !== 17) return
    setLoading(true); setResult(null); setError('')
    try {
      const res = await fetch(`${API_BASE}/vin/decode`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ vin: vinClean, listing: listing || null }),
      })
      const data = await res.json()
      if (!data.success) {
        setError(data.error || 'Greška pri dekodiranju VIN-a.')
      } else {
        setResult(data)
      }
    } catch {
      setError('Nije moguće povezati se sa serverom.')
    }
    setLoading(false)
  }

  const eligColor = result ? (ELIG_COLORS[result.serbia_eligibility?.status] || '#F97316') : '#F97316'

  const vinProgress = Math.min(vinClean.length, 17)
  const vinComplete = vinClean.length === 17

  return (
    <div style={{ fontFamily: 'inherit' }}>

      {/* VIN input sekcija */}
      <div style={{
        background: 'linear-gradient(135deg, rgba(99,102,241,.08), rgba(99,102,241,.03))',
        border: `2px solid ${vinComplete ? 'rgba(99,102,241,.5)' : 'rgba(99,102,241,.2)'}`,
        borderRadius: 16, padding: compact ? '14px 16px' : '20px',
        marginBottom: 16, transition: 'border-color .2s',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
          <span style={{ fontSize: compact ? 18 : 22 }}>🔐</span>
          <div>
            <div style={{ fontSize: compact ? 13 : 15, fontWeight: 700, color: '#818CF8' }}>
              VIN Provera Vozila
            </div>
            <div style={{ fontSize: 11, color: 'var(--text3)' }}>
              BESPLATNO · NHTSA baza podataka
            </div>
          </div>
        </div>

        {/* Input */}
        <div style={{ position: 'relative', marginBottom: 8 }}>
          <input
            value={vin}
            onChange={e => setVin(e.target.value.toUpperCase())}
            onKeyDown={e => e.key === 'Enter' && vinComplete && decode()}
            placeholder="Unesi 17-znakni VIN broj"
            maxLength={17}
            style={{
              width: '100%', boxSizing: 'border-box',
              background: 'var(--bg3)',
              border: `1px solid ${vinComplete ? 'rgba(99,102,241,.5)' : 'var(--border)'}`,
              borderRadius: 10, padding: '12px 50px 12px 14px',
              color: 'var(--text)', fontSize: 15, fontFamily: 'monospace',
              outline: 'none', letterSpacing: '0.05em',
              transition: 'border-color .2s',
            }}
          />
          {/* Brojač */}
          <span style={{
            position: 'absolute', right: 12, top: '50%', transform: 'translateY(-50%)',
            fontSize: 12, fontWeight: 700,
            color: vinComplete ? '#22C55E' : 'var(--text3)',
          }}>
            {vinClean.length}/17
          </span>
        </div>

        {/* Progress bar */}
        <div style={{ height: 3, background: 'rgba(255,255,255,.06)', borderRadius: 4, marginBottom: 12, overflow: 'hidden' }}>
          <div style={{
            height: '100%', borderRadius: 4, transition: 'width .2s, background .2s',
            width: `${(vinProgress / 17) * 100}%`,
            background: vinComplete ? '#22C55E' : '#818CF8',
          }} />
        </div>

        {/* Segmenti VIN-a */}
        {vinClean.length > 0 && (
          <div style={{ display: 'flex', gap: 4, marginBottom: 12, fontSize: 10, color: 'var(--text3)' }}>
            <div style={{ flex: 3, background: 'rgba(99,102,241,.1)', borderRadius: 6, padding: '4px 6px', textAlign: 'center' }}>
              <div style={{ fontWeight: 700, color: '#818CF8', fontSize: 11 }}>{vinClean.slice(0, 3)}</div>
              <div>WMI (Proizvođač)</div>
            </div>
            <div style={{ flex: 6, background: 'rgba(255,107,0,.08)', borderRadius: 6, padding: '4px 6px', textAlign: 'center' }}>
              <div style={{ fontWeight: 700, color: 'var(--accent)', fontSize: 11 }}>{vinClean.slice(3, 9) || '------'}</div>
              <div>VDS (Vozilo)</div>
            </div>
            <div style={{ flex: 8, background: 'rgba(34,197,94,.08)', borderRadius: 6, padding: '4px 6px', textAlign: 'center' }}>
              <div style={{ fontWeight: 700, color: '#22C55E', fontSize: 11 }}>{vinClean.slice(9) || '--------'}</div>
              <div>VIS (Serijski br.)</div>
            </div>
          </div>
        )}

        <button
          onClick={decode}
          disabled={!vinComplete || loading}
          style={{
            width: '100%', padding: '12px', borderRadius: 10, border: 'none',
            background: (!vinComplete || loading) ? 'var(--bg3)' : 'linear-gradient(135deg, rgba(99,102,241,.3), rgba(99,102,241,.2))',
            color: (!vinComplete || loading) ? 'var(--text3)' : '#818CF8',
            fontSize: 14, fontWeight: 700, cursor: (!vinComplete || loading) ? 'default' : 'pointer',
            border: `1px solid ${!vinComplete ? 'transparent' : 'rgba(99,102,241,.4)'}` as any,
            transition: 'all .2s',
          }}
        >
          {loading ? '⏳ Dekodiranje VIN-a...' : '🔍 Proveri VIN'}
        </button>

        {/* Napomena */}
        <p style={{ fontSize: 11, color: 'var(--text3)', margin: '10px 0 0', textAlign: 'center', lineHeight: 1.5 }}>
          VIN broj se nalazi na: tableici vozila · saobraćajnoj dozvoli · unutrašnjosti vrata
        </p>
      </div>

      {error && (
        <div style={{ background: 'rgba(239,68,68,.1)', border: '1px solid rgba(239,68,68,.3)', borderRadius: 12, padding: 14, marginBottom: 14, color: '#EF4444', fontSize: 14 }}>
          ⚠️ {error}
        </div>
      )}

      {/* Rezultati */}
      {result && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>

          {/* Match status — ako ima listing za poređenje */}
          {listing && result.match_status !== 'no_listing' && (
            <div style={{
              background: result.match_status === 'ok'
                ? 'rgba(34,197,94,.08)'
                : result.match_status === 'warning'
                ? 'rgba(249,115,22,.08)'
                : 'rgba(239,68,68,.08)',
              border: `2px solid ${result.match_status === 'ok' ? 'rgba(34,197,94,.3)' : result.match_status === 'warning' ? 'rgba(249,115,22,.3)' : 'rgba(239,68,68,.3)'}`,
              borderRadius: 14, padding: '14px 16px',
            }}>
              <div style={{ fontSize: 16, fontWeight: 800, marginBottom: 6 }}>
                {result.match_label}
              </div>
              {result.mismatches.length === 0 ? (
                <p style={{ fontSize: 13, color: 'var(--text2)', margin: 0 }}>
                  VIN potvrđuje sve podatke iz oglasa. Vozilo je konzistentno.
                </p>
              ) : (
                <div>
                  {result.mismatches.map((m, i) => (
                    <div key={i} style={{
                      marginTop: 8, padding: '10px 12px',
                      background: m.severity === 'critical' ? 'rgba(239,68,68,.1)' : 'rgba(249,115,22,.1)',
                      borderRadius: 8, borderLeft: `3px solid ${m.severity === 'critical' ? '#EF4444' : '#F97316'}`,
                    }}>
                      <div style={{ fontSize: 13, fontWeight: 700, color: m.severity === 'critical' ? '#EF4444' : '#F97316', marginBottom: 3 }}>
                        ⚠ {m.field}
                      </div>
                      <div style={{ fontSize: 12, color: 'var(--text2)' }}>{m.message}</div>
                      <div style={{ fontSize: 11, color: 'var(--text3)', marginTop: 4 }}>
                        VIN: <strong>{m.vin_value}</strong> · Oglas: <strong>{m.listing_value}</strong>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Dekodovani podaci */}
          <div style={{ background: 'var(--bg2)', border: '1px solid var(--border)', borderRadius: 14, padding: '14px 16px' }}>
            <div style={{ fontSize: 11, color: 'var(--text3)', fontWeight: 600, letterSpacing: '.07em', marginBottom: 12 }}>
              📋 DEKODOVANI PODACI
            </div>

            {/* Upozorenje ako NHTSA nema EU podatke */}
            {result.nhtsa_error_text && result.nhtsa_error_text.includes('11') && (
              <div style={{ background: 'rgba(249,115,22,.08)', border: '1px solid rgba(249,115,22,.2)', borderRadius: 8, padding: '8px 12px', marginBottom: 12, fontSize: 12, color: '#F97316' }}>
                ℹ️ NHTSA baza je US-fokusirana — EU vozila mogu imati nepotpune podatke. Godište i marka se detektuju lokalno.
              </div>
            )}

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
              {[
                { label: 'Marka',        value: result.make },
                { label: 'Model',        value: result.model },
                { label: 'Godište',      value: result.year },
                { label: 'Gorivo',       value: result.fuel_type ? (FUEL_LABELS[result.fuel_type] || result.fuel_type) : null },
                { label: 'Karoserija',   value: result.body_type },
                { label: 'Motor (L)',    value: result.engine_displacement },
                { label: 'Cilindri',     value: result.engine_cylinders },
                { label: 'Pogon',        value: result.drive_type },
                { label: 'Zemlja prod.', value: result.plant_country },
                { label: 'Proizvođač',   value: result.manufacturer },
              ].filter(f => f.value).map(({ label, value }) => (
                <div key={label} style={{ background: 'var(--bg3)', borderRadius: 8, padding: '8px 12px' }}>
                  <div style={{ fontSize: 10, color: 'var(--text3)', marginBottom: 2 }}>{label}</div>
                  <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text)' }}>{String(value)}</div>
                </div>
              ))}
            </div>

            {/* VIN segmenti */}
            <div style={{ marginTop: 12, padding: '8px 10px', background: 'var(--bg3)', borderRadius: 8 }}>
              <div style={{ fontSize: 10, color: 'var(--text3)', marginBottom: 4 }}>VIN STRUKTURA</div>
              <div style={{ fontFamily: 'monospace', fontSize: 13, letterSpacing: '0.1em' }}>
                <span style={{ color: '#818CF8' }}>{result.vin.slice(0, 3)}</span>
                <span style={{ color: 'var(--accent)' }}>{result.vin.slice(3, 9)}</span>
                <span style={{ color: '#22C55E' }}>{result.vin.slice(9)}</span>
              </div>
              <div style={{ fontSize: 10, color: 'var(--text3)', marginTop: 3 }}>
                <span style={{ color: '#818CF8' }}>WMI</span> · <span style={{ color: 'var(--accent)' }}>VDS</span> · <span style={{ color: '#22C55E' }}>VIS</span>
              </div>
            </div>
          </div>

          {/* Serbia eligibility */}
          <div style={{
            background: `${eligColor}11`, border: `1px solid ${eligColor}33`,
            borderRadius: 14, padding: '14px 16px',
          }}>
            <div style={{ fontSize: 11, color: 'var(--text3)', fontWeight: 600, letterSpacing: '.07em', marginBottom: 6 }}>
              UVOZ U SRBIJU
            </div>
            <div style={{ fontSize: 15, fontWeight: 800, color: eligColor, marginBottom: 4 }}>
              {result.serbia_eligibility.emoji} {result.serbia_eligibility.label}
            </div>
            <p style={{ fontSize: 13, color: 'var(--text2)', margin: '0 0 8px', lineHeight: 1.5 }}>
              {result.serbia_eligibility.reason}
            </p>
            {result.serbia_eligibility.carina_pct !== undefined && (
              <div style={{ fontSize: 12, color: 'var(--text3)' }}>
                Carina: <strong style={{ color: eligColor }}>{result.serbia_eligibility.carina_pct}%</strong>
                {result.serbia_eligibility.carina_pct === 0 && ' (oslobođeno)'}
              </div>
            )}
          </div>

          {/* Budući provajderi */}
          <div style={{
            background: 'var(--bg2)', border: '1px dashed rgba(255,255,255,.1)',
            borderRadius: 12, padding: '12px 16px',
          }}>
            <div style={{ fontSize: 11, color: 'var(--text3)', fontWeight: 600, marginBottom: 6 }}>
              🔮 DETALJNA ISTORIJA VOZILA — USKORO
            </div>
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              {['CarVertical', 'AutoDNA', 'CARFAX'].map(p => (
                <span key={p} style={{
                  fontSize: 11, padding: '3px 10px', borderRadius: 20,
                  background: 'var(--bg3)', border: '1px solid var(--border)',
                  color: 'var(--text3)',
                }}>{p}</span>
              ))}
            </div>
            <p style={{ fontSize: 11, color: 'var(--text3)', margin: '6px 0 0', lineHeight: 1.5, opacity: .7 }}>
              Provera nesreća, servisa, krađe i vlasnika — u sledećoj verziji.
            </p>
          </div>

          {/* Kopiraj VIN */}
          <button
            onClick={() => { navigator.clipboard.writeText(result.vin); setCopied(true); setTimeout(() => setCopied(false), 2000) }}
            style={{
              width: '100%', padding: '10px', borderRadius: 10,
              background: copied ? 'rgba(34,197,94,.1)' : 'transparent',
              border: `1px solid ${copied ? '#22C55E' : 'var(--border)'}`,
              color: copied ? '#22C55E' : 'var(--text3)',
              fontSize: 13, fontWeight: 600, cursor: 'pointer',
            }}
          >
            {copied ? '✓ VIN kopiran!' : `📋 Kopiraj VIN: ${result.vin}`}
          </button>
        </div>
      )}
    </div>
  )
}
