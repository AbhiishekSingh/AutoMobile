// Accounts: summary, payments + bank reconciliation, payables, refunds/cancellations, customer price breakup.
// Owner / GM / Admin. All customer money is read live from the PBA payment records.
import { useCallback, useEffect, useState } from 'react'
import api from '../../lib/api'
import Layout from '../../components/Layout'
import { Empty, Loading, fmtDate, fmtDateTime } from '../../components/ui'

const rs = (n) => (n == null ? '—' : `₹ ${Math.round(Number(n)).toLocaleString('en-IN')}`)
const err = (e) => e.response?.data?.detail || 'Something went wrong.'
const TABS = [['summary', 'Summary'], ['payments', 'Payments & reconciliation'], ['bills', 'Payables'], ['refunds', 'Cancellations & refunds'], ['customers', 'Customer-wise']]
const PS = { PAID: 'Paid', PARTIALLY_PAID: 'Part-paid', PENDING: 'Pending' }
const Tile = ({ label, value, sub }) => <div className="card" style={{ padding: 12 }}><div className="muted-note">{label}</div><div style={{ fontSize: 22, fontWeight: 700 }}>{value}</div>{sub && <div className="muted-note">{sub}</div>}</div>
const Grid = ({ children }) => <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(190px,1fr))', gap: 10, marginBottom: 16 }}>{children}</div>
const Msg = ({ m }) => m ? <div className="hint" style={{ marginBottom: 10, ...(m.ok ? {} : { background: 'var(--red-light)', color: '#7a2318' }) }}>{m.text}</div> : null

export default function AccountsPage() {
  const [tab, setTab] = useState('summary')
  const [branch, setBranch] = useState('')
  const [branches, setBranches] = useState([])
  useEffect(() => { api.get('/accounts/summary').then((r) => setBranches(r.data.branches)).catch(() => {}) }, [])
  const bp = branch ? { branch_id: branch } : {}
  return (
    <Layout title="Accounts" sub="Collections, bank reconciliation, payables and refunds">
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 14, alignItems: 'center' }}>
        {TABS.map(([k, l]) => <button key={k} className={`btn btn-sm ${tab === k ? 'btn-primary' : 'btn-outline'}`} onClick={() => setTab(k)}>{l}</button>)}
        <select className="input" style={{ maxWidth: 180, marginLeft: 'auto' }} value={branch} onChange={(e) => setBranch(e.target.value)}>
          <option value="">All branches</option>{branches.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}</select>
      </div>
      {tab === 'summary' && <Summary bp={bp} />}
      {tab === 'payments' && <Payments bp={bp} />}
      {tab === 'bills' && <Bills bp={bp} branches={branches} />}
      {tab === 'refunds' && <Refunds bp={bp} />}
      {tab === 'customers' && <Customers bp={bp} />}
    </Layout>
  )
}

function Summary({ bp }) {
  const [s, setS] = useState(null)
  useEffect(() => { api.get('/accounts/summary', { params: bp }).then((r) => setS(r.data)).catch(() => setS(false)) }, [bp.branch_id])
  if (s === null) return <Loading />
  if (!s) return <div className="hint">Could not load.</div>
  return (<>
    <Grid>
      <Tile label="Collection today" value={rs(s.collection_today)} /><Tile label="Collection this month" value={rs(s.collection_month)} />
      <Tile label="Value of booked vehicles" value={rs(s.booked_value)} /><Tile label="Payments received" value={rs(s.received)} />
      <Tile label="Receivable (outstanding)" value={rs(s.receivable)} sub={`${s.status_counts.PAID} paid · ${s.status_counts.PARTIALLY_PAID} part · ${s.status_counts.PENDING} unpaid`} />
      <Tile label="Payables pending" value={rs(s.payables)} sub={`${s.payables_count} bills · ${s.overdue_count} overdue (${rs(s.overdue)})`} />
      <Tile label="Payables paid" value={rs(s.payables_paid)} />
      <Tile label="Bank reconciled" value={rs(s.reconciled_amount)} sub={`${s.reconciled} payments`} />
      <Tile label="Not yet reconciled" value={rs(s.unreconciled_amount)} sub={`${s.unreconciled} payments`} />
      <Tile label="Refunds pending" value={rs(s.refund_pending)} sub={`${s.refund_pending_count} customers${s.cancelled_no_refund_set ? ` · ${s.cancelled_no_refund_set} cancelled with no refund decision` : ''}`} />
      <Tile label="Refunds processed" value={rs(s.refund_processed)} sub={`${s.refund_processed_count} customers`} />
    </Grid></>)
}

