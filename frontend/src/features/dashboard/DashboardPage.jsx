import { useEffect, useState } from 'react'
import Layout from '../../components/Layout'
import { Loading } from '../../components/ui'
import api from '../../lib/api'
import TargetTrackerChart from './TargetTrackerChart'
import TotalSalesChart from './TotalSalesChart'
import SlaComplianceChart from './SlaComplianceChart'
import LeadSourceChart from './LeadSourceChart'
import LostReasonsChart from './LostReasonsChart'
import QuotationFunnelChart from './QuotationFunnelChart'

const TREND_TILES = [
  {
    key: 'open_bookings', label: 'OPEN BOOKINGS', accent: '#2563EB', accentLight: '#DCEAFD',
    icon: (
      <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="#2563EB" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
        <polyline points="14 2 14 8 20 8" />
        <line x1="12" y1="12" x2="12" y2="18" />
        <line x1="9" y1="15" x2="15" y2="15" />
      </svg>
    ),
  },
  {
    key: 'booked', label: 'BOOKED', accent: '#2E9E6B', accentLight: '#DCF3E7',
    icon: (
      <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="#2E9E6B" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="12" cy="12" r="10" />
        <polyline points="8 12 11 15 16 9" />
      </svg>
    ),
  },
  {
    key: 'invoiced', label: 'INVOICED', accent: '#D97706', accentLight: '#FCEACB',
    icon: (
      <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="#D97706" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
        <polyline points="14 2 14 8 20 8" />
        <line x1="8" y1="13" x2="16" y2="13" />
        <line x1="8" y1="17" x2="13" y2="17" />
      </svg>
    ),
  },
  {
    key: 'delivered', label: 'DELIVERED', accent: '#7C3AED', accentLight: '#E9DFFB',
    icon: (
      <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="#7C3AED" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <rect x="1" y="7" width="15" height="10" rx="1" />
        <path d="M16 10h3.5a1 1 0 0 1 .9.55L22 14v3h-6" />
        <circle cx="6" cy="19" r="2" />
        <circle cx="17.5" cy="19" r="2" />
      </svg>
    ),
  },
]

const ACTIVITY_TILES = [
  {
    key: 'calls_today', label: 'NO. OF CALLS', sub: 'Follow-ups Scheduled',
    accent: '#2E9E6B', accentLight: '#DCF3E7',
    icon: (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#2E9E6B" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72c.127.96.362 1.903.7 2.81a2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45c.907.338 1.85.573 2.81.7A2 2 0 0 1 22 16.92z" />
      </svg>
    ),
  },
  {
    key: 'quotations_shared', label: 'QUOTATION SHARED', sub: 'Quotes Sent Today',
    accent: '#2563EB', accentLight: '#DCEAFD',
    icon: (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#2563EB" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
        <polyline points="14 2 14 8 20 8" />
        <line x1="8" y1="13" x2="16" y2="13" />
        <line x1="8" y1="17" x2="16" y2="17" />
      </svg>
    ),
  },
]

const PERIODS = [
  { key: 'today', label: 'Today'      },
  { key: 'week',  label: 'This Week'  },
  { key: 'month', label: 'This Month' },
  { key: 'year',  label: 'This Year'  },
]

