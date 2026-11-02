import { Suspense } from 'react'
import SearchPageClient from './page-client'

export const dynamic = 'force-dynamic'

export default function Page() {
  return (
    <Suspense fallback={null}>
      <SearchPageClient />
    </Suspense>
  )
}