function Payments({ bp }) {
  const [rows, setRows] = useState(null)
  const [f, setF] = useState({ recon: 'PENDING', mode: '', q: '', date_from: '', date_to: '' })
  const [sel, setSel] = useState({})
  const [ref, setRef] = useState('')
  const [m, setM] = useState(null)
  const load = useCallback(() => api.get('/accounts/payments', { params: { ...bp, ...Object.fromEntries(Object.entries(f).filter(([, v]) => v)) } }).then((r) => { setRows(r.data); setSel({}) }).catch(() => setRows([])), [bp.branch_id, f])
  useEffect(() => { load() }, [load])
  const ids = Object.keys(sel).filter((k) => sel[k]).map(Number)
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value })
  async function recon() { try { const r = await api.post('/accounts/payments/reconcile', { payment_ids: ids, bank_ref: ref }); setM({ ok: true, text: `${r.data.reconciled} payment(s) reconciled.` }); setRef(''); load() } catch (e) { setM({ ok: false, text: err(e) }) } }
  async function undo(id) { if (!window.confirm('Mark this payment as not reconciled?')) return; try { await api.delete(`/accounts/payments/${id}/reconcile`); load() } catch (e) { setM({ ok: false, text: err(e) }) } }
  const total = (rows || []).filter((r) => sel[r.payment_id]).reduce((a, r) => a + r.amount, 0)
  return (<div className="card">
    <div className="card-header" style={{ flexWrap: 'wrap', gap: 8 }}>
      <select className="input" style={{ maxWidth: 150 }} value={f.recon} onChange={set('recon')}><option value="">All</option><option value="PENDING">Not reconciled</option><option value="RECONCILED">Reconciled</option></select>
      <select className="input" style={{ maxWidth: 150 }} value={f.mode} onChange={set('mode')}><option value="">All modes</option>{['CASH', 'CHEQUE', 'UPI', 'BANK_TRANSFER', 'CARD', 'FINANCE'].map((x) => <option key={x}>{x}</option>)}</select>
      <input className="input" type="date" style={{ maxWidth: 140 }} value={f.date_from} onChange={set('date_from')} /><input className="input" type="date" style={{ maxWidth: 140 }} value={f.date_to} onChange={set('date_to')} />
      <input className="input" style={{ maxWidth: 190 }} placeholder="Search customer / receipt / UTR" value={f.q} onChange={set('q')} />
    </div>
    <div className="card-pad"><Msg m={m} />
      {ids.length > 0 && <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap', marginBottom: 10 }}>
        <b>{ids.length} selected · {rs(total)}</b><input className="input" style={{ maxWidth: 240 }} placeholder="Bank statement ref (optional)" value={ref} onChange={(e) => setRef(e.target.value)} />
        <button className="btn btn-primary btn-sm" onClick={recon}>Mark reconciled</button></div>}
      <div className="table-wrap"><table className="data-table"><thead><tr><th></th><th>Date</th><th>Receipt</th><th>Customer</th><th>Branch</th><th>Mode</th><th>Reference</th><th style={{ textAlign: 'right' }}>Amount</th><th>Bank</th></tr></thead>
        <tbody>{(rows || []).map((r) => <tr key={r.payment_id}>
          <td>{!r.reconciled && <input type="checkbox" checked={!!sel[r.payment_id]} onChange={(e) => setSel({ ...sel, [r.payment_id]: e.target.checked })} />}</td>
          <td>{fmtDate(r.payment_date)}</td><td>{r.receipt_no}</td><td>{r.customer}<div className="muted-note">{r.booking_no}</div></td><td>{r.branch || '—'}</td><td>{r.mode_label}</td><td>{r.reference || '—'}</td>
          <td style={{ textAlign: 'right' }}>{rs(r.amount)}</td>
          <td>{r.reconciled ? <span><span className="badge badge-green">Reconciled</span> <a href="#" onClick={(e) => { e.preventDefault(); undo(r.payment_id) }} className="muted-note" title={`${r.reconciled_by || ''} ${r.bank_ref || ''}`}>undo</a></span> : <span className="badge badge-amber">Pending</span>}</td></tr>)}</tbody></table>
        {rows === null && <Loading />}{rows && !rows.length && <Empty>No payments.</Empty>}</div></div></div>)
}

