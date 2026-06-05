'use client'
import { useState, useEffect } from 'react'

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'https://autoai-platform-production.up.railway.app/api/v1'

export default function ProfilePage() {
  const [email,   setEmail]   = useState('')
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    const token = localStorage.getItem('autoai_token')
    const mail  = localStorage.getItem('autoai_email')
    if (!token) { window.location.href = '/login'; return }
    setEmail(mail || '')
  }, [])

  const handleLogout = () => {
    localStorage.removeItem('autoai_token')
    localStorage.removeItem('autoai_email')
    window.location.href = '/'
  }

  const menuItems = [
    { href:'/searches',  icon:'🎯', label:'Moje potrage',   desc:'Aktivne pretrage i rezultati' },
    { href:'/favorites', icon:'❤️', label:'Sačuvani oglasi', desc:'Vozila koja si zapamtio' },
    { href:'/inbox',     icon:'📬', label:'Inbox',           desc:'Poruke sa prodavcima' },
  ]

  return (
    <div style={{ minHeight:'100vh', padding:'40px 0 80px' }}>
      <div className="container" style={{ maxWidth:520 }}>

        {/* Header */}
        <div style={{ textAlign:'center', marginBottom:36 }}>
          <div style={{ width:72, height:72, borderRadius:'50%', background:'linear-gradient(135deg,rgba(255,107,0,.2),rgba(255,107,0,.08))', border:'2px solid rgba(255,107,0,.3)', display:'flex', alignItems:'center', justifyContent:'center', fontSize:32, margin:'0 auto 16px' }}>
            👤
          </div>
          <h1 style={{ fontSize:22, fontFamily:'Syne,sans-serif', marginBottom:4 }}>Moj nalog</h1>
          <p style={{ color:'var(--text3)', fontSize:14 }}>{email}</p>
        </div>

        {/* Brze veze */}
        <div style={{ display:'flex', flexDirection:'column', gap:8, marginBottom:24 }}>
          {menuItems.map(item => (
            <a key={item.href} href={item.href} style={{
              display:'flex', alignItems:'center', gap:14, padding:'16px 20px',
              background:'var(--bg2)', border:'1px solid var(--border)', borderRadius:14,
              textDecoration:'none', transition:'all .15s',
            }}
            onMouseEnter={e=>{(e.currentTarget as HTMLElement).style.borderColor='rgba(255,107,0,.3)'}}
            onMouseLeave={e=>{(e.currentTarget as HTMLElement).style.borderColor='var(--border)'}}>
              <span style={{ fontSize:24, flexShrink:0 }}>{item.icon}</span>
              <div style={{ flex:1 }}>
                <div style={{ fontSize:14, fontWeight:600, color:'var(--text)', marginBottom:2 }}>{item.label}</div>
                <div style={{ fontSize:12, color:'var(--text3)' }}>{item.desc}</div>
              </div>
              <span style={{ fontSize:16, color:'var(--text3)' }}>›</span>
            </a>
          ))}
        </div>

        {/* Podešavanja */}
        <div style={{ background:'var(--bg2)', border:'1px solid var(--border)', borderRadius:14, overflow:'hidden', marginBottom:16 }}>
          <div style={{ padding:'14px 20px', borderBottom:'1px solid var(--border)' }}>
            <div style={{ fontSize:11, color:'var(--text3)', fontWeight:600, letterSpacing:'.07em' }}>NALOG</div>
          </div>
          <div style={{ padding:'12px 20px', borderBottom:'1px solid var(--border)', display:'flex', justifyContent:'space-between', alignItems:'center' }}>
            <div>
              <div style={{ fontSize:13, color:'var(--text2)' }}>Email</div>
              <div style={{ fontSize:12, color:'var(--text3)' }}>{email}</div>
            </div>
          </div>
          <div style={{ padding:'12px 20px', display:'flex', justifyContent:'space-between', alignItems:'center' }}>
            <div>
              <div style={{ fontSize:13, color:'var(--text2)' }}>Plan</div>
              <div style={{ fontSize:12, color:'var(--text3)' }}>Besplatno · Beta</div>
            </div>
            <span style={{ fontSize:10, padding:'3px 8px', borderRadius:20, background:'rgba(255,107,0,.12)', color:'var(--accent)', fontWeight:700, border:'1px solid rgba(255,107,0,.25)' }}>BETA</span>
          </div>
        </div>

        {/* Odjava */}
        <button onClick={handleLogout} style={{
          width:'100%', padding:'13px', borderRadius:12, fontSize:14,
          background:'transparent', border:'1px solid var(--border)',
          color:'var(--text3)', cursor:'pointer', fontWeight:500,
        }}>
          Odjava
        </button>
      </div>
    </div>
  )
}
