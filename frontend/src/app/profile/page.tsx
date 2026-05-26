'use client'
import { useState, useEffect } from 'react'

const FUEL_LABELS: Record<string, string> = {
  diesel: 'Dizel', petrol: 'Benzin', gasoline: 'Benzin',
  electric: 'Električni', hybrid: 'Hibrid', lpg: 'Plin',
}

export default function ProfilePage() {
  const [alerts,    setAlerts]    = useState<any[]>([])
  const [loading,   setLoading]   = useState(true)
  const [email,     setEmail]     = useState('')
  const [error,     setError]     = useState('')

  const apiBase = process.env.NEXT_PUBLIC_API_URL || 'https://autoai-platform-production.up.railway.app/api/v1'

  useEffect(() => {
    const token = localStorage.getItem('autoai_token')
    const mail  = localStorage.getItem('autoai_email')
    if (!token) { window.location.href = '/login'; return }
    setEmail(mail || '')
    fetchAlerts(token)
  }, [])

  const fetchAlerts = async (token: string) => {
    try {
      const res  = await fetch(`${apiBase}/alerts/`, {
        headers: { 'Authorization': `Bearer ${token}` }
      })
      const data = await res.json()
      setAlerts(Array.isArray(data) ? data : [])
    } catch { setError('Greška pri učitavanju') }
    finally  { setLoading(false) }
  }

  const deleteAlert = async (id: string) => {
    const token = localStorage.getItem('autoai_token')
    if (!token) return
    try {
      await fetch(`${apiBase}/alerts/${id}`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${token}` }
      })
      setAlerts(prev => prev.filter(a => a.id !== id))
    } catch {}
  }

  const toggleAlert = async (id: string) => {
    const token = localStorage.getItem('autoai_token')
    if (!token) return
    try {
      const res  = await fetch(`${apiBase}/alerts/${id}/toggle`, {
        method: 'PATCH',
        headers: { 'Authorization': `Bearer ${token}` }
      })
      const data = await res.json()
      setAlerts(prev => prev.map(a => a.id === id ? data : a))
    } catch {}
  }

  const formatFilters = (filters: any) => {
    const tags = [
      filters.make       && `🚗 ${filters.make}`,
      filters.model      && `📋 ${filters.model}`,
      filters.min_price  && `od ${Number(filters.min_price).toLocaleString()} €`,
      filters.max_price  && `do ${Number(filters.max_price).toLocaleString()} €`,
      filters.min_year   && `od ${filters.min_year}.`,
      filters.max_year   && `do ${filters.max_year}.`,
      filters.max_km     && `max ${Number(filters.max_km).toLocaleString()} km`,
      filters.fuel_type  && `⛽ ${FUEL_LABELS[filters.fuel_type] || filters.fuel_type}`,
    ].filter(Boolean)
    return tags.length > 0 ? tags : ['Svi oglasi']
  }

  return (
    <div style={{ minHeight:'100vh', padding:'40px 0 80px' }}>
      <div className="container">

        {/* Header */}
        <div style={{ marginBottom:32 }}>
          <h1 style={{ fontSize:26, fontFamily:'Syne,sans-serif', marginBottom:6 }}>
            👤 Moj profil
          </h1>
          <p style={{ color:'var(--text3)', fontSize:14 }}>{email}</p>
        </div>

        {/* Tabs */}
        <div style={{ display:'flex', gap:4, marginBottom:28, borderBottom:'1px solid var(--border)', paddingBottom:0 }}>
          {['🔔 Aktivni alerti', '❤️ Sačuvani oglasi'].map((tab, i) => (
            <a key={i} href={i === 1 ? '/favorites' : '#'} style={{
              padding:'10px 18px', fontSize:14, fontWeight:600,
              color: i === 0 ? 'var(--accent)' : 'var(--text3)',
              borderBottom: i === 0 ? '2px solid var(--accent)' : '2px solid transparent',
              textDecoration:'none', marginBottom:-1,
            }}>{tab}</a>
          ))}
        </div>

        {/* Alerti */}
        {loading ? (
          <div style={{ display:'flex', flexDirection:'column', gap:12 }}>
            {[...Array(3)].map((_,i) => <div key={i} className="skeleton" style={{ height:100, borderRadius:12 }} />)}
          </div>
        ) : error ? (
          <p style={{ color:'#EF4444' }}>{error}</p>
        ) : alerts.length === 0 ? (
          <div style={{ textAlign:'center', padding:'60px 20px', background:'var(--bg2)', borderRadius:16, border:'1px solid var(--border)' }}>
            <div style={{ fontSize:48, marginBottom:16 }}>🔔</div>
            <p style={{ fontSize:17, fontWeight:600, marginBottom:8 }}>Nema aktivnih alerta</p>
            <p style={{ color:'var(--text3)', fontSize:14, marginBottom:24 }}>
              Sačuvaj pretragu na stranici pretrage da dobijaš obaveštenja o novim oglasima.
            </p>
            <a href="/search" style={{ display:'inline-block', padding:'12px 28px', borderRadius:10, background:'var(--accent)', color:'#fff', textDecoration:'none', fontWeight:700 }}>
              Idi na pretragu
            </a>
          </div>
        ) : (
          <div style={{ display:'flex', flexDirection:'column', gap:12 }}>
            {alerts.map(alert => (
              <div key={alert.id} style={{
                background:'var(--bg2)', border:`1px solid ${alert.is_active ? 'rgba(99,102,241,.3)' : 'var(--border)'}`,
                borderRadius:14, padding:'18px 20px',
                opacity: alert.is_active ? 1 : 0.6,
              }}>
                <div style={{ display:'flex', justifyContent:'space-between', alignItems:'flex-start', marginBottom:10 }}>
                  <div>
                    <div style={{ fontSize:15, fontWeight:700, marginBottom:4 }}>
                      {alert.is_active ? '🔔' : '🔕'} {alert.name}
                    </div>
                    <div style={{ fontSize:11, color:'var(--text3)' }}>
                      Kreiran: {new Date(alert.created_at).toLocaleDateString('sr')}
                      {alert.frequency && ` · ${alert.frequency}`}
                    </div>
                  </div>
                  <div style={{ display:'flex', gap:6 }}>
                    <button onClick={() => toggleAlert(alert.id)} style={{
                      padding:'6px 12px', borderRadius:8, fontSize:12, fontWeight:600,
                      background: alert.is_active ? 'rgba(99,102,241,.1)' : 'var(--bg3)',
                      border: `1px solid ${alert.is_active ? 'rgba(99,102,241,.3)' : 'var(--border)'}`,
                      color: alert.is_active ? '#818CF8' : 'var(--text3)',
                      cursor:'pointer',
                    }}>
                      {alert.is_active ? 'Pauziraj' : 'Aktiviraj'}
                    </button>
                    <button onClick={() => deleteAlert(alert.id)} style={{
                      padding:'6px 12px', borderRadius:8, fontSize:12,
                      background:'rgba(239,68,68,.08)', border:'1px solid rgba(239,68,68,.25)',
                      color:'#F87171', cursor:'pointer', fontWeight:600,
                    }}>Obriši</button>
                  </div>
                </div>

                {/* Filter tagovi */}
                <div style={{ display:'flex', flexWrap:'wrap', gap:6 }}>
                  {formatFilters(alert.filters || {}).map((tag: string, i: number) => (
                    <span key={i} style={{
                      background:'rgba(255,107,0,.08)', border:'1px solid rgba(255,107,0,.2)',
                      color:'var(--accent)', borderRadius:20, padding:'3px 10px', fontSize:12,
                    }}>{tag}</span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
