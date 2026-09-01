import {
  RadialBarChart, RadialBar, Legend, Tooltip, ResponsiveContainer, PolarAngleAxis,
} from 'recharts'

const COLORS = {
  green: '#2E9E6B',
  yellow: '#D9A72E',
  red: '#D85B4A',
}

const LABELS = {
  green: 'On Time',
  yellow: 'Pending',
  red: 'Overdue',
}

const CustomTooltip = ({ active, payload }) => {
  if (!active || !payload?.length) return null
  const p = payload[0]
  return (
    <div style={{
      background: '#fff', border: '1px solid #D9E2EC',
      borderRadius: 9, padding: '8px 14px', fontSize: 13,
    }}>
      <span style={{ fontWeight: 700, color: p.payload.fill }}>{p.payload.name}: </span>{p.payload.count}
    </div>
  )
}

function SkeletonRadial() {
  return (
    <div style={{ position: 'relative', height: 240 }}>
      <div style={{
        width: 200, height: 200, borderRadius: '50%',
        border: '28px solid #EEF2F7', margin: '20px auto 0', position: 'relative',
      }}>
        <div style={{
          position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column',
          alignItems: 'center', justifyContent: 'center',
        }}>
          <div style={{ fontSize: 22, fontWeight: 800, color: '#C8D6E5' }}>—</div>
          <div style={{ fontSize: 12, color: '#C8D6E5', fontWeight: 600 }}>Total</div>
        </div>
      </div>
      <div style={{
        position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column',
        alignItems: 'center', justifyContent: 'center',
        background: 'rgba(244,247,251,0.78)', borderRadius: 14, gap: 6,
      }}>
        <div style={{ fontSize: 26 }}>⏱️</div>
        <div style={{ fontWeight: 700, color: '#1B2A3A', fontSize: 14 }}>No follow-up data yet</div>
        <div style={{ fontSize: 12, color: '#6B7F96', textAlign: 'center', maxWidth: 200 }}>
          SLA status appears once leads are assigned
        </div>
      </div>
    </div>
  )
}

export default function SlaComplianceChart({ data = {} }) {
  const green = data.green ?? 0
  const yellow = data.yellow ?? 0
  const red = data.red ?? 0
  const total = green + yellow + red
  const isEmpty = total === 0

  // Each entry in `data` renders as its own concentric arc — first item is
  // innermost. Red (Overdue) innermost so it reads as the "core" concern,
  // On Time as the widest/outermost ring.
  const radialData = [
    { key: 'red', name: LABELS.red, count: red, value: total ? Math.round((red / total) * 100) : 0, fill: COLORS.red },
    { key: 'yellow', name: LABELS.yellow, count: yellow, value: total ? Math.round((yellow / total) * 100) : 0, fill: COLORS.yellow },
    { key: 'green', name: LABELS.green, count: green, value: total ? Math.round((green / total) * 100) : 0, fill: COLORS.green },
  ]

  return (
    <div className="card">
      <div className="card-header">
        <div>
          <h3 style={{ margin: 0 }}>SLA Compliance</h3>
          <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 2 }}>
            (Follow-up Responsiveness)
          </div>
        </div>
      </div>
      <div className="card-pad">
        {isEmpty ? (
          <SkeletonRadial />
        ) : (
          <div style={{ position: 'relative' }}>
            <ResponsiveContainer width="100%" height={260}>
              <RadialBarChart
                data={radialData}
                innerRadius="30%"
                outerRadius="100%"
                barSize={16}
                startAngle={90}
                endAngle={-270}
                cx="38%"
              >
                <PolarAngleAxis type="number" domain={[0, 100]} angleAxisId={0} tick={false} />
                <RadialBar
                  background={{ fill: '#F0F3F8' }}
                  dataKey="value"
                  cornerRadius={8}
                />
                <Tooltip content={<CustomTooltip />} />
                <Legend
                  iconType="circle"
                  iconSize={10}
                  layout="vertical"
                  verticalAlign="middle"
                  align="right"
                  formatter={(_val, entry) => (
                    <span style={{ fontSize: 12, color: '#6B7F96', fontWeight: 600 }}>
                      {entry.payload.name} ({entry.payload.count})
                    </span>
                  )}
                />
              </RadialBarChart>
            </ResponsiveContainer>
            <div style={{
              position: 'absolute', top: '50%', left: '38%',
              transform: 'translate(-50%, -50%)', textAlign: 'center', pointerEvents: 'none',
            }}>
              <div style={{ fontSize: 24, fontWeight: 800, color: '#1B2A3A' }}>{total}</div>
              <div style={{ fontSize: 11, color: '#6B7F96', fontWeight: 600 }}>Leads</div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}