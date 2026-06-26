'use client'

import { useEffect, useState } from 'react'
import { getCoverageStats } from '@/lib/api'

export default function CoveragePage() {
  const [stats, setStats] = useState<any>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getCoverageStats()
      .then(setStats)
      .catch(() => setStats(null))
      .finally(() => setLoading(false))
  }, [])

  if (loading) {
    return <div className="container" style={{ padding: '40px 0', color: 'var(--text3)' }}>Učitavam pokrivenost podataka...</div>
  }

  if (!stats) {
    return <div className="container" style={{ padding: '40px 0', color: 'var(--text3)' }}>Coverage podaci nisu dostupni.</div>
  }

  return (
    <div style={{ padding: '32px 0 80px' }}>
      <div className="container">
        <div style={{ marginBottom: 24 }}>
          <h1 style={{ fontSize: 24, marginBottom: 6 }}>Data Coverage</h1>
          <div style={{ color: 'var(--text3)', fontSize: 13 }}>
            Rast marketplace baze i spremnost za pouzdanu tržišnu procenu.
          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, marginBottom: 24 }}>
          <MetricCard label="Ukupno vozila" value={stats.total_listings} />
          <MetricCard label="Aktivni oglasi" value={stats.active_listings} />
          <MetricCard label="Sa cenom" value={stats.listings_with_price} />
          <MetricCard label="Specijalna vozila" value={stats.special_vehicle_count} />
        </div>

        <section style={{ marginBottom: 24 }}>
          <h2 style={{ fontSize: 16, marginBottom: 12 }}>Valuation readiness</h2>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12 }}>
            <ReadinessCard icon="🟡" label="50+ comparables" value={stats.valuation_readiness?.models_with_50_plus_comparables || 0} />
            <ReadinessCard icon="🟢" label="100+ comparables" value={stats.valuation_readiness?.models_with_100_plus_comparables || 0} />
            <ReadinessCard icon="🚀" label="300+ comparables" value={stats.valuation_readiness?.models_with_300_plus_comparables || 0} />
          </div>
        </section>

        <section style={{ marginBottom: 24 }}>
          <h2 style={{ fontSize: 16, marginBottom: 12 }}>Nightly expansion</h2>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12 }}>
            <MetricCard label="Poslednji run" value={formatDate(stats.last_expansion_run?.last_run_at)} />
            <MetricCard label="Poslednji uspeh" value={formatDate(stats.last_expansion_run?.last_success_at)} />
            <MetricCard label="Trajanje" value={formatDuration(stats.last_expansion_run?.last_duration_seconds)} />
            <MetricCard label="Kreirano" value={stats.last_expansion_run?.last_created_count || 0} />
          </div>
        </section>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
          <Panel title="Po izvoru">
            <KeyValueList data={stats.source_coverage || stats.by_source} />
          </Panel>

          <Panel title="Po zemlji">
            <KeyValueList data={stats.by_country} />
          </Panel>

          <Panel title="Top marke">
            <KeyValueList data={stats.by_make} limit={12} />
          </Panel>

          <Panel title="Top modeli">
            <div style={{ display: 'grid', gap: 8 }}>
              {(stats.by_model || []).slice(0, 20).map((item: any) => (
                <Row key={`${item.make}-${item.model}`} label={`${item.make} ${item.model}`} value={item.count} />
              ))}
            </div>
          </Panel>
        </div>
      </div>
    </div>
  )
}

function MetricCard({ label, value }: { label: string, value: number | string }) {
  return (
    <div style={{ background: 'var(--bg2)', border: '1px solid var(--border)', borderRadius: 8, padding: 16 }}>
      <div style={{ color: 'var(--text3)', fontSize: 12, marginBottom: 6 }}>{label}</div>
      <div style={{ fontSize: 24, fontWeight: 800 }}>{typeof value === 'number' ? Number(value || 0).toLocaleString() : value}</div>
    </div>
  )
}

function ReadinessCard({ icon, label, value }: { icon: string, label: string, value: number }) {
  return (
    <div style={{ background: 'var(--bg2)', border: '1px solid var(--border)', borderRadius: 8, padding: 16 }}>
      <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 8 }}>
        <span>{icon}</span>
        <span style={{ color: 'var(--text2)', fontSize: 13 }}>{label}</span>
      </div>
      <div style={{ fontSize: 22, fontWeight: 800 }}>{Number(value || 0).toLocaleString()} modela</div>
    </div>
  )
}

function Panel({ title, children }: { title: string, children: React.ReactNode }) {
  return (
    <section style={{ background: 'var(--bg2)', border: '1px solid var(--border)', borderRadius: 8, padding: 16 }}>
      <h2 style={{ fontSize: 15, marginBottom: 12 }}>{title}</h2>
      {children}
    </section>
  )
}

function KeyValueList({ data, limit = 20 }: { data: Record<string, number>, limit?: number }) {
  const rows = Object.entries(data || {}).sort((a, b) => Number(b[1]) - Number(a[1])).slice(0, limit)
  return (
    <div style={{ display: 'grid', gap: 8 }}>
      {rows.map(([label, value]) => <Row key={label} label={label} value={value} />)}
      {!rows.length && <div style={{ color: 'var(--text3)', fontSize: 13 }}>Nema podataka.</div>}
    </div>
  )
}

function Row({ label, value }: { label: string, value: number }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 16, fontSize: 13 }}>
      <span style={{ color: 'var(--text2)' }}>{label || '-'}</span>
      <strong>{Number(value || 0).toLocaleString()}</strong>
    </div>
  )
}

function formatDate(value: string | null | undefined) {
  if (!value) return '—'
  return new Date(value).toLocaleString('sr')
}

function formatDuration(seconds: number | null | undefined) {
  if (seconds === null || seconds === undefined) return '—'
  const minutes = Math.floor(Number(seconds) / 60)
  const rest = Number(seconds) % 60
  return minutes ? `${minutes}m ${rest}s` : `${rest}s`
}
