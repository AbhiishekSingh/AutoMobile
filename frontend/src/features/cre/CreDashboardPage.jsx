// CRE Dashboard: KPI cards, funnel, sales trend, opportunity / follow-up / test-ride donuts, weekday activity, insights.
import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import api from '../../lib/api'
import Layout from '../../components/Layout'
import { Empty, Loading, fmtDateTime } from '../../components/ui'

const today = new Date()
const iso = (d) => d.toISOString().slice(0, 10)
const PAL = ['#2563eb', '#16a34a', '#f59e0b', '#7c3aed', '#ef4444', '#0891b2', '#64748b']
const nf = (n) => Number(n || 0).toLocaleString('en-IN')

function Delta({ cur, prev }) {
  if (!prev) return null
  const p = Math.round(((cur - prev) * 100) / prev)
  return <span style={{ fontSize: 12, fontWeight: 600, color: p >= 0 ? '#16a34a' : '#dc2626' }}>{p >= 0 ? '▲' : '▼'} {Math.abs(p)}%</span>
}

function Kpi({ label, value, prev, tone, onClick }) {
  const T = { blue: ['#eff6ff', '#2563eb'], green: ['#f0fdf4', '#16a34a'], orange: ['#fff7ed', '#ea580c'], red: ['#fef2f2', '#dc2626'], purple: ['#f5f3ff', '#7c3aed'], teal: ['#f0fdfa', '#0d9488'] }[tone]
  return (
    <div onClick={onClick} style={{ background: T[0], border: `1px solid ${T[1]}33`, borderRadius: 12, padding: '14px 16px', cursor: onClick ? 'pointer' : 'default' }}>
      <div style={{ fontSize: 13, color: '#334155', fontWeight: 600, minHeight: 34 }}>{label}</div>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 10 }}>
        <span style={{ fontSize: 30, fontWeight: 700, color: T[1] }}>{nf(value)}</span>{prev !== undefined && <Delta cur={value} prev={prev} />}
      </div>
    </div>)
}

function Donut({ items, centerTop, centerSub, size = 150 }) {
  const total = items.reduce((a, i) => a + i.value, 0)
  const r = 54, c = 2 * Math.PI * r
  let off = 0
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
      <svg width={size} height={size} viewBox="0 0 140 140">
        <circle cx="70" cy="70" r={r} fill="none" stroke="#e5e7eb" strokeWidth="18" />
        {total > 0 && items.map((i, k) => {
          const len = (i.value / total) * c
          const el = <circle key={i.label} cx="70" cy="70" r={r} fill="none" stroke={PAL[k % PAL.length]} strokeWidth="18" strokeDasharray={`${len} ${c - len}`} strokeDashoffset={-off} transform="rotate(-90 70 70)" />
          off += len; return el
        })}
        <text x="70" y="68" textAnchor="middle" fontSize="22" fontWeight="700" fill="#0f172a">{centerTop}</text>
        <text x="70" y="86" textAnchor="middle" fontSize="11" fill="#64748b">{centerSub}</text>
      </svg>
      <div style={{ fontSize: 13 }}>{items.map((i, k) => (
        <div key={i.label} style={{ display: 'flex', gap: 8, alignItems: 'center', margin: '4px 0' }}>
          <span style={{ width: 10, height: 10, borderRadius: 10, background: PAL[k % PAL.length] }} /><span style={{ minWidth: 110 }}>{i.label}</span><b>{nf(i.value)}</b>
          {i.pct != null && <span style={{ color: '#64748b' }}>{i.pct}%</span>}
        </div>))}</div>
    </div>)
}

function Funnel({ steps }) {
  const max = Math.max(1, steps[0]?.count || 1)
  const cols = ['#3b82f6', '#22c55e', '#f59e0b', '#8b5cf6']
  return (
    <div>{steps.map((s, k) => {
      const w = Math.max(28, (s.count / max) * 100)
      return (<div key={s.label} style={{ display: 'flex', alignItems: 'center', gap: 10, margin: '6px 0' }}>
        <div style={{ flex: 1, display: 'flex', justifyContent: 'center' }}>
          <div style={{ width: `${w}%`, background: cols[k % 4], color: '#fff', textAlign: 'center', padding: '8px 0', fontWeight: 700, borderRadius: 6, clipPath: 'polygon(0 0,100% 0,94% 100%,6% 100%)' }}>{nf(s.count)}</div>
        </div>
        <span style={{ width: 90, fontSize: 13 }}>{s.label}</span></div>)
    })}</div>)
}

