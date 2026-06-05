'use client'
import { useState, useEffect } from 'react'

const FUEL_LABELS: Record<string, string> = {
  diesel: 'Dizel', petrol: 'Benzin', gasoline: 'Benzin',
  electric: 'Električni', hybrid: 'Hibrid', lpg: 'Plin',
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'https://autoai-platform-production.up.railway.app/api/v1'

function formatFilters(filters: any) {
  const tags = [
    filters.make      && `🚗 ${filters.make}`,
    filters.model     && `📋 ${filters.model}`,
    filters.min_price && `od ${Number(filters.min_price).toLocaleString()} €`,
    filters.max_price && `do ${Number(filters.max_price).toLocaleString()} €`,
    filters.min_year  && `od ${filters.min_year}.`,
    filters.max_year  && `do ${filters.max_year}.`,
    filters.max_km    && `max ${Number(filters.max_km).toLocaleString()} km`,
    filters.fuel_type && `⛽ ${FUEL_LABELS[filters.fuel_type] || filters.fuel_type}`,
  ].filter(Boolean)
  return tags.length > 0 ? tags : ['Svi oglasi']
}

function daysSince(dateStr: string) {
  const d = new Date(dateStr)
  const now = new Date()
  return Math.floor((now.getTime() - d.getTime()) / (1000*60*60*24))
}

export default function ProfilePage() {
  const [tab, setTab]       = useState(0)
  const [alerts, setAlerts] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [email, setEmail]   = useState('')
  const [error, setError]   = useState('')

  useEffect(() => {
    const token = localStorage.getItem('autoai_token')
    const mail  = localStorage.getItem('autoai_email')
    if (!token) { window.location.href = '/login'; return }
    setEmail(mail || '')
    fetchAlerts(token)
  }, [])

  const fetchAlerts = async (token: string) => {
    try {
      const res  = await fetch(`${API_BASE}/alerts/`, { headers: { 'Authorization': `Bearer ${token}` } })
      const data = await res.json()
      setAlerts(Array.isArray(data) ? data : [])
    } catch { setError('Greška pri učitavanju') }
    finally  { setLoading(false) }
  }

  const deleteAlert = async (id: string) => {
    const token = localStorage.getItem('autoai_token'); if (!token) return
    try {
      await fetch(`${API_BASE}/alerts/${id}`, { method:'DELETE', headers:{'Authorization':`Bearer ${token}`} })
      setAlerts(prev => prev.filter(a => a.id !== id))
    } catch {}
  }

  const toggleAlert = async (id: string) => {
    const token = localStorage.getItem('autoai_token'); if (!token) return
    try {
      const res  = await fetch(`${API_BASE}/alerts/${id}/toggle`, { method:'PATCH', headers:{'Authorization':`Bearer ${token}`} })
      const data = await res.json()
      setAlerts(prev => prev.map(a => a.id === id ? data : a))
    } catch {}
  }

  const TABS = ['🔎 Moje potrage', '🔔 Alerti', '❤️ Sačuvani oglasi']

  return (
    <div style={{ minHeight:'100vh', padding:'40px 0 80px' }}>
      <div className="container">

        {/* Header */}
        <div style={{ marginBottom:28 }}>
          <h1 style={{ fontSize:26, fontFamily:'Syne,sans-serif', marginBottom:6 }}>👤 Moj profil</h1>
          <p style={{ color:'var(--text3)', fontSize:14 }}>{email}</p>
        </div>

        {/* Tabs */}
        <div style={{ display:'flex', gap:4, marginBottom:28, borderBottom:'1px solid var(--border)' }}>
          {TABS.map((t, i) => (
            <button key={i} onClick={() => i === 2 ? (window.location.href='/favorites') : setTab(i)}
              style={{
                padding:'10px 16px', fontSize:13, fontWeight:600, cursor:'pointer',
                background:'none', border:'none',
                color: tab===i ? 'var(--accent)' : 'var(--text3)',
                borderBottom: tab===i ? '2px solid var(--accent)' : '2px solid transparent',
                marginBottom:-1, transition:'all .15s',
              }}>{t}</button>
          ))}
        </div>

        {/* TAB 0 — Moje potrage */}
        {tab === 0 && (
          <div>
            {loading ? (
              <div style={{ display:'flex', flexDirection:'column', gap:12 }}>
                {[...Array(3)].map((_,i) => <div key={i} className="skeleton" style={{ height:140, borderRadius:14 }} />)}
              </div>
            ) : error ? (
              <p style={{ color:'#EF4444' }}>{error}</p>
            ) : alerts.length === 0 ? (
              <div style={{ textAlign:'center', padding:'60px 20px', background:'var(--bg2)', borderRadius:16, border:'1px solid var(--border)' }}>
                <div style={{ fontSize:52, marginBottom:16 }}>🔎</div>
                <p style={{ fontSize:17, fontWeight:700, marginBottom:8 }}>Nema aktivnih potraga</p>
                <p style={{ color:'var(--text3)', fontSize:14, marginBottom:24, lineHeight:1.6 }}>
                  Aktiviraj "Pronađi mi ovakav auto" na stranici pretrage<br/>i AutoAI će tražiti umesto tebe.
                </p>
                <a href="/search" style={{ display:'inline-block', padding:'13px 28px', borderRadius:12, background:'var(--accent)', color:'#fff', textDecoration:'none', fontWeight:700, fontSize:15, boxShadow:'0 4px 20px rgba(255,107,0,.35)' }}>
                  🔎 Pronađi mi auto
                </a>
              </div>
            ) : (
              <div style={{ display:'flex', flexDirection:'column', gap:12 }}>
                {/* Beta banner */}
                <div style={{ background:'rgba(255,107,0,.07)', border:'1px solid rgba(255,107,0,.2)', borderRadius:12, padding:'12px 16px', display:'flex', alignItems:'center', gap:10 }}>
                  <span style={{ fontSize:16 }}>🤖</span>
                  <div>
                    <div style={{ fontSize:13, fontWeight:700, color:'var(--accent)' }}>AutoAI aktivno pretražuje za vas</div>
                    <div style={{ fontSize:11, color:'var(--text3)', marginTop:2 }}>Dobijate email kada pronađemo nova vozila · Rezultati su ovde</div>
                  </div>
                  <span style={{ marginLeft:'auto', fontSize:10, padding:'3px 8px', borderRadius:20, background:'rgba(255,107,0,.15)', color:'var(--accent)', fontWeight:800 }}>BETA</span>
                </div>

                {alerts.map(alert => (
                  <div key={alert.id} style={{
                    background:'var(--bg2)',
                    border:`1px solid ${alert.is_active ? 'rgba(255,107,0,.25)' : 'var(--border)'}`,
                    borderRadius:16, overflow:'hidden',
                    opacity: alert.is_active ? 1 : 0.6,
                  }}>
                    {/* Header kartice */}
                    <div style={{ padding:'16px 20px', borderBottom:'1px solid var(--border)' }}>
                      <div style={{ display:'flex', justifyContent:'space-between', alignItems:'flex-start' }}>
                        <div>
                          <div style={{ display:'flex', alignItems:'center', gap:8, marginBottom:4 }}>
                            <span style={{ fontSize:16 }}>{alert.is_active ? '🔎' : '⏸️'}</span>
                            <span style={{ fontSize:15, fontWeight:700 }}>{alert.name}</span>
                            {alert.is_active && (
                              <span style={{ fontSize:10, padding:'2px 7px', borderRadius:20, background:'rgba(34,197,94,.12)', color:'#22C55E', fontWeight:700 }}>AKTIVNO</span>
                            )}
                          </div>
                          <div style={{ fontSize:11, color:'var(--text3)' }}>
                            Traži se {daysSince(alert.created_at)} dana
                            {alert.last_triggered_at && ` · Poslednji email: ${new Date(alert.last_triggered_at).toLocaleDateString('sr')}`}
                          </div>
                        </div>
                        <div style={{ display:'flex', gap:6 }}>
                          <button onClick={() => toggleAlert(alert.id)} style={{
                            padding:'6px 12px', borderRadius:8, fontSize:12, fontWeight:600,
                            background: alert.is_active ? 'rgba(99,102,241,.1)' : 'var(--bg3)',
                            border: `1px solid ${alert.is_active ? 'rgba(99,102,241,.3)' : 'var(--border)'}`,
                            color: alert.is_active ? '#818CF8' : 'var(--text3)', cursor:'pointer',
                          }}>
                            {alert.is_active ? 'Pauziraj' : 'Aktiviraj'}
                          </button>
                          <button onClick={() => deleteAlert(alert.id)} style={{
                            padding:'6px 12px', borderRadius:8, fontSize:12, fontWeight:600,
                            background:'rgba(239,68,68,.08)', border:'1px solid rgba(239,68,68,.25)',
                            color:'#F87171', cursor:'pointer',
                          }}>Obriši</button>
                        </div>
                      </div>
                    </div>

                    {/* Kriterijumi */}
                    <div style={{ padding:'12px 20px 14px' }}>
                      <div style={{ fontSize:11, color:'var(--text3)', fontWeight:600, letterSpacing:'.06em', marginBottom:8 }}>KRITERIJUMI</div>
                      <div style={{ display:'flex', flexWrap:'wrap', gap:6, marginBottom:12 }}>
                        {formatFilters(alert.filters || {}).map((tag: string, i: number) => (
                          <span key={i} style={{
                            background:'rgba(255,107,0,.08)', border:'1px solid rgba(255,107,0,.2)',
                            color:'var(--accent)', borderRadius:20, padding:'3px 10px', fontSize:12,
                          }}>{tag}</span>
                        ))}
                      </div>

                      {/* Statistike */}
                      <div style={{ display:'grid', gridTemplateColumns:'repeat(3,1fr)', gap:8 }}>
                        <div style={{ background:'var(--bg3)', borderRadius:10, padding:'10px 12px', textAlign:'center' }}>
                          <div style={{ fontSize:20, fontWeight:800, color:'var(--text)' }}>{alert.matches_count || 0}</div>
                          <div style={{ fontSize:10, color:'var(--text3)', marginTop:2 }}>Pronađeno</div>
                        </div>
                        <div style={{ background:'var(--bg3)', borderRadius:10, padding:'10px 12px', textAlign:'center' }}>
                          <div style={{ fontSize:20, fontWeight:800, color: (alert.new_matches_count || 0) > 0 ? '#22C55E' : 'var(--text)' }}>
                            {alert.new_matches_count || 0}
                          </div>
                          <div style={{ fontSize:10, color:'var(--text3)', marginTop:2 }}>Novo</div>
                        </div>
                        <div style={{ background:'var(--bg3)', borderRadius:10, padding:'10px 12px', textAlign:'center' }}>
                          <div style={{ fontSize:20, fontWeight:800, color:'var(--text)' }}>{daysSince(alert.created_at)}</div>
                          <div style={{ fontSize:10, color:'var(--text3)', marginTop:2 }}>Dana aktivo</div>
                        </div>
                      </div>

                      {/* CTA za rezultate */}
                      {(alert.matches_count || 0) > 0 && (
                        <a href={`/search?make=${encodeURIComponent(alert.filters?.make||'')}&model=${encodeURIComponent(alert.filters?.model||'')}&max_price=${alert.filters?.max_price||''}&max_km=${alert.filters?.max_km||''}&min_year=${alert.filters?.min_year||''}`}
                          style={{ display:'flex', alignItems:'center', justifyContent:'center', gap:8, marginTop:12, padding:'11px', borderRadius:12, background:'rgba(255,107,0,.1)', border:'1px solid rgba(255,107,0,.3)', color:'var(--accent)', textDecoration:'none', fontSize:13, fontWeight:700 }}>
                          🔎 Pogledaj pronađena vozila →
                        </a>
                      )}
                    </div>
                  </div>
                ))}

                {/* Dodaj novu potragu */}
                <a href="/search" style={{ display:'flex', alignItems:'center', justifyContent:'center', gap:8, padding:'14px', borderRadius:14, background:'var(--bg2)', border:'2px dashed rgba(255,107,0,.3)', color:'var(--accent)', textDecoration:'none', fontSize:14, fontWeight:600 }}>
                  + Dodaj novu potragu
                </a>
              </div>
            )}
          </div>
        )}

        {/* TAB 1 — Alerti (stari view) */}
        {tab === 1 && (
          <div>
            {loading ? (
              <div style={{ display:'flex', flexDirection:'column', gap:12 }}>
                {[...Array(3)].map((_,i) => <div key={i} className="skeleton" style={{ height:100, borderRadius:12 }} />)}
              </div>
            ) : alerts.length === 0 ? (
              <div style={{ textAlign:'center', padding:'60px 20px', background:'var(--bg2)', borderRadius:16, border:'1px solid var(--border)' }}>
                <div style={{ fontSize:48, marginBottom:16 }}>🔔</div>
                <p style={{ fontSize:17, fontWeight:600, marginBottom:8 }}>Nema aktivnih alerta</p>
                <p style={{ color:'var(--text3)', fontSize:14, marginBottom:24 }}>Sačuvaj pretragu na stranici pretrage da dobijaš obaveštenja.</p>
                <a href="/search" style={{ display:'inline-block', padding:'12px 28px', borderRadius:10, background:'var(--accent)', color:'#fff', textDecoration:'none', fontWeight:700 }}>Idi na pretragu</a>
              </div>
            ) : (
              <div style={{ display:'flex', flexDirection:'column', gap:12 }}>
                {alerts.map(alert => (
                  <div key={alert.id} style={{ background:'var(--bg2)', border:`1px solid ${alert.is_active?'rgba(99,102,241,.3)':'var(--border)'}`, borderRadius:14, padding:'18px 20px', opacity:alert.is_active?1:0.6 }}>
                    <div style={{ display:'flex', justifyContent:'space-between', alignItems:'flex-start', marginBottom:10 }}>
                      <div>
                        <div style={{ fontSize:15, fontWeight:700, marginBottom:4 }}>{alert.is_active?'🔔':'🔕'} {alert.name}</div>
                        <div style={{ fontSize:11, color:'var(--text3)' }}>Kreiran: {new Date(alert.created_at).toLocaleDateString('sr')}{alert.frequency&&` · ${alert.frequency}`}</div>
                      </div>
                      <div style={{ display:'flex', gap:6 }}>
                        <button onClick={() => toggleAlert(alert.id)} style={{ padding:'6px 12px', borderRadius:8, fontSize:12, fontWeight:600, background:alert.is_active?'rgba(99,102,241,.1)':'var(--bg3)', border:`1px solid ${alert.is_active?'rgba(99,102,241,.3)':'var(--border)'}`, color:alert.is_active?'#818CF8':'var(--text3)', cursor:'pointer' }}>
                          {alert.is_active?'Pauziraj':'Aktiviraj'}
                        </button>
                        <button onClick={() => deleteAlert(alert.id)} style={{ padding:'6px 12px', borderRadius:8, fontSize:12, background:'rgba(239,68,68,.08)', border:'1px solid rgba(239,68,68,.25)', color:'#F87171', cursor:'pointer', fontWeight:600 }}>Obriši</button>
                      </div>
                    </div>
                    <div style={{ display:'flex', flexWrap:'wrap', gap:6 }}>
                      {formatFilters(alert.filters||{}).map((tag:string,i:number) => (
                        <span key={i} style={{ background:'rgba(255,107,0,.08)', border:'1px solid rgba(255,107,0,.2)', color:'var(--accent)', borderRadius:20, padding:'3px 10px', fontSize:12 }}>{tag}</span>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

      </div>
    </div>
  )
}
