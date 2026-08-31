import { Suspense } from 'react'
import HomePageClient from './page-client'

export default function Page() {
  return (
    <Suspense fallback={null}>
      <HomePageClient />
    </Suspense>
  )
}
