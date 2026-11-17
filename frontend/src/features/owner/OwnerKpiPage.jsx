// Owner KPI view: sales-funnel conversion (enquiry -> delivered) and deal-workflow speed (time per hand-over, longest waiting).
import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import Layout from '../../components/Layout'
import { Loading, Empty, fmtDateTime } from '../../components/ui'
import api from '../../lib/api'

const PERIODS = [['day', 'Daily'], ['week', 'Weekly'], ['month', 'Monthly'], ['quarter', 'Quarterly'], ['year', 'Yearly']]
const iso = (d) => d.toISOString().slice(0, 10)
const today = () => iso(new Date(Date.now() + 330 * 60 * 1000))
function shift(period, on, dir) {
  const d = new Date(on + 'T00:00:00Z')
  if (period === 'day') d.setUTCDate(d.getUTCDate() + dir)
  else if (period === 'week') d.setUTCDate(d.getUTCDate() + 7 * dir)
  else if (period === 'month') d.setUTCMonth(d.getUTCMonth() + dir, 1)
  else if (period === 'quarter') d.setUTCMonth(d.getUTCMonth() + 3 * dir, 1)
  else d.setUTCFullYear(d.getUTCFullYear() + dir, 0, 1)
  return iso(d)
}
// 90 -> "3 d 18 h", 5.5 -> "5.5 h"
const dur = (h) => (h == null ? '—' : h >= 48 ? `${Math.floor(h / 24)} d ${Math.round(h % 24)} h` : `${h} h`)
const pct = (v) => (v == null ? '—' : v + '%')
const R = { textAlign: 'right' }
const COLORS = ['#2f80ed', '#3b8bf0', '#4b97f2', '#5ba3f4', '#e09a00', '#1f8a4c', '#17673a']

