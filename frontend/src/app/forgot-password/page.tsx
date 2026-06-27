'use client'

import { useState } from 'react'
import { forgotPassword } from '@/lib/api'

const SUCCESS_MESSAGE = 'Ako nalog postoji, poslat je link za reset lozinke.'

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setMessage('')
    setLoading(true)
    try {
      const res = await forgotPassword({ email })
      setMessage(res?.message || SUCCESS_MESSAGE)
    } catch (err: any) {
      setError(err?.message || 'Nije moguće poslati zahtev. Pokušajte ponovo.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ padding: '48px 0 80px' }}>
      <div className="container" style={{ maxWidth: 420 }}>
        <h1 style={{ fontSize: 32, marginBottom: 8 }}>Reset lozinke</h1>
        <p style={{ color: 'var(--text2)', marginBottom: 24 }}>
          Unesite email adresu i poslaćemo link za promenu lozinke.
        </p>

        <form onSubmit={submit} style={{
          background: 'var(--bg2)', border: '1px solid var(--border)',
          borderRadius: 'var(--radius)', padding: 24,
        }}>
          <Field label="Email">
            <input
              type="email"
              value={email}
              onChange={e => setEmail(e.target.value)}
              required
              autoComplete="email"
              style={inputStyle}
            />
          </Field>

          {error && <p style={{ color: 'var(--red)', fontSize: 13, marginBottom: 12 }}>{error}</p>}
          {message && <p style={{ color: 'var(--green)', fontSize: 13, marginBottom: 12 }}>{message}</p>}

          <button disabled={loading} style={buttonStyle}>
            {loading ? 'Šaljem...' : 'Pošalji link'}
          </button>

          <p style={{ color: 'var(--text3)', fontSize: 13, marginTop: 16 }}>
            Setili ste se lozinke? <a href="/login" style={{ color: 'var(--accent)' }}>Login</a>
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
