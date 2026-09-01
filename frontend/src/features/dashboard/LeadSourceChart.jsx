import {
  BarChart, Bar, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer, LabelList,
} from 'recharts'

const COLORS = {
  csv: '#7C3AED',
  walkin: '#2563EB',
}

const LABELS = {
  csv: 'Imported (CSV)',
  walkin: 'Walk-in',
}

const CustomTooltip = ({ active, payload }) => {
  if (!active || !payload?.length) return null
  return (
    <div style={{
      background: '#fff', border: '1px solid #D9E2EC',
      borderRadius: 9, padding: '10px 14px', fontSize: 13,
    }}>
      {payload.map((p) => (
        <div key={p.dataKey} style={{ color: p.fill, fontWeight: 600 }}>
          {p.name}: {p.payload[`${p.dataKey}_count`]} ({p.value}%)
        </div>
      ))}
    </div>
  )
}

function SkeletonBar() {
  return (
    <div style={{ position: 'relative', height: 140 }}>
      <div style={{
        height: 32, borderRadius: 999, background: '#EEF2F7',
        margin: '46px 0',
      }} />
      <div style={{
        position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column',
        alignItems: 'center', justifyContent: 'center',
        background: 'rgba(244,247,251,0.78)', borderRadius: 14, gap: 6,
      }}>
        <div style={{ fontSize: 26 }}>📥</div>
        <div style={{ fontWeight: 700, color: '#1B2A3A', fontSize: 14 }}>No leads yet</div>
        <div style={{ fontSize: 12, color: '#6B7F96', textAlign: 'center', maxWidth: 200 }}>
          Source split appears once leads are logged
        </div>
      </div>
    </div>
  )
}

export default function LeadSourceChart({ data = {} }) {
  const csv = data.csv ?? 0
  const walkin = data.walkin ?? 0
  const total = csv + walkin
  const isEmpty = total === 0

  const csvPct = total ? Math.round((csv / total) * 100) : 0
  const walkinPct = total ? 100 - csvPct : 0

  const chartData = [{
    name: 'Leads',
    csv: csvPct,
    walkin: walkinPct,
    csv_count: csv,
    walkin_count: walkin,
  }]

  return (
    <div className="card">
      <div className="card-header">
        <div>
          <h3 style={{ margin: 0 }}>Lead Source Split</h3>
          <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 2 }}>
            (Imported vs Walk-in)
          </div>
        </div>
      </div>
      <div className="card-pad">
        {isEmpty ? (
          <SkeletonBar />
        ) : (
          <>
            {/* Stat chips — mirrors the pattern used on Total Sales */}
            <div style={{ display: 'flex', gap: 10, marginBottom: 20, flexWrap: 'wrap' }}>
              <div style={{
                flex: 1, background: '#EEE6FA', borderRadius: 10,
                padding: '12px 16px', minWidth: 100,
              }}>
                <div style={{ fontSize: 11, fontWeight: 700, color: COLORS.csv, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                  {LABELS.csv}
                </div>
                <div style={{ fontSize: 24, fontWeight: 800, color: '#1B2A3A', marginTop: 4 }}>{csv}</div>
              </div>
              <div style={{
                flex: 1, background: '#DCEAFD', borderRadius: 10,
                padding: '12px 16px', minWidth: 100,
              }}>
                <div style={{ fontSize: 11, fontWeight: 700, color: COLORS.walkin, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                  {LABELS.walkin}
                </div>
                <div style={{ fontSize: 24, fontWeight: 800, color: '#1B2A3A', marginTop: 4 }}>{walkin}</div>
              </div>
            </div>

            <ResponsiveContainer width="100%" height={110}>
              <BarChart
                data={chartData}
                layout="vertical"
                margin={{ top: 0, right: 10, left: 10, bottom: 0 }}
                barCategoryGap="0%"
              >
                <XAxis type="number" domain={[0, 100]} hide />
                <YAxis type="category" dataKey="name" hide />
                <Tooltip content={<CustomTooltip />} cursor={{ fill: 'transparent' }} />
                <Bar dataKey="csv" name={LABELS.csv} stackId="a" fill={COLORS.csv} radius={[999, 0, 0, 999]} barSize={32}>
                  <LabelList
                    dataKey="csv"
                    position="center"
                    fill="#fff"
                    fontSize={12}
                    fontWeight={700}
                    formatter={(v) => (v > 8 ? `${v}%` : '')}
                  />
                </Bar>
                <Bar dataKey="walkin" name={LABELS.walkin} stackId="a" fill={COLORS.walkin} radius={[0, 999, 999, 0]} barSize={32}>
                  <LabelList
                    dataKey="walkin"
                    position="center"
                    fill="#fff"
                    fontSize={12}
                    fontWeight={700}
                    formatter={(v) => (v > 8 ? `${v}%` : '')}
                  />
                </Bar>
                <Legend
                  iconType="circle"
                  iconSize={10}
                  formatter={(val) => (
                    <span style={{ fontSize: 12, color: '#6B7F96', fontWeight: 600 }}>{val}</span>
                  )}
                />
              </BarChart>
            </ResponsiveContainer>
          </>
        )}
      </div>
    </div>
  )
}