function Bills({ bp, branches }) {
  const [d, setD] = useState(null)
  const [st, setSt] = useState('PENDING')
  const [form, setForm] = useState(null)
  const [pay, setPay] = useState(null)
  const [m, setM] = useState(null)
  const load = useCallback(() => api.get('/accounts/bills', { params: { ...bp, ...(st ? { status: st } : {}) } }).then((r) => setD(r.data)).catch(() => setD(false)), [bp.branch_id, st])
  useEffect(() => { load() }, [load])
  async function save() {
    const body = { ...form, amount: form.amount === '' ? null : Number(form.amount), branch_id: form.branch_id ? Number(form.branch_id) : null }
    ;['bill_date', 'due_date'].forEach((k) => { if (!body[k]) body[k] = null })
    try { form.id ? await api.patch(`/accounts/bills/${form.id}`, body) : await api.post('/accounts/bills', body); setForm(null); setM({ ok: true, text: 'Saved.' }); load() } catch (e) { setM({ ok: false, text: err(e) }) }
  }
  async function markPaid() { try { await api.post(`/accounts/bills/${pay.id}/pay`, { paid_date: pay.paid_date || null, paid_mode: pay.paid_mode, paid_ref: pay.paid_ref }); setPay(null); setM({ ok: true, text: 'Marked paid.' }); load() } catch (e) { setM({ ok: false, text: err(e) }) } }
  if (d === null) return <Loading />
  if (!d) return <div className="hint">Could not load.</div>
  const S = (k) => (e) => setForm({ ...form, [k]: e.target.value })
  return (<>
    <Grid><Tile label="Payables pending" value={rs(d.payables)} sub={`${d.payables_count} bills`} /><Tile label="Overdue" value={rs(d.overdue)} sub={`${d.overdue_count} bills`} /><Tile label="Paid so far" value={rs(d.payables_paid)} /></Grid>
    <Msg m={m} />
    <div className="card"><div className="card-header" style={{ gap: 8 }}>
      <select className="input" style={{ maxWidth: 150 }} value={st} onChange={(e) => setSt(e.target.value)}><option value="PENDING">Pending</option><option value="PAID">Paid</option><option value="">All</option></select>
      <button className="btn btn-primary btn-sm" style={{ marginLeft: 'auto' }} onClick={() => setForm({ vendor: '', category: 'BIKE_PURCHASE', branch_id: '', bill_no: '', bill_date: new Date().toISOString().slice(0, 10), due_date: '', amount: '', note: '' })}>+ Add bill</button></div>
      <div className="card-pad">
        {form && <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(170px,1fr))', gap: 10, marginBottom: 12 }}>
          <div className="field"><label>Vendor *</label><input className="input" value={form.vendor || ''} onChange={S('vendor')} /></div>
          <div className="field"><label>Category</label><select className="input" value={form.category || 'OTHER'} onChange={S('category')}>{d.categories.map((c) => <option key={c.value} value={c.value}>{c.label}</option>)}</select></div>
          <div className="field"><label>Branch</label><select className="input" value={form.branch_id || ''} onChange={S('branch_id')}><option value="">All / head office</option>{branches.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}</select></div>
          <div className="field"><label>Bill no.</label><input className="input" value={form.bill_no || ''} onChange={S('bill_no')} /></div>
          <div className="field"><label>Bill date *</label><input className="input" type="date" value={form.bill_date || ''} onChange={S('bill_date')} /></div>
          <div className="field"><label>Due date</label><input className="input" type="date" value={form.due_date || ''} onChange={S('due_date')} /></div>
          <div className="field"><label>Amount (₹) *</label><input className="input" type="number" min="0" value={form.amount ?? ''} onChange={S('amount')} /></div>
          <div className="field"><label>Note</label><input className="input" value={form.note || ''} onChange={S('note')} /></div>
          <div style={{ display: 'flex', gap: 8, alignItems: 'end' }}><button className="btn btn-primary btn-sm" onClick={save}>Save</button><button className="btn btn-outline btn-sm" onClick={() => setForm(null)}>Cancel</button></div></div>}
        {pay && <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'end', marginBottom: 12 }}>
          <b>Pay bill #{pay.id}</b>
          <select className="input" style={{ maxWidth: 160 }} value={pay.paid_mode || ''} onChange={(e) => setPay({ ...pay, paid_mode: e.target.value })}><option value="">How paid?</option>{d.modes.map((x) => <option key={x}>{x}</option>)}</select>
          <input className="input" type="date" style={{ maxWidth: 150 }} value={pay.paid_date || ''} onChange={(e) => setPay({ ...pay, paid_date: e.target.value })} />
          <input className="input" style={{ maxWidth: 200 }} placeholder="UTR / cheque no." value={pay.paid_ref || ''} onChange={(e) => setPay({ ...pay, paid_ref: e.target.value })} />
          <button className="btn btn-primary btn-sm" disabled={!pay.paid_mode} onClick={markPaid}>Mark paid</button><button className="btn btn-outline btn-sm" onClick={() => setPay(null)}>Cancel</button></div>}
        <div className="table-wrap"><table className="data-table"><thead><tr><th>Vendor</th><th>Category</th><th>Branch</th><th>Bill</th><th>Due</th><th style={{ textAlign: 'right' }}>Amount</th><th>Status</th><th></th></tr></thead>
          <tbody>{d.bills.map((b) => <tr key={b.id}><td>{b.vendor}</td><td>{b.category_label}</td><td>{b.branch}</td><td>{b.bill_no || '—'}<div className="muted-note">{fmtDate(b.bill_date)}</div></td>
            <td>{b.due_date ? fmtDate(b.due_date) : '—'}{b.overdue && <span className="badge badge-amber" style={{ marginLeft: 4 }}>Overdue</span>}</td><td style={{ textAlign: 'right' }}>{rs(b.amount)}</td>
            <td>{b.status === 'PAID' ? <span className="badge badge-green">Paid {fmtDate(b.paid_date)}</span> : 'Pending'}</td>
            <td>{b.status === 'PENDING' && <><button className="btn btn-outline btn-sm" onClick={() => setForm({ ...b, amount: b.amount, branch_id: b.branch_id || '' })}>Edit</button> <button className="btn btn-primary btn-sm" onClick={() => setPay({ id: b.id })}>Pay</button></>}</td></tr>)}</tbody></table>
          {!d.bills.length && <Empty>No bills.</Empty>}</div></div></div></>)
}

