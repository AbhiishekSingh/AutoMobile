import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, LabelList,
} from 'recharts'

const SKELETON_DATA = [
  { reason: 'Reason A', count: 12 },
  { reason: 'Reason B', count: 9 },
  { reason: 'Reason C', count: 6 },
  { reason: 'Reason D', count: 3 },
]

const CustomTooltip = ({ active, payload, label, isEmpty }) => {
  if (!active || !payload?.length || isEmpty) return null
  return (
    <div style={{
      background: '#fff', border: '1px solid #D9E2EC',
      borderRadius: 9, padding: '10px 14px', fontSize: 13,
    }}>
      <div style={{ fontWeight: 700, marginBottom: 4 }}>{label}</div>
      <div style={{ color: '#D85B4A', fontWeight: 600 }}>Lost: {payload[0].value}</div>
    </div>
  )
}

export default function LostReasonsChart({ data = [] }) {
  const isEmpty = data.length === 0
  const chartData = isEmpty ? SKELETON_DATA : [...data].slice(0, 8)

  return (
    <div className="card">
      <div className="card-header">
        <div>
          <h3 style={{ margin: 0 }}>Top Lost Reasons</h3>
          <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 2 }}>
            (Closed Leads)
          </div>
        </div>
      </div>

      <div className="card-pad" style={{ position: 'relative' }}>
        {isEmpty && (
          <div style={{
            position: 'absolute', inset: 0, zIndex: 10,
            display: 'flex', flexDirection: 'column',
            alignItems: 'center', justifyContent: 'center',
            background: 'rgba(244,247,251,0.80)',
            borderRadius: '0 0 14px 14px', gap: 8,
          }}>
            <div style={{ fontSize: 28 }}>📉</div>
            <div style={{ fontWeight: 700, color: '#1B2A3A', fontSize: 14 }}>
              No lost leads yet
            </div>
            <div style={{ fontSize: 12, color: '#6B7F96', textAlign: 'center', maxWidth: 210 }}>
              Reasons appear once leads are closed with a lost reason
            </div>
          </div>
        )}

        <ResponsiveContainer width="100%" height={300}>
          <BarChart
            data={chartData}
            layout="vertical"
            margin={{ top: 10, right: 30, left: 10, bottom: 10 }}
            barCategoryGap="22%"
          >
            <CartesianGrid horizontal={false} stroke="#EEF2F7" />
            <XAxis type="number" tick={{ fontSize: 11, fill: '#6B7F96' }} axisLine={false} tickLine={false} allowDecimals={false} />
            <YAxis
              type="category"
              dataKey="reason"
              width={110}
              tick={{ fontSize: 11, fill: isEmpty ? '#C8D6E5' : '#6B7F96', fontWeight: 500 }}
              axisLine={false}
              tickLine={false}
            />
            <Tooltip content={<CustomTooltip isEmpty={isEmpty} />} cursor={{ fill: '#F4F7FB' }} />
            <Bar dataKey="count" name="Lost" fill={isEmpty ? '#F3D9D3' : '#D85B4A'} radius={[0, 4, 4, 0]} barSize={22}>
              {!isEmpty && (
                <LabelList dataKey="count" position="right" fontSize={12} fontWeight={700} fill="#1B2A3A" />
              )}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
