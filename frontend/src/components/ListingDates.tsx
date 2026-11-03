import { formatListingDate } from '@/lib/listing-dates'

export default function ListingDates({ listing }: { listing: any }) {
  const dates = listing.source_dates || {}
  const rows = [
    [dates.published?.semantics === 'published_or_renewed' ? 'Objavljeno / obnovljeno na sajtu' : 'Objavljeno na sajtu', formatListingDate(dates.published?.value, dates.published?.precision)],
    ['Izmenjeno na sajtu', formatListingDate(dates.modified?.value, dates.modified?.precision)],
    ['AutoAI poslednja provera', formatListingDate(listing.last_seen_at)],
  ]
  return <section aria-label="Datumi oglasa" style={{ margin: '12px 0', fontSize: 11, color: 'var(--text3)', lineHeight: 1.5 }}>
    {rows.map(([label, value]) => <div key={label} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: 10, padding: '3px 0', flexWrap: 'wrap' }}>
      <span>{label}</span><span style={{ color: 'var(--text2)' }}>{value}</span>
    </div>)}
    <div style={{ fontSize: 10, marginTop: 3 }}>Vreme je prikazano za Beč. Provera označava poslednje preuzimanje oglasa.</div>
  </section>
}
