'use client'
import { useState } from 'react'

const QUICK_QUESTIONS = [
  'Da li je auto imao udes?',
  'Da li postoji servisna istorija?',
  'Koja je poslednja cena?',
  'Da li je moguć izvoz?',
  'Da li je auto još dostupan?',
  'Koliko ima vlasnika?',
  'Da li postoje skrivene mane?',
  'Da li je moguća test vožnja?',
]

const COUNTRY_LANG: Record<string, { name: string; code: string }> = {
  DE: { name: 'Nemačkom (Deutsch)',     code: 'German'  },
  AT: { name: 'Nemačkom (Deutsch)',     code: 'German'  },
  CH: { name: 'Nemačkom (Deutsch)',     code: 'German'  },
  FR: { name: 'Francuskom (Français)', code: 'French'  },
  IT: { name: 'Italijanskom (Italiano)',code: 'Italian' },
  NL: { name: 'Holandskom (Nederlands)',code: 'Dutch'   },
  BE: { name: 'Holandskom (Nederlands)',code: 'Dutch'   },
  ES: { name: 'Španskom (Español)',     code: 'Spanish' },
  DK: { name: 'Danskom (Dansk)',        code: 'Danish'  },
  SE: { name: 'Švedskom (Svenska)',     code: 'Swedish' },
  NO: { name: 'Norveškom (Norsk)',      code: 'Norwegian'},
  PL: { name: 'Poljskom (Polski)',      code: 'Polish'  },
}

interface Props {
  listing: any
  onClose: () => void
}

