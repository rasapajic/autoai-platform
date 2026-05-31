'use client'
import { useState, useEffect } from 'react'

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'https://autoai-platform-production.up.railway.app/api/v1'

const QUICK_QUESTIONS = [
  'Da li je auto imao udes?',
  'Da li postoji servisna istorija?',
  'Koja je poslednja cena?',
  'Da li je moguć izvoz?',
  'Da li je auto još dostupan?',
  'Koliko ima vlasnika?',
  'Da li postoje skrivene mane?',
  'Da li je moguća test vožnja?',
  'Da li je moguće ukloniti MwSt (PDV) za izvoz van EU?',
]

const COUNTRY_LANG: Record<string, { name: string; code: string }> = {
  DE: { name: 'Nemačkom (Deutsch)',       code: 'German'    },
  AT: { name: 'Nemačkom (Deutsch)',       code: 'German'    },
  CH: { name: 'Nemačkom (Deutsch)',       code: 'German'    },
  FR: { name: 'Francuskom (Français)',   code: 'French'    },
  IT: { name: 'Italijanskom (Italiano)',  code: 'Italian'   },
  NL: { name: 'Holandskom (Nederlands)', code: 'Dutch'     },
  BE: { name: 'Holandskom (Nederlands)', code: 'Dutch'     },
  ES: { name: 'Španskom (Español)',       code: 'Spanish'   },
  DK: { name: 'Danskom (Dansk)',          code: 'Danish'    },
  SE: { name: 'Švedskom (Svenska)',       code: 'Swedish'   },
  NO: { name: 'Norveškom (Norsk)',        code: 'Norwegian' },
  PL: { name: 'Poljskom (Polski)',        code: 'Polish'    },
}

const VIN_MESSAGES: Record<string, string> = {
  German:    'Könnten Sie mir bitte die Fahrgestellnummer (VIN/Chassisnummer) mitteilen, damit ich das Fahrzeug und die Importbedingungen überprüfen kann?',
  Dutch:     'Kunt u mij alstublieft het VIN/chassisnummer sturen zodat ik het voertuig en de importvoorwaarden kan controleren?',
  French:    "Pourriez-vous me communiquer le numéro de châssis (VIN) afin que je puisse vérifier le véhicule et les conditions d'importation?",
  Italian:   'Potrebbe fornirmi il numero di telaio (VIN) per poter verificare il veicolo e le condizioni di importazione?',
  Spanish:   '¿Podría proporcionarme el número de bastidor (VIN) para verificar el vehículo y las condiciones de importación?',
  Danish:    'Må jeg bede om køretøjets stelnummer (VIN), så jeg kan verificere køretøjet og importbetingelserne?',
  Swedish:   'Kan du skicka fordonets chassinummer (VIN) så att jag kan kontrollera fordonet och importvillkoren?',
  Norwegian: 'Kan du oppgi kjøretøyets chassisnummer (VIN) slik at jeg kan verifisere kjøretøyet og importbetingelsene?',
  Polish:    'Czy mógłby Pan/Pani podać numer VIN pojazdu, abym mógł zweryfikować pojazd i warunki importu?',
}

interface Props {
  listing: any
  onClose: () => void
}

