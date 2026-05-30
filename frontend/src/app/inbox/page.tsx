'use client'
import { useEffect, useState } from 'react'

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'https://autoai-platform-production.up.railway.app/api/v1'

const STATUS_CONFIG: Record<string, {label:string; color:string; bg:string; emoji:string}> = {
  pending_send:    { label:'Čeka slanje',     color:'#9CA3AF', bg:'rgba(156,163,175,.1)', emoji:'📝' },
  sent:            { label:'Poslato',          color:'#818CF8', bg:'rgba(99,102,241,.1)',  emoji:'📤' },
  reply_received:  { label:'Odgovor primljen', color:'#F97316', bg:'rgba(249,115,22,.1)',  emoji:'📩' },
  vin_received:    { label:'VIN primljen',     color:'#22C55E', bg:'rgba(34,197,94,.1)',   emoji:'🔐' },
  negotiating:     { label:'Pregovori',        color:'#EAB308', bg:'rgba(234,179,8,.1)',   emoji:'🤝' },
  closed:          { label:'Zatvoreno',        color:'#22C55E', bg:'rgba(34,197,94,.1)',   emoji:'✅' },
  rejected:        { label:'Odbijeno',         color:'#EF4444', bg:'rgba(239,68,68,.1)',   emoji:'❌' },
}

const RECOM_CONFIG: Record<string, {label:string; color:string}> = {
  buy:       { label:'🟢 Preporučuje se kupovina', color:'#22C55E' },
  negotiate: { label:'🟡 Pregovaraj o ceni',        color:'#EAB308' },
  verify:    { label:'🟠 Potrebna dodatna provera',  color:'#F97316' },
  skip:      { label:'🔴 Preskoči oglas',            color:'#EF4444' },
}

function fmt(n: any) { return Number(n).toLocaleString('de-DE') }

function timeAgo(iso: string): string {
  if (!iso) return ''
  const diff = (Date.now() - new Date(iso).getTime()) / 1000
  if (diff < 60)   return 'Upravo'
  if (diff < 3600) return `${Math.floor(diff/60)} min`
  if (diff < 86400) return `${Math.floor(diff/3600)}h`
  return `${Math.floor(diff/86400)}d`
}

