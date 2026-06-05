'use client'
import { useState, useEffect } from 'react'
import './globals.css'

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'https://autoai-platform-production.up.railway.app/api/v1'

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
  const [menuOpen,  setMenuOpen]  = useState(false)
  const [unread,    setUnread]    = useState(0)
  const [newSearches, setNewSearches] = useState(0)

  useEffect(() => {
    const email = localStorage.getItem('autoai_email')
    const token = localStorage.getItem('autoai_token')
    setUserEmail(email)

    if (token) {
      // Inbox badge
      fetch(`${API_BASE}/inbox/conversations/stats/summary`, {
        headers: { 'Authorization': `Bearer ${token}` }
      }).then(r => r.ok ? r.json() : null)
        .then(data => { if (data?.unread_replies) setUnread(data.unread_replies) })
        .catch(() => {})

      // Potrage badge — broj novih match-eva
      fetch(`${API_BASE}/alerts/`, {
        headers: { 'Authorization': `Bearer ${token}` }
      }).then(r => r.ok ? r.json() : null)
        .then(data => {
          if (Array.isArray(data)) {
            const total = data.reduce((acc: number, a: any) => acc + (a.new_matches_count || 0), 0)
            setNewSearches(total)
          }
        }).catch(() => {})
    }
  }, [])

  const handleLogout = () => {
    localStorage.removeItem('autoai_token')
    localStorage.removeItem('autoai_email')
    window.location.href = '/'
  }

  const links = [
    { href:'/search',            label:'Pretraga',      icon:'🔍' },
    { href:'/searches',          label:'Moje potrage',  icon:'🎯', badge: newSearches },
    { href:'/analyze',           label:'Proveri oglas', icon:'✓'  },
    { href:'/import-calculator', label:'Kalkulator',    icon:'🧮' },
    { href:'/inbox',             label:'Inbox',         icon:'📬', badge: unread },
    { href:'/favorites',         label:'Sačuvani',      icon:'❤️' },
    { href:'/profile',           label:'Profil',        icon:'👤' },
  ]

  return (
    <header style={{ position:'sticky', top:0, zIndex:100, borderBottom:'1px solid var(--border)', background:'rgba(12,12,14,.95)', backdropFilter:'blur(12px)' }}>
      <style>{`
        @media(max-width:768px){.nav-desktop{display:none!important}.nav-hamburger{display:flex!important}}
        @media(min-width:769px){.nav-mobile-menu{display:none!important}.nav-hamburger{display:none!important}}
        .navlink:hover{color:var(--text)!important;background:var(--bg3)!important}
      `}</style>

      <div className="container" style={{ display:'flex', alignItems:'center', justifyContent:'space-between', height:56, gap:8 }}>
        {/* Logo */}
        <a href="/" style={{ display:'flex', alignItems:'center', gap:8, textDecoration:'none', flexShrink:0 }}>
          <div style={{ width:30, height:30, borderRadius:8, background:'linear-gradient(135deg,var(--accent),#f43f5e)', display:'flex', alignItems:'center', justifyContent:'center', fontSize:15 }}>🚗</div>
          <span style={{ fontFamily:'Syne,sans-serif', fontWeight:800, fontSize:17, letterSpacing:'-0.04em', color:'var(--text)' }}>
            Auto<span style={{ color:'var(--accent)' }}>AI</span>
          </span>
        </a>

        {/* Desktop nav */}
        <nav className="nav-desktop" style={{ display:'flex', gap:2, alignItems:'center' }}>
          {links.map(link => (
            <a key={link.href} href={link.href} className="navlink" style={{
              padding:'6px 12px', borderRadius:8, fontSize:13, color:'var(--text2)',
              textDecoration:'none', transition:'all .15s', position:'relative',
              display:'inline-flex', alignItems:'center', gap:5,
            }}>
              {link.href === '/searches' ? (
                <span style={{ fontWeight:600, color:'var(--text2)' }}>🎯 Moje potrage</span>
              ) : link.label}
              {(link.badge || 0) > 0 && (
                <span style={{
                  fontSize:10, borderRadius:20, padding:'1px 6px', fontWeight:700, lineHeight:1.4,
                  background: link.href === '/searches' ? 'rgba(255,107,0,.2)' : '#EF4444',
                  color: link.href === '/searches' ? 'var(--accent)' : '#fff',
                  border: link.href === '/searches' ? '1px solid rgba(255,107,0,.4)' : 'none',
                }}>
                  {link.badge}
                </span>
              )}
            </a>
          ))}
          {userEmail ? (
            <div style={{ display:'flex', alignItems:'center', gap:6, marginLeft:8 }}>
              <span style={{ fontSize:12, color:'var(--text2)', background:'var(--bg3)', border:'1px solid var(--border)', padding:'5px 10px', borderRadius:8 }}>
                👤 {userEmail.split('@')[0]}
              </span>
              <button onClick={handleLogout} style={{ padding:'5px 10px', borderRadius:8, fontSize:12, background:'transparent', border:'1px solid var(--border)', color:'var(--text3)', cursor:'pointer' }}>
                Odjava
              </button>
            </div>
          ) : (
            <div style={{ display:'flex', gap:4, marginLeft:8 }}>
              <a href="/login"    style={{ padding:'6px 14px', borderRadius:8, fontSize:13, textDecoration:'none', color:'var(--text2)', border:'1px solid var(--border)', fontWeight:500 }}>Prijava</a>
              <a href="/register" style={{ padding:'6px 14px', borderRadius:8, textDecoration:'none', background:'var(--accent)', color:'#fff', fontSize:13, fontWeight:500 }}>Registracija</a>
            </div>
          )}
        </nav>

        {/* Mobile right */}
        <div className="nav-hamburger" style={{ display:'none', alignItems:'center', gap:8 }}>
          {userEmail
            ? <span style={{ fontSize:12, color:'var(--text2)', background:'var(--bg3)', border:'1px solid var(--border)', padding:'5px 10px', borderRadius:8 }}>👤 {userEmail.split('@')[0]}</span>
            : <a href="/register" style={{ padding:'6px 12px', borderRadius:8, textDecoration:'none', background:'var(--accent)', color:'#fff', fontSize:13, fontWeight:600 }}>Registracija</a>
          }
          <button onClick={() => setMenuOpen(!menuOpen)} style={{ background:'var(--bg3)', border:'1px solid var(--border)', borderRadius:8, padding:'6px 10px', color:'var(--text)', fontSize:18, cursor:'pointer', lineHeight:1, position:'relative' }}>
            {menuOpen ? '✕' : '☰'}
            {(unread + newSearches) > 0 && !menuOpen && (
              <span style={{ position:'absolute', top:-4, right:-4, width:16, height:16, background:'var(--accent)', borderRadius:'50%', fontSize:9, color:'#fff', display:'flex', alignItems:'center', justifyContent:'center', fontWeight:700 }}>
                {unread + newSearches}
              </span>
            )}
          </button>
        </div>
      </div>

      {/* Mobile dropdown */}
      {menuOpen && (
        <div className="nav-mobile-menu" style={{ background:'var(--bg2)', borderTop:'1px solid var(--border)', padding:'12px 16px 16px' }}>
          <div style={{ display:'flex', flexDirection:'column', gap:4 }}>
            {links.map(link => (
              <a key={link.href} href={link.href} onClick={() => setMenuOpen(false)} style={{
                padding:'10px 14px', borderRadius:8, fontSize:14, color:'var(--text2)',
                textDecoration:'none', background:'var(--bg3)', border:'1px solid var(--border)',
                display:'flex', justifyContent:'space-between', alignItems:'center',
              }}>
                <span>{link.icon} {link.label}</span>
                {(link.badge || 0) > 0 && (
                  <span style={{
                    fontSize:11, borderRadius:20, padding:'2px 8px', fontWeight:700,
                    background: link.href === '/searches' ? 'rgba(255,107,0,.2)' : '#EF4444',
                    color: link.href === '/searches' ? 'var(--accent)' : '#fff',
                    border: link.href === '/searches' ? '1px solid rgba(255,107,0,.4)' : 'none',
                  }}>
                    {link.badge}
                  </span>
                )}
              </a>
            ))}
            <div style={{ borderTop:'1px solid var(--border)', marginTop:8, paddingTop:8 }}>
              {userEmail
                ? <button onClick={handleLogout} style={{ width:'100%', padding:'10px', borderRadius:8, fontSize:13, background:'transparent', border:'1px solid var(--border)', color:'var(--text3)', cursor:'pointer' }}>Odjava</button>
                : <div style={{ display:'flex', gap:8 }}>
                    <a href="/login"    style={{ flex:1, padding:'10px', borderRadius:8, fontSize:13, textDecoration:'none', color:'var(--text2)', border:'1px solid var(--border)', fontWeight:500, textAlign:'center' as any }}>Prijava</a>
                    <a href="/register" style={{ flex:1, padding:'10px', borderRadius:8, textDecoration:'none', background:'var(--accent)', color:'#fff', fontSize:13, fontWeight:500, textAlign:'center' as any }}>Registracija</a>
                  </div>
              }
            </div>
          </div>
        </div>
      )}
    </header>
  )
}

function Footer() {
  return (
    <footer style={{ borderTop:'1px solid var(--border)', marginTop:80, padding:'32px 0', color:'var(--text3)', fontSize:13 }}>
      <div className="container" style={{ display:'flex', justifyContent:'space-between', alignItems:'center' }}>
        <span>© 2026 AutoAI Platform</span>
        <span>AutoScout24 · Willhaben · Marktplaats · 2dehands · Kleinanzeigen</span>
      </div>
    </footer>
  )
}
