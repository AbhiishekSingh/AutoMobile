import { useEffect, useState } from 'react'
import Layout from '../../components/Layout'
import { Loading } from '../../components/ui'
import api from '../../lib/api'

// Trend tiles the client asked for (Screen 1 after login).
const TREND_TILES = [
  { key: 'open_bookings', label: 'Open Booking', accent: '#2563EB' },
  { key: 'booked', label: 'Booked', accent: '#7C3AED' },
  { key: 'invoiced', label: 'Invoiced', accent: '#D97706' },
  { key: 'delivered', label: 'Delivered', accent: '#059669' },
]

const ACTIVITY_TILES = [
  { key: 'calls_today', label: 'Calls / Follow-ups Due' },
  { key: 'quotations_shared', label: 'Quotations Shared' },
  { key: 'test_rides_scheduled', label: 'Test Rides Scheduled' },
  { key: 'test_rides_completed', label: 'Test Rides Completed' },
]

const PERIODS = [
  { key: 'today', label: 'Today' },
  { key: 'week', label: 'This Week' },
  { key: 'month', label: 'This Month' },
  { key: 'year', label: 'This Year' },
]

function Ring({ pct, label, color }) {
  const p = Math.max(0, Math.min(100, pct || 0))
  return (
    <div style={{ textAlign: 'center' }}>
      <div
        style={{
          width: 120, height: 120, borderRadius: '50%', margin: '0 auto',
          background: `conic-gradient(${color} ${p * 3.6}deg, #E8EEF6 0deg)`,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}
      >
        <div style={{
          width: 88, height: 88, borderRadius: '50%', background: '#fff',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 22, fontWeight: 700, color: '#1F2937',
        }}>{p}%</div>
      </div>
      <div style={{ marginTop: 10, color: 'var(--muted)', fontWeight: 600 }}>{label}</div>
    </div>
  )
}

export default function DashboardPage() {
  const [data, setData] = useState(null)
  const [period, setPeriod] = useState('today')
  const [err, setErr] = useState('')

  useEffect(() => {
    setErr('')
    // period is passed so it works once the backend starts honouring it;
    // today it returns the same totals — the UI is ready either way.
    api.get('/pba/dashboard', { params: { period } })
      .then((r) => setData(r.data))
      .catch(() => setErr('Could not load dashboard.'))
  }, [period])

  return (
    <Layout title="PBA Dashboard" sub="Trends & activity at a glance">
      <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 16 }}>
        <select className="input" style={{ maxWidth: 180 }} value={period}
                onChange={(e) => setPeriod(e.target.value)}>
          {PERIODS.map((p) => <option key={p.key} value={p.key}>{p.label}</option>)}
        </select>
      </div>

      {err && <div className="card"><div className="card-pad" style={{ color: '#B91C1C' }}>{err}</div></div>}
      {!data && !err && <Loading />}

      {data && (
        <>
          <div className="grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16 }}>
            {TREND_TILES.map((t) => (
              <div key={t.key} className="card">
                <div className="card-pad">
                  <div style={{ color: 'var(--muted)', fontWeight: 600, fontSize: 13 }}>{t.label}</div>
                  <div style={{ fontSize: 34, fontWeight: 800, color: t.accent, marginTop: 6 }}>
                    {data[t.key] ?? 0}
                  </div>
                </div>
              </div>
            ))}
          </div>

          <div className="grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16, marginTop: 16 }}>
            {ACTIVITY_TILES.map((t) => (
              <div key={t.key} className="card">
                <div className="card-pad">
                  <div style={{ color: 'var(--muted)', fontWeight: 600, fontSize: 13 }}>{t.label}</div>
                  <div style={{ fontSize: 28, fontWeight: 700, marginTop: 6 }}>{data[t.key] ?? 0}</div>
                </div>
              </div>
            ))}
          </div>

          <div className="card" style={{ marginTop: 16 }}>
            <div className="card-header"><h3>Target Achievement</h3></div>
            <div className="card-pad" style={{ display: 'flex', gap: 48, justifyContent: 'center', flexWrap: 'wrap' }}>
              <Ring pct={data.total_target_ratio} label="Overall Target" color="#2563EB" />
              <Ring pct={data.td_completed_ratio} label="Test Drives Completed" color="#059669" />
            </div>
          </div>
        </>
      )}
    </Layout>
  )
}
