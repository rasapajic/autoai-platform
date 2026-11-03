import { resolveRecommendation } from '@/lib/listing-recommendation'

const COLORS = { consider: '#22C55E', negotiate: '#F97316', verify: '#F97316', avoid: '#EF4444' }

export default function ListingRecommendation({ listing, vinResult, fraud }: { listing: any; vinResult?: any; fraud?: any }) {
  const recommendation = resolveRecommendation(listing, vinResult, fraud)
  const color = COLORS[recommendation.status]
  const comparison = recommendation.comparison
  return (
    <section aria-label="AutoAI preporuka" style={{ border: `1px solid ${color}55`, background: `${color}0a`, borderRadius: 12, padding: 12, margin: '12px 0', overflowWrap: 'anywhere' }}>
      <div style={{ fontSize: 10, letterSpacing: '.06em', color: 'var(--text3)', fontWeight: 700, marginBottom: 6 }}>AUTOAI PREPORUKA</div>
      <div style={{ fontSize: 15, fontWeight: 800, color, lineHeight: 1.35 }}>{recommendation.title}</div>
      <p style={{ fontSize: 12, lineHeight: 1.6, color: 'var(--text2)', margin: '7px 0' }}><strong>Zašto: </strong>{recommendation.reason}</p>
      <p style={{ fontSize: 12, lineHeight: 1.6, color: 'var(--text2)', margin: '7px 0' }}><strong>Sledeći korak: </strong>{recommendation.next_step}</p>
      <div style={{ fontSize: 10, color: 'var(--text3)', lineHeight: 1.5 }}>Pouzdanost preporuke: {recommendation.confidence === 'limited' ? 'ograničena' : 'nedovoljna za odluku o kupovini'}.</div>
      <details style={{ marginTop: 8, fontSize: 11, color: 'var(--text3)', lineHeight: 1.6 }}>
        <summary style={{ cursor: 'pointer', color: 'var(--text2)' }}>Podaci i ograničenja procene</summary>
        {comparison && <p style={{ margin: '6px 0' }}>{comparison.reason} Za poređenje se prihvataju samo oglasi preuzeti u prethodnih {comparison.freshness_days} dana; to nije potvrda trenutne dostupnosti. Uzorak posle uklanjanja očiglednih ponavljanja: {comparison.sample_size}.</p>}
        {recommendation.cautions.map((caution, i) => <p key={i} style={{ margin: '6px 0' }}>{caution}</p>)}
      </details>
    </section>
  )
}
