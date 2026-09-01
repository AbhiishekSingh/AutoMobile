import {
  BarChart, Bar, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer, LabelList,
} from 'recharts'

const STAGE_LABELS = {
  DRAFT: 'Draft',
  SHARED: 'Shared',
}

const STAGE_COLORS = {
  DRAFT: '#C8D6E5',
  SHARED: '#2563EB',
}

const CustomTooltip = ({ active, payload, isEmpty }) => {
  if (!active || !payload?.length || isEmpty) return null
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
        <div style={{ fontSize: 26 }}>📄</div>
        <div style={{ fontWeight: 700, color: '#1B2A3A', fontSize: 14 }}>No quotations yet</div>
        <div style={{ fontSize: 12, color: '#6B7F96', textAlign: 'center', maxWidth: 200 }}>
          Split appears once quotations are created
        </div>
      </div>
    </div>
  )
}

export default function QuotationFunnelChart({ data = [] }) {
  // Only Draft and Shared are relevant here — filter out any other
  // quotation statuses (Accepted / Expired / Rejected) the API may return.
  const byStatus = Object.fromEntries((data || []).map((d) => [d.status, d.count || 0]))
  const draftCount = byStatus.DRAFT || 0
  const sharedCount = byStatus.SHARED || 0
  const total = draftCount + sharedCount
  const isEmpty = total === 0

  const draftPct = total ? Math.round((draftCount / total) * 100) : 0
  const sharedPct = total ? 100 - draftPct : 0

  const chartData = [{
    name: 'Quotations',
    draft: draftPct,
    shared: sharedPct,
    draft_count: draftCount,
    shared_count: sharedCount,
  }]

  return (
    <div className="card">
      <div className="card-header">
        <div>
          <h3 style={{ margin: 0 }}>Quotation Funnel</h3>
          <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 2 }}>
            (Draft vs Shared)
          </div>
        </div>
        {!isEmpty && (
          <div style={{
            fontSize: 12, fontWeight: 700, color: '#2563EB',
            background: '#DCEAFD', padding: '4px 10px', borderRadius: 999,
          }}>
            {sharedPct}% shared
          </div>
        )}
      </div>
      <div className="card-pad">
        {isEmpty ? (
          <SkeletonBar />
        ) : (
          <>
            {/* Stat chips — mirrors the pattern used on Lead Source Split */}
            <div style={{ display: 'flex', gap: 10, marginBottom: 20, flexWrap: 'wrap' }}>
              <div style={{
                flex: 1, background: '#F0F3F8', borderRadius: 10,
                padding: '12px 16px', minWidth: 100,
              }}>
                <div style={{ fontSize: 11, fontWeight: 700, color: '#6B7F96', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                  {STAGE_LABELS.DRAFT}
                </div>
                <div style={{ fontSize: 24, fontWeight: 800, color: '#1B2A3A', marginTop: 4 }}>{draftCount}</div>
              </div>
              <div style={{
                flex: 1, background: '#DCEAFD', borderRadius: 10,
                padding: '12px 16px', minWidth: 100,
              }}>
                <div style={{ fontSize: 11, fontWeight: 700, color: STAGE_COLORS.SHARED, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                  {STAGE_LABELS.SHARED}
                </div>
                <div style={{ fontSize: 24, fontWeight: 800, color: '#1B2A3A', marginTop: 4 }}>{sharedCount}</div>
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
                <Tooltip content={<CustomTooltip isEmpty={isEmpty} />} cursor={{ fill: 'transparent' }} />
                <Bar dataKey="draft" name={STAGE_LABELS.DRAFT} stackId="a" fill={STAGE_COLORS.DRAFT} radius={[999, 0, 0, 999]} barSize={32}>
                  <LabelList
                    dataKey="draft"
                    position="center"
                    fill="#1B2A3A"
                    fontSize={12}
                    fontWeight={700}
                    formatter={(v) => (v > 8 ? `${v}%` : '')}
                  />
                </Bar>
                <Bar dataKey="shared" name={STAGE_LABELS.SHARED} stackId="a" fill={STAGE_COLORS.SHARED} radius={[0, 999, 999, 0]} barSize={32}>
                  <LabelList
                    dataKey="shared"
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