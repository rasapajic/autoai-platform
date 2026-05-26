'use client'
import { useEffect, useState } from 'react'

export default function NotFound() {
  const [countdown, setCountdown] = useState(5)

  useEffect(() => {
    const interval = setInterval(() => {
      setCountdown(prev => {
        if (prev <= 1) {
          clearInterval(interval)
          window.location.href = '/'
          return 0
        }
        return prev - 1
      })
    }, 1000)
    return () => clearInterval(interval)
  }, [])

  return (
    <div style={{
      minHeight: '80vh', display: 'flex', alignItems: 'center',
      justifyContent: 'center', padding: 20,
    }}>
      <div style={{ textAlign: 'center', maxWidth: 480 }}>
        <div style={{ fontSize: 80, marginBottom: 16 }}>🚗</div>
        <h1 style={{
          fontSize: 32, fontFamily: 'Syne,sans-serif',
          marginBottom: 12, letterSpacing: '-0.03em',
        }}>
          Stranica nije pronađena
        </h1>
        <p style={{ color: 'var(--text3)', fontSize: 15, marginBottom: 32, lineHeight: 1.6 }}>
          Oglas koji tražiš možda više nije dostupan, ili je link neispravan.
        </p>

        <div style={{ display: 'flex', gap: 12, justifyContent: 'center', flexWrap: 'wrap' }}>
          <a href="/search" style={{
            padding: '13px 28px', borderRadius: 10,
            background: 'var(--accent)', color: '#fff',
            textDecoration: 'none', fontWeight: 700, fontSize: 15,
          }}>
            🔍 Pretraži automobile
          </a>
          <a href="/" style={{
            padding: '13px 28px', borderRadius: 10,
            background: 'var(--bg2)', color: 'var(--text2)',
            border: '1px solid var(--border)',
            textDecoration: 'none', fontWeight: 600, fontSize: 15,
          }}>
            Početna
          </a>
        </div>

        <p style={{ color: 'var(--text3)', fontSize: 13, marginTop: 32, opacity: .6 }}>
          Automatski redirect za {countdown}s...
        </p>
      </div>
    </div>
  )
}
