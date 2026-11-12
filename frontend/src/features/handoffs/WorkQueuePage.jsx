// Worklist for the Owner (approvals + ATW waiting) and the RTO (cases not yet registered).
// The server decides what each role gets (GET /handoffs/queue). Click a row to open the file.
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../../lib/api'
import Layout from '../../components/Layout'
import { Empty, Loading, fmtDateTime } from '../../components/ui'

const KIND = { APPROVAL: 'Owner approval', ATW: 'ATW approval', RTO: 'RTO registration', INSURANCE: 'Insurance' }

export default function WorkQueuePage({ title }) {
  const nav = useNavigate()
  const [rows, setRows] = useState(null)
  useEffect(() => { api.get('/handoffs/queue').then((r) => setRows(r.data)).catch(() => setRows([])) }, [])
  return (
    <Layout title={title} sub="Click a customer to open the file">
      <div className="card">
        <div className="card-header"><h3>Waiting for you <span className="muted-note">({rows ? rows.length : '…'})</span></h3></div>
        <div className="table-wrap">
          <table className="data-table">
            <thead><tr><th>Enquiry</th><th>Customer</th><th>Branch</th><th>Work</th><th>Details</th><th>Waiting since</th></tr></thead>
            <tbody>
              {(rows || []).map((r, i) => (
                <tr key={i} style={{ cursor: 'pointer' }} onClick={() => nav(`/handoff/${r.lead_id}`)}>
                  <td className="cell-primary">{r.enquiry_no}</td><td>{r.customer_name}</td><td>{r.branch || '—'}</td>
                  <td><span className="badge badge-amber">{KIND[r.kind]}</span></td>
                  <td>{[r.status && r.status.replace(/_/g, ' ').toLowerCase(), r.items?.join(', '), r.registration_type,
                        r.model_name, r.delivery_date && `delivery ${r.delivery_date}`].filter(Boolean).join(' · ') || '—'}</td>
                  <td className="cell-muted">{fmtDateTime(r.since)}</td>
                </tr>))}
            </tbody>
          </table>
          {rows === null && <Loading />}
          {rows && rows.length === 0 && <Empty>Nothing waiting.</Empty>}
        </div>
      </div>
    </Layout>
  )
}
