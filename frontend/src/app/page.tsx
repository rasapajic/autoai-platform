import { Suspense } from 'react'
import SearchPageClient from './search/page-client'

export const dynamic = 'force-dynamic'

export default function Page() {
  return (
    <Suspense fallback={null}>
      <SearchPageClient />
    </Suspense>
  )
}

