'use client'
import { useState, useEffect } from 'react'
import './globals.css'

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="sr">
      <body>
        <Navbar />
        <main>{children}</main>
        <Footer />
      </body>
    </html>
  )
}

function Navbar() {
  const [userEmail, setUserEmail] = useState<string | null>(null)

  useEffect(() => {
    setUserEmail(localStorage.getItem('autoai_email'))
  }, [])

  const handleLogout = () => {
    localStorage.removeItem('autoai_token')
    localStorage.removeItem('autoai_email')
    window.location.href = '/'
  }

  return (
    <header style={{
      position: 'sticky', top: 0, zIndex: 100,
      borderBottom: '1px solid var(--border)',
      background: 'rgba(12,12,14,.92)',
      backdropFilter: 'blur(12px)',
    }}>
      <div className="container" style={{
        display: 'flex', alignItems: 'center',
        justifyContent: 'space-between', height: 60,
      }}>
        <a href="/" style={{ display: 'flex', alignItems: 'center', gap: 10, textDecoration: 'none' }}>
          <div style={{
            width: 32, height: 32, borderRadius: 8,
            background: 'linear-gradient(135deg, var(--accent), #f43f5e)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 16,
          }}>🚗</div>
          <span style={{ fontFamily: 'Syne, sans-serif', fontWeight: 800, fontSize: 18, letterSpacing: '-0.04em', color: 'var(--text)' }}>
            Auto<span style={{ color: 'var(--accent)' }}>AI</span>
          </span>
        </a>

        <nav style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
          {[
            { href: '/search',            label: 'Pretraga' },
            { href: '/analyze',           label: 'Proveri oglas' },
            { href: '/import-calculator', label: 'Uvoz kalkulator' },
            { href: '/favorites', label: '❤️ Sačuvani' }
          ].map(link => (
            <a key={link.href} href={link.href} style={{
              padding: '6px 14px', borderRadius: 8, fontSize: 14,
              color: 'var(--text2)', transition: 'all .15s', textDecoration: 'none',
            }}
            onMouseEnter={e => { (e.target as HTMLElement).style.color = 'var(--text)'; (e.target as HTMLElement).style.background = 'var(--bg3)' }}
            onMouseLeave={e => { (e.target as HTMLElement).style.color = 'var(--text2)'; (e.target as HTMLElement).style.background = 'transparent' }}
            >{link.label}</a>
          ))}

          {userEmail ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginLeft: 8 }}>
              <span style={{
                fontSize: 13, color: 'var(--text2)',
                background: 'var(--bg3)', border: '1px solid var(--border)',
                padding: '6px 12px', borderRadius: 8,
              }}>
                👤 {userEmail.split('@')[0]}
              </span>
              <button onClick={handleLogout} style={{
                padding: '6px 12px', borderRadius: 8, fontSize: 13,
                background: 'transparent', border: '1px solid var(--border)',
                color: 'var(--text3)', cursor: 'pointer',
              }}>Odjava</button>
            </div>
          ) : (
            <div style={{ display: 'flex', gap: 4, marginLeft: 8 }}>
              <a href="/login" style={{
                padding: '7px 16px', borderRadius: 8, fontSize: 14, textDecoration: 'none',
                color: 'var(--text2)', border: '1px solid var(--border)', fontWeight: 500,
              }}>Prijava</a>
              <a href="/register" style={{
                padding: '7px 16px', borderRadius: 8, textDecoration: 'none',
                background: 'var(--accent)', color: '#fff', fontSize: 14, fontWeight: 500,
              }}>Registracija</a>
            </div>
          )}
        </nav>
      </div>
    </header>
  )
}

function Footer() {
  return (
    <footer style={{
      borderTop: '1px solid var(--border)', marginTop: 80,
      padding: '32px 0', color: 'var(--text3)', fontSize: 13,
    }}>
      <div className="container" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span>© 2026 AutoAI Platform</span>
        <span>Podaci sa AutoScout24 · Mobile.de</span>
      </div>
    </footer>
  )
}
