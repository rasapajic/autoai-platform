'use client'

import { useEffect, useState } from 'react'
import { usePathname } from 'next/navigation'

export default function AuthNav() {
  const pathname = usePathname()
  const [hasToken, setHasToken] = useState(false)

  useEffect(() => {
    setHasToken(Boolean(localStorage.getItem('token')))
  }, [pathname])

  return (
    <>
      {hasToken ? (
        <a href="/account" className="nav-link" style={{
          padding: '6px 14px', borderRadius: 8, fontSize: 14,
          color: 'var(--text2)', transition: 'all .15s',
        }}>Nalog</a>
      ) : (
        <a href="/login" className="nav-link" style={{
          padding: '6px 14px', borderRadius: 8, fontSize: 14,
          color: 'var(--text2)', transition: 'all .15s',
        }}>Login</a>
      )}
    </>
  )
}
