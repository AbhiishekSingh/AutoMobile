import { PieChart, Pie, Cell, Tooltip, Legend, ResponsiveContainer } from 'recharts'

const COLORS = {
  achieved: '#2E9E6B',
  to_be_achieved: '#2563EB',
  cancelled: '#D85B4A',
}

function StatChip({ label, value, color, bg, icon }) {
  return (
    <div style={{
      flex: 1, background: bg, borderRadius: 10,
      padding: '12px 16px', display: 'flex',
      flexDirection: 'column', gap: 6, minWidth: 100,
    }}>
      <div style={{ fontSize: 11, fontWeight: 700, color, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
        {label}
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <span style={{ fontSize: 28, fontWeight: 800, color: '#1B2A3A' }}>{value}</span>
        <span style={{ fontSize: 22 }}>{icon}</span>
      </div>
    </div>
  )
}

const renderCustomLabel = ({ cx, cy, midAngle, innerRadius, outerRadius, percent }) => {
  if (percent < 0.05) return null
  const RADIAN = Math.PI / 180
  const radius = innerRadius + (outerRadius - innerRadius) * 0.5
  const x = cx + radius * Math.cos(-midAngle * RADIAN)
  const y = cy + radius * Math.sin(-midAngle * RADIAN)
  return (
    <text x={x} y={y} fill="#fff" textAnchor="middle"
      dominantBaseline="central" fontSize={12} fontWeight={700}>
      {`${(percent * 100).toFixed(1)}%`}
    </text>
  )
}

const CustomTooltip = ({ active, payload }) => {
  if (!active || !payload?.length) return null
  return (
    <div style={{
      background: '#fff', border: '1px solid #D9E2EC',
      borderRadius: 9, padding: '8px 14px', fontSize: 13,
    }}>
      <span style={{ fontWeight: 700 }}>{payload[0].name}: </span>{payload[0].value}
    </div>
  )
}

// Skeleton donut shown when no data
function SkeletonDonut() {
  return (
    <div style={{ position: 'relative', height: 240 }}>
      {/* Grey placeholder ring */}
      <div style={{
        width: 200, height: 200,
        borderRadius: '50%',
        border: '28px solid #EEF2F7',
        margin: '20px auto 0',
        position: 'relative',
      }}>
        <div style={{
          position: 'absolute', inset: 0,
          display: 'flex', flexDirection: 'column',
          alignItems: 'center', justifyContent: 'center',
        }}>
          <div style={{ fontSize: 22, fontWeight: 800, color: '#C8D6E5' }}>—</div>
          <div style={{ fontSize: 12, color: '#C8D6E5', fontWeight: 600 }}>Total</div>
        </div>
      </div>
      {/* Overlay message */}
      <div style={{
        position: 'absolute', inset: 0,
        display: 'flex', flexDirection: 'column',
        alignItems: 'center', justifyContent: 'center',
        background: 'rgba(244,247,251,0.78)',
        borderRadius: 14, gap: 6,
      }}>
        <div style={{ fontSize: 26 }}>🏍️</div>
        <div style={{ fontWeight: 700, color: '#1B2A3A', fontSize: 14 }}>
          No sales data yet
        </div>
        <div style={{ fontSize: 12, color: '#6B7F96', textAlign: 'center', maxWidth: 200 }}>
          Sales will appear once leads reach Booked or Invoiced stage
        </div>
      </div>
    </div>
  )
}

export default function TotalSalesChart({ data = {} }) {
  const achieved      = data.achieved       ?? 0
  const to_be_achieved = data.to_be_achieved ?? 0
  const cancelled     = data.cancelled      ?? 0
  const total = achieved + to_be_achieved + cancelled
  const isEmpty = total === 0

  const pieData = [
    { name: 'Achieved',        value: achieved,        key: 'achieved' },
    { name: 'To Be Achieved',  value: to_be_achieved,  key: 'to_be_achieved' },
    { name: 'Cancelled',       value: cancelled,        key: 'cancelled' },
  ].filter((d) => d.value > 0)

  return (
    <div className="card">
      <div className="card-header">
        <h3 style={{ margin: 0 }}>Total Sales of Vehicles</h3>
      </div>
      <div className="card-pad">

        {/* Stat chips — always visible */}
        <div style={{ display: 'flex', gap: 10, marginBottom: 20, flexWrap: 'wrap' }}>
          <StatChip label="Achieved"       value={achieved}        color="#2E9E6B" bg="#DFF3E9" icon="🏍️" />
          <StatChip label="To Be Achieved" value={to_be_achieved}  color="#2563EB" bg="#E4EFFB" icon="🛵" />
          <StatChip label="Cancelled"      value={cancelled}       color="#D85B4A" bg="#FBE0DB" icon="❌" />
        </div>

        {/* Skeleton or real donut */}
        {isEmpty ? (
          <SkeletonDonut />
        ) : (
          <ResponsiveContainer width="100%" height={240}>
            <PieChart>
              <Pie
                data={pieData}
                cx="50%"
                cy="50%"
                innerRadius={65}
                outerRadius={100}
                paddingAngle={2}
                dataKey="value"
                labelLine={false}
                label={renderCustomLabel}
              >
                {pieData.map((entry) => (
                  <Cell key={entry.key} fill={COLORS[entry.key]} />
                ))}
              </Pie>
              <text x="50%" y="44%" textAnchor="middle"
                dominantBaseline="middle" fontSize={26} fontWeight={800} fill="#1B2A3A">
                {total}
              </text>
              <text x="50%" y="56%" textAnchor="middle"
                dominantBaseline="middle" fontSize={12} fill="#6B7F96" fontWeight={600}>
                Total
              </text>
              <Tooltip content={<CustomTooltip />} />
              <Legend
                iconType="circle"
                iconSize={10}
                formatter={(val, entry) => (
                  <span style={{ fontSize: 12, color: '#6B7F96', fontWeight: 600 }}>
                    {val} ({entry.payload.value})
                  </span>
                )}
              />
            </PieChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  )
}