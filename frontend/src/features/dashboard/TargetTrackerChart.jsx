import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  Legend, LabelList, ResponsiveContainer, Cell,
} from 'recharts'

// Value label on top of each bar
const TopLabel = ({ x, y, width, value, isEmpty }) => {
  if (isEmpty) return null
  return (
    <text
      x={x + width / 2} y={y - 6}
      textAnchor="middle" fontSize={12} fontWeight={700} fill="#1B2A3A"
    >
      {value}
    </text>
  )
}

// Wrap a model name into up to 2 lines so long names don't overlap neighbors
const wrapLabel = (name, maxCharsPerLine = 11) => {
  const words = name.split(' ')
  const lines = []
  let current = ''

  words.forEach((word) => {
    const candidate = current ? `${current} ${word}` : word
    if (candidate.length > maxCharsPerLine && current) {
      lines.push(current)
      current = word
    } else {
      current = candidate
    }
  })
  if (current) lines.push(current)

  // Cap at 2 lines; if more, merge the rest into the second line
  if (lines.length > 2) {
    return [lines[0], lines.slice(1).join(' ')]
  }
  return lines
}

// Custom X-axis tick: model name (wrapped) + achievement % below it
const AchievementTick = ({ x, y, payload, data, isEmpty }) => {
  const row = data.find((d) => d.model === payload.value)
  const pct  = row?.achievement_pct ?? 0
  const lines = isEmpty ? ['───'] : wrapLabel(String(payload.value))

  return (
    <g>
      {lines.map((line, i) => (
        <text
          key={i}
          x={x} y={y + 14 + i * 13}
          textAnchor="middle" fontSize={11} fontWeight={500}
          fill={isEmpty ? '#C8D6E5' : '#6B7F96'}
        >
          {line}
        </text>
      ))}
      {!isEmpty && (
        <text
          x={x} y={y + 14 + 2 * 13 + 4}
          textAnchor="middle" fontSize={12} fontWeight={700}
          fill="#2E9E6B"
        >
          {pct}%
        </text>
      )}
    </g>
  )
}

const CustomTooltip = ({ active, payload, label, isEmpty }) => {
  if (!active || !payload?.length || isEmpty) return null
  return (
    <div style={{
      background: '#fff', border: '1px solid #D9E2EC',
      borderRadius: 9, padding: '10px 14px', fontSize: 13,
    }}>
      <div style={{ fontWeight: 700, marginBottom: 6 }}>{label}</div>
      {payload.map((p) => (
        <div key={p.dataKey} style={{ color: p.fill, fontWeight: 600 }}>
          {p.name}: {p.value}
        </div>
      ))}
    </div>
  )
}

const SKELETON_DATA = [
  { model: 'Model A', target: 50, achieved: 40, achievement_pct: 80 },
  { model: 'Model B', target: 45, achieved: 32, achievement_pct: 71 },
  { model: 'Model C', target: 35, achieved: 28, achievement_pct: 80 },
  { model: 'Model D', target: 25, achieved: 18, achievement_pct: 72 },
  { model: 'Model E', target: 20, achieved: 15, achievement_pct: 75 },
]

export default function TargetTrackerChart({ data = [] }) {
  const isEmpty = data.length === 0

  // ✅ Show only top 5 models by target count — matches Figma layout
  const chartData = isEmpty
    ? SKELETON_DATA
    : [...data].sort((a, b) => b.target - a.target).slice(0, 5)

  return (
    <div className="card">
      <div className="card-header">
        <div>
          <h3 style={{ margin: 0 }}>Target Tracker – Achievements</h3>
          <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 2 }}>
            (Vehicle Model Wise)
          </div>
        </div>
      </div>

      <div className="card-pad" style={{ position: 'relative' }}>

        {/* Skeleton overlay */}
        {isEmpty && (
          <div style={{
            position: 'absolute', inset: 0, zIndex: 10,
            display: 'flex', flexDirection: 'column',
            alignItems: 'center', justifyContent: 'center',
            background: 'rgba(244,247,251,0.80)',
            borderRadius: '0 0 14px 14px', gap: 8,
          }}>
            <div style={{ fontSize: 28 }}>📊</div>
            <div style={{ fontWeight: 700, color: '#1B2A3A', fontSize: 14 }}>
              No target data yet
            </div>
            <div style={{ fontSize: 12, color: '#6B7F96', textAlign: 'center', maxWidth: 210 }}>
              Targets appear once leads are linked to vehicle models
            </div>
          </div>
        )}

        <ResponsiveContainer width="100%" height={340}>
          <BarChart
            data={chartData}
            margin={{ top: 28, right: 20, left: 10, bottom: 56 }}
            barCategoryGap="18%"
            barGap={4}
          >
            <CartesianGrid vertical={false} stroke="#EEF2F7" />

            <XAxis
              dataKey="model"
              tick={<AchievementTick data={chartData} isEmpty={isEmpty} />}
              tickLine={false}
              axisLine={false}
              interval={0}
              // ✅ enough height for wrapped name (up to 2 lines) + pct below
              height={64}
            />

            <YAxis
              tick={{ fontSize: 11, fill: '#6B7F96' }}
              axisLine={false}
              tickLine={false}
              label={{
                value: 'Count',
                angle: -90,
                position: 'insideLeft',
                offset: 0,
                style: { fontSize: 11, fill: '#6B7F96' },
              }}
            />

            <Tooltip content={<CustomTooltip isEmpty={isEmpty} />} />

            <Legend
              verticalAlign="top"
              align="right"
              iconType="square"
              iconSize={12}
              formatter={(val) => (
                <span style={{ fontSize: 12, color: '#6B7F96', fontWeight: 600 }}>
                  {val}
                </span>
              )}
            />

            {/* ✅ Target first (grey) then Achieved (blue) — matches Figma order */}
            <Bar dataKey="target" name="Target"
              fill={isEmpty ? '#EEF2F7' : '#C8D6E5'}
              radius={[4, 4, 0, 0]}
              barSize={28}
            >
              <LabelList content={(props) => <TopLabel {...props} isEmpty={isEmpty} />} />
            </Bar>

            <Bar dataKey="achieved" name="Achieved"
              fill={isEmpty ? '#D6E4F7' : '#2563EB'}
              radius={[4, 4, 0, 0]}
              barSize={28}
            >
              <LabelList content={(props) => <TopLabel {...props} isEmpty={isEmpty} />} />
            </Bar>
          </BarChart>
        </ResponsiveContainer>

        {/* Achievement % footer label */}
        <div style={{
          textAlign: 'center', fontSize: 12, fontWeight: 700,
          color: isEmpty ? '#C8D6E5' : '#2E9E6B',
          marginTop: -18,
        }}>
          Achievement %
        </div>
      </div>
    </div>
  )
}