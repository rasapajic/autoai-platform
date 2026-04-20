'use client'
import { useState } from 'react'
import { useSearchParams } from 'next/navigation'
import { importCost } from '@/lib/api'

const COUNTRIES = ['DE','AT','FR','IT','NL','BE','PL','CZ','SK','HU','HR','SI','CH']
const FUEL_TYPES = ['diesel','petrol','electric','hybrid','lpg']

export default function ImportCalculatorPage() {
  const sp = useSearchParams()
  const [form, setForm] = useState({
    price_eur:    sp.get('price') || '',
    year:         sp.get('year') || '',
    engine_cc:    sp.get('cc') || '',
    fuel_type:    sp.get('fuel') || 'diesel',
    from_country: sp.get('from') || 'DE',
    to_country:   'RS',
  })
  const [result, setResult] = useState<any>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const calc = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!form.price_eur || !form.year) { setError('Unesite cenu i godište.'); return }
    setError(''); setLoading(true)
    try {
      const res = await importCost({
        price_eur:    Number(form.price_eur),
        year:         Number(form.year),
        engine_cc:    form.engine_cc ? Number(form.engine_cc) : null,
        fuel_type:    form.fuel_type || null,
        from_country: form.from_country,
        to_country:   form.to_country,
      })
      setResult(res)
    } catch (err: any) {
      setError('Greška u kalkulaciji. Pokušaj ponovo.')
    } finally { setLoading(false) }
  }

  const set = (key: string, val: string) => setForm(f => ({ ...f, [key]: val }))

  return (
    <div style={{ padding: '40px 0 80px' }}>
      <div className="container" style={{ maxWidth: 800 }}>

        <div style={{ marginBottom: 32 }}>
          <div style={{ fontSize: 12, color: 'var(--accent)', letterSpacing: '0.08em', marginBottom: 8 }}>ALAT</div>
          <h1 style={{ fontSize: 'clamp(1.8rem, 4vw, 2.6rem)', marginBottom: 12 }}>
            Kalkulator uvoza automobila<br/>
            <span style={{ color: 'var(--accent)' }}>u Srbiju</span>
          </h1>
          <p style={{ color: 'var(--text2)', fontSize: 15 }}>
            Izračunaj ukupan trošak uvoza — carina, PDV, akciza i transport.
          </p>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: result ? '1fr 1fr' : '1fr', gap: 24, alignItems: 'start' }}>

          {/* Form */}
          <form onSubmit={calc} style={{
            background: 'var(--bg2)', border: '1px solid var(--border)',
            borderRadius: 'var(--radius)', padding: 28,
          }}>
            <Field label="Cena vozila (EUR)" required>
              <input type="number" value={form.price_eur} onChange={e => set('price_eur', e.target.value)}
                placeholder="npr. 12500" style={iStyle} />
            </Field>

            <Field label="Godište" required>
              <input type="number" value={form.year} onChange={e => set('year', e.target.value)}
                placeholder="npr. 2019" style={iStyle} />
            </Field>

            <Field label="Kubikaza (cc)">
              <input type="number" value={form.engine_cc} onChange={e => set('engine_cc', e.target.value)}
                placeholder="npr. 1998" style={iStyle} />
            </Field>

            <Field label="Gorivo">
              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                {FUEL_TYPES.map(f => (
                  <button key={f} type="button" onClick={() => set('fuel_type', f)} style={{
                    padding: '6px 12px', borderRadius: 8, fontSize: 13, cursor: 'pointer',
                    background: form.fuel_type === f ? 'var(--accent)20' : 'var(--bg3)',
                    border: `1px solid ${form.fuel_type === f ? 'var(--accent)' : 'var(--border)'}`,
                    color: form.fuel_type === f ? 'var(--accent)' : 'var(--text3)',
                    transition: 'all .15s',
                  }}>{f}</button>
                ))}
              </div>
            </Field>

            <Field label="Uvoz iz">
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                {COUNTRIES.map(c => (
                  <button key={c} type="button" onClick={() => set('from_country', c)} style={{
                    width: 44, padding: '6px 0', borderRadius: 8, fontSize: 13, cursor: 'pointer',
                    background: form.from_country === c ? 'var(--accent)20' : 'var(--bg3)',
                    border: `1px solid ${form.from_country === c ? 'var(--accent)' : 'var(--border)'}`,
                    color: form.from_country === c ? 'var(--accent)' : 'var(--text3)',
                    fontWeight: form.from_country === c ? 600 : 400,
                    transition: 'all .15s',
                  }}>{c}</button>
                ))}
              </div>
            </Field>

            {error && <p style={{ color: '#EF4444', fontSize: 13, marginBottom: 12 }}>{error}</p>}

            <button type="submit" disabled={loading} style={{
              width: '100%', padding: 13, background: 'var(--accent)', color: '#fff',
              border: 'none', borderRadius: 10, fontSize: 15, fontWeight: 600, cursor: 'pointer',
              transition: 'opacity .15s',
            }}>{loading ? 'Računam...' : 'Izračunaj troškove →'}</button>
          </form>

          {/* Result */}
          {result && (
            <div style={{
              background: 'var(--bg2)', border: '1px solid var(--border)',
              borderRadius: 'var(--radius)', padding: 28,
            }}>
              <h2 style={{ fontSize: 17, marginBottom: 20 }}>Ukupni troškovi uvoza</h2>

              {result.breakdown?.map((row: any) => (
                <div key={row.stavka} style={{
                  display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                  padding: '10px 0', borderBottom: '1px solid var(--border)',
                  fontWeight: row.stavka === 'UKUPNO' ? 700 : 400,
                  fontSize: row.stavka === 'UKUPNO' ? 16 : 14,
                }}>
                  <span style={{ color: row.stavka === 'UKUPNO' ? 'var(--text)' : 'var(--text2)' }}>
                    {row.stavka}
                    {row.procenat && <span style={{ fontSize: 11, color: 'var(--text3)', marginLeft: 6 }}>({row.procenat})</span>}
                  </span>
                  <span style={{ color: row.stavka === 'UKUPNO' ? 'var(--accent)' : 'var(--text)' }}>
                    {Number(row.eur).toLocaleString()} €
                  </span>
                </div>
              ))}

              <div style={{
                marginTop: 16, background: 'var(--accent)10', border: '1px solid var(--accent)40',
                borderRadius: 10, padding: 16,
              }}>
                <div style={{ fontSize: 12, color: 'var(--text3)', marginBottom: 4 }}>Ukupno u dinarima (~117 RSD/€)</div>
                <div style={{ fontSize: 24, fontWeight: 800, color: 'var(--accent)' }}>
                  {Number(result.total_cost_rsd).toLocaleString()} RSD
                </div>
              </div>

              {result.notes?.length > 0 && (
                <div style={{ marginTop: 16 }}>
                  <div style={{ fontSize: 12, color: 'var(--text3)', marginBottom: 8 }}>NAPOMENE</div>
                  {result.notes.map((n: string) => (
                    <div key={n} style={{ fontSize: 12, color: 'var(--text2)', display: 'flex', gap: 8, marginBottom: 6 }}>
                      <span style={{ color: 'var(--accent)', flexShrink: 0 }}>i</span>
                      <span>{n}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Info box */}
        <div style={{
          marginTop: 24, background: 'var(--bg3)', border: '1px solid var(--border)',
          borderRadius: 'var(--radius)', padding: 20,
        }}>
          <p style={{ fontSize: 12, color: 'var(--text3)', lineHeight: 1.7 }}>
            ⚠️ <strong style={{ color: 'var(--text2)' }}>Napomena:</strong> Ove kalkulacije su aproksimativne i služe kao orijentacija.
            Tačne iznose potvrdi kod carinskog agenta pre uvoza. Poreske stope se mogu promeniti.
            Procena transporta zavisi od konkretnog prevoznika.
          </p>
        </div>
      </div>
    </div>
  )
}

function Field({ label, children, required }: { label: string, children: React.ReactNode, required?: boolean }) {
  return (
    <div style={{ marginBottom: 18 }}>
      <label style={{ display: 'block', fontSize: 12, color: 'var(--text3)', marginBottom: 6, letterSpacing: '0.05em' }}>
        {label.toUpperCase()}{required && <span style={{ color: 'var(--accent)', marginLeft: 4 }}>*</span>}
      </label>
      {children}
    </div>
  )
}

const iStyle: React.CSSProperties = {
  width: '100%', background: 'var(--bg3)', border: '1px solid var(--border)',
  borderRadius: 8, padding: '10px 14px', color: 'var(--text)', fontSize: 14,
  outline: 'none', transition: 'border-color .15s',
}
