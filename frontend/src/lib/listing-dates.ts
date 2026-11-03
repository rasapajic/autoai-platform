export function formatListingDate(value: unknown, precision: string = 'second'): string {
  if (typeof value !== 'string') return 'Nije dostupno'
  if (precision === 'date') {
    const parts = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value)
    if (!parts) return 'Nije dostupno'
    const [, year, month, day] = parts
    const parsed = new Date(`${value}T00:00:00Z`)
    if (!Number.isFinite(parsed.getTime()) || parsed.toISOString().slice(0, 10) !== value) return 'Nije dostupno'
    return `${Number(day)}.${Number(month)}.${year}.`
  }
  if (!/^\d{4}-\d{2}-\d{2}T.*(?:Z|[+-]\d{2}:\d{2})$/.test(value)) return 'Nije dostupno'
  const parsed = new Date(value)
  if (!Number.isFinite(parsed.getTime())) return 'Nije dostupno'
  return new Intl.DateTimeFormat('sr-Latn-RS', {
    timeZone: 'Europe/Vienna', year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', hourCycle: 'h23',
  }).format(parsed)
}
