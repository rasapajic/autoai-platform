'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { register } from '@/lib/api'

export default function RegisterPage() {
  const router = useRouter()
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const res = await register({ name, email, password })
      localStorage.setItem('token', res.access_token)
      router.push('/account')
    } catch (err: any) {
      setError(err?.message || 'Registracija nije uspela.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ padding: '48px 0 80px' }}>
      <div className="container" style={{ maxWidth: 420 }}>
        <h1 style={{ fontSize: 32, marginBottom: 8 }}>Registracija</h1>
        <p style={{ color: 'var(--text2)', marginBottom: 24 }}>Napravi nalog za favorite i sačuvane potrage.</p>

        <form onSubmit={submit} style={{
          background: 'var(--bg2)', border: '1px solid var(--border)',
          borderRadius: 'var(--radius)', padding: 24,
        }}>
          <Field label="Ime">
            <input value={name} onChange={e => setName(e.target.value)} style={inputStyle} />
          </Field>
          <Field label="Email">
            <input type="email" value={email} onChange={e => setEmail(e.target.value)} required style={inputStyle} />
          </Field>
          <Field label="Lozinka">
            <input type="password" value={password} onChange={e => setPassword(e.target.value)} required minLength={8} style={inputStyle} />
          </Field>
          {error && <p style={{ color: 'var(--red)', fontSize: 13, marginBottom: 12 }}>{error}</p>}
          <button disabled={loading} style={buttonStyle}>{loading ? 'Kreiram...' : 'Registruj se'}</button>
          <p style={{ color: 'var(--text3)', fontSize: 13, marginTop: 16 }}>
            Već imaš nalog? <a href="/login" style={{ color: 'var(--accent)' }}>Login</a>
          </p>
        </form>
      </div>
    </div>
  )
}

function Field({ label, children }: { label: string, children: React.ReactNode }) {
  return (
    <label style={{ display: 'block', marginBottom: 16 }}>
      <span style={{ display: 'block', color: 'var(--text3)', fontSize: 12, marginBottom: 6 }}>{label.toUpperCase()}</span>
      {children}
    </label>
  )
}

const inputStyle: React.CSSProperties = {
  width: '100%', background: 'var(--bg3)', border: '1px solid var(--border)',
  borderRadius: 8, padding: '10px 12px', color: 'var(--text)', outline: 'none',
}

const buttonStyle: React.CSSProperties = {
  width: '100%', padding: 12, border: 'none', borderRadius: 10,
  background: 'var(--accent)', color: '#fff', fontWeight: 700,
}
