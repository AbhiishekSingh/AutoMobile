// Insurance team home: KPI cards + customer listing with filters. Click a row to open the case.
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../../lib/api'
import Layout from '../../components/Layout'
import { Empty, Loading, fmtDate } from '../../components/ui'

const KPIS = [['total', 'Booked customers received'], ['pending', 'Insurance pending'], ['documents_pending', 'Documents pending'],
  ['in_progress', 'Insurance in progress'], ['completed', 'Insurance completed'], ['pdf_not_uploaded', 'Insurance PDF not uploaded'],
  ['pba_notification_pending', 'PBA notification pending'], ['whatsapp_failed', 'WhatsApp failed']]
const ST = { PENDING: 'Pending', IN_PROGRESS: 'In progress', COMPLETED: 'Completed' }
const DS = { COMPLETE: ['Complete', 'badge-green'], PENDING: ['Pending', 'badge-amber'], NO_POLICY_TYPE: ['Select policy type', 'badge-amber'] }
const WA = { NOT_SENT: 'Not sent', PENDING: 'Pending', SENT: 'Sent', DELIVERED: 'Delivered', READ: 'Read', FAILED: 'Failed' }

export default function InsuranceDashboardPage() {
  const nav = useNavigate()
  const [kpi, setKpi] = useState(null)
  const [rows, setRows] = useState(null)
  const [pbas, setPbas] = useState([])
  const [f, setF] = useState({ q: '', status: '', policy_type: '', pba_id: '', document_status: '', date_from: '', date_to: '' })
  useEffect(() => { api.get('/insurance/dashboard').then((r) => setKpi(r.data)).catch(() => setKpi({})); api.get('/insurance/pbas').then((r) => setPbas(r.data)).catch(() => {}) }, [])
  useEffect(() => {
    const params = Object.fromEntries(Object.entries(f).filter(([, v]) => v))
    api.get('/insurance/cases', { params }).then((r) => setRows(r.data)).catch(() => setRows([]))
  }, [f])
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value })
  return (
    <Layout title="Insurance" sub="Booked customers waiting for insurance">
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(150px,1fr))', gap: 10, marginBottom: 16 }}>
        {KPIS.map(([k, label]) => (
          <div key={k} className="card" style={{ padding: 12 }}>
            <div className="muted-note">{label}</div><div style={{ fontSize: 24, fontWeight: 700 }}>{kpi ? (kpi[k] ?? 0) : '…'}</div>
          </div>))}
      </div>
      <div className="card">
        <div className="card-header" style={{ flexWrap: 'wrap', gap: 8 }}>
          <input className="input" style={{ maxWidth: 200 }} placeholder="Search name / mobile / booking / policy" value={f.q} onChange={set('q')} />
          <select className="input" style={{ maxWidth: 150 }} value={f.status} onChange={set('status')}><option value="">All status</option>
            {Object.entries(ST).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select>
          <select className="input" style={{ maxWidth: 170 }} value={f.policy_type} onChange={set('policy_type')}><option value="">All policy types</option>
            <option value="MBO_ACKO">MBO – ACKO</option><option value="CUSTOMER_BAGIC">Customer – BAGIC</option></select>
          <select className="input" style={{ maxWidth: 150 }} value={f.pba_id} onChange={set('pba_id')}><option value="">All PBAs</option>
            {pbas.map((p) => <option key={p.user_id} value={p.user_id}>{p.full_name}</option>)}</select>
          <select className="input" style={{ maxWidth: 150 }} value={f.document_status} onChange={set('document_status')}><option value="">Documents: all</option>
            <option value="PENDING">Pending</option><option value="COMPLETE">Complete</option></select>
          <input className="input" type="date" style={{ maxWidth: 140 }} value={f.date_from} onChange={set('date_from')} title="Booked from" />
          <input className="input" type="date" style={{ maxWidth: 140 }} value={f.date_to} onChange={set('date_to')} title="Booked to" />
        </div>
        <div className="table-wrap">
          <table className="data-table">
            <thead><tr><th>Booking ID</th><th>Customer</th><th>Mobile</th><th>Model</th><th>PBA</th><th>Booked</th><th>Policy type</th>
              <th>Documents</th><th>Nominee</th><th>Status</th><th>Policy no.</th><th>PDF</th><th>PBA notified</th><th>WhatsApp</th></tr></thead>
            <tbody>
              {(rows || []).map((r) => (
                <tr key={r.lead_id} style={{ cursor: 'pointer' }} onClick={() => nav(`/insurance/${r.lead_id}`)}>
                  <td className="cell-primary">{r.booking_no || '—'}</td><td>{r.customer_name}</td><td>{r.mobile}</td><td>{r.model || '—'}</td>
                  <td>{r.pba_name || '—'}</td><td className="cell-muted">{fmtDate(r.booking_date)}</td><td>{r.policy_type_label || '—'}</td>
                  <td><span className={`badge ${DS[r.document_status][1]}`}>{DS[r.document_status][0]}</span></td>
                  <td>{r.nominee_status === 'COMPLETE' ? 'Done' : 'Pending'}</td><td>{ST[r.status]}</td><td>{r.policy_no || '—'}</td>
                  <td>{r.pdf_uploaded ? 'Uploaded' : 'No'}</td><td>{r.status === 'COMPLETED' ? (r.pba_notified ? 'Yes' : 'Pending') : '—'}</td>
                  <td>{WA[r.whatsapp_status]}</td>
                </tr>))}
            </tbody>
          </table>
          {rows === null && <Loading />}
          {rows && rows.length === 0 && <Empty>No customers match.</Empty>}
        </div>
      </div>
    </Layout>
  )
}
