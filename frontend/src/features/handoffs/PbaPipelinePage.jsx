// PBA worklists: "Invoices" and "RTO". One table of booked customers still waiting for delivery, each with a tag for the stage
// the customer is in now (Insurance / RTO / Invoice / Ready), so the PBA can pick the next customer and open that customer's
// Approvals & Delivery tab directly. Data: GET /handoffs/pipeline (the server works out the stage).
import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../../lib/api'
import Layout from '../../components/Layout'
import { Empty, Loading, fmtDate } from '../../components/ui'

const TAG = {
  INSURANCE: ['Insurance', '#fff1d6', '#8a5a00'],
  RTO: ['RTO', '#e6f0ff', '#2459c4'],
  INVOICE: ['Invoice', '#fde8e6', '#b3261e'],
  READY: ['Ready for delivery', '#e3f5ea', '#17673a'],
}
const MODES = {
  invoice: {
    title: 'Invoices', sub: 'Booked customers waiting for their invoice details',
    tabs: [['todo', 'Invoice to do', (r) => !r.invoice_done], ['done', 'Invoice done', (r) => r.invoice_done], ['all', 'All', () => true]],
    empty: { todo: 'No customer is waiting for an invoice.', done: 'No invoice saved yet.', all: 'No booked customers.' },
    action: (r) => (r.invoice_done ? 'View' : 'Add invoice'),
  },
  rto: {
    title: 'RTO', sub: 'Booked customers and where their registration stands',
    tabs: [['todo', 'In progress', (r) => !r.rto_done], ['done', 'Registered', (r) => r.rto_done], ['all', 'All', () => true]],
    empty: { todo: 'No registration is in progress.', done: 'No customer is registered yet.', all: 'No booked customers.' },
    action: (r) => (r.rto_done ? 'View' : 'Open'),
  },
}

function Pill({ bg, fg, children }) {
  return <span style={{ display: 'inline-block', padding: '3px 11px', borderRadius: 99, fontSize: 12, fontWeight: 700, background: bg, color: fg, whiteSpace: 'nowrap' }}>{children}</span>
}
function Step({ ok, label }) {
  return (
    <span title={`${label}: ${ok ? 'done' : 'pending'}`} style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 11.5, color: ok ? '#17673a' : '#8a93a0', fontWeight: 600 }}>
      <span style={{ width: 16, height: 16, borderRadius: 8, display: 'inline-flex', alignItems: 'center', justifyContent: 'center', fontSize: 10,
                     background: ok ? '#1f8a4c' : '#fff', color: '#fff', border: ok ? 'none' : '2px solid #cfd5de' }}>{ok ? '✓' : ''}</span>{label}
    </span>)
}

export default function PbaPipelinePage({ mode = 'invoice' }) {
  const nav = useNavigate()
  const cfg = MODES[mode]
  const [rows, setRows] = useState(null)
  const [tab, setTab] = useState('todo')
  const [q, setQ] = useState('')
  useEffect(() => { setRows(null); setTab('todo'); api.get('/handoffs/pipeline').then((r) => setRows(r.data)).catch(() => setRows([])) }, [mode])

  const active = cfg.tabs.find((t) => t[0] === tab) || cfg.tabs[0]
  const shown = useMemo(() => (rows || []).filter(active[2]).filter((r) =>
    !q || [r.customer_name, r.mobile, r.enquiry_no, r.booking_no, r.model].join(' ').toLowerCase().includes(q.toLowerCase())), [rows, active, q])
  const open = (r) => nav(`/leads/${r.lead_id}?tab=approvals`)

  return (
    <Layout title={cfg.title} sub={cfg.sub}>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center', marginBottom: 14 }}>
        {cfg.tabs.map(([k, label, f]) => (
          <button key={k} type="button" className={'btn btn-sm ' + (tab === k ? 'btn-primary' : 'btn-outline')} onClick={() => setTab(k)}>
            {label}{rows ? ` · ${rows.filter(f).length}` : ''}</button>))}
        <input className="input" style={{ maxWidth: 300, flex: '1 1 220px', marginLeft: 'auto' }} placeholder="🔍 Search customer, mobile, enquiry or model" value={q} onChange={(e) => setQ(e.target.value)} />
      </div>
      {rows === null && <Loading />}
      {rows && shown.length === 0 && <Empty>{q ? 'No customer matches.' : cfg.empty[tab]}</Empty>}
      {rows && shown.length > 0 && (
        <div className="card">
          <div className="table-wrap">
            <table className="data-table">
              <thead><tr>
                <th>Customer</th><th>Model</th><th>Stage now</th><th>Progress</th>
                <th>{mode === 'invoice' ? 'Invoice' : 'Registration'}</th><th>Delivery date</th><th></th></tr></thead>
              <tbody>
                {shown.map((r) => {
                  const [tl, bg, fg] = TAG[r.stage] || TAG.INSURANCE
                  return (
                    <tr key={r.lead_id} style={{ cursor: 'pointer' }} onClick={() => open(r)}>
                      <td><div className="cell-primary">{r.customer_name}</div>
                        <div className="muted-note" style={{ fontSize: 12 }}>{r.mobile}{r.booking_no ? ` · ${r.booking_no}` : ` · ${r.enquiry_no}`}</div></td>
                      <td>{r.model || '—'}<div className="muted-note" style={{ fontSize: 12 }}>{r.branch || ''}</div></td>
                      <td><Pill bg={bg} fg={fg}>{tl}</Pill></td>
                      <td><div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
                        <Step ok={r.insurance_done} label="Insurance" /><Step ok={r.rto_done} label="RTO" /><Step ok={r.invoice_done} label="Invoice" /></div></td>
                      <td>{mode === 'invoice'
                        ? (r.invoice_done ? <>{r.invoice_no || 'Saved'}<div className="muted-note" style={{ fontSize: 12 }}>{r.invoice_date ? fmtDate(r.invoice_date) : ''}</div></> : <span className="muted-note">Not added</span>)
                        : <>{r.rto_status_label || 'Waiting for insurance'}
                            <div className="muted-note" style={{ fontSize: 12 }}>{[r.registration_type, r.registration_no].filter(Boolean).join(' · ')}</div></>}</td>
                      <td>{r.delivery_date ? fmtDate(r.delivery_date) : <span className="muted-note">Not set</span>}</td>
                      <td style={{ textAlign: 'right' }}>
                        <button type="button" className={'btn btn-sm ' + ((mode === 'invoice' ? r.invoice_done : r.rto_done) ? 'btn-outline' : 'btn-primary')}
                          onClick={(e) => { e.stopPropagation(); open(r) }}>{cfg.action(r)}</button></td>
                    </tr>)
                })}
              </tbody>
            </table>
          </div>
        </div>)}
    </Layout>)
}
