import { RadialBarChart, RadialBar, PolarAngleAxis, Tooltip, ResponsiveContainer } from 'recharts'

// Two progress gauges for the selected period:
//   Total Target Ratio       = leads that reached BOOKED/INVOICED ÷ all leads
//   Total TD Completed Ratio = test rides completed ÷ all test rides
// Percentages and the numbers behind them come from /pba/dashboard — see
// pba_dashboard() in app/modules/leads/router.py.

const GaugeTooltip = ({ active, payload }) => {
  if (!active || !payload?.length) return null
  const p = payload[0].payload
  return (
    <div style={{
      background: '#fff', border: '1px solid #D9E2EC',
      borderRadius: 9, padding: '8px 14px', fontSize: 13,
    }}>
      <div style={{ fontWeight: 700, color: '#1B2A3A' }}>{p.name}: {p.value}%</div>
      <div style={{ color: '#6B7F96', marginTop: 2 }}>{p.detail}</div>
    </div>
  )
}

function Gauge({ name, pct, color, detail }) {
  const value = Math.max(0, Math.min(100, pct || 0))
  const data = [{ name, value, detail, fill: color }]
  return (
    <div style={{ flex: '1 1 200px', minWidth: 180, textAlign: 'center' }}>
      <div style={{ position: 'relative', height: 190 }}>
        <ResponsiveContainer width="100%" height="100%">
          <RadialBarChart data={data} innerRadius="72%" outerRadius="100%" barSize={16}
                          startAngle={90} endAngle={-270}>
            <PolarAngleAxis type="number" domain={[0, 100]} angleAxisId={0} tick={false} />
            <RadialBar background={{ fill: '#F0F3F8' }} dataKey="value" cornerRadius={8} />
            <Tooltip content={<GaugeTooltip />} />
          </RadialBarChart>
        </ResponsiveContainer>
        <div style={{
          position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column',
          alignItems: 'center', justifyContent: 'center', pointerEvents: 'none',
        }}>
          <div style={{ fontSize: 26, fontWeight: 800, color: '#1B2A3A' }}>{value}%</div>
        </div>
      </div>
      <div style={{ marginTop: 8, fontWeight: 700, color: '#1B2A3A', fontSize: 13 }}>{name}</div>
      <div style={{ marginTop: 2, fontSize: 12, color: '#6B7F96' }}>{detail}</div>
    </div>
  )
}

export default function RatioGaugesChart({
  targetRatio = 0, targetAchieved = 0, targetTotal = 0,
  tdRatio = 0, tdCompleted = 0, tdTotal = 0,
}) {
  return (
    <div className="card">
      <div className="card-header">
        <div>
          <h3 style={{ margin: 0 }}>Target &amp; Test Drive Ratios</h3>
          <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 2 }}>
            (for the selected period)
          </div>
        </div>
      </div>
      <div className="card-pad" style={{ display: 'flex', gap: 16, flexWrap: 'wrap', justifyContent: 'space-around' }}>
        <Gauge
          name="Total Target Ratio" pct={targetRatio} color="#2563EB"
          detail={`${targetAchieved} of ${targetTotal} leads booked / invoiced`}
        />
        <Gauge
          name="Total TD Completed Ratio" pct={tdRatio} color="#2E9E6B"
          detail={`${tdCompleted} of ${tdTotal} test rides completed`}
        />
      </div>
    </div>
  )
}