function LineChart({ points, area, height = 130, color = '#2563eb' }) {
  const W = 320, H = height, max = Math.max(1, ...points.map((p) => p.value))
  const x = (i) => 20 + (i * (W - 40)) / Math.max(1, points.length - 1)
  const y = (v) => H - 24 - (v / max) * (H - 44)
  const path = points.map((p, i) => `${i ? 'L' : 'M'}${x(i)},${y(p.value)}`).join(' ')
  return (
    <svg viewBox={`0 0 ${W} ${H}`} style={{ width: '100%' }}>
      {area && <path d={`${path} L${x(points.length - 1)},${H - 24} L${x(0)},${H - 24} Z`} fill={color + '22'} />}
      <path d={path} fill="none" stroke={color} strokeWidth="2" />
      {points.map((p, i) => <g key={p.label}><circle cx={x(i)} cy={y(p.value)} r="3" fill={color} /><text x={x(i)} y={H - 8} textAnchor="middle" fontSize="10" fill="#64748b">{p.label}</text>
        <text x={x(i)} y={y(p.value) - 7} textAnchor="middle" fontSize="10" fill="#334155">{p.value}</text></g>)}
    </svg>)
}

function SalesTrend({ months }) {
  const W = 320, H = 150, max = Math.max(1, ...months.map((m) => m.bookings)), maxP = Math.max(1, ...months.map((m) => m.conversion_pct))
  const bx = (i) => 40 + i * 70
  const py = (v) => 100 - (v / maxP) * 60
  return (
    <svg viewBox={`0 0 ${W} ${H}`} style={{ width: '100%' }}>
      {months.map((m, i) => { const h = (m.bookings / max) * 70; return <g key={m.label}>
        <rect x={bx(i) - 14} y={110 - h} width="28" height={h} rx="3" fill="#3b82f6" />
        <text x={bx(i)} y={106 - h} textAnchor="middle" fontSize="10" fontWeight="700">{m.bookings}</text>
        <text x={bx(i)} y={126} textAnchor="middle" fontSize="10" fill="#64748b">{m.label}</text>
        <text x={bx(i)} y={py(m.conversion_pct) - 6} textAnchor="middle" fontSize="9" fill="#16a34a">{m.conversion_pct}%</text></g> })}
      <path d={months.map((m, i) => `${i ? 'L' : 'M'}${bx(i)},${py(m.conversion_pct)}`).join(' ')} fill="none" stroke="#16a34a" strokeWidth="2" />
      {months.map((m, i) => <circle key={m.label} cx={bx(i)} cy={py(m.conversion_pct)} r="3" fill="#16a34a" />)}
      <text x="40" y="146" fontSize="10" fill="#3b82f6">■ Bookings</text><text x="110" y="146" fontSize="10" fill="#16a34a">● Conversion %</text>
    </svg>)
}

const Panel = ({ title, children, style }) => <div className="card" style={{ marginBottom: 0, ...style }}><div className="card-header"><h3>{title}</h3></div><div className="card-pad">{children}</div></div>