export default function InboxPage() {
  const [convs,       setConvs]       = useState<any[]>([])
  const [selected,    setSelected]    = useState<any>(null)
  const [loading,     setLoading]     = useState(true)
  const [replyText,   setReplyText]   = useState('')
  const [replyLoading,setReplyLoading]= useState(false)
  const [stats,       setStats]       = useState<any>(null)
  const [filterStatus,setFilterStatus]= useState('')
  const [error,       setError]       = useState('')

  const token = typeof window !== 'undefined' ? localStorage.getItem('autoai_token') : null

  useEffect(() => {
    if (!token) { window.location.href = '/login'; return }
    loadConvs()
    loadStats()
  }, [filterStatus])

  const authHeaders = { 'Content-Type':'application/json', 'Authorization':`Bearer ${token}` }

  async function loadConvs() {
    setLoading(true)
    try {
      const url = `${API_BASE}/inbox/conversations${filterStatus ? `?status=${filterStatus}` : ''}`
      const res = await fetch(url, { headers: authHeaders })
      const data = await res.json()
      setConvs(Array.isArray(data) ? data : [])
    } catch { setError('Greška pri učitavanju.') }
    setLoading(false)
  }

  async function loadStats() {
    try {
      const res = await fetch(`${API_BASE}/inbox/conversations/stats/summary`, { headers: authHeaders })
      const data = await res.json()
      setStats(data)
    } catch {}
  }

  async function openConv(id: string) {
    try {
      const res = await fetch(`${API_BASE}/inbox/conversations/${id}`, { headers: authHeaders })
      const data = await res.json()
      setSelected(data)
      // Označi poruke kao pročitane
    } catch {}
  }

  async function sendReply() {
    if (!replyText.trim() || !selected) return
    setReplyLoading(true)
    try {
      const res = await fetch(`${API_BASE}/inbox/conversations/${selected.id}/reply`, {
        method: 'POST', headers: authHeaders,
        body: JSON.stringify({ content: replyText.trim() }),
      })
      const data = await res.json()
      setSelected(data)
      setReplyText('')
      loadConvs()
      loadStats()
    } catch { setError('Greška pri slanju odgovora.') }
    setReplyLoading(false)
  }

  async function updateStatus(id: string, status: string) {
    try {
      await fetch(`${API_BASE}/inbox/conversations/${id}/status`, {
        method: 'PUT', headers: authHeaders,
        body: JSON.stringify({ status }),
      })
      loadConvs()
      if (selected?.id === id) setSelected((prev: any) => ({ ...prev, status }))
    } catch {}
  }

  async function deleteConv(id: string) {
    if (!confirm('Obrisati konverzaciju?')) return
    await fetch(`${API_BASE}/inbox/conversations/${id}`, { method: 'DELETE', headers: authHeaders })
    if (selected?.id === id) setSelected(null)
    loadConvs()
    loadStats()
  }

  const unread = stats?.unread_replies || 0

  return (
    <div style={{ minHeight:'100vh', background:'var(--bg)', paddingBottom:40 }}>
      <style>{`
        @media(max-width:768px){
          .inbox-grid { grid-template-columns:1fr !important; }
          .inbox-detail { display: ${selected ? 'block' : 'none'} !important; }
          .inbox-list { display: ${selected ? 'none' : 'block'} !important; }
        }
      `}</style>

      <div className="container" style={{ padding:'20px 16px 0' }}>

        {/* Header */}
        <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:20 }}>
          <div>
            <h1 style={{ fontSize:22, fontWeight:800, fontFamily:'Syne,sans-serif', margin:'0 0 4px' }}>
              📬 AI Inbox
              {unread > 0 && (
                <span style={{ marginLeft:10, fontSize:13, background:'#EF4444', color:'#fff', borderRadius:20, padding:'2px 8px', fontWeight:700 }}>
                  {unread} novo
                </span>
              )}
            </h1>
            <p style={{ fontSize:13, color:'var(--text3)', margin:0 }}>Komunikacija sa prodavcima vozila</p>
          </div>
        </div>

        {/* Stats */}
        {stats && (
          <div style={{ display:'flex', gap:8, marginBottom:16, overflowX:'auto', paddingBottom:4 }}>
            {[
              { key:'', label:'Sve', count:stats.total },
              { key:'sent', label:'📤 Poslato', count:stats.sent },
              { key:'reply_received', label:'📩 Odgovor', count:stats.reply_received },
              { key:'vin_received', label:'🔐 VIN', count:stats.vin_received },
              { key:'negotiating', label:'🤝 Pregovori', count:stats.negotiating },
            ].map(({ key, label, count }) => (
              <button key={key} onClick={() => setFilterStatus(key)} style={{
                flexShrink:0, padding:'6px 12px', borderRadius:20, fontSize:12, cursor:'pointer',
                background: filterStatus===key ? 'rgba(255,107,0,.15)' : 'var(--bg2)',
                border: `1px solid ${filterStatus===key ? 'var(--accent)' : 'var(--border)'}`,
                color: filterStatus===key ? 'var(--accent)' : 'var(--text2)',
                fontWeight: filterStatus===key ? 700 : 400,
              }}>
                {label} <span style={{ opacity:.6 }}>{count}</span>
              </button>
            ))}
          </div>
        )}

        {error && (
          <div style={{ background:'rgba(239,68,68,.1)', border:'1px solid rgba(239,68,68,.3)', borderRadius:10, padding:'10px 14px', marginBottom:12, color:'#EF4444', fontSize:13 }}>
            ⚠️ {error}
          </div>
        )}

        <div className="inbox-grid" style={{ display:'grid', gridTemplateColumns:'340px 1fr', gap:16, alignItems:'start' }}>

          {/* Lista konverzacija */}
          <div className="inbox-list">
            {loading ? (
              [...Array(4)].map((_,i) => <div key={i} className="skeleton" style={{ height:80, borderRadius:12, marginBottom:8 }} />)
            ) : convs.length === 0 ? (
              <div style={{ textAlign:'center', padding:'40px 20px', background:'var(--bg2)', borderRadius:16, border:'1px solid var(--border)' }}>
                <div style={{ fontSize:40, marginBottom:10 }}>📭</div>
                <p style={{ fontSize:15, fontWeight:600, marginBottom:6 }}>Nema konverzacija</p>
                <p style={{ fontSize:13, color:'var(--text3)' }}>
                  Kontaktiraj prodavca sa listing stranice i poruka će se pojaviti ovde.
                </p>
              </div>
            ) : (
              convs.map(conv => {
                const statusCfg = STATUS_CONFIG[conv.status] || STATUS_CONFIG.sent
                const isSelected = selected?.id === conv.id
                return (
                  <div key={conv.id} onClick={() => openConv(conv.id)} style={{
                    background: isSelected ? 'rgba(255,107,0,.06)' : 'var(--bg2)',
                    border: `1px solid ${isSelected ? 'rgba(255,107,0,.4)' : 'var(--border)'}`,
                    borderRadius:12, padding:'12px 14px', marginBottom:8, cursor:'pointer',
                    transition:'all .15s',
                  }}>
                    <div style={{ display:'flex', justifyContent:'space-between', alignItems:'flex-start', marginBottom:6 }}>
                      <div style={{ flex:1, overflow:'hidden' }}>
                        <div style={{ fontSize:13, fontWeight:600, overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>
                          {conv.listing_title || 'Nepoznato vozilo'}
                        </div>
                        <div style={{ fontSize:11, color:'var(--text3)', marginTop:2 }}>
                          {conv.listing_source && <span style={{ marginRight:6 }}>{conv.listing_source}</span>}
                          {conv.listing_price && <span>{fmt(conv.listing_price)} €</span>}
                        </div>
                      </div>
                      <div style={{ textAlign:'right', flexShrink:0, marginLeft:8 }}>
                        <span style={{ fontSize:10, padding:'2px 7px', borderRadius:20, background:statusCfg.bg, color:statusCfg.color, fontWeight:600 }}>
                          {statusCfg.emoji} {statusCfg.label}
                        </span>
                        <div style={{ fontSize:10, color:'var(--text3)', marginTop:3 }}>{timeAgo(conv.last_message_at)}</div>
                      </div>
                    </div>

                    {/* Indikatori */}
                    <div style={{ display:'flex', gap:5, flexWrap:'wrap' }}>
                      {conv.vin_received  && <span style={{ fontSize:10, padding:'1px 6px', borderRadius:20, background:'rgba(34,197,94,.1)', color:'#22C55E', border:'1px solid rgba(34,197,94,.2)' }}>🔐 VIN</span>}
                      {conv.service_history_confirmed === true  && <span style={{ fontSize:10, padding:'1px 6px', borderRadius:20, background:'rgba(34,197,94,.1)', color:'#22C55E' }}>📋 Servis</span>}
                      {conv.coc_document_confirmed === true     && <span style={{ fontSize:10, padding:'1px 6px', borderRadius:20, background:'rgba(34,197,94,.1)', color:'#22C55E' }}>📄 COC</span>}
                      {conv.damage_mentioned === true            && <span style={{ fontSize:10, padding:'1px 6px', borderRadius:20, background:'rgba(239,68,68,.1)', color:'#EF4444' }}>⚠ Oštećenje</span>}
                      {conv.status === 'reply_received'          && <span style={{ fontSize:10, padding:'1px 6px', borderRadius:20, background:'rgba(249,115,22,.15)', color:'#F97316', fontWeight:700 }}>● Novo</span>}
                    </div>
                  </div>
                )
              })
            )}
          </div>

          {/* Detalji konverzacije */}
          <div className="inbox-detail">
            {!selected ? (
              <div style={{ textAlign:'center', padding:'80px 20px', background:'var(--bg2)', borderRadius:16, border:'1px solid var(--border)' }}>
                <div style={{ fontSize:48, marginBottom:12 }}>💬</div>
                <p style={{ fontSize:16, fontWeight:600, marginBottom:6 }}>Izaberi konverzaciju</p>
                <p style={{ fontSize:13, color:'var(--text3)' }}>Klikni na konverzaciju iz liste da vidiš detalje</p>
              </div>
            ) : (
              <div style={{ background:'var(--bg2)', border:'1px solid var(--border)', borderRadius:16, overflow:'hidden' }}>

                {/* Header konverzacije */}
                <div style={{ padding:'16px 20px', borderBottom:'1px solid var(--border)', display:'flex', justifyContent:'space-between', alignItems:'flex-start' }}>
                  <div style={{ flex:1 }}>
                    <div style={{ display:'flex', alignItems:'center', gap:8, marginBottom:4 }}>
                      <button onClick={() => setSelected(null)} style={{ background:'none', border:'none', color:'var(--text3)', cursor:'pointer', fontSize:18, padding:0, display:'none' }} className="mobile-back">←</button>
                      <h2 style={{ fontSize:15, fontWeight:700, margin:0 }}>{selected.listing_title}</h2>
                    </div>
                    <div style={{ display:'flex', gap:8, flexWrap:'wrap', alignItems:'center' }}>
                      {selected.listing_price && <span style={{ fontSize:13, color:'var(--accent)', fontWeight:700 }}>{fmt(selected.listing_price)} €</span>}
                      {selected.listing_source && <span style={{ fontSize:11, color:'var(--text3)' }}>{selected.listing_source}</span>}
                      <span style={{ fontSize:11, padding:'2px 7px', borderRadius:20, background:STATUS_CONFIG[selected.status]?.bg, color:STATUS_CONFIG[selected.status]?.color, fontWeight:600 }}>
                        {STATUS_CONFIG[selected.status]?.emoji} {STATUS_CONFIG[selected.status]?.label}
                      </span>
                    </div>
                  </div>
                  <div style={{ display:'flex', gap:6 }}>
                    {selected.listing_url && (
                      <a href={selected.listing_url} target="_blank" rel="noopener" style={{ fontSize:12, padding:'6px 10px', background:'var(--bg3)', border:'1px solid var(--border)', color:'var(--text2)', borderRadius:8, textDecoration:'none' }}>Oglas →</a>
                    )}
                    <button onClick={() => deleteConv(selected.id)} style={{ fontSize:12, padding:'6px 10px', background:'transparent', border:'1px solid rgba(239,68,68,.3)', color:'#EF4444', borderRadius:8, cursor:'pointer' }}>🗑</button>
                  </div>
                </div>

                {/* AI Analiza */}
                {(selected.ai_summary || selected.ai_recommendation) && (
                  <div style={{ margin:'12px 20px', background:'rgba(99,102,241,.07)', border:'1px solid rgba(99,102,241,.2)', borderRadius:12, padding:'12px 14px' }}>
                    <div style={{ fontSize:11, color:'#818CF8', fontWeight:600, marginBottom:6 }}>🤖 AI ANALIZA</div>
                    {selected.ai_recommendation && RECOM_CONFIG[selected.ai_recommendation] && (
                      <div style={{ fontSize:13, fontWeight:700, color:RECOM_CONFIG[selected.ai_recommendation].color, marginBottom:4 }}>
                        {RECOM_CONFIG[selected.ai_recommendation].label}
                      </div>
                    )}
                    {selected.ai_summary && <p style={{ fontSize:12, color:'var(--text2)', margin:0, lineHeight:1.6 }}>{selected.ai_summary}</p>}
                  </div>
                )}

                {/* Prikupljene informacije */}
                {(selected.vin_received || selected.service_history_confirmed !== null || selected.coc_document_confirmed !== null) && (
                  <div style={{ margin:'0 20px 12px', background:'var(--bg3)', borderRadius:12, padding:'12px 14px' }}>
                    <div style={{ fontSize:11, color:'var(--text3)', fontWeight:600, marginBottom:8 }}>📊 PRIKUPLJENE INFORMACIJE</div>
                    <div style={{ display:'grid', gridTemplateColumns:'repeat(3,1fr)', gap:8 }}>
                      {[
                        { label:'VIN', value:selected.vin_received ? '✅ Primljen' : '⏳ Čeka', ok:!!selected.vin_received },
                        { label:'Servisna', value:selected.service_history_confirmed===true?'✅ Da':selected.service_history_confirmed===false?'❌ Ne':'⏳ N/A', ok:selected.service_history_confirmed===true },
                        { label:'COC', value:selected.coc_document_confirmed===true?'✅ Da':selected.coc_document_confirmed===false?'❌ Ne':'⏳ N/A', ok:selected.coc_document_confirmed===true },
                        { label:'Export', value:selected.export_possible_confirmed===true?'✅ Da':selected.export_possible_confirmed===false?'❌ Ne':'⏳ N/A', ok:selected.export_possible_confirmed===true },
                        { label:'Cena', value:selected.seller_confirmed_price?`${fmt(selected.seller_confirmed_price)} €`:'⏳ N/A', ok:!!selected.seller_confirmed_price },
                        { label:'Oštećenje', value:selected.damage_mentioned===true?`⚠️ ${selected.damage_description||'Da'}`:selected.damage_mentioned===false?'✅ Nema':'⏳ N/A', ok:selected.damage_mentioned===false },
                      ].map(({ label, value, ok }) => (
                        <div key={label} style={{ background:'var(--bg2)', borderRadius:8, padding:'7px 10px' }}>
                          <div style={{ fontSize:10, color:'var(--text3)', marginBottom:2 }}>{label}</div>
                          <div style={{ fontSize:11, fontWeight:600, color:ok?'#22C55E':'var(--text2)' }}>{value}</div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Poruke */}
                <div style={{ padding:'0 20px', maxHeight:400, overflowY:'auto', display:'flex', flexDirection:'column', gap:10, paddingTop:12 }}>
                  {(selected.messages || []).map((msg: any) => (
                    <div key={msg.id} style={{
                      display:'flex', flexDirection:'column',
                      alignItems: msg.direction==='outbound' ? 'flex-end' : 'flex-start',
                    }}>
                      <div style={{ fontSize:10, color:'var(--text3)', marginBottom:3 }}>
                        {msg.direction==='outbound' ? '📤 Ti' : '📩 Prodavac'} · {timeAgo(msg.created_at)}
                      </div>
                      <div style={{
                        maxWidth:'80%', padding:'10px 14px', borderRadius:12, fontSize:13, lineHeight:1.6, whiteSpace:'pre-wrap',
                        background: msg.direction==='outbound' ? 'rgba(99,102,241,.15)' : 'var(--bg3)',
                        border: `1px solid ${msg.direction==='outbound' ? 'rgba(99,102,241,.3)' : 'var(--border)'}`,
                        color: 'var(--text2)',
                        borderTopRightRadius: msg.direction==='outbound' ? 4 : 12,
                        borderTopLeftRadius:  msg.direction==='inbound'  ? 4 : 12,
                      }}>
                        {msg.content}
                      </div>
                      {msg.ai_extracted && msg.direction==='inbound' && (
                        <div style={{ fontSize:10, color:'#818CF8', marginTop:3, maxWidth:'80%' }}>
                          🤖 AI izvukao: {Object.entries(msg.ai_extracted).filter(([k,v]) => v && !['summary','recommendation','recommendation_reason'].includes(k)).map(([k,v]) => `${k}: ${v}`).join(' · ')}
                        </div>
                      )}
                    </div>
                  ))}
                </div>

                {/* Unos odgovora prodavca */}
                <div style={{ padding:'16px 20px', borderTop:'1px solid var(--border)', marginTop:12 }}>
                  <div style={{ fontSize:11, color:'var(--text3)', fontWeight:600, marginBottom:8 }}>
                    📩 ZALIJEPI ODGOVOR PRODAVCA
                  </div>
                  <textarea
                    value={replyText}
                    onChange={e => setReplyText(e.target.value)}
                    placeholder="Kopiraj i zalijepi odgovor koji si dobio od prodavca — AI će automatski analizirati..."
                    rows={4}
                    style={{ width:'100%', background:'var(--bg3)', border:'1px solid var(--border)', borderRadius:10, padding:'10px 13px', color:'var(--text)', fontSize:13, outline:'none', resize:'none', boxSizing:'border-box', fontFamily:'inherit', lineHeight:1.6, marginBottom:10 }}
                  />
                  <div style={{ display:'flex', gap:8 }}>
                    <button onClick={sendReply} disabled={replyLoading || !replyText.trim()} style={{
                      flex:1, padding:'11px', borderRadius:10, border:'none', cursor:'pointer', fontSize:13, fontWeight:700,
                      background: (!replyText.trim() || replyLoading) ? 'var(--bg3)' : 'var(--accent)',
                      color: (!replyText.trim() || replyLoading) ? 'var(--text3)' : '#fff',
                    }}>
                      {replyLoading ? '⏳ AI analizira...' : '🤖 Dodaj odgovor i analiziraj'}
                    </button>
                    <select onChange={e => updateStatus(selected.id, e.target.value)} value={selected.status} style={{ padding:'0 12px', background:'var(--bg3)', border:'1px solid var(--border)', color:'var(--text2)', borderRadius:10, fontSize:12, cursor:'pointer', outline:'none' }}>
                      {Object.entries(STATUS_CONFIG).map(([k,v]) => (
                        <option key={k} value={k}>{v.emoji} {v.label}</option>
                      ))}
                    </select>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