function Ring({ pct, label, color }) {
  const p = Math.max(0, Math.min(100, pct || 0))
  return (
    <div style={{ textAlign: 'center' }}>
      <div style={{
        width: 120, height: 120, borderRadius: '50%', margin: '0 auto',
        background: `conic-gradient(${color} ${p * 3.6}deg, #E8EEF6 0deg)`,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}>
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
  const [data,      setData]      = useState(null)
  // ✅ FIX: initialise as undefined (not null) so we can distinguish
  //         "not yet fetched" from "fetched but empty"
  const [chartData, setChartData] = useState(undefined)
  const [period,    setPeriod]    = useState('today')
  const [err,       setErr]       = useState('')

  useEffect(() => {
    setErr('')
    setData(null)
    api.get('/pba/dashboard', { params: { period } })
      .then((r) => setData(r.data))
      .catch(() => setErr('Could not load dashboard.'))
  }, [period])

  useEffect(() => {
    // ✅ FIX: reset to undefined on period change so charts don't flash skeleton
    setChartData(undefined)
    api.get('/dashboard/charts', { params: { period } })
      .then((r) => setChartData(r.data))
      .catch(() => {
        // endpoint missing or error — set to null to trigger skeleton
        setChartData(null)
      })
  }, [period])

  // ✅ FIX: derive safe props ONLY when chartData has actually resolved
  //    undefined = still loading  → pass nothing (charts show loading spinner)
  //    null      = error/no data  → pass empty (charts show skeleton)
  //    object    = real data      → pass it through
  const trackerData  = chartData === undefined ? undefined
                     : chartData === null       ? []
                     : chartData.target_tracker ?? []

  const salesData    = chartData === undefined ? undefined
                     : chartData === null       ? {}
                     : chartData.total_sales    ?? {}

  const slaData        = chartData === undefined ? undefined
                       : chartData === null       ? {}
                       : chartData.sla_compliance ?? {}

  const leadSourceData = chartData === undefined ? undefined
                       : chartData === null       ? {}
                       : chartData.lead_source    ?? {}

  const lostReasonsData = chartData === undefined ? undefined
                        : chartData === null       ? []
                        : chartData.lost_reasons   ?? []

  const quotationFunnelData = chartData === undefined ? undefined
                            : chartData === null       ? []
                            : chartData.quotation_funnel ?? []

  return (
    <Layout title="PBA Dashboard" sub="Trends & activity at a glance">
      <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 16 }}>
        <select className="input" style={{ maxWidth: 180 }} value={period}
                onChange={(e) => setPeriod(e.target.value)}>
          {PERIODS.map((p) => <option key={p.key} value={p.key}>{p.label}</option>)}
        </select>
      </div>

      {err && (
        <div className="card">
          <div className="card-pad" style={{ color: '#B91C1C' }}>{err}</div>
        </div>
      )}
      {!data && !err && <Loading />}

      {data && (
        <>
          {/* ── Performance Tracker + Today's ── */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr) 1.15fr', gap: 16 }}>
            <div style={{
              gridColumn: 'span 4', fontWeight: 800, fontSize: 13, letterSpacing: '0.02em',
              color: '#1B2A3A', paddingLeft: 2,
            }}>
              PERFORMANCE TRACKER
            </div>
            <div style={{
              fontWeight: 800, fontSize: 13, letterSpacing: '0.02em',
              color: '#1B2A3A', paddingLeft: 2,
            }}>
              TODAY&apos;S
            </div>

            {TREND_TILES.map((t) => (
              <div key={t.key} className="card">
                <div className="card-pad" style={{ paddingTop: 16, paddingBottom: 16 }}>
                  <div style={{ color: 'var(--muted)', fontWeight: 800, fontSize: 11.5, letterSpacing: '0.04em' }}>
                    {t.label}
                  </div>
                  <div style={{
                    width: 52, height: 52, borderRadius: '50%', background: t.accentLight,
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    margin: '14px 0 16px',
                  }}>
                    {t.icon}
                  </div>
                  <div style={{ fontSize: 30, fontWeight: 800, color: '#1B2A3A' }}>
                    {data[t.key] ?? 0}
                  </div>
                  <div style={{ height: 3, borderRadius: 2, background: t.accent, marginTop: 12 }} />
                </div>
              </div>
            ))}

            {/* ── Today's cards ── */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {ACTIVITY_TILES.map((t) => (
                <div key={t.key} className="card" style={{ marginBottom: 0 }}>
                  <div className="card-pad" style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
                    <div style={{
                      width: 44, height: 44, minWidth: 44, borderRadius: '50%', background: t.accentLight,
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                    }}>
                      {t.icon}
                    </div>
                    <div>
                      <div style={{ color: 'var(--muted)', fontWeight: 700, fontSize: 10, letterSpacing: '0.03em' }}>
                        {t.label}
                      </div>
                      <div style={{ fontSize: 25, fontWeight: 800, color: t.accent, marginTop: 2 }}>
                        {data[t.key] ?? 0}
                      </div>
                      <div style={{ fontSize: 11.5, color: 'var(--muted)', marginTop: 1 }}>{t.sub}</div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* ── Target Achievement rings ── */}
          {/* <div className="card" style={{ marginTop: 16 }}>
            <div className="card-header"><h3>Target Achievement</h3></div>
            <div className="card-pad" style={{ display: 'flex', gap: 48, justifyContent: 'center', flexWrap: 'wrap' }}>
              <Ring pct={data.total_target_ratio}  label="Overall Target"          color="#2563EB" />
              <Ring pct={data.td_completed_ratio}  label="Test Drives Completed"   color="#059669" />
            </div>
          </div> */}

          {/* ── Charts row ── */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginTop: 5 }}>
            {/* ✅ FIX: show a mini spinner inside the card while chartData is loading */}
            {trackerData === undefined ? (
              <div className="card">
                <div className="card-header">
                  <h3 style={{ margin: 0 }}>Target Tracker – Achievements</h3>
                </div>
                <div className="card-pad" style={{ display: 'flex', justifyContent: 'center', padding: '60px 0' }}>
                  <Loading />
                </div>
              </div>
            ) : (
              <TargetTrackerChart data={trackerData} />
            )}

            {salesData === undefined ? (
              <div className="card">
                <div className="card-header">
                  <h3 style={{ margin: 0 }}>Total Sales of Vehicles</h3>
                </div>
                <div className="card-pad" style={{ display: 'flex', justifyContent: 'center', padding: '60px 0' }}>
                  <Loading />
                </div>
              </div>
            ) : (
              <TotalSalesChart data={salesData} />
            )}
          </div>

          {/* ── Charts row 2 — SLA & Lead Source ── */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginTop: 16 }}>
            {slaData === undefined ? (
              <div className="card">
                <div className="card-header"><h3 style={{ margin: 0 }}>SLA Compliance</h3></div>
                <div className="card-pad" style={{ display: 'flex', justifyContent: 'center', padding: '60px 0' }}>
                  <Loading />
                </div>
              </div>
            ) : (
              <SlaComplianceChart data={slaData} />
            )}

            {leadSourceData === undefined ? (
              <div className="card">
                <div className="card-header"><h3 style={{ margin: 0 }}>Lead Source Split</h3></div>
                <div className="card-pad" style={{ display: 'flex', justifyContent: 'center', padding: '60px 0' }}>
                  <Loading />
                </div>
              </div>
            ) : (
              <LeadSourceChart data={leadSourceData} />
            )}
          </div>

          {/* ── Charts row 3 — Lost Reasons & Quotation Funnel ── */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginTop: 16 }}>
            {lostReasonsData === undefined ? (
              <div className="card">
                <div className="card-header"><h3 style={{ margin: 0 }}>Top Lost Reasons</h3></div>
                <div className="card-pad" style={{ display: 'flex', justifyContent: 'center', padding: '60px 0' }}>
                  <Loading />
                </div>
              </div>
            ) : (
              <LostReasonsChart data={lostReasonsData} />
            )}

            {quotationFunnelData === undefined ? (
              <div className="card">
                <div className="card-header"><h3 style={{ margin: 0 }}>Quotation Funnel</h3></div>
                <div className="card-pad" style={{ display: 'flex', justifyContent: 'center', padding: '60px 0' }}>
                  <Loading />
                </div>
              </div>
            ) : (
              <QuotationFunnelChart data={quotationFunnelData} />
            )}
          </div>
        </>
      )}
    </Layout>
  )
}