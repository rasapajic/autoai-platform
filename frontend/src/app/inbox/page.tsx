'use client'
import { useState, useEffect } from 'react'

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'https://autoai-platform-production.up.railway.app/api/v1'

// ── Tipovi ────────────────────────────────────────────────────────
interface AnalysisResult {
  translation:    string
  keyInfo:        KeyInfo
  aiConclusion:   string
  nextReplyDE:    string
  nextReplySR:    string
  nextReplyEN:    string
}

interface KeyInfo {
  available:       boolean | null
  vin:             string | null
  price:           string | null
  mileage:         string | null
  serviceHistory:  boolean | null
  coc:             boolean | null
  damage:          string | null
  exportPossible:  boolean | null
}

const CONVERSATION_STATUSES = [
  { key:'new',          label:'Novo vozilo',               color:'#9CA3AF' },
  { key:'contacted',    label:'Kontaktiran prodavac',       color:'#818CF8' },
  { key:'waiting',      label:'Čeka odgovor',               color:'#F97316' },
  { key:'vin_received', label:'VIN primljen',               color:'#22C55E' },
  { key:'negotiating',  label:'U pregovorima',              color:'#EAB308' },
  { key:'purchased',    label:'Kupljeno',                   color:'#10B981' },
  { key:'rejected',     label:'Odbijeno',                   color:'#EF4444' },
]

// ── Helpers ───────────────────────────────────────────────────────
function StatusBadge({ status }: { status: string }) {
  const s = CONVERSATION_STATUSES.find(x => x.key === status) || CONVERSATION_STATUSES[0]
  return (
    <span style={{ fontSize:11, padding:'2px 9px', borderRadius:20, fontWeight:700,
      background: s.color+'20', color: s.color, border:`1px solid ${s.color}40` }}>
      {s.label}
    </span>
  )
}

function InfoRow({ label, value, ok }: { label: string; value: string | null; ok: boolean | null }) {
  const icon = ok === null ? '—' : ok ? '✅' : '❌'
  const color = ok === null ? 'var(--text3)' : ok ? '#22C55E' : '#EF4444'
  return (
    <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center',
      padding:'7px 0', borderBottom:'1px solid var(--border)' }}>
      <span style={{ fontSize:13, color:'var(--text3)' }}>{label}</span>
      <span style={{ fontSize:13, fontWeight:600, color, textAlign:'right', maxWidth:'55%' }}>
        {icon} {value || (ok === null ? 'nije navedeno' : ok ? 'da' : 'ne')}
      </span>
    </div>
  )
}

