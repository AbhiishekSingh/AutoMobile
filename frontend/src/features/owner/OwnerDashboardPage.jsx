// Owner dashboard: period comparison, branch-wise and PBA-wise reporting, pending customers, accounting, stock.
import { Fragment, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import Layout from '../../components/Layout'
import Tabs, { Tab } from '../../components/Tabs'
import { useAuth } from '../../lib/auth'
import { Loading, fmtDateTime } from '../../components/ui'
import api from '../../lib/api'
import GmSections from '../gm/GmSections'

const PERIODS = [['day', 'Daily'], ['week', 'Weekly'], ['month', 'Monthly'], ['quarter', 'Quarterly'], ['year', 'Yearly']]
const KINDS = [['PAYMENT', 'Payment pending'], ['INSURANCE', 'Insurance pending'], ['RTO', 'RTO pending'],
  ['INVOICE', 'Invoice pending'], ['DELIVERY', 'Delivery pending'], ['CANCELLED', 'Cancelled bookings']]
const KIND_NAME = { VEHICLE: 'Vehicles', HELMET: 'Helmets', PARKING_COVER: 'Parking covers' }
const rs = (n) => 'Rs ' + Math.round(n || 0).toLocaleString('en-IN')
const dash = (v) => (v === null || v === undefined ? '—' : v)
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

const Growth = ({ g }) => g === null || g === undefined ? <span className="muted-note">—</span> :
  <span style={{ fontWeight: 600, color: g >= 0 ? '#12703f' : '#b42318' }}>{g >= 0 ? '▲' : '▼'} {Math.abs(g)}%</span>
const R = { textAlign: 'right' }

export default function OwnerDashboardPage({ gm = false }) {
  const TITLE = gm ? 'GM dashboard' : 'Owner dashboard'
  const nav = useNavigate()
  const { user } = useAuth()
  const [period, setPeriod] = useState('month')
  const [on, setOn] = useState(today())
  const [branch, setBranch] = useState('')
  const [d, setD] = useState(null)
  const [lists, setLists] = useState({})
  const [open, setOpen] = useState(null)
  const [busy, setBusy] = useState(false)
  const params = useMemo(() => ({ period, on, ...(branch ? { branch_id: branch } : {}) }), [period, on, branch])

  useEffect(() => {
    setD(null)
    api.get('/owner/dashboard', { params }).then((r) => setD(r.data)).catch(() => setD(false))
  }, [params])
  useEffect(() => {
    setLists({})
    KINDS.forEach(([k]) => api.get('/owner/pending', { params: { kind: k, ...(branch ? { branch_id: branch } : {}) } })
      .then((r) => setLists((l) => ({ ...l, [k]: r.data.rows }))).catch(() => setLists((l) => ({ ...l, [k]: [] }))))
  }, [branch])

  async function exportXlsx() {
    setBusy(true)
    try {
      const r = await api.get('/owner/dashboard/export', { params, responseType: 'blob' })
      const a = document.createElement('a'); a.href = URL.createObjectURL(r.data)
      a.download = `owner-report-${period}-${on}.xlsx`; a.click()
    } finally { setBusy(false) }
  }

  if (d === null) return <Layout title={TITLE}><Loading /></Layout>
  if (d === false) return <Layout title={TITLE}><div className="hint">Could not load the dashboard.</div></Layout>
  const A = d.accounting
  const Th = ({ children, r }) => <th style={r ? R : undefined}>{children}</th>

  const hd = (k) => d.headline.find((x) => x.key === k)
  const bk = hd('bookings'), others = ['invoiced', 'delivered', 'collection'].map(hd).filter(Boolean), extra = ['leads', 'cancelled'].map(hd).filter(Boolean)
  const pctT = d.target_total ? Math.min(100, Math.round(bk.current * 100 / d.target_total)) : null
  const hour = new Date().getHours()
  const hello = `${hour < 12 ? 'Good morning' : hour < 17 ? 'Good afternoon' : 'Good evening'}, ${(user?.full_name || '').split(' ')[0] || 'there'}`
  const ago = (iso) => (iso ? Math.max(0, Math.floor((Date.now() - new Date(iso).getTime()) / 86400000)) : null)
  const oldest = (k) => { const ds = (lists[k] || []).map((r) => ago(r.since)).filter((x) => x !== null); return ds.length ? Math.max(...ds) : null }
  const TONE = { PAYMENT: '#e09a00', INSURANCE: '#e09a00', DELIVERY: '#e09a00', RTO: '#2f80ed', INVOICE: '#2f80ed', CANCELLED: '#d93025' }
  const maxB = Math.max(1, ...d.branches.map((b) => b.bookings))
  const money = [['Collected', A.collection, '#1f8a4c'], ['Outstanding', A.outstanding, '#e09a00'], ['Payables due', A.payables, '#d93025']]
  const moneyTotal = Math.max(1, money.reduce((t, m) => t + (m[1] || 0), 0))

  return (
    <Layout title={hello} sub={`${TITLE} · ${d.branch_name || 'All branches'} · ${d.label}`}>
      <style>{`
        @media print{.sidebar,.topbar,.no-print{display:none!important}.main{margin:0!important}.content{padding:0!important}.table-wrap{overflow:visible!important}.tabs-body>div{display:block!important}.modern [role=tab]{display:none!important}}
        .od-seg{display:inline-flex;background:#fff;border:1px solid #dfe3ea;border-radius:10px;padding:3px;flex-wrap:wrap}
        .od-seg button{border:0;background:transparent;padding:6px 14px;border-radius:8px;font-weight:600;color:#6b7686;font-size:13px;cursor:pointer}
        .od-seg button.on{background:#2f80ed;color:#fff}
        .od-kpi{background:#fff;border:1px solid #edf0f4;border-radius:16px;padding:16px 18px}
        .od-kpi .l{color:#7c8696;font-size:12.5px;font-weight:600}.od-kpi .v{font-size:28px;font-weight:800;margin:4px 0 2px;color:#1c2740}
        .od-hero{background:linear-gradient(135deg,#1d4fa8,#2f80ed);color:#fff;border-radius:16px;padding:18px 22px}
        .od-bar{height:8px;border-radius:5px;background:#eef0f4;overflow:hidden}.od-bar i{display:block;height:100%;border-radius:5px;background:#2f80ed}
        .od-tile{background:#fff;border:1px solid #edf0f4;border-radius:12px;padding:12px 14px;text-align:left;cursor:pointer;font:inherit;color:inherit}
        .od-tile.on{box-shadow:0 0 0 2px #2f80ed inset}
        .od-grid{display:grid;gap:14px}
        .od-tabs .card-header{display:none}
        .od-tabs .card-pad{padding:6px 22px 18px}
        .od-tabs .table-wrap{overflow-x:auto}
        .od-tabs .data-table th,.od-tabs .data-table td{white-space:nowrap;padding:12px 16px}
        .od-tabs .data-table th:first-child,.od-tabs .data-table td:first-child{position:sticky;left:0;z-index:1;background:#fff;box-shadow:1px 0 0 #eef0f4}
        .od-tabs .data-table th:first-child{background:#fafbfc}
        .od-tabs .data-table tbody tr:hover td{background:#f7faff}
        @media(max-width:1100px){.od-hero-row{grid-template-columns:1fr 1fr!important}.od-two{grid-template-columns:1fr!important}}
        @media(max-width:600px){.od-hero-row{grid-template-columns:1fr!important}}
      `}</style>

      <div className="no-print" style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center', marginBottom: 16 }}>
        <div className="od-seg">{PERIODS.map(([k, l]) => <button key={k} className={period === k ? 'on' : ''} onClick={() => setPeriod(k)}>{l}</button>)}</div>
        <button className="btn btn-outline btn-sm" onClick={() => setOn(shift(period, on, -1))}>◀</button>
        <input className="input" type="date" style={{ maxWidth: 160 }} value={on} onChange={(e) => e.target.value && setOn(e.target.value)} />
        <button className="btn btn-outline btn-sm" onClick={() => setOn(shift(period, on, 1))}>▶</button>
        <button className="btn btn-outline btn-sm" onClick={() => setOn(today())}>Today</button>
        <select className="input" style={{ maxWidth: 220 }} value={branch} onChange={(e) => setBranch(e.target.value)}>
          <option value="">All branches</option>{d.branch_options.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}</select>
        <span style={{ flex: 1 }} />
        <button className="btn btn-outline btn-sm" disabled={busy} onClick={exportXlsx}>Export Excel</button>
        <button className="btn btn-outline btn-sm" onClick={() => window.print()}>Export PDF</button>
      </div>

      {/* headline: bookings against target, then the other numbers (current vs previous period) */}
      <div className="od-grid od-hero-row" style={{ gridTemplateColumns: '1.25fr 1fr 1fr 1fr', marginBottom: 14 }}>
        <div className="od-hero">
          <div style={{ opacity: .85, fontWeight: 600, fontSize: 13 }}>{bk.label} · {d.label}</div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 20, marginTop: 8 }}>
            <div style={{ fontSize: 46, fontWeight: 800, lineHeight: 1 }}>{bk.current}</div>
            {pctT !== null && (
              <svg width="84" height="84" style={{ flexShrink: 0 }}>
                <circle cx="42" cy="42" r="34" stroke="rgba(255,255,255,.25)" strokeWidth="9" fill="none" />
                <circle cx="42" cy="42" r="34" stroke="#fff" strokeWidth="9" fill="none" strokeLinecap="round" strokeDasharray={`${2 * Math.PI * 34 * pctT / 100} 400`} transform="rotate(-90 42 42)" />
                <text x="42" y="47" textAnchor="middle" fill="#fff" fontWeight="800" fontSize="16">{pctT}%</text>
              </svg>)}
          </div>
          <div style={{ opacity: .9, marginTop: 8, fontSize: 13 }}>
            {d.target_total ? `of ${d.target_total} target · ` : 'No target set · '}
            {bk.growth === null || bk.growth === undefined ? 'no comparison' : `${bk.growth >= 0 ? '▲' : '▼'} ${Math.abs(bk.growth)}% vs ${d.previous_label}`}
          </div>
        </div>
        {others.map((h) => (
          <div className="od-kpi" key={h.key}>
            <div className="l">{h.label}</div>
            <div className="v">{h.money ? rs(h.current) : h.current}</div>
            <div><Growth g={h.growth} /> <span className="muted-note">vs {d.previous_label}: {h.money ? rs(h.previous) : h.previous}</span></div>
          </div>))}
      </div>
      <div className="muted-note" style={{ display: 'flex', gap: 22, flexWrap: 'wrap', marginBottom: 14 }}>
        {extra.map((h) => <span key={h.key}>{h.label}: <b style={{ color: '#1c2740' }}>{h.current}</b> <Growth g={h.growth} /></span>)}
      </div>

      {/* pending customers */}
      <div className="card" style={{ marginBottom: 14 }}>
        <div className="card-header" style={{ display: 'flex', justifyContent: 'space-between' }}><h3>⚠ Needs your attention <span className="muted-note">(right now)</span></h3><span className="muted-note">click a tile to see the customers</span></div>
        <div className="card-pad">
          <div className="od-grid" style={{ gridTemplateColumns: 'repeat(auto-fit,minmax(150px,1fr))', gap: 10 }}>
            {KINDS.map(([k, l]) => { const o = oldest(k); return (
              <button key={k} className={'od-tile' + (open === k ? ' on' : '')} style={{ borderLeft: `4px solid ${TONE[k]}` }} onClick={() => setOpen(open === k ? null : k)}>
                <div className="muted-note" style={{ fontWeight: 600 }}>{l}</div>
                <div style={{ fontSize: 24, fontWeight: 800, margin: '2px 0' }}>{lists[k] ? lists[k].length : '…'}</div>
                <div className="muted-note" style={{ fontSize: 11.5 }}>{lists[k] && lists[k].length ? (o === null ? ' ' : o === 0 ? 'oldest: today' : `oldest: ${o} day${o === 1 ? '' : 's'}`) : lists[k] ? 'all clear' : ' '}</div></button>) })}
          </div>
          {open && (<div className="table-wrap" style={{ marginTop: 12 }}>
            <table className="data-table"><thead><tr><th>Enquiry</th><th>Customer</th><th>Phone</th><th>Branch</th><th>PBA</th><th>Detail</th><th>Waiting</th></tr></thead>
              <tbody>{(lists[open] || []).map((r) => (
                <tr key={r.lead_id} style={{ cursor: 'pointer' }} onClick={() => nav(`/handoff/${r.lead_id}`)}>
                  <td className="cell-primary">{r.enquiry_no}</td><td>{r.customer}</td><td>{r.phone}</td><td>{dash(r.branch)}</td><td>{dash(r.pba)}</td><td>{r.detail}</td>
                  <td>{ago(r.since) === null ? '—' : `${ago(r.since)} d`}</td></tr>))}</tbody></table>
            {lists[open] && lists[open].length === 0 && <div className="muted-note" style={{ padding: 12 }}>Nobody in this list.</div>}
          </div>)}
        </div>
      </div>

      {/* branch leaderboard + money */}
      <div className="od-grid od-two" style={{ gridTemplateColumns: '1.5fr 1fr', marginBottom: 14, alignItems: 'start' }}>
        <div className="card"><div className="card-pad">
          <h3 style={{ margin: '0 0 12px' }}>Branch leaderboard <span className="muted-note" style={{ fontWeight: 500 }}>bookings{d.target_total ? ' vs target' : ''}{!branch && ' · click a branch for its full view'}</span></h3>
          {d.branches.length === 0 && <div className="muted-note">No branches.</div>}
          {d.branches.map((b) => (
            <div key={b.branch_id} style={{ display: 'grid', gridTemplateColumns: '110px 1fr 110px', gap: 12, alignItems: 'center', marginBottom: 11, cursor: branch ? 'default' : 'pointer' }}
              onClick={() => !branch && setBranch(String(b.branch_id))}>
              <b style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={b.name}>{b.name.replace(/^S\.?K\.? ?KTM /i, '')}</b>
              <div className="od-bar"><i style={{ width: `${Math.min(100, b.achievement_pct !== null ? b.achievement_pct : Math.round(b.bookings * 100 / maxB))}%` }} /></div>
              <span className="muted-note"><b style={{ color: '#1c2740' }}>{b.bookings}</b>{b.achievement_pct !== null && ` · ${b.achievement_pct}%`}</span>
            </div>))}
          {branch && <button className="btn btn-outline btn-sm no-print" onClick={() => setBranch('')}>← All branches</button>}
        </div></div>
        <div className="card"><div className="card-pad">
          <h3 style={{ margin: '0 0 12px' }}>Money</h3>
          <div style={{ display: 'flex', height: 14, borderRadius: 7, overflow: 'hidden', marginBottom: 12, background: '#eef0f4' }}>
            {money.map(([l, v, c]) => <i key={l} title={`${l}: ${rs(v)}`} style={{ width: `${(v || 0) * 100 / moneyTotal}%`, background: c }} />)}</div>
          <div style={{ display: 'grid', gridTemplateColumns: 'auto 1fr', gap: '8px 14px', alignItems: 'center' }}>
            {money.map(([l, v, c]) => (<Fragment key={l}><span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}><i style={{ width: 10, height: 10, borderRadius: 5, background: c, display: 'inline-block' }} />{l}</span><b>{rs(v)}{l === 'Payables due' && A.overdue_count ? <span className="muted-note"> · {A.overdue_count} overdue</span> : null}</b></Fragment>))}
          </div>
          <hr style={{ border: 0, borderTop: '1px solid #eef0f4', margin: '14px 0' }} />
          <div className="muted-note">Bank reconciliation</div><b>{A.reconciled} matched · {A.unreconciled} pending ({rs(A.unreconciled_amount)})</b>
          <div className="muted-note" style={{ marginTop: 10 }}>Refunds</div><b>{rs(A.refund_pending)} pending · {rs(A.refund_processed)} processed</b>
        </div></div>
      </div>

      {/* the full reports, one tab each */}
      <div className="od-tabs"><Tabs tabs={[{ key: 'branch', label: 'Branch-wise' }, { key: 'pba', label: 'PBA-wise', count: d.pba.length }, { key: 'acct', label: 'Accounting' }, { key: 'models', label: 'Models' }, { key: 'stock', label: 'Stock' }]}>
        <Tab k="branch">
      {/* branches */}
      <div className="card" style={{ marginBottom: 16 }}>
        <div className="card-header"><h3>Branch-wise {!branch && <span className="muted-note">(click a branch for its full view)</span>}</h3></div>
        <div className="card-pad table-wrap">
          <table className="data-table"><thead><tr><th>Branch</th><Th r>Leads</Th><Th r>Bookings</Th><Th r>vs before</Th><Th r>Invoiced</Th><Th r>Delivered</Th>
            <Th r>Target</Th><Th r>Ach.</Th><Th r>Vehicles in stock</Th><Th r>Booked stock</Th><Th r>Insurance pending</Th><Th r>RTO pending</Th>
            <Th r>Delivery pending</Th><Th r>Collected</Th><Th r>Outstanding</Th><Th r>Cancelled</Th></tr></thead>
            <tbody>{d.branches.map((b) => (
              <tr key={b.branch_id} style={{ cursor: branch ? 'default' : 'pointer' }} onClick={() => !branch && setBranch(String(b.branch_id))}>
                <td className="cell-primary">{b.name}<div className="muted-note">{b.code}</div></td>
                <td style={R}>{b.leads}</td><td style={R}>{b.bookings}</td><td style={R}><Growth g={b.bookings_growth} /></td>
                <td style={R}>{b.invoiced}</td><td style={R}>{b.delivered}</td><td style={R}>{dash(b.target)}</td>
                <td style={R}>{b.achievement_pct === null ? '—' : b.achievement_pct + '%'}</td>
                <td style={R}>{b.stock_vehicles}</td><td style={R}>{b.booked_stock}</td><td style={R}>{b.ins_pending}</td><td style={R}>{b.rto_pending}</td>
                <td style={R}>{b.delivery_pending}</td><td style={R}>{rs(b.booking_amount)}</td><td style={R}>{rs(b.outstanding)}</td><td style={R}>{b.cancelled}</td></tr>))}
            </tbody></table>
          {branch && <button className="btn btn-outline btn-sm no-print" style={{ marginTop: 10 }} onClick={() => setBranch('')}>← All branches</button>}
        </div>
      </div>

        </Tab>
        <Tab k="pba">
      {/* PBAs */}
      <div className="card" style={{ marginBottom: 16 }}>
        <div className="card-header"><h3>PBA-wise</h3></div>
        <div className="card-pad table-wrap">
          <table className="data-table"><thead><tr><th>PBA</th><Th r>Leads</Th><Th r>Bookings</Th><Th r>vs before</Th><Th r>Target</Th><Th r>Ach.</Th>
            <Th r>Invoiced</Th><Th r>Delivered</Th><Th r>Collected</Th><Th r>Outstanding</Th><th>Payments (paid / part / unpaid)</th>
            <th>Insurance (done / pending)</th><th>RTO (done / pending)</th><Th r>Test rides</Th><Th r>Cancelled</Th><Th r>Conversion</Th></tr></thead>
            <tbody>{d.pba.map((p) => (
              <tr key={p.user_id ?? 'x'}><td className="cell-primary">{p.name}<div className="muted-note">{p.branch}</div></td>
                <td style={R}>{p.leads}</td><td style={R}>{p.bookings}</td><td style={R}><Growth g={p.bookings_growth} /></td>
                <td style={R}>{dash(p.target)}</td><td style={R}>{p.achievement_pct === null ? '—' : p.achievement_pct + '%'}</td>
                <td style={R}>{p.invoiced}</td><td style={R}>{p.delivered}</td><td style={R}>{rs(p.booking_amount)}</td><td style={R}>{rs(p.outstanding)}</td>
                <td>{p.pay_paid} / {p.pay_partial} / {p.pay_pending}</td><td>{p.ins_done} / {p.ins_pending}</td><td>{p.rto_done} / {p.rto_pending}</td>
                <td style={R}>{p.test_rides_done}/{p.test_rides}</td><td style={R}>{p.cancelled}</td><td style={R}>{p.conversion_pct === null ? '—' : p.conversion_pct + '%'}</td></tr>))}
            </tbody></table>
          {d.pba.length === 0 && <div className="muted-note">No PBA activity.</div>}
        </div>
      </div>

        </Tab>
        <Tab k="acct">
      {/* accounting */}
      <div className="card" style={{ marginBottom: 16 }}>
        <div className="card-header"><h3>Accounting status</h3></div>
        <div className="card-pad">
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(200px,1fr))', gap: 12 }}>
            <div><div className="muted-note">Collected this period</div><b style={{ fontSize: 20 }}>{rs(A.collection)}</b><div className="muted-note">Before: {rs(A.collection_prev)} <Growth g={A.collection_growth} /></div></div>
            <div><div className="muted-note">Value of booked vehicles</div><b style={{ fontSize: 20 }}>{rs(A.booked_value)}</b></div>
            <div><div className="muted-note">Outstanding from customers</div><b style={{ fontSize: 20 }}>{rs(A.outstanding)}</b></div>
            <div><div className="muted-note">Booking payment status</div><b>{A.paid} paid · {A.partial} part-paid · {A.pending} unpaid</b></div>
            <div><div className="muted-note">Total payables (pending)</div><b style={{ fontSize: 20 }}>{rs(A.payables)}</b><div className="muted-note">{A.payables_count} bills · {A.overdue_count} overdue</div></div>
            <div><div className="muted-note">Bank reconciliation</div><b>{A.reconciled} reconciled · {A.unreconciled} pending</b><div className="muted-note">{rs(A.unreconciled_amount)} not yet matched</div></div>
            <div><div className="muted-note">Refunds</div><b>{rs(A.refund_pending)} pending · {rs(A.refund_processed)} processed</b></div>
            <div><div className="muted-note">Cancelled this period</div><b>{A.cancelled} bookings · {rs(A.cancelled_amount)} received on them</b></div>
          </div>
          {d.notes.map((n) => <div key={n} className="muted-note" style={{ marginTop: 10 }}>{n}</div>)}
        </div>
      </div>

        </Tab>
        <Tab k="models">
      <div className="card" style={{ marginBottom: 16 }}>
        <div className="card-header"><h3>Vehicle model-wise sales</h3></div>
        <div className="card-pad table-wrap">
          {d.models.length === 0 ? <div className="muted-note">No bookings in this period.</div> : (
            <table className="data-table"><thead><tr><th>Model</th><Th r>Bookings</Th><Th r>Invoiced</Th><Th r>Delivered</Th></tr></thead>
              <tbody>{d.models.map((m) => <tr key={m.model}><td>{m.model}</td><td style={R}>{m.bookings}</td><td style={R}>{m.invoiced}</td><td style={R}>{m.delivered}</td></tr>)}</tbody></table>)}
        </div>
      </div>
        </Tab>
        <Tab k="stock">
      {/* stock */}
      <div className="card">
        <div className="card-header"><h3>Stock report</h3></div>
        <div className="card-pad">
          <div style={{ display: 'flex', gap: 24, flexWrap: 'wrap', marginBottom: 10 }}>
            {Object.entries(d.stock.kinds).map(([k, v]) => (<div key={k}><div className="muted-note">{KIND_NAME[k]}</div>
              <b style={{ fontSize: 20 }}>{v.closing}</b> <span className="muted-note">in stock · {v.received} received · {v.issued} issued this period</span></div>))}
          </div>
          {d.stock.out_of_stock.length > 0 && <div className="hint" style={{ marginBottom: 10, background: 'var(--red-light)', color: '#7a2318' }}>Out of stock: {d.stock.out_of_stock.join(', ')}</div>}
          <div className="table-wrap">
            {d.stock.items.length === 0 ? <div className="muted-note">No stock items yet.</div> : (
              <table className="data-table"><thead><tr><th>Type</th><th>Item</th><Th r>In stock</Th><Th r>Warehouse</Th><Th r>Received</Th><Th r>Allocated</Th><Th r>Transferred</Th><Th r>Issued</Th><Th r>Count difference</Th></tr></thead>
                <tbody>{d.stock.items.map((i) => (<tr key={i.id}><td>{KIND_NAME[i.kind]}</td><td>{i.label}</td>
                  <td style={{ ...R, fontWeight: 700, color: i.closing <= 0 ? '#b42318' : undefined }}>{i.closing}</td><td style={R}>{i.warehouse}</td>
                  <td style={R}>{i.received}</td><td style={R}>{i.allocated}</td><td style={R}>{i.transferred}</td><td style={R}>{i.issued}</td><td style={R}>{i.count_diff}</td></tr>))}</tbody></table>)}
          </div>
        </div>
      </div>
        </Tab>
      </Tabs></div>
      {gm && <GmSections start={iso(new Date(d.start))} end={iso(new Date(d.end))} branch={branch} />}
    </Layout>
  )
}
