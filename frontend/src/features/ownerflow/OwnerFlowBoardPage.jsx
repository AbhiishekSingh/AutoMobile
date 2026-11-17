// Live status of every booked deal across the workflow. Owner / GM / Admin: all; PBA: own; CRE: own branches.
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../../lib/api'
import { useAuth } from '../../lib/auth'
import Layout from '../../components/Layout'
import { Empty, Loading } from '../../components/ui'

const rupees = (v) => (v === null || v === undefined || v === '') ? '—' : `₹ ${Number(v).toLocaleString('en-IN')}`
const TONE = { APPROVED: 'badge-green', DONE: 'badge-green', COMPLETED: 'badge-green', REGISTERED: 'badge-green', ENABLED: 'badge-green',
               PENDING: 'badge-amber', IN_PROGRESS: 'badge-amber', IN_PROCESS: 'badge-amber', REJECTED: 'badge-red', LOCKED: 'badge-gray' }
const pretty = (s) => (s || '').replace(/_/g, ' ').toLowerCase().replace(/^\w/, (c) => c.toUpperCase())
const B = ({ v }) => (<span className={'badge ' + (TONE[v] || 'badge-gray')}>{v ? pretty(v) : '—'}</span>)
const FILTERS = [['', 'All'], ['AWAITING_INITIAL_APPROVAL', 'Initial approval'], ['AWAITING_PBA', 'With PBA'], ['AT_INSURANCE', 'Insurance'],
                 ['AWAITING_FINAL_APPROVAL', 'Final approval'], ['AT_RTO', 'RTO'], ['INITIAL_REJECTED', 'Rejected']]

export default function OwnerFlowBoardPage() {
  const nav = useNavigate()
  const { user } = useAuth()
  const open = (id) => nav(['PBA', 'CRE'].includes(user?.role) ? `/leads/${id}` : `/handoff/${id}`)
  const [st, setSt] = useState('')
  const [page, setPage] = useState(1)
  const [data, setData] = useState(null)
  const rows = data && data.rows
  useEffect(() => { setData(null); api.get('/owner-flow/board', { params: { status: st || undefined, page } }).then((r) => setData(r.data)).catch(() => setData({ rows: [], total: 0, page_size: 25 })) }, [st, page])
  const pages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1
  return (
    <Layout title="Deal workflow" sub="Where every booked deal stands — updates live">
      <div style={{ display: 'flex', gap: 8, marginBottom: 12, flexWrap: 'wrap' }}>
        {FILTERS.map(([k, l]) => (<button key={k} className={'btn btn-sm ' + (st === k ? 'btn-primary' : 'btn-outline')} onClick={() => { setSt(k); setPage(1) }}>{l}</button>))}
      </div>
      <div className="card"><div className="table-wrap">
        <table className="data-table">
          <thead><tr><th>Enquiry</th><th>Customer</th><th>Branch / PBA</th><th>Model</th><th>Price</th><th>Where it is now</th><th>Initial</th><th>Final</th><th>RTO</th><th>Challan</th></tr></thead>
          <tbody>{(rows || []).map((r) => (
            <tr key={r.lead_id} style={{ cursor: 'pointer' }} onClick={() => open(r.lead_id)}>
              <td className="cell-primary">{r.enquiry_no}</td><td>{r.customer_name}</td><td>{r.branch || '—'}<div className="muted-note">{r.pba}</div></td><td>{r.model || '—'}</td>
              <td>{rupees(r.discounted_price || r.bike_price)}</td><td><b>{r.label}</b></td>
              <td><B v={r.stages.initial} /></td><td><B v={r.stages.final} /></td><td><B v={r.stages.rto} /></td><td><B v={r.stages.challan} /></td></tr>))}</tbody>
        </table>
        {rows === null && <Loading />}{rows && rows.length === 0 && <Empty>No deals here.</Empty>}
      </div></div>
      {data && pages > 1 && (<div style={{ display: 'flex', gap: 8, justifyContent: 'center', marginTop: 12 }}>
        <button className="btn btn-sm btn-outline" disabled={page <= 1} onClick={() => setPage(page - 1)}>Previous</button>
        <span className="muted-note">Page {page} of {pages} · {data.total} deals</span>
        <button className="btn btn-sm btn-outline" disabled={page >= pages} onClick={() => setPage(page + 1)}>Next</button></div>)}
    </Layout>
  )
}
