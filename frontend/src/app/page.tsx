'use client'
import { useState, useEffect } from 'react'
import { parseQuery, searchListings, getSearchStats } from '@/lib/api'
import { useRouter } from 'next/navigation'

export default function HomePage() {
  const [query, setQuery]   = useState('')
  const [loading, setLoading] = useState(false)
  const [stats, setStats]   = useState<any>(null)
  const router = useRouter()

  useEffect(() => {
    getSearchStats().then(setStats).catch(() => {})
  }, [])

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!query.trim()) { router.push('/search'); return }
    setLoading(true)
    try {
      const { filters } = await parseQuery(query)
      const params = new URLSearchParams(
        Object.entries(filters).filter(([,v]) => v != null).map(([k,v]) => [k, String(v)])
      )
      router.push(`/search?${params}&q=${encodeURIComponent(query)}`)
    } catch {
      router.push(`/search?q=${encodeURIComponent(query)}`)
    } finally {
      setLoading(false)
    }
  }

  const examples = [
    'BMW 5 dizel do 15000 eura',
    'Tesla Model 3 2021 ili noviji',
    'Mali gradski auto do 5000',
    'SUV automat iz Nemačke max 100k km',
    'Golf benzin 2018–2021',
  ]

  return (
    <div>
      {/* Hero */}
      <section style={{
        padding: '80px 0 60px',
        background: 'radial-gradient(ellipse 80% 50% at 50% -10%, #F9731620 0%, transparent 70%)',
        borderBottom: '1px solid var(--border)',
      }}>
        <div className="container" style={{ maxWidth: 720, textAlign: 'center' }}>
          <div className="fade-up" style={{
            display: 'inline-flex', alignItems: 'center', gap: 6,
            background: 'var(--bg3)', border: '1px solid var(--border2)',
            borderRadius: 20, padding: '5px 14px', fontSize: 12,
            color: 'var(--accent)', marginBottom: 24, letterSpacing: '0.05em',
          }}>
            <span>✦</span> AI PRETRAGA AUTOMOBILA
          </div>

          <h1 className="fade-up" style={{
            fontSize: 'clamp(2.2rem, 6vw, 3.8rem)',
            marginBottom: 20,
            animationDelay: '.05s',
          }}>
            Pronađi pravi auto<br />
            <span style={{ color: 'var(--accent)' }}>u celoj Evropi</span>
          </h1>

          <p className="fade-up" style={{
            color: 'var(--text2)', fontSize: 17, marginBottom: 36,
            animationDelay: '.1s',
          }}>
            Pretraži milione oglasa sa AutoScout24, Mobile.de i Polovniautomobili.
            AI razumije šta tražiš — piši slobodnim jezikom.
          </p>

          {/* Search box */}
          <form onSubmit={handleSearch} className="fade-up" style={{ animationDelay: '.15s' }}>
            <div style={{
              display: 'flex', gap: 8,
              background: 'var(--bg3)', border: '1px solid var(--border2)',
              borderRadius: 14, padding: 6,
              boxShadow: '0 8px 40px rgba(0,0,0,.3)',
            }}>
              <div style={{ flex: 1, display: 'flex', alignItems: 'center', gap: 10, padding: '0 12px' }}>
                <span style={{ fontSize: 18 }}>🤖</span>
                <input
                  value={query}
                  onChange={e => setQuery(e.target.value)}
                  placeholder='npr. "BMW dizel do 15000, max 150k km"'
                  style={{
                    flex: 1, background: 'none', border: 'none', outline: 'none',
                    color: 'var(--text)', fontSize: 15,
                  }}
                />
              </div>
              <button type="submit" disabled={loading} style={{
                background: loading ? 'var(--border2)' : 'var(--accent)',
                color: '#fff', border: 'none', borderRadius: 10,
                padding: '12px 24px', fontSize: 14, fontWeight: 600,
                transition: 'all .15s', whiteSpace: 'nowrap',
              }}>
                {loading ? '...' : 'Traži →'}
              </button>
            </div>
          </form>

          {/* Example queries */}
          <div className="fade-up" style={{
            display: 'flex', flexWrap: 'wrap', gap: 8,
            justifyContent: 'center', marginTop: 16,
            animationDelay: '.2s',
          }}>
            {examples.map(ex => (
              <button key={ex} onClick={() => setQuery(ex)} style={{
                background: 'var(--bg3)', border: '1px solid var(--border)',
                color: 'var(--text2)', borderRadius: 20, padding: '5px 14px',
                fontSize: 13, transition: 'all .15s',
              }}
              onMouseEnter={e => { const t = e.target as HTMLElement; t.style.borderColor='var(--accent)'; t.style.color='var(--accent)' }}
              onMouseLeave={e => { const t = e.target as HTMLElement; t.style.borderColor='var(--border)'; t.style.color='var(--text2)' }}
              >{ex}</button>
            ))}
          </div>
        </div>
      </section>

      {/* Stats */}
      {stats && (
        <section style={{ padding: '48px 0', borderBottom: '1px solid var(--border)' }}>
          <div className="container" style={{
            display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 16,
          }}>
            {[
              { label: 'Aktivnih oglasa', value: stats.active_listings?.toLocaleString() || '—', icon: '🚗' },
              { label: 'Portala', value: Object.keys(stats.portals || {}).length, icon: '🌍' },
              { label: 'Prosečna cena', value: stats.avg_price_eur ? `${Math.round(stats.avg_price_eur).toLocaleString()} €` : '—', icon: '💶' },
              { label: 'Marki', value: stats.top_makes?.length || '—', icon: '🏷️' },
            ].map(s => (
              <div key={s.label} style={{
                background: 'var(--bg2)', border: '1px solid var(--border)',
                borderRadius: 'var(--radius)', padding: '20px 24px',
                textAlign: 'center',
              }}>
                <div style={{ fontSize: 28, marginBottom: 8 }}>{s.icon}</div>
                <div style={{ fontFamily: 'Syne, sans-serif', fontSize: 26, fontWeight: 700 }}>{s.value}</div>
                <div style={{ color: 'var(--text3)', fontSize: 13, marginTop: 4 }}>{s.label}</div>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Features */}
      <section style={{ padding: '64px 0' }}>
        <div className="container">
          <h2 style={{ textAlign: 'center', fontSize: 'clamp(1.6rem, 4vw, 2.4rem)', marginBottom: 48 }}>
            Zašto <span style={{ color: 'var(--accent)' }}>AutoAI</span>?
          </h2>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: 16 }}>
            {[
              { icon: '🤖', title: 'AI Pretraga', desc: 'Piši slobodnim jezikom. "BMW dizel do 15k" automatski postaje precizna pretraga.' },
              { icon: '💰', title: 'Fer cena', desc: 'ML model procenjuje tržišnu vrednost svakog vozila. Odmah vidiš da li je oglas povoljno ili skupo.' },
              { icon: '🛡️', title: 'Detekcija prevara', desc: 'AI automatski označava sumnjive oglase — nerealne cene, lažni prodavci, prevarantski opisi.' },
              { icon: '✈️', title: 'Kalkulator uvoza', desc: 'Tačan obračun carine, PDV-a, akcize i transporta za uvoz iz bilo koje EU zemlje u Srbiju.' },
              { icon: '🔔', title: 'Alertovi', desc: 'Postavi parametre i odmah dobij obaveštenje kada se pojavi auto koji tražiš.' },
              { icon: '📊', title: 'Istorija cena', desc: 'Prati kako se cena menjala. Znaj kada je pravo vreme da kupiš.' },
            ].map(f => (
              <div key={f.title} style={{
                background: 'var(--bg2)', border: '1px solid var(--border)',
                borderRadius: 'var(--radius)', padding: '24px',
                transition: 'border-color .2s',
              }}
              onMouseEnter={e => ((e.currentTarget as HTMLElement).style.borderColor = 'var(--accent)')}
              onMouseLeave={e => ((e.currentTarget as HTMLElement).style.borderColor = 'var(--border)')}
              >
                <div style={{ fontSize: 32, marginBottom: 12 }}>{f.icon}</div>
                <h3 style={{ fontSize: 17, marginBottom: 8 }}>{f.title}</h3>
                <p style={{ color: 'var(--text2)', fontSize: 14, lineHeight: 1.7 }}>{f.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>
    </div>
  )
}
