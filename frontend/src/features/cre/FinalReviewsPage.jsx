// CRE worklist: delivered customers waiting for the final review, plus recently closed ones.
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import api from '../../lib/api'
import Layout from '../../components/Layout'
import { Empty, Loading, fmtDate, fmtDateTime } from '../../components/ui'

export default function FinalReviewsPage() {
  const [d, setD] = useState(null)
  useEffect(() => { api.get('/final-reviews').then((r) => setD(r.data)).catch(() => setD(false)) }, [])
  if (d === null) return <Layout title="Final reviews"><Loading /></Layout>
  if (!d) return <Layout title="Final reviews"><div className="hint">Could not load.</div></Layout>
  const LS = { CALLBACK_NEEDED: 'Call back', NOT_REACHABLE: 'Not reachable' }
  return (
    <Layout title="Final reviews" sub="Delivered customers stay open until you record the final review">
      <div className="card" style={{ marginBottom: 14 }}><div className="card-header"><h3>Due ({d.due.length})</h3></div>
        <div className="table-wrap"><table className="data-table"><thead><tr><th>Enquiry</th><th>Customer</th><th>Mobile</th><th>Model</th><th>Branch</th><th>Delivered</th><th>Last attempt</th><th></th></tr></thead>
          <tbody>{d.due.map((r) => <tr key={r.lead_id}><td>{r.enquiry_no}</td><td>{r.customer}</td><td>{r.mobile}</td><td>{r.model || '—'}</td><td>{r.branch || '—'}</td><td>{fmtDate(r.delivered_since)}</td>
            <td>{r.last_status ? `${LS[r.last_status] || r.last_status} (${r.attempts})` : '—'}</td><td><Link className="btn btn-primary btn-sm" to={`/leads/${r.lead_id}`}>Do review</Link></td></tr>)}</tbody></table>
          {!d.due.length && <Empty>No final reviews pending.</Empty>}</div></div>
      <div className="card"><div className="card-header"><h3>Recently closed</h3></div>
        <div className="table-wrap"><table className="data-table"><thead><tr><th>Customer</th><th>Closed</th><th>CRE</th><th>Product</th><th>Experience</th></tr></thead>
          <tbody>{d.closed.map((r) => <tr key={r.lead_id}><td><Link to={`/leads/${r.lead_id}`}>{r.customer}</Link></td><td>{fmtDateTime(r.closed_at)}</td><td>{r.reviewed_by}</td><td>{r.product_satisfaction}/5</td><td>{r.customer_experience}/5</td></tr>)}</tbody></table>
          {!d.closed.length && <Empty>None yet.</Empty>}</div></div>
    </Layout>
  )
}
