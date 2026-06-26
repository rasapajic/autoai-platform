'use client'

import { Suspense, useState } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { login } from '@/lib/api'

export default function LoginPage() {
  return (
    <Suspense fallback={null}>
      <LoginPageContent />
    </Suspense>
  )
}

function LoginPageContent() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const res = await login({ email, password })
      localStorage.setItem('token', res.access_token)
      router.push(searchParams.get('next') || '/account')
    } catch (err: any) {
      setError(err?.message || 'Login nije uspeo.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ padding: '48px 0 80px' }}>
      <div className="container" style={{ maxWidth: 420 }}>
        <h1 style={{ fontSize: 32, marginBottom: 8 }}>Login</h1>
        <p style={{ color: 'var(--text2)', marginBottom: 24 }}>Pristupi nalogu i sačuvanim potragama.</p>

        <form onSubmit={submit} style={{
          background: 'var(--bg2)', border: '1px solid var(--border)',
          borderRadius: 'var(--radius)', padding: 24,
        }}>
          <Field label="Email">
            <input type="email" value={email} onChange={e => setEmail(e.target.value)} required style={inputStyle} />
          </Field>
          <Field label="Lozinka">
            <PasswordInput value={password} onChange={setPassword} />
          </Field>
          {error && <p style={{ color: 'var(--red)', fontSize: 13, marginBottom: 12 }}>{error}</p>}
          <button disabled={loading} style={buttonStyle}>{loading ? 'Ulazim...' : 'Login'}</button>
          <p style={{ color: 'var(--text3)', fontSize: 13, marginTop: 16 }}>
            Nemaš nalog? <a href="/register" style={{ color: 'var(--accent)' }}>Registruj se</a>
          </p>
        </form>
      </div>
    </div>
  )
}

function Field({ label, children }: { label: string, children: React.ReactNode }) {
  return (
    <div style={{ display: 'block', marginBottom: 16 }}>
      <span style={{ display: 'block', color: 'var(--text3)', fontSize: 12, marginBottom: 6 }}>{label.toUpperCase()}</span>
      {children}
    </div>
  )
}

function PasswordInput({ value, onChange }: { value: string, onChange: (value: string) => void }) {
  const [visible, setVisible] = useState(false)

  return (
    <div style={{ position: 'relative' }}>
      <input
        type={visible ? 'text' : 'password'}
        value={value}
        onChange={e => onChange(e.target.value)}
        required
        autoComplete="current-password"
        style={{ ...inputStyle, paddingRight: 44 }}
      />
      <button
        type="button"
        aria-label={visible ? 'Sakrij lozinku' : 'Prikaži lozinku'}
        title={visible ? 'Sakrij lozinku' : 'Prikaži lozinku'}
        onClick={() => setVisible(!visible)}
        style={{
          position: 'absolute',
          right: 8,
          top: '50%',
          transform: 'translateY(-50%)',
          width: 30,
          height: 30,
          border: 'none',
          borderRadius: 6,
          background: 'transparent',
          color: 'var(--text2)',
          cursor: 'pointer',
          fontSize: 16,
          lineHeight: 1,
        }}
      >
        👁
      </button>
    </div>
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
