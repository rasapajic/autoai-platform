'use client'

import { Suspense, useState } from 'react'
import { useSearchParams } from 'next/navigation'
import { resetPassword } from '@/lib/api'

export default function ResetPasswordPage() {
  return (
    <Suspense fallback={null}>
      <ResetPasswordContent />
    </Suspense>
  )
}

function ResetPasswordContent() {
  const searchParams = useSearchParams()
  const token = searchParams.get('token') || ''
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setMessage('')

    if (!token) {
      setError('Link za reset lozinke nije ispravan.')
      return
    }
    if (password.length < 8) {
      setError('Lozinka mora imati najmanje 8 karaktera.')
      return
    }
    if (password !== confirmPassword) {
      setError('Lozinke se ne poklapaju.')
      return
    }

    setLoading(true)
    try {
      const res = await resetPassword({ token, password })
      setMessage(res?.message || 'Lozinka je uspešno promenjena.')
      setPassword('')
      setConfirmPassword('')
    } catch (err: any) {
      setError(err?.message || 'Reset lozinke nije uspeo.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ padding: '48px 0 80px' }}>
      <div className="container" style={{ maxWidth: 420 }}>
        <h1 style={{ fontSize: 32, marginBottom: 8 }}>Nova lozinka</h1>
        <p style={{ color: 'var(--text2)', marginBottom: 24 }}>
          Unesite novu lozinku za AutoAI nalog.
        </p>

        <form onSubmit={submit} style={{
          background: 'var(--bg2)', border: '1px solid var(--border)',
          borderRadius: 'var(--radius)', padding: 24,
        }}>
          <Field label="Nova lozinka">
            <input
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              required
              minLength={8}
              autoComplete="new-password"
              style={inputStyle}
            />
          </Field>
          <Field label="Potvrdi lozinku">
            <input
              type="password"
              value={confirmPassword}
              onChange={e => setConfirmPassword(e.target.value)}
              required
              minLength={8}
              autoComplete="new-password"
              style={inputStyle}
            />
          </Field>

          {!token && <p style={{ color: 'var(--red)', fontSize: 13, marginBottom: 12 }}>Link za reset lozinke nije ispravan.</p>}
          {error && <p style={{ color: 'var(--red)', fontSize: 13, marginBottom: 12 }}>{error}</p>}
          {message && <p style={{ color: 'var(--green)', fontSize: 13, marginBottom: 12 }}>{message}</p>}

          <button disabled={loading || !token} style={buttonStyle}>
            {loading ? 'Čuvam...' : 'Promeni lozinku'}
          </button>

          {message && (
            <p style={{ color: 'var(--text3)', fontSize: 13, marginTop: 16 }}>
              Lozinka je promenjena. <a href="/login" style={{ color: 'var(--accent)' }}>Idi na login</a>
            </p>
          )}
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