function Refunds({ bp }) {
  const [d, setD] = useState(null)
  const [f, setF] = useState(null)
  const [m, setM] = useState(null)
  const load = useCallback(() => api.get('/accounts/cancellations', { params: bp }).then((r) => setD(r.data)).catch(() => setD(false)), [bp.branch_id])
  useEffect(() => { load() }, [load])
  async function save(status) {
    try { await api.put(`/accounts/cancellations/${f.lead_id}/refund`, { amount: Number(f.amount), status, mode: f.mode || null, reference: f.reference, note: f.note, processed_date: f.processed_date || null }); setF(null); setM({ ok: true, text: status === 'PROCESSED' ? 'Refund marked processed.' : 'Refund saved as pending.' }); load() } catch (e) { setM({ ok: false, text: err(e) }) }
  }
  if (d === null) return <Loading />
  if (!d) return <div className="hint">Could not load.</div>
  const LBL = { NOT_SET: 'Not decided', PENDING: 'Pending', PROCESSED: 'Processed', NOTHING_TO_REFUND: 'Nothing to refund' }
  return (<>
    <Grid><Tile label="Refunds pending" value={rs(d.refund_pending)} sub={`${d.refund_pending_count} customers`} /><Tile label="Refunds processed" value={rs(d.refund_processed)} sub={`${d.refund_processed_count} customers`} /><Tile label="Cancelled, no refund decision" value={d.cancelled_no_refund_set} /></Grid>
    <Msg m={m} />
    {f && <div className="card" style={{ padding: 12, marginBottom: 12 }}><b>Refund — {f.customer} (received {rs(f.received)})</b>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', margin: '8px 0', alignItems: 'end' }}>
        <input className="input" type="number" style={{ maxWidth: 140 }} placeholder="Refund ₹" value={f.amount} onChange={(e) => setF({ ...f, amount: e.target.value })} />
        <select className="input" style={{ maxWidth: 160 }} value={f.mode || ''} onChange={(e) => setF({ ...f, mode: e.target.value })}><option value="">Mode (when paid)</option>{d.modes.map((x) => <option key={x}>{x}</option>)}</select>
        <input className="input" type="date" style={{ maxWidth: 150 }} value={f.processed_date || ''} onChange={(e) => setF({ ...f, processed_date: e.target.value })} />
        <input className="input" style={{ maxWidth: 200 }} placeholder="UTR / reference" value={f.reference || ''} onChange={(e) => setF({ ...f, reference: e.target.value })} />
        <input className="input" style={{ maxWidth: 220 }} placeholder="Note" value={f.note || ''} onChange={(e) => setF({ ...f, note: e.target.value })} /></div>
      <button className="btn btn-outline btn-sm" onClick={() => save('PENDING')}>Save as pending</button> <button className="btn btn-primary btn-sm" onClick={() => save('PROCESSED')}>Mark processed</button> <button className="btn btn-outline btn-sm" onClick={() => setF(null)}>Cancel</button></div>}
    <div className="card"><div className="table-wrap"><table className="data-table"><thead><tr><th>Booking</th><th>Customer</th><th>Branch</th><th style={{ textAlign: 'right' }}>Received</th><th style={{ textAlign: 'right' }}>Refund</th><th>Status</th><th></th></tr></thead>
      <tbody>{d.rows.map((r) => <tr key={r.lead_id}><td>{r.booking_no}</td><td>{r.customer}</td><td>{r.branch || '—'}</td><td style={{ textAlign: 'right' }}>{rs(r.received)}</td><td style={{ textAlign: 'right' }}>{rs(r.refund_amount)}</td>
        <td>{LBL[r.refund_status]}{r.processed_date && ` · ${fmtDate(r.processed_date)}`}</td>
        <td>{r.refund_status !== 'PROCESSED' && r.refund_status !== 'NOTHING_TO_REFUND' && <button className="btn btn-outline btn-sm" onClick={() => setF({ lead_id: r.lead_id, customer: r.customer, received: r.received, amount: r.refund_amount ?? r.received, mode: '', reference: '', note: r.note || '', processed_date: '' })}>{r.refund_status === 'NOT_SET' ? 'Set refund' : 'Update'}</button>}</td></tr>)}</tbody></table>
      {!d.rows.length && <Empty>No cancelled bookings.</Empty>}</div></div></>)
}

