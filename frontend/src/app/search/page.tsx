'use client'
import { useState, useEffect } from 'react'

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'https://autoai-platform-production.up.railway.app/api/v1'

const FUEL_LABELS: Record<string, string> = {
  diesel:'Dizel', petrol:'Benzin', gasoline:'Benzin',
  electric:'Električni', hybrid:'Hibrid', lpg:'Plin',
}

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
  return Math.floor((Date.now() - new Date(dateStr).getTime()) / (1000*60*60*24))
}

export default function SearchesPage() {
  const [alerts,  setAlerts]  = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [error,   setError]   = useState('')

  useEffect(() => {
    const token = localStorage.getItem('autoai_token')
    if (!token) { window.location.href = '/login'; return }
    fetch(`${API_BASE}/alerts/`, { headers: { 'Authorization': `Bearer ${token}` } })
      .then(r => r.ok ? r.json() : [])
      .then(data => setAlerts(Array.isArray(data) ? data : []))
      .catch(() => setError('Greška pri učitavanju'))
      .finally(() => setLoading(false))
  }, [])

  const deleteAlert = async (id: string) => {
    const token = localStorage.getItem('autoai_token'); if (!token) return
    await fetch(`${API_BASE}/alerts/${id}`, { method:'DELETE', headers:{'Authorization':`Bearer ${token}`} })
    setAlerts(prev => prev.filter(a => a.id !== id))
  }

  const toggleAlert = async (id: string) => {
    const token = localStorage.getItem('autoai_token'); if (!token) return
    const res  = await fetch(`${API_BASE}/alerts/${id}/toggle`, { method:'PATCH', headers:{'Authorization':`Bearer ${token}`} })
    const data = await res.json()
    setAlerts(prev => prev.map(a => a.id === id ? data : a))
  }

  const totalFound   = alerts.reduce((acc, a) => acc + (a.matches_count || 0), 0)
  const totalNew     = alerts.reduce((acc, a) => acc + (a.new_matches_count || 0), 0)
  const activeCount  = alerts.filter(a => a.is_active).length

  return (
    <div style={{ minHeight:'100vh', padding:'40px 0 80px' }}>
      <div className="container" style={{ maxWidth:680 }}>

        {/* Header */}
        <div style={{ display:'flex', justifyContent:'space-between', alignItems:'flex-start', marginBottom:24 }}>
          <div>
            <h1 style={{ fontSize:26, fontFamily:'Syne,sans-serif', marginBottom:6, display:'flex', alignItems:'center', gap:10 }}>
              🎯 Moje potrage
              {totalNew > 0 && (
                <span style={{ fontSize:13, padding:'3px 10px', borderRadius:20, background:'rgba(255,107,0,.15)', color:'var(--accent)', fontWeight:700, border:'1px solid rgba(255,107,0,.3)' }}>
                  {totalNew} novo
                </span>
              )}
            </h1>
            <p style={{ color:'var(--text3)', fontSize:14, margin:0 }}>AutoAI aktivno prati oglase za vas. Rezultati se pojavljuju ovde.</p>
          </div>
          <a href="/search" style={{ flexShrink:0, padding:'10px 18px', borderRadius:12, background:'var(--accent)', color:'#fff', textDecoration:'none', fontSize:14, fontWeight:700, boxShadow:'0 4px 16px rgba(255,107,0,.3)', whiteSpace:'nowrap' }}>
            + Nova potraga
          </a>
        </div>

        {/* Statistike */}
        {alerts.length > 0 && (
          <div style={{ display:'grid', gridTemplateColumns:'repeat(3,1fr)', gap:10, marginBottom:24 }}>
            {[
              { label:'Aktivne potrage', val:activeCount, color:'#22C55E' },
              { label:'Ukupno pronađeno', val:totalFound, color:'var(--text)' },
              { label:'Nova vozila', val:totalNew, color:totalNew>0?'var(--accent)':'var(--text)' },
            ].map(({label,val,color}) => (
              <div key={label} style={{ background:'var(--bg2)', border:'1px solid var(--border)', borderRadius:14, padding:'16px', textAlign:'center' }}>
                <div style={{ fontSize:28, fontWeight:800, color, lineHeight:1, marginBottom:6 }}>{val}</div>
                <div style={{ fontSize:11, color:'var(--text3)' }}>{label}</div>
              </div>
            ))}
          </div>
        )}

        {/* Beta banner */}
        {alerts.length > 0 && (
          <div style={{ background:'rgba(255,107,0,.07)', border:'1px solid rgba(255,107,0,.2)', borderRadius:12, padding:'12px 16px', display:'flex', alignItems:'center', gap:10, marginBottom:20 }}>
            <span style={{ fontSize:16 }}>🤖</span>
            <div style={{ flex:1 }}>
              <div style={{ fontSize:13, fontWeight:700, color:'var(--accent)' }}>AutoAI aktivno pretražuje za vas</div>
              <div style={{ fontSize:11, color:'var(--text3)', marginTop:2 }}>Dobijate email kada pronađemo nova vozila · Rezultati su dostupni ovde</div>
            </div>
            <span style={{ fontSize:10, padding:'3px 8px', borderRadius:20, background:'rgba(255,107,0,.15)', color:'var(--accent)', fontWeight:800, flexShrink:0 }}>BETA</span>
          </div>
        )}

        {/* Sadržaj */}
        {loading ? (
          <div style={{ display:'flex', flexDirection:'column', gap:12 }}>
            {[...Array(3)].map((_,i) => <div key={i} className="skeleton" style={{ height:160, borderRadius:16 }} />)}
          </div>
        ) : error ? (
          <p style={{ color:'#EF4444' }}>{error}</p>
        ) : alerts.length === 0 ? (
          <div style={{ textAlign:'center', padding:'80px 20px', background:'var(--bg2)', borderRadius:20, border:'1px solid var(--border)' }}>
            <div style={{ fontSize:56, marginBottom:20 }}>🎯</div>
            <p style={{ fontSize:18, fontWeight:700, marginBottom:10 }}>Još nema aktivnih potraga</p>
            <p style={{ color:'var(--text3)', fontSize:14, marginBottom:32, lineHeight:1.7 }}>
              Reci AutoAI kakav auto tražiš.<br/>
              Mi pratimo oglase i javljamo ti čim pronađemo.
            </p>
            <a href="/search" style={{ display:'inline-flex', alignItems:'center', gap:10, padding:'15px 32px', borderRadius:14, background:'var(--accent)', color:'#fff', textDecoration:'none', fontWeight:800, fontSize:16, boxShadow:'0 6px 24px rgba(255,107,0,.35)' }}>
              🔎 Pronađi mi ovakav auto
            </a>
            <p style={{ fontSize:12, color:'var(--text3)', marginTop:14, opacity:.7 }}>Besplatno tokom beta faze</p>
          </div>
        ) : (
          <div style={{ display:'flex', flexDirection:'column', gap:12 }}>
            {alerts.map(alert => (
              <div key={alert.id} style={{
                background:'var(--bg2)',
                border:`1px solid ${alert.is_active ? 'rgba(255,107,0,.25)' : 'var(--border)'}`,
                borderRadius:16, overflow:'hidden', opacity:alert.is_active?1:.6,
              }}>
                {/* Kartica header */}
                <div style={{ padding:'16px 20px', borderBottom:'1px solid var(--border)' }}>
                  <div style={{ display:'flex', justifyContent:'space-between', alignItems:'flex-start' }}>
                    <div>
                      <div style={{ display:'flex', alignItems:'center', gap:8, marginBottom:4 }}>
                        <span style={{ fontSize:15 }}>{alert.is_active ? '🔎' : '⏸️'}</span>
                        <span style={{ fontSize:15, fontWeight:700 }}>{alert.name}</span>
                        {alert.is_active && (
                          <span style={{ fontSize:10, padding:'2px 7px', borderRadius:20, background:'rgba(34,197,94,.12)', color:'#22C55E', fontWeight:700 }}>AKTIVNO</span>
                        )}
                        {(alert.new_matches_count || 0) > 0 && (
                          <span style={{ fontSize:10, padding:'2px 8px', borderRadius:20, background:'rgba(255,107,0,.15)', color:'var(--accent)', fontWeight:800, border:'1px solid rgba(255,107,0,.3)' }}>
                            {alert.new_matches_count} novo
                          </span>
                        )}
                      </div>
                      <div style={{ fontSize:11, color:'var(--text3)' }}>
                        Traži se {daysSince(alert.created_at)} dana
                        {alert.last_triggered_at && ` · Poslednji email: ${new Date(alert.last_triggered_at).toLocaleDateString('sr')}`}
                      </div>
                    </div>
                    <div style={{ display:'flex', gap:6 }}>
                      <button onClick={() => toggleAlert(alert.id)} style={{
                        padding:'6px 12px', borderRadius:8, fontSize:12, fontWeight:600, cursor:'pointer',
                        background:alert.is_active?'rgba(99,102,241,.1)':'var(--bg3)',
                        border:`1px solid ${alert.is_active?'rgba(99,102,241,.3)':'var(--border)'}`,
                        color:alert.is_active?'#818CF8':'var(--text3)',
                      }}>{alert.is_active?'Pauziraj':'Aktiviraj'}</button>
                      <button onClick={() => deleteAlert(alert.id)} style={{
                        padding:'6px 12px', borderRadius:8, fontSize:12, fontWeight:600, cursor:'pointer',
                        background:'rgba(239,68,68,.08)', border:'1px solid rgba(239,68,68,.25)', color:'#F87171',
                      }}>Obriši</button>
                    </div>
                  </div>
                </div>

                {/* Kriterijumi + statistike */}
                <div style={{ padding:'14px 20px' }}>
                  <div style={{ display:'flex', flexWrap:'wrap', gap:6, marginBottom:14 }}>
                    {formatFilters(alert.filters || {}).map((tag:string, i:number) => (
                      <span key={i} style={{ background:'rgba(255,107,0,.08)', border:'1px solid rgba(255,107,0,.2)', color:'var(--accent)', borderRadius:20, padding:'3px 10px', fontSize:12 }}>{tag}</span>
                    ))}
                  </div>

                  <div style={{ display:'grid', gridTemplateColumns:'repeat(3,1fr)', gap:8, marginBottom:12 }}>
                    {[
                      { label:'Pronađeno', val: alert.matches_count || 0 },
                      { label:'Novo', val: alert.new_matches_count || 0, accent: (alert.new_matches_count||0) > 0 },
                      { label:'Dana aktivno', val: daysSince(alert.created_at) },
                    ].map(({label,val,accent}) => (
                      <div key={label} style={{ background:'var(--bg3)', borderRadius:10, padding:'10px', textAlign:'center' }}>
                        <div style={{ fontSize:20, fontWeight:800, color: accent ? 'var(--accent)' : 'var(--text)', lineHeight:1 }}>{val}</div>
                        <div style={{ fontSize:10, color:'var(--text3)', marginTop:3 }}>{label}</div>
                      </div>
                    ))}
                  </div>

                  {(alert.matches_count || 0) > 0 && (
                    <a href={`/search?make=${encodeURIComponent(alert.filters?.make||'')}&model=${encodeURIComponent(alert.filters?.model||'')}&max_price=${alert.filters?.max_price||''}&max_km=${alert.filters?.max_km||''}&min_year=${alert.filters?.min_year||''}`}
                      style={{ display:'flex', alignItems:'center', justifyContent:'center', gap:8, padding:'11px', borderRadius:12, background:'rgba(255,107,0,.1)', border:'1px solid rgba(255,107,0,.3)', color:'var(--accent)', textDecoration:'none', fontSize:13, fontWeight:700 }}>
                      🔎 Pogledaj pronađena vozila →
                    </a>
                  )}
                </div>
              </div>
            ))}

            <a href="/search" style={{ display:'flex', alignItems:'center', justifyContent:'center', gap:8, padding:'14px', borderRadius:14, background:'var(--bg2)', border:'2px dashed rgba(255,107,0,.3)', color:'var(--accent)', textDecoration:'none', fontSize:14, fontWeight:600 }}>
              + Dodaj novu potragu
            </a>
          </div>
        )}
      </div>
    </div>
  )
}
