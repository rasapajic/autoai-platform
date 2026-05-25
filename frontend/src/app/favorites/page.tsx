'use client'
import { useState, useEffect } from 'react'

function fmt(n: any) { return Number(n).toLocaleString('de-DE') }

function fullImg(url: string): string {
  if (!url) return url
  return url.replace(/\/\d+x\d+\.(webp|jpg|jpeg|png)/i, '/800x600.$1')
}

export default function FavoritesPage() {
  const [favorites, setFavorites] = useState<any[]>([])
  const [loading,   setLoading]   = useState(true)
  const [error,     setError]     = useState('')

  useEffect(() => {
    const token = localStorage.getItem('autoai_token')
    if (!token) { window.location.href = '/login'; return }

    const apiBase = process.env.NEXT_PUBLIC_API_URL || 'https://autoai-platform-production.up.railway.app/api/v1'
    fetch(`${apiBase}/users/me/favorites`, {
      headers: { 'Authorization': `Bearer ${token}` }
    })
      .then(res => res.json())
      .then(data => { setFavorites(Array.isArray(data) ? data : []); setLoading(false) })
      .catch(() => { setError('Greška pri učitavanju'); setLoading(false) })
  }, [])

  return (
    <div style={{ minHeight: '100vh', padding: '40px 0 80px' }}>
      <div className="container">
        <h1 style={{ fontSize: 26, fontFamily: 'Syne,sans-serif', marginBottom: 8 }}>
          ❤️ Sačuvani oglasi
        </h1>
        <p style={{ color: 'var(--text3)', fontSize: 14, marginBottom: 32 }}>
          Oglasi koje si sačuvao za kasniji pregled
        </p>

        {loading ? (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(280px,1fr))', gap: 20 }}>
            {[...Array(4)].map((_,i) => (
              <div key={i} className="skeleton" style={{ height: 280, borderRadius: 16 }} />
            ))}
          </div>
        ) : error ? (
          <div style={{ textAlign: 'center', padding: '60px 0', color: '#EF4444' }}>{error}</div>
        ) : favorites.length === 0 ? (
          <div style={{
            textAlign: 'center', padding: '80px 20px',
            background: 'var(--bg2)', borderRadius: 16, border: '1px solid var(--border)'
          }}>
            <div style={{ fontSize: 52, marginBottom: 16 }}>🤍</div>
            <p style={{ fontSize: 17, fontWeight: 600, marginBottom: 8 }}>Nema sačuvanih oglasa</p>
            <p style={{ color: 'var(--text3)', fontSize: 14, marginBottom: 24 }}>
              Klikni "Sačuvaj oglas" na bilo kom autu da ga dodaš ovde
            </p>
            <a href="/search" style={{
              display: 'inline-block', padding: '12px 28px', borderRadius: 10,
              background: 'var(--accent)', color: '#fff', textDecoration: 'none', fontWeight: 700,
            }}>Pretraži automobile</a>
          </div>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(280px,1fr))', gap: 20 }}>
            {favorites.map((l: any) => (
              <a key={l.id} href={`/listing/${l.id}`} style={{
                background: 'var(--bg2)', border: '1px solid var(--border)',
                borderRadius: 16, overflow: 'hidden', display: 'block', textDecoration: 'none',
                transition: 'all .2s',
              }}>
                <div style={{ height: 180, background: 'var(--bg3)', overflow: 'hidden' }}>
                  {l.images?.[0]
                    ? <img src={fullImg(l.images[0])} alt=""
                        style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                        onError={e => { (e.target as HTMLImageElement).src = l.images[0] }} />
                    : <div style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 40 }}>🚗</div>
                  }
                </div>
                <div style={{ padding: '14px 16px' }}>
                  <div style={{ fontSize: 15, fontWeight: 600, color: 'var(--text)', marginBottom: 4 }}>
                    {l.year} {l.make} {l.model}
                  </div>
                  <div style={{ fontSize: 18, fontWeight: 800, color: 'var(--accent)', marginBottom: 8 }}>
                    {l.price ? `${fmt(l.price)} €` : 'Na upit'}
                  </div>
                  {l.mileage && (
                    <div style={{ fontSize: 12, color: 'var(--text3)' }}>
                      🛣 {Number(l.mileage).toLocaleString('de-DE')} km
                    </div>
                  )}
                </div>
              </a>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
