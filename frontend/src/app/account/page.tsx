'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { deleteAlert, getAlerts, getFavorites, getProfile, toggleAlert } from '@/lib/api'

export default function AccountPage() {
  const router = useRouter()
  const [user, setUser] = useState<any>(null)
  const [favorites, setFavorites] = useState<any[]>([])
  const [alerts, setAlerts] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const load = async () => {
    setLoading(true)
    try {
      const [profile, favs, saved] = await Promise.all([
        getProfile(),
        getFavorites(),
        getAlerts(),
      ])
      setUser(profile)
      setFavorites(favs)
      setAlerts(saved)
      setError('')
    } catch {
      localStorage.removeItem('token')
      router.push('/login?next=/account')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const logout = () => {
    localStorage.removeItem('token')
    router.push('/')
  }

  const removeAlert = async (id: string) => {
    await deleteAlert(id)
    setAlerts(alerts.filter(a => a.id !== id))
  }

  const toggle = async (id: string) => {
    const updated = await toggleAlert(id)
    setAlerts(alerts.map(a => a.id === id ? updated : a))
  }

  if (loading) {
    return <div className="container" style={{ padding: '64px 20px', color: 'var(--text2)' }}>Učitavam nalog...</div>
  }

  return (
    <div style={{ padding: '40px 0 80px' }}>
      <div className="container">
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 16, alignItems: 'center', marginBottom: 28 }}>
          <div>
            <h1 style={{ fontSize: 32, marginBottom: 6 }}>Moj nalog</h1>
            <p style={{ color: 'var(--text2)' }}>{user?.email}</p>
          </div>
          <button onClick={logout} style={{
            padding: '9px 14px', borderRadius: 8, border: '1px solid var(--border)',
            background: 'transparent', color: 'var(--text2)',
          }}>Logout</button>
        </div>

        {error && <p style={{ color: 'var(--red)', marginBottom: 16 }}>{error}</p>}

        <section style={sectionStyle}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
            <h2 style={{ fontSize: 18 }}>Moja potraga</h2>
            <a href="/search" style={{ color: 'var(--accent)', fontSize: 14 }}>Nova potraga</a>
          </div>
          {alerts.length ? (
            <div style={{ display: 'grid', gap: 10 }}>
              {alerts.map(alert => (
                <div key={alert.id} style={rowStyle}>
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                      <div style={{ fontWeight: 700 }}>{alert.name}</div>
                      <span style={{
                        color: alert.is_active ? 'var(--green)' : 'var(--text3)',
                        border: `1px solid ${alert.is_active ? 'var(--green)' : 'var(--border)'}`,
                        borderRadius: 20,
                        padding: '1px 8px',
                        fontSize: 11,
                      }}>{alert.is_active ? 'Aktivna' : 'Pauzirana'}</span>
                    </div>
                    <div style={{ color: 'var(--text3)', fontSize: 12, marginTop: 6 }}>
                      {formatAlertCriteria(alert.filters)}
                    </div>
                  </div>
                  <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                    <button onClick={() => toggle(alert.id)} style={smallButtonStyle}>
                      {alert.is_active ? 'Aktivna' : 'Pauzirana'}
                    </button>
                    <button onClick={() => removeAlert(alert.id)} style={smallButtonStyle}>Obriši</button>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p style={{ color: 'var(--text3)' }}>Nema sačuvanih potraga.</p>
          )}
        </section>

        <section style={sectionStyle}>
          <h2 style={{ fontSize: 18, marginBottom: 16 }}>Favoriti</h2>
          {favorites.length ? (
            <div style={{ display: 'grid', gap: 10 }}>
              {favorites.map(f => (
                <a key={f.id} href={`/listing/${f.id}`} style={rowStyle}>
                  <div>
                    <div style={{ fontWeight: 700 }}>{f.year} {f.make} {f.model}</div>
                    <div style={{ color: 'var(--text3)', fontSize: 12 }}>{f.country} | {f.mileage?.toLocaleString?.() || f.mileage || '-'} km</div>
                  </div>
                  <div style={{ color: 'var(--accent)', fontWeight: 800 }}>
                    {f.price ? `${Number(f.price).toLocaleString()} €` : 'Cena na upit'}
                  </div>
                </a>
              ))}
            </div>
          ) : (
            <p style={{ color: 'var(--text3)' }}>Nema favorita.</p>
          )}
        </section>
      </div>
    </div>
  )
}

const sectionStyle: React.CSSProperties = {
  background: 'var(--bg2)', border: '1px solid var(--border)',
  borderRadius: 'var(--radius)', padding: 24, marginBottom: 20,
}

const rowStyle: React.CSSProperties = {
  display: 'flex', justifyContent: 'space-between', gap: 16, alignItems: 'center',
  background: 'var(--bg3)', border: '1px solid var(--border)',
  borderRadius: 8, padding: '12px 14px',
}

const smallButtonStyle: React.CSSProperties = {
  padding: '6px 10px', borderRadius: 8, border: '1px solid var(--border)',
  background: 'transparent', color: 'var(--text2)', fontSize: 12,
}

function formatAlertCriteria(filters: Record<string, any> = {}) {
  const labels: Record<string, string> = {
    query_text: 'Tekst',
    make: 'Marka',
    model: 'Model',
    min_price: 'Cena od',
    max_price: 'Cena do',
    min_year: 'Godište od',
    max_year: 'Godište do',
    max_km: 'Max km',
    fuel_type: 'Gorivo',
    body_type: 'Karoserija',
    country: 'Zemlja',
    price_rating: 'Ocena cene',
  }

  const parts = Object.entries(filters)
    .filter(([, value]) => value !== null && value !== undefined && value !== '')
    .map(([key, value]) => `${labels[key] || key}: ${value}`)

  return parts.length ? parts.join(' | ') : 'Svi oglasi'
}