// ── Glavni Inbox ──────────────────────────────────────────────────
export default function InboxPage() {
  const [conversations, setConversations] = useState<any[]>([])
  const [selected,      setSelected]      = useState<any>(null)
  const [loading,       setLoading]       = useState(true)
  const [pasteText,     setPasteText]     = useState('')
  const [analyzing,     setAnalyzing]     = useState(false)
  const [analysis,      setAnalysis]      = useState<AnalysisResult | null>(null)
  const [analysisError, setAnalysisError] = useState('')
  const [replyLang,     setReplyLang]     = useState<'DE'|'SR'|'EN'>('DE')
  const [replyCopied,   setReplyCopied]   = useState(false)
  const [view,          setView]          = useState<'list'|'detail'>('list')
  const [statusUpdating, setStatusUpdating] = useState(false)

  useEffect(() => { fetchConversations() }, [])

  const fetchConversations = async () => {
    const token = localStorage.getItem('autoai_token')
    if (!token) { setLoading(false); return }
    try {
      const res = await fetch(`/api/inbox`, {
        headers: { 'Authorization': `Bearer ${token}` }
      })
      if (res.ok) {
        const data = await res.json()
        setConversations(data.conversations || data || [])
      }
    } catch {}
    setLoading(false)
  }

  const openConversation = (conv: any) => {
    setSelected(conv)
    setPasteText('')
    setAnalysis(null)
    setAnalysisError('')
    setView('detail')
  }

  const analyzeReply = async () => {
    if (!pasteText.trim()) return
    setAnalyzing(true); setAnalysis(null); setAnalysisError('')
    try {
      const res = await fetch(`/api/inbox/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('autoai_token')}` },
        body: JSON.stringify({
          reply_text:      pasteText,
          conversation_id: selected?.id || null,
          listing_title:   selected?.listing_title || '',
          seller_language: selected?.seller_language || 'German',
        }),
      })
      if (!res.ok) throw new Error()
      const data = await res.json()
      setAnalysis(data)
      // Refresh conversations
      fetchConversations()
    } catch {
      setAnalysisError('Greška pri analizi. Pokušaj ponovo.')
    }
    setAnalyzing(false)
  }

  const updateStatus = async (newStatus: string) => {
    if (!selected) return
    const token = localStorage.getItem('autoai_token')
    setStatusUpdating(true)
    try {
      const res = await fetch(`/api/inbox/${selected.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
        body: JSON.stringify({ status: newStatus }),
      })
      if (res.ok) {
        setSelected({ ...selected, status: newStatus })
        fetchConversations()
      }
    } catch {}
    setStatusUpdating(false)
  }

  const copyReply = () => {
    const reply = replyLang === 'DE' ? analysis?.nextReplyDE
                : replyLang === 'SR' ? analysis?.nextReplySR
                : analysis?.nextReplyEN
    if (reply) {
      navigator.clipboard.writeText(reply)
      setReplyCopied(true)
      setTimeout(() => setReplyCopied(false), 2000)
    }
  }

  const currentReply = replyLang === 'DE' ? analysis?.nextReplyDE
                     : replyLang === 'SR' ? analysis?.nextReplySR
                     : analysis?.nextReplyEN

  // ── MOBILE: Lista konverzacija ─────────────────────────────────
  if (view === 'list' || !selected) {
    return (
      <div style={{ minHeight:'100vh', background:'var(--bg)', padding:'16px 16px 80px' }}>
        <div style={{ marginBottom:20 }}>
          <h1 style={{ fontSize:22, fontWeight:800, fontFamily:'Syne,sans-serif', margin:'0 0 4px' }}>
            📥 AutoAI Inbox
          </h1>
          <p style={{ fontSize:13, color:'var(--text3)', margin:0 }}>
            Komunikacija sa prodavcima · AI analiza odgovora
          </p>
        </div>

        {/* Empty state */}
        {!loading && conversations.length === 0 && (
          <div style={{ textAlign:'center', padding:'60px 20px', background:'var(--bg2)',
            borderRadius:16, border:'1px solid var(--border)' }}>
            <div style={{ fontSize:48, marginBottom:16 }}>📭</div>
            <p style={{ fontSize:16, fontWeight:600, marginBottom:8 }}>Nema sačuvanih konverzacija</p>
            <p style={{ color:'var(--text3)', fontSize:14, marginBottom:20, lineHeight:1.6 }}>
              Kada kontaktiraš prodavca i klikneš<br />
              "Sačuvaj u Inbox", konverzacija se pojavi ovde.
            </p>
            <a href="/search" style={{ display:'inline-block', padding:'11px 22px',
              background:'var(--accent)', color:'#fff', borderRadius:10,
              fontWeight:700, fontSize:14, textDecoration:'none' }}>
              🔍 Pretraži vozila
            </a>
          </div>
        )}

        {/* Lista konverzacija */}
        {loading ? (
          <div style={{ display:'flex', flexDirection:'column', gap:10 }}>
            {[1,2,3].map(i => (
              <div key={i} className="skeleton" style={{ height:90, borderRadius:14 }} />
            ))}
          </div>
        ) : (
          <div style={{ display:'flex', flexDirection:'column', gap:10 }}>
            {conversations.map(conv => (
              <button key={conv.id} onClick={() => openConversation(conv)}
                style={{ background:'var(--bg2)', border:'1px solid var(--border)',
                  borderRadius:14, padding:'14px 16px', textAlign:'left', cursor:'pointer',
                  width:'100%', transition:'all .15s' }}>
                <div style={{ display:'flex', justifyContent:'space-between', alignItems:'flex-start', marginBottom:6 }}>
                  <div style={{ fontSize:14, fontWeight:700, color:'var(--text)', flex:1, marginRight:8 }}>
                    {conv.listing_title || 'Vozilo'}
                  </div>
                  <StatusBadge status={conv.status || 'new'} />
                </div>
                <div style={{ display:'flex', gap:12, fontSize:12, color:'var(--text3)' }}>
                  {conv.listing_price && (
                    <span>💶 {Number(conv.listing_price).toLocaleString('de-DE')} €</span>
                  )}
                  {conv.seller_country && <span>📍 {conv.seller_country}</span>}
                  <span>🌐 {conv.seller_language?.split(' ')[0] || 'DE'}</span>
                </div>
                {conv.last_message_at && (
                  <div style={{ fontSize:11, color:'var(--text3)', marginTop:4, opacity:.6 }}>
                    {new Date(conv.last_message_at).toLocaleDateString('sr-RS')}
                  </div>
                )}
              </button>
            ))}
          </div>
        )}
      </div>
    )
  }

  // ── DETAIL VIEW ────────────────────────────────────────────────
  return (
    <div style={{ minHeight:'100vh', background:'var(--bg)', padding:'0 0 80px' }}>

      {/* Header */}
      <div style={{ padding:'14px 16px', borderBottom:'1px solid var(--border)',
        background:'var(--bg2)', display:'flex', alignItems:'center', gap:12, position:'sticky', top:0, zIndex:10 }}>
        <button onClick={() => { setView('list'); setSelected(null) }}
          style={{ background:'none', border:'none', color:'var(--text2)', fontSize:20, cursor:'pointer', padding:0 }}>
          ←
        </button>
        <div style={{ flex:1 }}>
          <div style={{ fontSize:14, fontWeight:700, color:'var(--text)' }}>
            {selected.listing_title || 'Konverzacija'}
          </div>
          <StatusBadge status={selected.status || 'new'} />
        </div>
        {selected.listing_url && (
          <a href={selected.listing_url} target="_blank" rel="noopener"
            style={{ fontSize:12, color:'var(--accent)', textDecoration:'none', fontWeight:600 }}>
            Oglas →
          </a>
        )}
      </div>

      <div style={{ padding:'16px' }}>

        {/* Status promjena */}
        <div style={{ background:'var(--bg2)', border:'1px solid var(--border)',
          borderRadius:14, padding:'12px 14px', marginBottom:16 }}>
          <div style={{ fontSize:11, color:'var(--text3)', fontWeight:600,
            letterSpacing:'.07em', marginBottom:10 }}>PROMIJENI STATUS</div>
          <div style={{ display:'flex', flexWrap:'wrap', gap:6 }}>
            {CONVERSATION_STATUSES.map(s => (
              <button key={s.key} onClick={() => updateStatus(s.key)}
                disabled={statusUpdating}
                style={{ padding:'5px 10px', borderRadius:20, fontSize:11, cursor:'pointer',
                  fontWeight:600, transition:'all .15s',
                  background: selected.status === s.key ? s.color+'20' : 'transparent',
                  border: `1px solid ${selected.status === s.key ? s.color : 'var(--border)'}`,
                  color: selected.status === s.key ? s.color : 'var(--text3)' }}>
                {s.label}
              </button>
            ))}
          </div>
        </div>

        {/* Paste area */}
        <div style={{ background:'var(--bg2)', border:'1px solid var(--border)',
          borderRadius:14, padding:'14px', marginBottom:16 }}>
          <div style={{ fontSize:13, fontWeight:700, marginBottom:10, display:'flex', alignItems:'center', gap:8 }}>
            <span>📨</span> Nalepi odgovor prodavca
          </div>
          <textarea
            value={pasteText}
            onChange={e => setPasteText(e.target.value)}
            placeholder="Kopiraj email od prodavca i nalepi ovde (Ctrl+V)...

Beispiel / Örnek:
Guten Tag,
vielen Dank für Ihre Anfrage. Das Fahrzeug ist noch verfügbar.
Die FIN/VIN lautet: WBA3A510X0F123456
..."
            rows={7}
            style={{ width:'100%', background:'var(--bg3)', border:'1px solid var(--border)',
              borderRadius:10, padding:'12px 14px', color:'var(--text)', fontSize:13,
              outline:'none', resize:'vertical', boxSizing:'border-box' as any,
              fontFamily:'inherit', lineHeight:1.6 }}
          />
          <button onClick={analyzeReply} disabled={analyzing || !pasteText.trim()}
            style={{ width:'100%', marginTop:10, padding:'13px', borderRadius:10, border:'none',
              background: (!pasteText.trim() || analyzing) ? 'var(--bg3)' : 'var(--accent)',
              color: (!pasteText.trim() || analyzing) ? 'var(--text3)' : '#fff',
              fontSize:14, fontWeight:700,
              cursor: (!pasteText.trim() || analyzing) ? 'default' : 'pointer' }}>
            {analyzing ? '🔍 Analiziram odgovor...' : '🔍 Analiziraj odgovor'}
          </button>
          {analysisError && (
            <p style={{ color:'#EF4444', fontSize:13, margin:'8px 0 0', textAlign:'center' }}>
              {analysisError}
            </p>
          )}
        </div>

        {/* Rezultat analize */}
        {analysis && (
          <div style={{ display:'flex', flexDirection:'column', gap:12 }}>

            {/* Prevod */}
            <div style={{ background:'var(--bg2)', border:'1px solid var(--border)',
              borderRadius:14, padding:'14px' }}>
              <div style={{ fontSize:12, fontWeight:700, color:'var(--text3)',
                letterSpacing:'.07em', marginBottom:10 }}>🌐 PREVOD NA SRPSKI</div>
              <p style={{ fontSize:13, color:'var(--text2)', lineHeight:1.7,
                margin:0, whiteSpace:'pre-wrap' }}>
                {analysis.translation}
              </p>
            </div>

            {/* Ključne informacije */}
            <div style={{ background:'var(--bg2)', border:'1px solid var(--border)',
              borderRadius:14, padding:'14px' }}>
              <div style={{ fontSize:12, fontWeight:700, color:'var(--text3)',
                letterSpacing:'.07em', marginBottom:10 }}>📋 KLJUČNE INFORMACIJE</div>
              <InfoRow label="Vozilo dostupno"    value={null}                        ok={analysis.keyInfo.available} />
              <InfoRow label="VIN broj"           value={analysis.keyInfo.vin}        ok={!!analysis.keyInfo.vin} />
              <InfoRow label="Poslednja cena"     value={analysis.keyInfo.price}      ok={!!analysis.keyInfo.price} />
              <InfoRow label="Kilometraža"        value={analysis.keyInfo.mileage}    ok={!!analysis.keyInfo.mileage} />
              <InfoRow label="Servisna istorija"  value={null}                        ok={analysis.keyInfo.serviceHistory} />
              <InfoRow label="COC dokument"       value={null}                        ok={analysis.keyInfo.coc} />
              <InfoRow label="Oštećenja"          value={analysis.keyInfo.damage}     ok={analysis.keyInfo.damage === null ? null : false} />
              <InfoRow label="Izvoz moguć"        value={null}                        ok={analysis.keyInfo.exportPossible} />
            </div>

            {/* AI zaključak */}
            <div style={{ background:'rgba(99,102,241,.07)', border:'1px solid rgba(99,102,241,.3)',
              borderRadius:14, padding:'14px' }}>
              <div style={{ fontSize:12, fontWeight:700, color:'#818CF8',
                letterSpacing:'.07em', marginBottom:8 }}>🤖 AI ZAKLJUČAK</div>
              <p style={{ fontSize:13, color:'var(--text2)', lineHeight:1.7, margin:0 }}>
                {analysis.aiConclusion}
              </p>
            </div>

            {/* Predlog sledećeg odgovora */}
            <div style={{ background:'var(--bg2)', border:'1px solid var(--border)',
              borderRadius:14, padding:'14px' }}>
              <div style={{ fontSize:12, fontWeight:700, color:'var(--text3)',
                letterSpacing:'.07em', marginBottom:10 }}>✍️ PREDLOG SLEDEĆEG ODGOVORA</div>

              {/* Izbor jezika */}
              <div style={{ display:'flex', gap:6, marginBottom:10 }}>
                {[
                  { key:'DE', flag:'🇩🇪', label:'Nemački' },
                  { key:'SR', flag:'🇷🇸', label:'Srpski' },
                  { key:'EN', flag:'🇬🇧', label:'Engleski' },
                ].map(l => (
                  <button key={l.key} onClick={() => setReplyLang(l.key as any)}
                    style={{ flex:1, padding:'7px', borderRadius:8, fontSize:12, fontWeight:600,
                      cursor:'pointer', transition:'all .15s',
                      background: replyLang === l.key ? 'rgba(255,107,0,.15)' : 'var(--bg3)',
                      border: `1px solid ${replyLang === l.key ? 'var(--accent)' : 'var(--border)'}`,
                      color: replyLang === l.key ? 'var(--accent)' : 'var(--text3)' }}>
                    {l.flag} {l.label}
                  </button>
                ))}
              </div>

              <div style={{ background:'var(--bg3)', border:'1px solid var(--border)',
                borderRadius:10, padding:'12px 14px', fontSize:13, lineHeight:1.75,
                color:'var(--text2)', whiteSpace:'pre-wrap', marginBottom:10,
                maxHeight:200, overflowY:'auto' }}>
                {currentReply}
              </div>

              <button onClick={copyReply} style={{
                width:'100%', padding:'11px', borderRadius:10, fontSize:13, fontWeight:700,
                cursor:'pointer', transition:'all .2s',
                background: replyCopied ? 'rgba(34,197,94,.12)' : 'rgba(255,107,0,.1)',
                border: `1px solid ${replyCopied ? '#22C55E' : 'rgba(255,107,0,.3)'}`,
                color: replyCopied ? '#22C55E' : 'var(--accent)',
              }}>
                {replyCopied ? '✓ Kopirano!' : '📋 Kopiraj odgovor'}
              </button>
            </div>

          </div>
        )}

        {/* Istorija poruka */}
        {selected.messages && selected.messages.length > 0 && (
          <div style={{ marginTop:16 }}>
            <div style={{ fontSize:12, fontWeight:700, color:'var(--text3)',
              letterSpacing:'.07em', marginBottom:10 }}>📜 ISTORIJA KOMUNIKACIJE</div>
            <div style={{ display:'flex', flexDirection:'column', gap:8 }}>
              {selected.messages.map((msg: any) => (
                <div key={msg.id} style={{
                  background: msg.direction === 'outbound' ? 'rgba(99,102,241,.08)' : 'var(--bg2)',
                  border: `1px solid ${msg.direction === 'outbound' ? 'rgba(99,102,241,.3)' : 'var(--border)'}`,
                  borderRadius:12, padding:'10px 14px',
                }}>
                  <div style={{ display:'flex', justifyContent:'space-between', marginBottom:4 }}>
                    <span style={{ fontSize:11, fontWeight:700,
                      color: msg.direction === 'outbound' ? '#818CF8' : '#22C55E' }}>
                      {msg.direction === 'outbound' ? '📤 Tvoja poruka' : '📥 Odgovor prodavca'}
                    </span>
                    <span style={{ fontSize:11, color:'var(--text3)' }}>
                      {new Date(msg.created_at).toLocaleDateString('sr-RS')}
                    </span>
                  </div>
                  <p style={{ fontSize:12, color:'var(--text2)', margin:0, lineHeight:1.6,
                    maxHeight:80, overflow:'hidden', textOverflow:'ellipsis' }}>
                    {msg.content?.slice(0, 200)}{msg.content?.length > 200 ? '...' : ''}
                  </p>
                </div>
              ))}
            </div>
          </div>
        )}

      </div>
    </div>
  )
}
