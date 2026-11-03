export type OfferRecommendation = {
  status: 'consider' | 'negotiate' | 'verify' | 'avoid'
  title: string
  reason: string
  next_step: string
  confidence: 'limited' | 'insufficient'
  cautions: string[]
  comparison?: {
    available: boolean
    sample_size: number
    reference_price: number | null
    delta_pct: number | null
    reason: string
    freshness_days: number
  }
}

// Safety evidence takes precedence over the observed asking-price comparison.
export function resolveRecommendation(listing: any, vinResult?: any, fraud?: any): OfferRecommendation {
  const fallback: OfferRecommendation = {
    status: 'verify', title: 'Prvo proveri podatke', confidence: 'insufficient',
    reason: 'Nema dovoljno podataka za obrazloženu preporuku kupovine.',
    next_step: 'Proveri aktuelnu cenu, zatraži VIN i servisnu dokumentaciju pre odluke.',
    cautions: ['Broj fotografija i popunjena polja nisu potvrda stanja vozila.'],
  }
  const source = listing?.recommendation
  const valid = source && ['consider', 'negotiate', 'verify', 'avoid'].includes(source.status)
    && typeof source.reason === 'string' && typeof source.title === 'string'
    && typeof source.next_step === 'string' && Array.isArray(source.cautions)
  const base: OfferRecommendation = valid ? source : fallback
  const mismatches = Array.isArray(vinResult?.mismatches) ? vinResult.mismatches : []
  const critical = mismatches.filter((m: any) => m.severity === 'critical')
  const warnings = mismatches.filter((m: any) => m.severity === 'warning')
  const conflicts = critical.length ? critical : warnings
  if (conflicts.length) {
    return { ...base, status: critical.length ? 'avoid' : 'verify', confidence: 'insufficient',
      title: critical.length ? 'Ne kupuj dok se podaci ne razjasne' : 'Prvo razjasni VIN neslaganje',
      reason: `VIN provera navodi neslaganje: ${conflicts.map((m: any) => m.message || m.field || 'podaci vozila').join('; ')}`,
      next_step: 'Zatraži fotografiju VIN oznake i originalne dokumente; razjasni razlike pre bilo kakve uplate.',
    }
  }
  if (fraud?.risk_level === 'critical' || fraud?.risk_level === 'high') {
    return { ...base, status: fraud.risk_level === 'critical' ? 'avoid' : 'verify', confidence: 'insufficient',
      title: 'Prvo razjasni bezbednosne rizike',
      reason: `Bezbednosna analiza navodi rizike: ${Array.isArray(fraud.red_flags) && fraud.red_flags.length ? fraud.red_flags.join('; ') : 'potrebna je dodatna provera prodavca i oglasa'}.`,
      next_step: 'Proveri identitet prodavca, dokumentaciju i vozilo uživo pre bilo kakve uplate.',
    }
  }
  // A successful VIN decode alone does not verify mileage, damage or ownership.
  return base
}
