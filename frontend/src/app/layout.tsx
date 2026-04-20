import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'AutoAI — Polovni automobili u Evropi',
  description: 'AI pretraga polovnih automobila. Pronađi najbolju ponudu u Evropi.',
}

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
        <a href="/" style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{
            width: 32, height: 32, borderRadius: 8,
            background: 'linear-gradient(135deg, var(--accent), #f43f5e)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 16,
          }}>🚗</div>
          <span style={{ fontFamily: 'Syne, sans-serif', fontWeight: 800, fontSize: 18, letterSpacing: '-0.04em' }}>
            Auto<span style={{ color: 'var(--accent)' }}>AI</span>
          </span>
        </a>

        <nav style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
          {[
            { href: '/search', label: 'Pretraga' },
            { href: '/import-calculator', label: 'Uvoz kalkulator' },
          ].map(link => (
            <a key={link.href} href={link.href} style={{
              padding: '6px 14px', borderRadius: 8, fontSize: 14,
              color: 'var(--text2)', transition: 'all .15s',
            }}
            onMouseEnter={e => { (e.target as HTMLElement).style.color = 'var(--text)'; (e.target as HTMLElement).style.background = 'var(--bg3)' }}
            onMouseLeave={e => { (e.target as HTMLElement).style.color = 'var(--text2)'; (e.target as HTMLElement).style.background = 'transparent' }}
            >{link.label}</a>
          ))}
          <a href="/search" style={{
            marginLeft: 8, padding: '7px 16px', borderRadius: 8,
            background: 'var(--accent)', color: '#fff', fontSize: 14, fontWeight: 500,
          }}>Traži auto</a>
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
        <span>© 2025 AutoAI Platform</span>
        <span>Podaci sa AutoScout24, Polovniautomobili, Mobile.de</span>
      </div>
    </footer>
  )
}
