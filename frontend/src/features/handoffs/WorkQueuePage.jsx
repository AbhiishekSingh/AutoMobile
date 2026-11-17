// Worklist for the Owner (approvals + ATW waiting) and the RTO (cases not yet registered).
// The server decides what each role gets (GET /handoffs/queue). Click a row to open the file.
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../../lib/api'
import { useAuth } from '../../lib/auth'
import Layout from '../../components/Layout'
import { Empty, Loading, fmtDateTime } from '../../components/ui'

const KIND = { INITIAL_APPROVAL: 'Initial approval', FINAL_APPROVAL: 'Final approval', APPROVAL: 'Owner approval', ATW: 'ATW approval', RTO: 'RTO registration', INSURANCE: 'Insurance' }

export default function WorkQueuePage({ title }) {
  const nav = useNavigate()
  const { user } = useAuth()
  const isRto = user?.role === 'RTO'
  const [tab, setTab] = useState('')          // RTO: '' = waiting, IN_PROCESS, REGISTERED
  const [rows, setRows] = useState(null)
  useEffect(() => { setRows(null); api.get('/handoffs/queue', { params: { status: isRto && tab ? tab : undefined } }).then((r) => setRows(r.data)).catch(() => setRows([])) }, [tab, isRto])
  return (
    <Layout title={title} sub="Click a customer to open the file"
            back={user?.role === 'OWNER' ? { label: 'Back to Approvals', onClick: () => nav('/owner') } : undefined}>
      {isRto && <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
        {[['', 'Waiting (pending + in process)'], ['IN_PROCESS', 'In process'], ['REGISTERED', 'Registered']].map(([k, l]) => (
          <button key={k} className={'btn btn-sm ' + (tab === k ? 'btn-primary' : 'btn-outline')} onClick={() => setTab(k)}>{l}</button>))}
      </div>}
      <div className="card">
        <div className="card-header"><h3>{tab === 'REGISTERED' ? 'Registered customers' : 'Waiting for you'}<span className="muted-note">({rows ? rows.length : '…'})</span></h3></div>
        <div className="table-wrap">
          <table className="data-table">
            <thead><tr><th>Enquiry</th><th>Customer</th><th>Branch</th><th>Work</th><th>Details</th><th>Waiting since</th></tr></thead>
            <tbody>
              {(rows || []).map((r, i) => (
                <tr key={i} style={{ cursor: 'pointer' }} onClick={() => nav(`/handoff/${r.lead_id}`)}>
                  <td className="cell-primary">{r.enquiry_no}</td><td>{r.customer_name}</td><td>{r.branch || '—'}</td>
                  <td><span className="badge badge-amber">{KIND[r.kind]}</span></td>
                  <td>{[r.status && r.status.replace(/_/g, ' ').toLowerCase(), r.items?.join(', '), r.registration_type, r.registration_no && `reg. no. ${r.registration_no}`, r.registration_date && `registered ${r.registration_date}`,
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
