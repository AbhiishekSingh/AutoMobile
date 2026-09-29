import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, LabelList, ResponsiveContainer, Cell,
} from 'recharts'

// Test rides in the selected period (by scheduled date, else the lead's
// enquiry date):
//   Completed   = marked Completed
//   Scheduled   = booked/rescheduled and still UPCOMING (date today or later)
//   Not updated = booked but the date has passed and nobody marked it
//                 Completed or Cancelled — shown as a note so it gets fixed
// Counts come from /pba/dashboard — see pba_dashboard() in
// app/modules/leads/router.py.
const COLORS = {
  completed: '#2E9E6B',
  scheduled: '#2563EB',
}

const CustomTooltip = ({ active, payload }) => {
  if (!active || !payload?.length) return null
  const p = payload[0].payload
  return (
    <div style={{
      background: '#fff', border: '1px solid #D9E2EC',
      borderRadius: 9, padding: '8px 14px', fontSize: 13,
    }}>
      <span style={{ fontWeight: 700, color: '#1B2A3A' }}>{p.name}: </span>{p.count}
    </div>
  )
}

function EmptyState() {
  return (
    <div style={{
      height: 240, display: 'flex', flexDirection: 'column', alignItems: 'center',
      justifyContent: 'center', gap: 6, background: 'rgba(244,247,251,0.78)', borderRadius: 14,
    }}>
      <div style={{ fontSize: 26 }}>🏍️</div>
      <div style={{ fontWeight: 700, color: '#1B2A3A', fontSize: 14 }}>No test rides in this period</div>
      <div style={{ fontSize: 12, color: '#6B7F96', textAlign: 'center', maxWidth: 220 }}>
        Booked and completed test rides will appear here
      </div>
    </div>
  )
}

export default function TestRidesChart({ completed = 0, scheduled = 0, notUpdated = 0, cancelled = 0 }) {
  const rows = [
    { key: 'completed', name: 'Test Ride Completed', short: 'Completed', count: completed },
    { key: 'scheduled', name: 'Test Ride Scheduled', short: 'Scheduled (upcoming)', count: scheduled },
  ]
  const isEmpty = completed + scheduled + notUpdated + cancelled === 0

  return (
    <div className="card">
      <div className="card-header">
        <div>
          <h3 style={{ margin: 0 }}>Test Rides</h3>
          <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 2 }}>
            (Completed vs Scheduled)
          </div>
        </div>
      </div>
      <div className="card-pad">
        {isEmpty ? <EmptyState /> : (
          <>
            {/* headline numbers — also the text alternative to the bars */}
            <div style={{ display: 'flex', gap: 28, marginBottom: 6 }}>
              {rows.map((r) => (
                <div key={r.key} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span style={{ width: 10, height: 10, borderRadius: '50%', background: COLORS[r.key] }} />
                  <span style={{ fontSize: 12, color: '#6B7F96', fontWeight: 600 }}>{r.name}</span>
                  <span style={{ fontSize: 18, fontWeight: 800, color: '#1B2A3A' }}>{r.count}</span>
                </div>
              ))}
            </div>
            <ResponsiveContainer width="100%" height={230}>
              <BarChart data={rows} margin={{ top: 24, right: 16, left: -12, bottom: 0 }} barCategoryGap="38%">
                <CartesianGrid vertical={false} stroke="#EEF2F7" />
                <XAxis dataKey="short" tickLine={false} axisLine={{ stroke: '#D9E2EC' }}
                       tick={{ fontSize: 12, fill: '#6B7F96', fontWeight: 600 }} />
                <YAxis allowDecimals={false} tickLine={false} axisLine={false}
                       tick={{ fontSize: 11, fill: '#6B7F96' }} />
                <Tooltip content={<CustomTooltip />} cursor={{ fill: 'rgba(37,99,235,0.05)' }} />
                <Bar dataKey="count" radius={[4, 4, 0, 0]} maxBarSize={72}>
                  {rows.map((r) => <Cell key={r.key} fill={COLORS[r.key]} />)}
                  <LabelList dataKey="count" position="top"
                             style={{ fontSize: 12, fontWeight: 700, fill: '#1B2A3A' }} />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
            {(notUpdated > 0 || cancelled > 0) && (
              <div style={{ marginTop: 8, fontSize: 12, color: '#6B7F96', display: 'flex', gap: 16, flexWrap: 'wrap' }}>
                {notUpdated > 0 && (
                  <span title="Booked test rides whose date has passed but were never marked Completed or Cancelled">
                    ⚠️ <b style={{ color: '#1B2A3A' }}>{notUpdated}</b> past booking{notUpdated === 1 ? '' : 's'} not updated
                  </span>
                )}
                {cancelled > 0 && <span><b style={{ color: '#1B2A3A' }}>{cancelled}</b> cancelled</span>}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}