function Customers({ bp }) {
  const [rows, setRows] = useState(null)
  const [f, setF] = useState({ q: '', status: '' })
  const [open, setOpen] = useState(null)
  useEffect(() => { api.get('/accounts/customers', { params: { ...bp, ...Object.fromEntries(Object.entries(f).filter(([, v]) => v)) } }).then((r) => setRows(r.data)).catch(() => setRows([])) }, [bp.branch_id, f])
  async function show(id) { try { setOpen((await api.get(`/accounts/customers/${id}`)).data) } catch { setOpen(null) } }
  return (<>
    {open && <div className="card" style={{ padding: 14, marginBottom: 12 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between' }}><h3 style={{ margin: 0 }}>{open.customer} · {open.booking_no}</h3><button className="btn btn-outline btn-sm" onClick={() => setOpen(null)}>Close</button></div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(170px,1fr))', gap: 8, margin: '10px 0' }}>
        <div><div className="muted-note">On-road price</div><b>{rs(open.on_road_price)}</b></div><div><div className="muted-note">Discount</div><b>{rs(open.discount)}</b></div>
        <div><div className="muted-note">Payable</div><b>{rs(open.payable)}</b></div><div><div className="muted-note">Paid</div><b>{rs(open.paid)}</b></div><div><div className="muted-note">Outstanding</div><b>{rs(open.outstanding)}</b></div>
        <div><div className="muted-note">Payment type</div><b>{open.payment_type || '—'}{open.finance_bank ? ` · ${open.finance_bank}` : ''}</b></div></div>
      <table className="data-table"><thead><tr><th>Date</th><th>Receipt</th><th>Mode</th><th>Reference</th><th style={{ textAlign: 'right' }}>Amount</th><th>Bank</th></tr></thead>
        <tbody>{open.payments.map((p) => <tr key={p.receipt_no}><td>{fmtDate(p.payment_date)}</td><td>{p.receipt_no}</td><td>{p.mode}</td><td>{p.reference || '—'}</td><td style={{ textAlign: 'right' }}>{rs(p.amount)}</td><td>{p.reconciled ? 'Reconciled' : 'Pending'}</td></tr>)}</tbody></table></div>}
    <div className="card"><div className="card-header" style={{ gap: 8 }}>
      <input className="input" style={{ maxWidth: 220 }} placeholder="Search customer / mobile / booking" value={f.q} onChange={(e) => setF({ ...f, q: e.target.value })} />
      <select className="input" style={{ maxWidth: 150 }} value={f.status} onChange={(e) => setF({ ...f, status: e.target.value })}><option value="">All payments</option>{Object.entries(PS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></div>
      <div className="table-wrap"><table className="data-table"><thead><tr><th>Booking</th><th>Customer</th><th>Branch</th><th>Stage</th><th style={{ textAlign: 'right' }}>Payable</th><th style={{ textAlign: 'right' }}>Paid</th><th style={{ textAlign: 'right' }}>Outstanding</th><th>Status</th></tr></thead>
        <tbody>{(rows || []).map((r) => <tr key={r.lead_id} style={{ cursor: 'pointer' }} onClick={() => show(r.lead_id)}><td>{r.booking_no}</td><td>{r.customer}<div className="muted-note">{r.mobile}</div></td><td>{r.branch || '—'}</td><td>{r.stage.replace(/_/g, ' ')}</td>
          <td style={{ textAlign: 'right' }}>{rs(r.cost)}</td><td style={{ textAlign: 'right' }}>{rs(r.paid)}</td><td style={{ textAlign: 'right' }}>{rs(r.outstanding)}</td><td>{PS[r.pay_status]}</td></tr>)}</tbody></table>
        {rows === null && <Loading />}{rows && !rows.length && <Empty>No customers.</Empty>}</div></div></>)
}
