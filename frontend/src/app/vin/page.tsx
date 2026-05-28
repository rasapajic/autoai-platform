'use client'
import VinChecker from '@/components/VinChecker'

export default function VinPage() {
  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg)', paddingBottom: 80 }}>
      <div className="container" style={{ maxWidth: 640, padding: '32px 16px 0' }}>

        {/* Hero */}
        <div style={{ textAlign: 'center', marginBottom: 28 }}>
          <div style={{ fontSize: 40, marginBottom: 10 }}>🔐</div>
          <h1 style={{ fontSize: 26, fontWeight: 800, fontFamily: 'Syne,sans-serif', margin: '0 0 10px' }}>
            VIN Provera Vozila
          </h1>
          <p style={{ fontSize: 14, color: 'var(--text2)', margin: 0, lineHeight: 1.6 }}>
            Unesi VIN broj koji si dobio od prodavca.<br />
            AutoAI proverava podatke i analizira uslove uvoza u Srbiju.
          </p>
          <div style={{ display: 'flex', gap: 8, justifyContent: 'center', flexWrap: 'wrap', marginTop: 14 }}>
            {['✓ Besplatno', '✓ Bez registracije', '✓ NHTSA baza', '✓ Uvoz analiza'].map(t => (
              <span key={t} style={{ fontSize: 12, color: 'var(--text3)', padding: '4px 10px', borderRadius: 20, background: 'var(--bg2)', border: '1px solid var(--border)' }}>{t}</span>
            ))}
          </div>
        </div>

        <VinChecker />

        <p style={{ fontSize: 11, color: 'var(--text3)', textAlign: 'center', marginTop: 20, lineHeight: 1.6, opacity: .7 }}>
          * Podaci su informatvni. NHTSA baza je primarno US-fokusirana — EU vozila mogu imati delimične podatke.
        </p>
      </div>
    </div>
  )
}
