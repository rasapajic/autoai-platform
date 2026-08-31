import { Suspense } from 'react'
import ImportCalculatorClient from './page-client'

export const dynamic = 'force-dynamic'

export default function ImportCalculatorPage() {
  return (
    <Suspense fallback={null}>
      <ImportCalculatorClient />
    </Suspense>
  )
}
