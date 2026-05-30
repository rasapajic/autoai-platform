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
  const [menuOpen,  setMenuOpen]  = useState(false)
  const [unread,    setUnread]    = useState(0)

  useEffect(() => {
    const email = localStorage.getItem('autoai_email')
    const token = localStorage.getItem('autoai_token')
    setUserEmail(email)

    // ✅ Učitaj broj nepročitanih poruka iz Inboxa
    if (token) {
      fetch(`${process.env.NEXT_PUBLIC_API_URL || 'https://autoai-platform-production.up.railway.app/api/v1'}/inbox/conversations/stats/summary`, {
        headers: { 'Authorization': `Bearer ${token}` }
      })
        .then(r => r.ok ? r.json() : null)
        .then(data => { if (data?.unread_replies) setUnread(data.unread_replies) })
        .catch(() => {})
    }
  }, [])

  const handleLogout = () => {
    localStorage.removeItem('autoai_token')
    localStorage.removeItem('autoai_email')
    window.location.href = '/'
  }

  const links = [
    { href: '/search',            label: 'Pretraga' },
    { href: '/analyze',           label: 'Proveri oglas' },
    { href: '/import-calculator', label: 'Kalkulator' },
    { href: '/inbox',             label: '📬 Inbox', badge: unread > 0 ? unread : 0 },
    { href: '/favorites',         label: '❤️ Sačuvani' },
    { href: '/profile',           label: '👤 Profil' },
  ]

  return (
    <header style={{
      position: 'sticky', top: 0, zIndex: 100,
      borderBottom: '1px solid var(--border)',
      background: 'rgba(12,12,14,.95)',
      backdropFilter: 'blur(12px)',
    }}>
      <style>{`
        @media(max-width:768px){
          .nav-desktop{display:none!important}
          .nav-hamburger{display:flex!important}
        }
        @media(min-width:769px){
          .nav-mobile-menu{display:none!important}
          .nav-hamburger{display:none!important}
        }
      `}</style>

      {/* Desktop + Mobile top row */}
      <div className="container" style={{ display:'flex', alignItems:'center', justifyContent:'space-between', height:56, gap:8 }}>

        {/* Logo */}
        <a href="/" style={{ display:'flex', alignItems:'center', gap:8, textDecoration:'none', flexShrink:0 }}>
          <div style={{ width:30, height:30, borderRadius:8, background:'linear-gradient(135deg, var(--accent), #f43f5e)', display:'flex', alignItems:'center', justifyContent:'center', fontSize:15 }}>🚗</div>
          <span style={{ fontFamily:'Syne,sans-serif', fontWeight:800, fontSize:17, letterSpacing:'-0.04em', color:'var(--text)' }}>
            Auto<span style={{ color:'var(--accent)' }}>AI</span>
          </span>
        </a>

        {/* Desktop nav */}
        <nav className="nav-desktop" style={{ display:'flex', gap:2, alignItems:'center' }}>
          {links.map(link => (
            <a key={link.href} href={link.href} style={{
              padding:'6px 12px', borderRadius:8, fontSize:13,
              color:'var(--text2)', textDecoration:'none', transition:'all .15s',
              position:'relative', display:'inline-flex', alignItems:'center', gap:4,
            }}
            onMouseEnter={e => { (e.currentTarget as HTMLElement).style.color='var(--text)'; (e.currentTarget as HTMLElement).style.background='var(--bg3)' }}
            onMouseLeave={e => { (e.currentTarget as HTMLElement).style.color='var(--text2)'; (e.currentTarget as HTMLElement).style.background='transparent' }}
            >
              {link.label}
              {(link as any).badge > 0 && (
                <span style={{ fontSize:10, background:'#EF4444', color:'#fff', borderRadius:20, padding:'1px 5px', fontWeight:700, lineHeight:1.4 }}>
                  {(link as any).badge}
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

        {/* Mobile right side */}
        <div className="nav-hamburger" style={{ display:'none', alignItems:'center', gap:8 }}>
          {userEmail ? (
            <span style={{ fontSize:12, color:'var(--text2)', background:'var(--bg3)', border:'1px solid var(--border)', padding:'5px 10px', borderRadius:8 }}>
              👤 {userEmail.split('@')[0]}
            </span>
          ) : (
            <a href="/register" style={{ padding:'6px 12px', borderRadius:8, textDecoration:'none', background:'var(--accent)', color:'#fff', fontSize:13, fontWeight:600 }}>
              Registracija
            </a>
          )}
          <button onClick={() => setMenuOpen(!menuOpen)} style={{
            background:'var(--bg3)', border:'1px solid var(--border)',
            borderRadius:8, padding:'6px 10px', color:'var(--text)',
            fontSize:18, cursor:'pointer', lineHeight:1, position:'relative',
          }}>
            {menuOpen ? '✕' : '☰'}
            {unread > 0 && !menuOpen && (
              <span style={{ position:'absolute', top:-4, right:-4, width:16, height:16, background:'#EF4444', borderRadius:'50%', fontSize:9, color:'#fff', display:'flex', alignItems:'center', justifyContent:'center', fontWeight:700 }}>
                {unread}
              </span>
            )}
          </button>
        </div>
      </div>

      {/* Mobile dropdown menu */}
      {menuOpen && (
        <div className="nav-mobile-menu" style={{ background:'var(--bg2)', borderTop:'1px solid var(--border)', padding:'12px 16px 16px' }}>
          <div style={{ display:'flex', flexDirection:'column', gap:4 }}>
            {links.map(link => (
              <a key={link.href} href={link.href} onClick={() => setMenuOpen(false)} style={{
                padding:'10px 14px', borderRadius:8, fontSize:14,
                color:'var(--text2)', textDecoration:'none',
                background:'var(--bg3)', border:'1px solid var(--border)',
                display:'flex', justifyContent:'space-between', alignItems:'center',
              }}>
                {link.label}
                {(link as any).badge > 0 && (
                  <span style={{ fontSize:11, background:'#EF4444', color:'#fff', borderRadius:20, padding:'2px 7px', fontWeight:700 }}>
                    {(link as any).badge}
                  </span>
                )}
              </a>
            ))}
            <div style={{ borderTop:'1px solid var(--border)', marginTop:8, paddingTop:8 }}>
              {userEmail ? (
                <button onClick={handleLogout} style={{ width:'100%', padding:'10px', borderRadius:8, fontSize:13, background:'transparent', border:'1px solid var(--border)', color:'var(--text3)', cursor:'pointer' }}>
                  Odjava
                </button>
              ) : (
                <div style={{ display:'flex', gap:8 }}>
                  <a href="/login"    style={{ flex:1, padding:'10px', borderRadius:8, fontSize:13, textDecoration:'none', color:'var(--text2)', border:'1px solid var(--border)', fontWeight:500, textAlign:'center' as any }}>Prijava</a>
                  <a href="/register" style={{ flex:1, padding:'10px', borderRadius:8, textDecoration:'none', background:'var(--accent)', color:'#fff', fontSize:13, fontWeight:500, textAlign:'center' as any }}>Registracija</a>
                </div>
              )}
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
