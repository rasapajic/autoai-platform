'use client'
import { useState } from 'react'

export default function LoginPage() {
  const [email,    setEmail]    = useState('')
  const [password, setPassword] = useState('')
  const [loading,  setLoading]  = useState(false)
  const [error,    setError]    = useState('')

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true); setError('')
    try {
      const apiBase = process.env.NEXT_PUBLIC_API_URL || 'https://autoai-platform-production.up.railway.app/api/v1'
      const res  = await fetch(`${apiBase}/users/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      })
      const data = await res.json()
      if (!res.ok) { setError(data.detail || 'Greška pri prijavi'); return }
      localStorage.setItem('autoai_token', data.access_token)
      localStorage.setItem('autoai_email', data.user?.email || email)
      window.location.href = '/search'
    } catch { setError('Greška pri konekciji') }
    finally { setLoading(false) }
  }

  return (
    <div style={{ minHeight:'100vh', display:'flex', alignItems:'center', justifyContent:'center', padding:20 }}>
      <div style={{ width:'100%', maxWidth:400 }}>
        <h1 style={{ fontSize:26, fontFamily:'Syne,sans-serif', marginBottom:8, textAlign:'center' }}>
          Prijava
        </h1>
        <p style={{ color:'var(--text3)', fontSize:14, textAlign:'center', marginBottom:32 }}>
          Uloguj se da čuvaš pretrage i dobijaš alerte
        </p>
        <div style={{ background:'var(--bg2)', border:'1px solid var(--border)', borderRadius:16, padding:28 }}>
          <div style={{ marginBottom:16 }}>
            <label style={{ fontSize:12, color:'var(--text3)', fontWeight:600, letterSpacing:'.07em' }}>EMAIL</label>
            <input type="email" value={email} onChange={e => setEmail(e.target.value)}
              placeholder="tvoj@email.com"
              style={{ width:'100%', boxSizing:'border-box' as any, marginTop:6,
                background:'var(--bg3)', border:'1px solid var(--border)', borderRadius:8,
                padding:'11px 14px', color:'var(--text)', fontSize:14, outline:'none' }} />
          </div>
          <div style={{ marginBottom:22 }}>
            <label style={{ fontSize:12, color:'var(--text3)', fontWeight:600, letterSpacing:'.07em' }}>LOZINKA</label>
            <input type="password" value={password} onChange={e => setPassword(e.target.value)}
              placeholder="••••••••"
              style={{ width:'100%', boxSizing:'border-box' as any, marginTop:6,
                background:'var(--bg3)', border:'1px solid var(--border)', borderRadius:8,
                padding:'11px 14px', color:'var(--text)', fontSize:14, outline:'none' }} />
          </div>
          {error && <p style={{ color:'#EF4444', fontSize:13, marginBottom:14 }}>{error}</p>}
          <button onClick={handleLogin} disabled={loading} style={{
            width:'100%', padding:'13px', borderRadius:10,
            background:'var(--accent)', color:'#fff',
            border:'none', fontSize:15, fontWeight:700, cursor:'pointer',
          }}>
            {loading ? 'Prijavljivanje...' : 'Prijavi se'}
          </button>
          <p style={{ textAlign:'center', marginTop:18, fontSize:13, color:'var(--text3)' }}>
            Nemaš nalog?{' '}
            <a href="/register" style={{ color:'var(--accent)', fontWeight:600 }}>Registruj se</a>
          </p>
        </div>
      </div>
    </div>
  )
}