export default function ContactModal({ listing, onClose }: Props) {
  const [selected,     setSelected]     = useState<string[]>([])
  const [vinRequested, setVinRequested] = useState(false)
  const [custom,       setCustom]       = useState('')
  const [loading,      setLoading]      = useState(false)
  const [message,      setMessage]      = useState('')
  const [copied,       setCopied]       = useState(false)
  const [error,        setError]        = useState('')
  const [userName,     setUserName]     = useState('')
  const [savedToInbox, setSavedToInbox] = useState(false)
  const [savingInbox,  setSavingInbox]  = useState(false)

  useEffect(() => {
    const name = localStorage.getItem('autoai_name') || ''
    setUserName(name)
  }, [])

  const detectCountry = (): string => {
    if (listing.country && listing.country.length <= 3) return listing.country
    const city = (listing.city || listing.country || '').toLowerCase()
    if (/napoli|roma|milano|torino|firenze|venezia|bologna|palermo|genova|cardito|bari|catania/i.test(city)) return 'IT'
    if (/paris|lyon|marseille|bordeaux|toulouse|nice|nantes|strasbourg|lille|rennes/i.test(city)) return 'FR'
    if (/wien|graz|salzburg|linz|innsbruck|klagenfurt|wels/i.test(city)) return 'AT'
    if (/amsterdam|rotterdam|utrecht|den haag|eindhoven|tilburg|groningen/i.test(city)) return 'NL'
    if (/madrid|barcelona|sevilla|valencia|bilbao|zaragoza|malaga/i.test(city)) return 'ES'
    if (/warsaw|krakow|gdansk|wroclaw|poznan|lodz|katowice/i.test(city)) return 'PL'
    if (/stockholm|göteborg|malmö|uppsala|västerås/i.test(city)) return 'SE'
    if (/copenhagen|aarhus|odense|aalborg/i.test(city)) return 'DK'
    return 'DE'
  }

  const country  = detectCountry()
  const langInfo = COUNTRY_LANG[country] || COUNTRY_LANG.DE
  const vinMsg   = VIN_MESSAGES[langInfo.code] || VIN_MESSAGES.German

  const toggleQ = (q: string) =>
    setSelected(s => s.includes(q) ? s.filter(x => x !== q) : [...s, q])

  const canGenerate = vinRequested || selected.length > 0 || custom.trim().length > 0

  const injectName = (msg: string): string => {
    if (!userName) return msg
    return msg
      .replace(/\[Name\]/g, userName)
      .replace(/\[Ihr Name\]/g, userName)
      .replace(/\[Vaše ime\]/g, userName)
      .replace(/\[Your Name\]/g, userName)
      .replace(/\[Naam\]/g, userName)
      .replace(/\[Votre nom\]/g, userName)
      .replace(/\[Suo nome\]/g, userName)
  }

  const generate = async () => {
    if (!canGenerate) return
    setLoading(true); setMessage(''); setError('')
    const vinQuestion  = vinRequested ? `[VIN] ${vinMsg}` : null
    const allQuestions = [...(vinQuestion ? [vinQuestion] : []), ...selected]
    try {
      const res = await fetch('/api/contact-message', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          country, make: listing.make, model: listing.model,
          year: listing.year, price: listing.price,
          questions: allQuestions, custom_text: custom,
          vin_requested: vinRequested,
          sender_name: userName || null,
        }),
      })
      if (!res.ok) throw new Error()
      const data = await res.json()
      setMessage(injectName(data.message || ''))
    } catch {
      setError('Greška pri generisanju. Pokušaj ponovo.')
    } finally { setLoading(false) }
  }

  const saveToInbox = async () => {
    if (!message || savedToInbox) return
    const token = localStorage.getItem('autoai_token')
    if (!token) { window.location.href = '/login'; return }
    setSavingInbox(true)
    try {
      const res = await fetch(`${API_BASE}/inbox/conversations`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
        body: JSON.stringify({
          listing_id:      listing.id || null,
          listing_title:   `${listing.year || ''} ${listing.make || ''} ${listing.model || ''}`.trim(),
          listing_url:     listing.url || null,
          listing_price:   listing.price ? Number(listing.price) : null,
          listing_source:  listing.source || null,
          seller_language: langInfo.name,
          seller_country:  country,
          message_content: message,
          questions_asked: selected,
          vin_requested:   vinRequested,
        }),
      })
      if (res.ok) setSavedToInbox(true)
    } catch {}
    setSavingInbox(false)
  }

  const copy = () => {
    navigator.clipboard.writeText(message)
    setCopied(true); setTimeout(() => setCopied(false), 2200)
  }

  const openWhatsApp = () =>
    window.open(`https://wa.me/?text=${encodeURIComponent(message)}`, '_blank')

  const openGmail = () => {
    const sub  = encodeURIComponent(`Inquiry: ${listing.year || ''} ${listing.make || ''} ${listing.model || ''}`)
    const body = encodeURIComponent(message)
    window.open(`https://mail.google.com/mail/?view=cm&fs=1&su=${sub}&body=${body}`, '_blank')
  }

  return (
    <div
      onClick={e => { if (e.target === e.currentTarget) onClose() }}
      style={{ position:'fixed', inset:0, zIndex:1000, background:'rgba(0,0,0,.78)', backdropFilter:'blur(6px)', display:'flex', alignItems:'center', justifyContent:'center', padding:20 }}
    >
      <div style={{ background:'var(--bg2)', border:'1px solid var(--border)', borderRadius:20, width:'100%', maxWidth:560, maxHeight:'92vh', overflowY:'auto', boxShadow:'0 28px 90px rgba(0,0,0,.65)' }}>

        <div style={{ padding:'20px 24px', borderBottom:'1px solid var(--border)', display:'flex', justifyContent:'space-between', alignItems:'flex-start' }}>
          <div>
            <h2 style={{ fontSize:18, fontWeight:700, margin:'0 0 5px', fontFamily:'Syne,sans-serif' }}>🤖 Kontaktiraj prodavca</h2>
            <p style={{ fontSize:13, color:'var(--text3)', margin:0 }}>
              AI generiše profesionalnu poruku na{' '}
              <strong style={{ color:'var(--accent)' }}>{langInfo.name}</strong>
              {userName && <span style={{ color:'var(--text3)' }}> · potpisano kao <strong style={{ color:'var(--text2)' }}>{userName}</strong></span>}
            </p>
          </div>
          <button onClick={onClose} style={{ background:'none', border:'none', color:'var(--text3)', fontSize:22, cursor:'pointer', padding:'0 4px', lineHeight:1 }}>✕</button>
        </div>

        <div style={{ padding:'20px 24px' }}>

          {!userName && (
            <div style={{ background:'rgba(255,107,0,.07)', border:'1px solid rgba(255,107,0,.25)', borderRadius:12, padding:'12px 16px', marginBottom:18, display:'flex', gap:10, alignItems:'center' }}>
              <span style={{ fontSize:20 }}>👤</span>
              <div style={{ flex:1 }}>
                <div style={{ fontSize:12, color:'var(--text3)', marginBottom:6 }}>Upiši svoje ime za automatski potpis:</div>
                <input
                  placeholder="Tvoje ime i prezime"
                  onBlur={e => { const v = e.target.value.trim(); if (v) { setUserName(v); localStorage.setItem('autoai_name', v) } }}
                  style={{ width:'100%', boxSizing:'border-box' as any, background:'var(--bg3)', border:'1px solid var(--border)', borderRadius:8, padding:'8px 12px', color:'var(--text)', fontSize:13, outline:'none' }}
                />
              </div>
            </div>
          )}

          <div style={{ background:'var(--bg3)', borderRadius:10, padding:'10px 14px', marginBottom:22, display:'flex', alignItems:'center', gap:12 }}>
            <span style={{ fontSize:22 }}>🚗</span>
            <div>
              <div style={{ fontWeight:600, fontSize:14 }}>
                {listing.year && `${listing.year} `}{listing.make} {listing.model}
              </div>
              <div style={{ color:'var(--text3)', fontSize:13 }}>
                {listing.price ? `${Number(listing.price).toLocaleString()} €` : ''}
                {listing.city ? ` · ${listing.city}` : ''}
                {listing.country ? ` · ${listing.country}` : ''}
              </div>
            </div>
          </div>

          <div style={{
            marginBottom:22,
            background: vinRequested ? 'linear-gradient(135deg, rgba(34,197,94,.08), rgba(34,197,94,.04))' : 'linear-gradient(135deg, rgba(99,102,241,.08), rgba(99,102,241,.04))',
            border: `2px solid ${vinRequested ? 'rgba(34,197,94,.4)' : 'rgba(99,102,241,.35)'}`,
            borderRadius:14, padding:'16px 18px', transition:'all .25s',
          }}>
            <div style={{ display:'flex', alignItems:'center', gap:10, marginBottom:8 }}>
              <span style={{ fontSize:22 }}>🔐</span>
              <div>
                <div style={{ fontSize:14, fontWeight:700, color:vinRequested?'#22C55E':'#818CF8' }}>Sigurnosna provera vozila</div>
                <div style={{ fontSize:11, color:'var(--text3)', marginTop:1 }}>PREPORUČEN KORAK · VISOKA VAŽNOST</div>
              </div>
              {vinRequested && (
                <span style={{ marginLeft:'auto', fontSize:11, fontWeight:700, color:'#22C55E', background:'rgba(34,197,94,.12)', border:'1px solid rgba(34,197,94,.3)', padding:'3px 10px', borderRadius:20 }}>✓ Dodato</span>
              )}
            </div>
            <p style={{ fontSize:13, color:'var(--text2)', margin:'0 0 12px', lineHeight:1.55 }}>
              Zatraži VIN broj radi detaljne provere vozila, Euro norme i istorije.
            </p>
            <div style={{ background:'rgba(0,0,0,.2)', borderRadius:8, padding:'10px 13px', marginBottom:12, fontSize:12, color:'var(--text3)', fontStyle:'italic', lineHeight:1.5, borderLeft:'3px solid rgba(99,102,241,.4)' }}>
              "{vinMsg}"
            </div>
            <button onClick={() => setVinRequested(v => !v)} style={{
              width:'100%', padding:'12px', borderRadius:10, cursor:'pointer', fontSize:14, fontWeight:700, transition:'all .2s',
              background: vinRequested ? 'rgba(34,197,94,.15)' : 'linear-gradient(135deg, rgba(99,102,241,.25), rgba(99,102,241,.15))',
              color: vinRequested ? '#22C55E' : '#818CF8',
              border: `1px solid ${vinRequested ? 'rgba(34,197,94,.4)' : 'rgba(99,102,241,.4)'}` as any,
            }}>
              {vinRequested ? '✓ VIN zahtev dodat u poruku' : '🔐 Zatraži VIN broj'}
            </button>
          </div>

          <div style={{ marginBottom:18 }}>
            <p style={{ fontSize:11, color:'var(--text3)', margin:'0 0 10px', fontWeight:600, letterSpacing:'.07em' }}>💬 DODATNA PITANJA (opcionalno)</p>
            <div style={{ display:'flex', flexWrap:'wrap', gap:8 }}>
              {QUICK_QUESTIONS.map(q => (
                <button key={q} onClick={() => toggleQ(q)} style={{
                  padding:'8px 14px', borderRadius:20, fontSize:13, cursor:'pointer', transition:'all .14s',
                  background: selected.includes(q) ? 'rgba(255,107,0,.14)' : 'var(--bg3)',
                  border: `1px solid ${selected.includes(q) ? 'var(--accent)' : 'var(--border)'}`,
                  color: selected.includes(q) ? 'var(--accent)' : 'var(--text2)',
                }}>{q}</button>
              ))}
            </div>
          </div>

          <div style={{ marginBottom:20 }}>
            <p style={{ fontSize:11, color:'var(--text3)', margin:'0 0 8px', fontWeight:600, letterSpacing:'.07em' }}>DODAJ VLASTITO PITANJE (opcionalno)</p>
            <textarea value={custom} onChange={e => setCustom(e.target.value)}
              placeholder='npr. "Pitaj da li je moguć uvoz u Srbiju i kakva je dokumentacija..."'
              rows={3}
              style={{ width:'100%', background:'var(--bg3)', border:'1px solid var(--border)', borderRadius:10, padding:'12px 14px', color:'var(--text)', fontSize:13, outline:'none', resize:'none', boxSizing:'border-box' as any, fontFamily:'inherit', lineHeight:1.6 }}
            />
          </div>

          <button onClick={generate} disabled={loading || !canGenerate} style={{
            width:'100%', padding:'14px', borderRadius:12, border:'none',
            background: (!canGenerate || loading) ? 'var(--bg3)' : 'var(--accent)',
            color: (!canGenerate || loading) ? 'var(--text3)' : '#fff',
            fontSize:15, fontWeight:700, cursor:(!canGenerate||loading)?'default':'pointer',
            marginBottom:16, transition:'all .2s',
          }}>
            {loading ? '⏳ Generišem poruku...' : `🤖 Generiši poruku na ${langInfo.name.split(' ')[0]}`}
          </button>

          {error && <p style={{ color:'#EF4444', fontSize:13, textAlign:'center', margin:'0 0 12px' }}>{error}</p>}

          {message && (
            <div>
              <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:8 }}>
                <span style={{ fontSize:11, color:'var(--text3)', fontWeight:600, letterSpacing:'.07em' }}>GENERISANA PORUKA</span>
                <span style={{ fontSize:11, color:'#22C55E', background:'rgba(34,197,94,.1)', padding:'3px 9px', borderRadius:10 }}>✓ Prevedeno AI-om</span>
              </div>
              <div style={{ background:'var(--bg3)', border:'1px solid var(--border)', borderRadius:12, padding:'16px', marginBottom:12, fontSize:13, lineHeight:1.75, color:'var(--text2)', whiteSpace:'pre-wrap' }}>
                {message}
              </div>
              <div style={{ display:'flex', gap:8, marginBottom:10 }}>
                <button onClick={copy} style={{
                  flex:1, padding:'11px', borderRadius:10,
                  background: copied ? 'rgba(34,197,94,.12)' : 'var(--bg3)',
                  border: `1px solid ${copied ? '#22C55E' : 'var(--border)'}`,
                  color: copied ? '#22C55E' : 'var(--text2)',
                  fontSize:13, fontWeight:600, cursor:'pointer',
                }}>{copied ? '✓ Kopirano!' : '📋 Kopiraj'}</button>
                <button onClick={openWhatsApp} style={{ flex:1, padding:'11px', borderRadius:10, background:'rgba(37,211,102,.1)', border:'1px solid rgba(37,211,102,.35)', color:'#25D366', fontSize:13, fontWeight:600, cursor:'pointer' }}>
                  💬 WhatsApp
                </button>
                <button onClick={openGmail} style={{ flex:1, padding:'11px', borderRadius:10, background:'rgba(234,67,53,.1)', border:'1px solid rgba(234,67,53,.35)', color:'#EA4335', fontSize:13, fontWeight:600, cursor:'pointer' }}>
                  ✉️ Gmail
                </button>
              </div>
              <button onClick={saveToInbox} disabled={savingInbox || savedToInbox} style={{
                width:'100%', padding:'11px', borderRadius:10, marginBottom:10, cursor: savedToInbox ? 'default' : 'pointer',
                background: savedToInbox ? 'rgba(34,197,94,.1)' : 'rgba(99,102,241,.1)',
                border: `1px solid ${savedToInbox ? 'rgba(34,197,94,.4)' : 'rgba(99,102,241,.3)'}`,
                color: savedToInbox ? '#22C55E' : '#818CF8',
                fontSize:13, fontWeight:600, transition:'all .2s',
              }}>
                {savingInbox ? '⏳ Čuvam...' : savedToInbox ? '✅ Sačuvano u Inbox' : '📬 Sačuvaj u Inbox — prati odgovor'}
              </button>
              <p style={{ fontSize:11, color:'var(--text3)', textAlign:'center', margin:0, lineHeight:1.5 }}>
                Poruka je generisana AI-om. Preporučujemo da je pregledate pre slanja.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
