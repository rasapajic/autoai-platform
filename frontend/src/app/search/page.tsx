import { Suspense } from 'react'
import SearchPageClient from './page-client'

export const dynamic = 'force-dynamic'

export default function SearchPage() {
  return (
    <Suspense fallback={null}>
      <SearchPageClient />
    </Suspense>
  )
}
