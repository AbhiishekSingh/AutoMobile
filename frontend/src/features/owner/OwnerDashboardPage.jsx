// Owner dashboard: period comparison, branch-wise and PBA-wise reporting, pending customers, accounting, stock.
import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import Layout from '../../components/Layout'
import { Loading, fmtDateTime } from '../../components/ui'
import api from '../../lib/api'

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

export default function OwnerDashboardPage() {
  const nav = useNavigate()
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

  if (d === null) return <Layout title="Owner dashboard"><Loading /></Layout>
  if (d === false) return <Layout title="Owner dashboard"><div className="hint">Could not load the dashboard.</div></Layout>
  const A = d.accounting
  const Th = ({ children, r }) => <th style={r ? R : undefined}>{children}</th>

  return (
    <Layout title="Owner dashboard" sub={`${d.branch_name || 'All branches'} · ${d.label}`}>
      <style>{`@media print{.sidebar,.topbar,.no-print{display:none!important}.main{margin:0!important}.content{padding:0!important}.table-wrap{overflow:visible!important}}`}</style>

      <div className="no-print" style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center', marginBottom: 14 }}>
        {PERIODS.map(([k, l]) => <button key={k} className={'btn btn-sm ' + (period === k ? 'btn-primary' : 'btn-outline')} onClick={() => setPeriod(k)}>{l}</button>)}
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

      {/* current vs previous period */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(170px,1fr))', gap: 12, marginBottom: 16 }}>
        {d.headline.map((h) => (
          <div className="card" key={h.key}><div className="card-pad">
            <div className="muted-note">{h.label}</div>
            <div style={{ fontSize: 26, fontWeight: 700 }}>{h.money ? rs(h.current) : h.current}</div>
            <div className="muted-note">Before ({d.previous_label}): {h.money ? rs(h.previous) : h.previous} <Growth g={h.growth} /></div>
          </div></div>))}
        {d.target_total ? (() => { const b = d.headline.find((x) => x.key === 'bookings').current; return (
          <div className="card"><div className="card-pad"><div className="muted-note">Target vs achievement</div>
            <div style={{ fontSize: 26, fontWeight: 700 }}>{Math.round(b * 100 / d.target_total)}%</div>
            <div className="muted-note">{b} booked of {d.target_total} target</div></div></div>) })() : null}
      </div>

      {/* pending customers */}
      <div className="card" style={{ marginBottom: 16 }}>
        <div className="card-header"><h3>Customers pending (right now)</h3></div>
        <div className="card-pad">
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(150px,1fr))', gap: 10 }}>
            {KINDS.map(([k, l]) => (
              <button key={k} className="btn btn-outline" style={{ textAlign: 'left', padding: 12, ...(open === k ? { borderColor: 'var(--blue)' } : {}) }}
                onClick={() => setOpen(open === k ? null : k)}>
                <div className="muted-note">{l}</div><div style={{ fontSize: 24, fontWeight: 700 }}>{lists[k] ? lists[k].length : '…'}</div></button>))}
          </div>
          {open && (<div className="table-wrap" style={{ marginTop: 12 }}>
            <table className="data-table"><thead><tr><th>Enquiry</th><th>Customer</th><th>Phone</th><th>Branch</th><th>PBA</th><th>Detail</th></tr></thead>
              <tbody>{(lists[open] || []).map((r) => (
                <tr key={r.lead_id} style={{ cursor: 'pointer' }} onClick={() => nav(`/handoff/${r.lead_id}`)}>
                  <td className="cell-primary">{r.enquiry_no}</td><td>{r.customer}</td><td>{r.phone}</td><td>{dash(r.branch)}</td><td>{dash(r.pba)}</td><td>{r.detail}</td></tr>))}</tbody></table>
            {lists[open] && lists[open].length === 0 && <div className="muted-note" style={{ padding: 12 }}>Nobody in this list.</div>}
          </div>)}
        </div>
      </div>

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

      {/* models */}
      {d.models.length > 0 && (<div className="card" style={{ marginBottom: 16 }}>
        <div className="card-header"><h3>Vehicle model-wise sales</h3></div>
        <div className="card-pad table-wrap"><table className="data-table"><thead><tr><th>Model</th><Th r>Bookings</Th><Th r>Invoiced</Th><Th r>Delivered</Th></tr></thead>
          <tbody>{d.models.map((m) => <tr key={m.model}><td>{m.model}</td><td style={R}>{m.bookings}</td><td style={R}>{m.invoiced}</td><td style={R}>{m.delivered}</td></tr>)}</tbody></table></div></div>)}

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
    </Layout>
  )
}