export default function OwnerKpiPage() {
  const nav = useNavigate()
  const [period, setPeriod] = useState('month')
  const [on, setOn] = useState(today())
  const [branch, setBranch] = useState('')
  const [d, setD] = useState(null)
  const params = useMemo(() => ({ period, on, ...(branch ? { branch_id: branch } : {}) }), [period, on, branch])
  useEffect(() => { setD(null); api.get('/owner/kpi', { params }).then((r) => setD(r.data)).catch(() => setD(false)) }, [params])

  const TITLE = 'KPI view'
  if (d === null) return <Layout title={TITLE}><Loading /></Layout>
  if (d === false) return <Layout title={TITLE}><div className="hint">Could not load the KPI view.</div></Layout>
  const max = Math.max(1, ...d.funnel.steps.map((s) => s.count))

  return (
    <Layout title={TITLE} sub={`${branch ? d.branch_options.find((b) => String(b.id) === String(branch))?.name : 'All branches'} · ${d.label}`}>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center', marginBottom: 14 }}>
        {PERIODS.map(([k, l]) => <button key={k} className={'btn btn-sm ' + (period === k ? 'btn-primary' : 'btn-outline')} onClick={() => setPeriod(k)}>{l}</button>)}
        <button className="btn btn-outline btn-sm" onClick={() => setOn(shift(period, on, -1))}>◀</button>
        <input className="input" type="date" style={{ maxWidth: 160 }} value={on} onChange={(e) => e.target.value && setOn(e.target.value)} />
        <button className="btn btn-outline btn-sm" onClick={() => setOn(shift(period, on, 1))}>▶</button>
        <button className="btn btn-outline btn-sm" onClick={() => setOn(today())}>Today</button>
        <select className="input" style={{ maxWidth: 220 }} value={branch} onChange={(e) => setBranch(e.target.value)}>
          <option value="">All branches</option>{d.branch_options.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}</select>
      </div>

      {/* 1. sales funnel */}
      <div className="card" style={{ marginBottom: 16 }}>
        <div className="card-header"><h3>Sales funnel <span className="muted-note">— enquiries received in this period, and how far they got</span></h3></div>
        <div className="card-pad">
          {d.funnel.steps[0].count === 0 ? <Empty>No enquiries in this period.</Empty> : d.funnel.steps.map((s, i) => (
            <div key={s.key} style={{ display: 'grid', gridTemplateColumns: '150px 1fr 150px', gap: 12, alignItems: 'center', marginBottom: 10 }}>
              <div style={{ fontWeight: 600 }}>{s.label}</div>
              <div style={{ background: '#eef1f5', borderRadius: 8, height: 26, overflow: 'hidden' }}>
                <div style={{ width: `${(s.count / max) * 100}%`, minWidth: s.count ? 4 : 0, height: '100%', background: COLORS[i] }} />
              </div>
              <div><b>{s.count.toLocaleString('en-IN')}</b>{i > 0 && <span className="muted-note"> · {pct(s.pct_of_enquiries)} of enquiries<> · {pct(s.pct_of_previous)} of previous step</></span>}</div>
            </div>))}
        </div>
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <div className="card-header"><h3>Funnel by branch</h3></div>
        <div className="table-wrap"><table className="data-table">
          <thead><tr><th>Branch</th><th style={R}>Enquiries</th><th style={R}>Followed up</th><th style={R}>Test rides</th><th style={R}>Quotations</th>
            <th style={R}>Booked</th><th style={R}>Owner approved</th><th style={R}>Delivered</th><th style={R}>Enquiry → Booked</th><th style={R}>Enquiry → Delivered</th></tr></thead>
          <tbody>{d.funnel.branches.map((b) => (
            <tr key={b.branch_id ?? 'none'}><td className="cell-primary">{b.branch}</td><td style={R}>{b.enquiry}</td><td style={R}>{b.followup}</td><td style={R}>{b.testride}</td>
              <td style={R}>{b.quotation}</td><td style={R}>{b.booking}</td><td style={R}>{b.approved}</td><td style={R}>{b.delivered}</td>
              <td style={R}><b>{pct(b.booking_pct)}</b></td><td style={R}><b>{pct(b.delivered_pct)}</b></td></tr>))}
            {d.funnel.branches.length === 0 && <tr><td colSpan={10}><Empty>No enquiries in this period.</Empty></td></tr>}</tbody>
        </table></div>
      </div>

      {/* 2. workflow speed */}
      <div className="card" style={{ marginBottom: 16 }}>
        <div className="card-header"><h3>Deal workflow speed <span className="muted-note">— time each hand-over took (finished in this period)</span></h3></div>
        <div className="table-wrap"><table className="data-table">
          <thead><tr><th>Hand-over</th><th style={R}>Deals</th><th style={R}>Average</th><th style={R}>Typical (median)</th><th style={R}>Slowest</th></tr></thead>
          <tbody>{d.speed.map((s) => (
            <tr key={s.label}><td><div className="cell-primary">{s.label}</div><div className="muted-note">{s.hint}</div></td>
              <td style={R}>{s.count}</td><td style={R}><b>{dur(s.avg_hours)}</b></td><td style={R}>{dur(s.median_hours)}</td><td style={R}>{dur(s.max_hours)}</td></tr>))}</tbody>
        </table></div>
      </div>

      <div className="card">
        <div className="card-header"><h3>Waiting the longest right now <span className="muted-note">— not limited to the period</span></h3></div>
        <div className="table-wrap"><table className="data-table">
          <thead><tr><th>Customer</th><th>Waiting at</th><th>With</th><th>Since</th><th style={R}>Waiting</th><th /></tr></thead>
          <tbody>{d.waiting.map((w) => (
            <tr key={w.step + w.lead_id}><td><div className="cell-primary">{w.customer}</div><div className="muted-note">{w.enquiry_no}</div></td>
              <td>{w.step}</td><td><span className="badge badge-amber">{w.department}</span></td><td className="cell-muted">{fmtDateTime(w.since)}</td>
              <td style={R}><b style={{ color: w.waiting_hours > 48 ? '#b42318' : undefined }}>{dur(w.waiting_hours)}</b></td>
              <td><button className="btn btn-outline btn-sm" onClick={() => nav(`/leads/${w.lead_id}`)}>Open</button></td></tr>))}
            {d.waiting.length === 0 && <tr><td colSpan={6}><Empty>Nothing is waiting.</Empty></td></tr>}</tbody>
        </table></div>
      </div>
    </Layout>
  )
}