export default function CreDashboardPage() {
  const [f, setF] = useState({ date_from: iso(new Date(today.getFullYear(), today.getMonth(), 1)), date_to: iso(today) })
  const [d, setD] = useState(null)
  const [drill, setDrill] = useState(null)
  const load = useCallback(() => { setD(null); api.get('/cre-reports', { params: f }).then((r) => setD(r.data)).catch(() => setD(false)) }, [f.date_from, f.date_to])
  useEffect(() => { load() }, [load])
  async function open(kind, title) {
    const r = await api.get('/cre-reports/leads', { params: { kind, ...f } })
    setDrill({ title: title || r.data.title, rows: r.data.rows })
  }
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value })
  const filters = (
    <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
      <input className="input" type="date" value={f.date_from} onChange={set('date_from')} /><span>–</span><input className="input" type="date" value={f.date_to} onChange={set('date_to')} />
    </div>)
  if (d === null) return <Layout title="CRE Dashboard"><Loading /></Layout>
  if (d === false) return <Layout title="CRE Dashboard"><div className="hint">Could not load the dashboard.</div></Layout>
  const t = d.total, x = d.dashboard, p = x.prev
  const opp = d.opportunity, oppTotal = opp.reduce((a, i) => a + i.count, 0) || 1
  const top = opp.slice(0, 4).map((o) => ({ label: o.name, value: o.count, pct: Math.round((o.count * 100) / oppTotal) }))
  const rest = opp.slice(4).reduce((a, i) => a + i.count, 0)
  if (rest) top.push({ label: 'Others', value: rest, pct: Math.round((rest * 100) / oppTotal) })
  const fuTot = x.followup.done + x.followup.pending
  const fuPct = fuTot ? Math.round((x.followup.done * 100) / fuTot) : 0
  const tdPct = t.tr_scheduled ? Math.round((t.tr_completed * 100) / t.tr_scheduled) : 0
  const funnel = [['Assigned Leads', t.total], ['Contacted', t.contacted], ['Qualified', t.qualified], ['Booked', t.booked]].map(([label, count]) => ({ label, count }))
  const conv = t.total ? Math.round((t.booked * 1000) / t.total) / 10 : 0
  const insights = [
    p.total ? `Leads ${t.total >= p.total ? 'up' : 'down'} ${Math.abs(Math.round(((t.total - p.total) * 100) / p.total))}% vs the previous period` : null,
    `Lead to booking conversion is ${conv}%`,
    `Test ride completion at ${tdPct}%`,
    t.overdue ? `${t.overdue} overdue follow-ups need attention` : 'No overdue follow-ups',
    p.booked ? `Bookings ${t.booked >= p.booked ? 'up' : 'down'} ${Math.abs(Math.round(((t.booked - p.booked) * 100) / p.booked))}% vs the previous period` : null,
  ].filter(Boolean)
  const kp = [
    ['Total Assigned Leads', t.total, p.total, 'blue', 'all'], ["Today's Followup", t.due_today, undefined, 'green', 'due_today'],
    ['Pending Followup', t.pending, undefined, 'orange', 'pending'], ['Over Due Followup', t.overdue, undefined, 'red', 'overdue'],
    ['Test Ride Scheduled', t.tr_scheduled, p.tr_scheduled, 'purple', 'tr_scheduled'], ['Test Ride Completed', t.tr_completed, p.tr_completed, 'green', 'tr_completed'],
    ['Showroom Visit', t.showroom, p.showroom, 'blue', 'showroom'], ['Service / Casual Enquiry / Wrong / False Enquiry / Out of MH', x.other_enquiry, undefined, 'orange', 'other'],
  ]
  return (
    <Layout title="CRE Dashboard">
      <div style={{ marginBottom: 12 }}>{filters}</div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(210px, 1fr))', gap: 12, marginBottom: 14 }}>
        {kp.map(([l, v, pv, tone, kind]) => <Kpi key={l} label={l} value={v} prev={pv} tone={tone} onClick={() => open(kind, l)} />)}
      </div>
      {drill && <div className="card" style={{ marginBottom: 14 }}><div className="card-header"><h3>{drill.title} ({drill.rows.length})</h3><button className="btn btn-outline btn-sm" onClick={() => setDrill(null)}>Close</button></div>
        <div className="table-wrap"><table className="data-table"><thead><tr><th>Enquiry</th><th>Customer</th><th>Mobile</th><th>Branch</th><th>PBA</th><th>Status</th><th>Next follow-up</th><th></th></tr></thead>
          <tbody>{drill.rows.map((r) => <tr key={r.lead_id}><td>{r.enquiry_no}</td><td>{r.customer}</td><td>{r.mobile}</td><td>{r.branch || '—'}</td><td>{r.pba || '—'}</td><td>{r.opportunity || r.stage}</td><td>{fmtDateTime(r.next_followup_at)}</td><td><Link className="btn btn-primary btn-sm" to={`/leads/${r.lead_id}`}>Open</Link></td></tr>)}</tbody></table>
          {!drill.rows.length && <Empty>No leads.</Empty>}</div></div>}

      <div style={{ background: '#0f2a5c', color: '#fff', padding: '8px 16px', borderRadius: '10px 10px 0 0', fontWeight: 700 }}>CRE Performance Overview</div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: 12, margin: '12px 0' }}>
        <Panel title="Lead Conversion Funnel"><Funnel steps={funnel} /></Panel>
        <Panel title="Sales Performance Trend"><SalesTrend months={x.monthly} /></Panel>
        <Panel title="Opportunity Status Distribution"><Donut items={top} centerTop={nf(oppTotal === 1 && !opp.length ? 0 : oppTotal)} centerSub="Total" /></Panel>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: 12, marginBottom: 14 }}>
        <Panel title="Follow-up Status"><Donut items={[{ label: 'Follow-up Done', value: x.followup.done }, { label: 'Follow-up Pending', value: x.followup.pending }]} centerTop={`${fuPct}%`} centerSub="Completed" /></Panel>
        <Panel title="TD Ratio"><Donut items={[{ label: 'Scheduled', value: t.tr_scheduled }, { label: 'Completed', value: t.tr_completed }, { label: 'Rescheduled', value: t.tr_rescheduled }]} centerTop={`${tdPct}%`} centerSub="Completion" /></Panel>
        <Panel title="CRE Activity Summary"><LineChart area points={x.weekday.map((w) => ({ label: w.label, value: w.count }))} /></Panel>
      </div>
      <Panel title="Key Insights"><ul style={{ margin: 0, paddingLeft: 18, fontSize: 14, lineHeight: 1.9 }}>{insights.map((i) => <li key={i}>{i}</li>)}</ul></Panel>
    </Layout>)
}
