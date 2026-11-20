// Owner KPI view: sales-funnel conversion (enquiry -> delivered) and deal-workflow speed (time per hand-over, longest waiting).
import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import Layout from '../../components/Layout'
import Tabs, { Tab } from '../../components/Tabs'
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

  const steps = d.funnel.steps
  const last = steps[steps.length - 1]
  const branchName = branch ? d.branch_options.find((b) => String(b.id) === String(branch))?.name : 'All branches'

  return (
    <Layout title={TITLE} sub={`${branchName} · ${d.label}`}>
      <style>{`
        .kp-seg{display:inline-flex;background:#fff;border:1px solid #dfe3ea;border-radius:10px;padding:3px;flex-wrap:wrap}
        .kp-seg button{border:0;background:transparent;padding:6px 14px;border-radius:8px;font-weight:600;color:#6b7686;font-size:13px;cursor:pointer}
        .kp-seg button.on{background:#2f80ed;color:#fff}
        .kp-step{background:#fff;border:1px solid #edf0f4;border-radius:12px;padding:10px 12px;position:relative}
        .kp-step .l{font-size:12px;font-weight:600;color:#7c8696;white-space:nowrap}
        .kp-step .v{font-size:24px;font-weight:800;color:#1c2740;line-height:1.15}
        .kp-step .b{height:6px;border-radius:4px;background:#eef1f5;margin:6px 0 5px;overflow:hidden}.kp-step .b i{display:block;height:100%;border-radius:4px}
        .kp-step .s{font-size:11.5px;color:#7c8696;line-height:1.35}
        .kp-tabs .card-header{display:none}
        .kp-tabs .data-table th,.kp-tabs .data-table td{white-space:nowrap;padding:11px 16px}
        .kp-tabs .table-wrap{overflow-x:auto}
        .kp-tabs .data-table th:first-child,.kp-tabs .data-table td:first-child{position:sticky;left:0;z-index:1;background:#fff;box-shadow:1px 0 0 #eef0f4}
        .kp-tabs .data-table th:first-child{background:#fafbfc}
      `}</style>
      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center', marginBottom: 14 }}>
        <div className="kp-seg">{PERIODS.map(([k, l]) => <button key={k} className={period === k ? 'on' : ''} onClick={() => setPeriod(k)}>{l}</button>)}</div>
        <button className="btn btn-outline btn-sm" onClick={() => setOn(shift(period, on, -1))}>◀</button>
        <input className="input" type="date" style={{ maxWidth: 160 }} value={on} onChange={(e) => e.target.value && setOn(e.target.value)} />
        <button className="btn btn-outline btn-sm" onClick={() => setOn(shift(period, on, 1))}>▶</button>
        <button className="btn btn-outline btn-sm" onClick={() => setOn(today())}>Today</button>
        <select className="input" style={{ maxWidth: 220 }} value={branch} onChange={(e) => setBranch(e.target.value)}>
          <option value="">All branches</option>{d.branch_options.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}</select>
      </div>

      {/* 1. sales funnel: one compact row */}
      <div className="card" style={{ marginBottom: 14 }}>
        <div className="card-header" style={{ display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: 6 }}>
          <h3>Sales funnel <span className="muted-note">— enquiries received in this period, and how far they got</span></h3>
          {steps[0].count > 0 && <span className="muted-note">Enquiry → Delivered: <b style={{ color: '#1c2740' }}>{pct(last.pct_of_enquiries)}</b></span>}
        </div>
        <div className="card-pad">
          {steps[0].count === 0 ? <Empty>No enquiries in this period.</Empty> : (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(135px,1fr))', gap: 10 }}>
              {steps.map((s, i) => (
                <div className="kp-step" key={s.key}>
                  <div className="l">{s.label}</div>
                  <div className="v">{s.count.toLocaleString('en-IN')}</div>
                  <div className="b"><i style={{ width: `${(s.count / max) * 100}%`, minWidth: s.count ? 3 : 0, background: COLORS[i] }} /></div>
                  {i > 0 ? <div className="s">{pct(s.pct_of_enquiries)} of enquiries<br />{pct(s.pct_of_previous)} of previous step</div> : <div className="s">All enquiries<br />&nbsp;</div>}
                </div>))}
            </div>)}
        </div>
      </div>

      {/* 2. the tables, one tab each */}
      <div className="kp-tabs">
        <Tabs tabs={[{ key: 'branch', label: 'Funnel by branch' }, { key: 'speed', label: 'Deal workflow speed' }, { key: 'wait', label: 'Waiting the longest', count: d.waiting.length }]}>
          <Tab k="branch">
            <div className="card">
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
          </Tab>
          <Tab k="speed">
            <div className="card">
              <div className="card-header"><h3>Deal workflow speed</h3></div>
              <div className="muted-note" style={{ padding: '12px 20px 0' }}>Time each hand-over took (finished in this period).</div>
              <div className="table-wrap"><table className="data-table">
                <thead><tr><th>Hand-over</th><th style={R}>Deals</th><th style={R}>Average</th><th style={R}>Typical (median)</th><th style={R}>Slowest</th></tr></thead>
                <tbody>{d.speed.map((s) => (
                  <tr key={s.label}><td><div className="cell-primary">{s.label}</div><div className="muted-note">{s.hint}</div></td>
                    <td style={R}>{s.count}</td><td style={R}><b>{dur(s.avg_hours)}</b></td><td style={R}>{dur(s.median_hours)}</td><td style={R}>{dur(s.max_hours)}</td></tr>))}</tbody>
              </table></div>
            </div>
          </Tab>
          <Tab k="wait">
            <div className="card">
              <div className="card-header"><h3>Waiting the longest right now</h3></div>
              <div className="muted-note" style={{ padding: '12px 20px 0' }}>Not limited to the period.</div>
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
          </Tab>
        </Tabs>
      </div>
    </Layout>
  )
}