export default function ContactModal({ listing, onClose }: Props) {
  const [selected, setSelected] = useState<string[]>([])
  const [custom,   setCustom]   = useState('')
  const [loading,  setLoading]  = useState(false)
  const [message,  setMessage]  = useState('')
  const [copied,   setCopied]   = useState(false)
  const [error,    setError]    = useState('')

  const langInfo = COUNTRY_LANG[listing.country || 'DE'] || COUNTRY_LANG.DE

  const toggleQ = (q: string) =>
    setSelected(s => s.includes(q) ? s.filter(x => x !== q) : [...s, q])

  const canGenerate = selected.length > 0 || custom.trim().length > 0

  const generate = async () => {
    if (!canGenerate) return
    setLoading(true); setMessage(''); setError('')
    try {
      const res = await fetch('/api/contact-message', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          country:     listing.country || 'DE',
          make:        listing.make,
          model:       listing.model,
          year:        listing.year,
          price:       listing.price,
          questions:   selected,
          custom_text: custom,
        }),
      })
      if (!res.ok) throw new Error()
      const data = await res.json()
      setMessage(data.message || '')
    } catch {
      setError('Greška pri generisanju. Pokušaj ponovo.')
    } finally { setLoading(false) }
  }

  const copy = () => {
    navigator.clipboard.writeText(message)
    setCopied(true); setTimeout(() => setCopied(false), 2200)
  }

 const openEmail = () => {
    const sub  = encodeURIComponent(`Inquiry: ${listing.year || ''} ${listing.make || ''} ${listing.model || ''}`)
    const body = encodeURIComponent(message)
    window.location.href = `mailto:?subject=${sub}&body=${body}`
}
  return (
    <div
      onClick={e => { if (e.target === e.currentTarget) onClose() }}
      style={{
        position: 'fixed', inset: 0, zIndex: 1000,
        background: 'rgba(0,0,0,.78)', backdropFilter: 'blur(6px)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        padding: 20,
      }}
    >
      <div style={{
        background: 'var(--bg2)', border: '1px solid var(--border)',
        borderRadius: 20, width: '100%', maxWidth: 560,
        maxHeight: '92vh', overflowY: 'auto',
        boxShadow: '0 28px 90px rgba(0,0,0,.65)',
      }}>

        {/* Header */}
        <div style={{
          padding: '20px 24px', borderBottom: '1px solid var(--border)',
          display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start',
        }}>
          <div>
            <h2 style={{ fontSize: 18, fontWeight: 700, margin: '0 0 5px', fontFamily: 'Syne,sans-serif' }}>
              🤖 Kontaktiraj prodavca
            </h2>
            <p style={{ fontSize: 13, color: 'var(--text3)', margin: 0 }}>
              AI generiše profesionalnu poruku na <strong style={{ color: 'var(--accent)' }}>{langInfo.name}</strong>
            </p>
          </div>
          <button onClick={onClose} style={{
            background: 'none', border: 'none', color: 'var(--text3)',
            fontSize: 22, cursor: 'pointer', padding: '0 4px', lineHeight: 1,
          }}>✕</button>
        </div>

        <div style={{ padding: '20px 24px' }}>

          {/* Listing chip */}
          <div style={{
            background: 'var(--bg3)', borderRadius: 10, padding: '10px 14px',
            marginBottom: 22, display: 'flex', alignItems: 'center', gap: 12,
          }}>
            <span style={{ fontSize: 22 }}>🚗</span>
            <div>
              <div style={{ fontWeight: 600, fontSize: 14 }}>
                {listing.year && `${listing.year} `}{listing.make} {listing.model}
              </div>
              <div style={{ color: 'var(--text3)', fontSize: 13 }}>
                {listing.price ? `${Number(listing.price).toLocaleString()} €` : ''} · {listing.country}
              </div>
            </div>
          </div>

          {/* Quick questions */}
          <div style={{ marginBottom: 18 }}>
            <p style={{ fontSize: 11, color: 'var(--text3)', margin: '0 0 10px', fontWeight: 600, letterSpacing: '.07em' }}>
              BRZA PITANJA (odaberi jedno ili više)
            </p>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 7 }}>
              {QUICK_QUESTIONS.map(q => (
                <button key={q} onClick={() => toggleQ(q)} style={{
                  padding: '7px 13px', borderRadius: 20, fontSize: 12,
                  background: selected.includes(q) ? 'rgba(255,107,0,.14)' : 'var(--bg3)',
                  border: `1px solid ${selected.includes(q) ? 'var(--accent)' : 'var(--border)'}`,
                  color: selected.includes(q) ? 'var(--accent)' : 'var(--text2)',
                  cursor: 'pointer', transition: 'all .14s',
                }}>{q}</button>
              ))}
            </div>
          </div>

          {/* Custom input */}
          <div style={{ marginBottom: 20 }}>
            <p style={{ fontSize: 11, color: 'var(--text3)', margin: '0 0 8px', fontWeight: 600, letterSpacing: '.07em' }}>
              DODAJ VLASTITO PITANJE (opcionalno)
            </p>
            <textarea
              value={custom}
              onChange={e => setCustom(e.target.value)}
              placeholder='npr. "Pitaj da li je moguć uvoz u Srbiju i kakva je dokumentacija..."'
              rows={3}
              style={{
                width: '100%', background: 'var(--bg3)', border: '1px solid var(--border)',
                borderRadius: 10, padding: '12px 14px', color: 'var(--text)',
                fontSize: 13, outline: 'none', resize: 'none',
                boxSizing: 'border-box', fontFamily: 'inherit', lineHeight: 1.6,
              }}
            />
          </div>

          {/* Generate button */}
          <button
            onClick={generate}
            disabled={loading || !canGenerate}
            style={{
              width: '100%', padding: '14px', borderRadius: 12, border: 'none',
              background: (!canGenerate || loading) ? 'var(--bg3)' : 'var(--accent)',
              color: (!canGenerate || loading) ? 'var(--text3)' : '#fff',
              fontSize: 15, fontWeight: 700,
              cursor: (!canGenerate || loading) ? 'default' : 'pointer',
              marginBottom: 16, transition: 'all .2s',
            }}
          >
            {loading
              ? '⏳ Generišem poruku...'
              : `🤖 Generiši poruku na ${langInfo.name.split(' ')[0]}`}
          </button>

          {/* Error */}
          {error && (
            <p style={{ color: '#EF4444', fontSize: 13, textAlign: 'center', margin: '0 0 12px' }}>{error}</p>
          )}

          {/* Generated message */}
          {message && (
            <div>
              <div style={{
                display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                marginBottom: 8,
              }}>
                <span style={{ fontSize: 11, color: 'var(--text3)', fontWeight: 600, letterSpacing: '.07em' }}>
                  GENERISANA PORUKA
                </span>
                <span style={{
                  fontSize: 11, color: '#22C55E',
                  background: 'rgba(34,197,94,.1)', padding: '3px 9px', borderRadius: 10,
                }}>✓ Prevedeno AI-om</span>
              </div>

              <div style={{
                background: 'var(--bg3)', border: '1px solid var(--border)',
                borderRadius: 12, padding: '16px', marginBottom: 12,
                fontSize: 13, lineHeight: 1.75, color: 'var(--text2)',
                whiteSpace: 'pre-wrap',
              }}>{message}</div>

              <div style={{ display: 'flex', gap: 10, marginBottom: 12 }}>
                <button onClick={copy} style={{
                  flex: 1, padding: '11px', borderRadius: 10,
                  background: copied ? 'rgba(34,197,94,.12)' : 'var(--bg3)',
                  border: `1px solid ${copied ? '#22C55E' : 'var(--border)'}`,
                  color: copied ? '#22C55E' : 'var(--text2)',
                  fontSize: 13, fontWeight: 600, cursor: 'pointer', transition: 'all .15s',
                }}>{copied ? '✓ Kopirano!' : '📋 Kopiraj'}</button>

                <button onClick={openEmail} style={{
                  flex: 1, padding: '11px', borderRadius: 10,
                  background: 'rgba(255,107,0,.1)',
                  border: '1px solid rgba(255,107,0,.3)',
                  color: 'var(--accent)',
                  fontSize: 13, fontWeight: 600, cursor: 'pointer',
                }}>✉️ Otvori email</button>
              </div>

              <p style={{ fontSize: 11, color: 'var(--text3)', textAlign: 'center', margin: 0, lineHeight: 1.5 }}>
                Poruka je generisana AI-om. Preporučujemo da je pregledate pre slanja.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
