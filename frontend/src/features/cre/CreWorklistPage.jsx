// CRE worklists: Walkin and LeadSquare leads of the CRE's branches. Open a row to call / edit (CRE may edit PBA fields).
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import api from '../../lib/api'
import Layout from '../../components/Layout'
import { Empty, Loading, fmtDateTime } from '../../components/ui'

export default function CreWorklistPage({ source }) {
  const title = source === 'WALKIN' ? 'Walkin' : 'LeadSquare'
  const [search, setSearch] = useState('')
  const [opp, setOpp] = useState('')
  const [lookups, setLookups] = useState(null)
  const [rows, setRows] = useState(null)
  const [sum, setSum] = useState(null)
  const [bucket, setBucket] = useState('')
  useEffect(() => { api.get('/lookups').then((r) => setLookups(r.data)).catch(() => {}) }, [])
  useEffect(() => {
    setRows(null)
    const t = setTimeout(() => {
      api.get('/cre-worklist', { params: { source, search: search || undefined, opportunity_status_id: opp || undefined, bucket: bucket || undefined } })
        .then((r) => { setRows(r.data.rows); setSum(r.data.summary) }).catch(() => setRows(false))
    }, 250)
    return () => clearTimeout(t)
  }, [source, search, opp, bucket])
  return (
    <Layout title={title} sub={`${title} leads of your branches — open a customer to call, add a follow-up or edit details`}>
      {sum && <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))', gap: 12, marginBottom: 14 }}>
        {[['', 'All leads', sum.total, '#2563eb'], ['due_today', "Today's follow-up", sum.due_today, '#16a34a'], ['pending', 'Pending follow-up', sum.pending, '#ea580c'],
          ['overdue', 'Over due follow-up', sum.overdue, '#dc2626'], ['other', 'Service / Casual / Wrong / False / Out of MH', sum.other, '#7c3aed']].map(([k, l, v, c]) => (
          <div key={l} onClick={() => setBucket(k)} style={{ cursor: 'pointer', background: '#fff', border: `2px solid ${bucket === k ? c : '#e5e7eb'}`, borderRadius: 12, padding: '10px 14px' }}>
            <div style={{ fontSize: 12.5, color: '#475569', fontWeight: 600, minHeight: 32 }}>{l}</div><div style={{ fontSize: 26, fontWeight: 700, color: c }}>{v}</div></div>))}
      </div>}
      <div className="card" style={{ marginBottom: 14 }}><div className="card-pad" style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
        <input className="input" style={{ maxWidth: 280 }} placeholder="Search name / mobile / enquiry no." value={search} onChange={(e) => setSearch(e.target.value)} />
        <select className="input" style={{ maxWidth: 220 }} value={opp} onChange={(e) => setOpp(e.target.value)}>
          <option value="">All statuses</option>
          {lookups?.opportunity_statuses?.map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}
        </select>
      </div></div>
      <div className="card">
        <div className="card-header"><h3>{title} leads {Array.isArray(rows) && <span className="muted-note">({rows.length})</span>}</h3></div>
        {rows === null ? <Loading /> : rows === false ? <div className="hint">Could not load.</div> : (
          <div className="table-wrap"><table className="data-table">
            <thead><tr><th>Lead ID</th><th>Customer</th><th>Mobile</th><th>Model</th><th>Variant / Colour</th><th>Source</th><th>PBA</th><th>PBA remark</th><th>Discounted price</th><th>Status</th><th>Created</th><th></th></tr></thead>
            <tbody>{rows.map((r) => (
              <tr key={r.lead_id}>
                <td>{r.enquiry_no}</td><td>{r.customer}</td><td><a href={`tel:${r.mobile}`}>{r.mobile}</a></td><td>{r.model || '—'}</td>
                <td>{[r.variant, r.colour].filter(Boolean).join(' / ') || '—'}</td><td>{r.source === 'WALKIN' ? 'Walkin' : 'LeadSquare'}</td>
                <td>{r.pba || '—'}</td><td style={{ maxWidth: 220 }}>{r.pba_remark || '—'}</td>
                <td>{r.discounted_price != null ? `₹${Number(r.discounted_price).toLocaleString('en-IN')}` : '—'}</td>
                <td>{r.opportunity || '—'}{r.stage !== 'OPEN' ? ` · ${r.stage}` : ''}</td><td className="cell-muted">{fmtDateTime(r.created_at)}</td>
                <td><Link className="btn btn-primary btn-sm" to={`/leads/${r.lead_id}`}>Open</Link></td>
              </tr>))}</tbody>
          </table>{!rows.length && <Empty>No leads found.</Empty>}</div>)}
      </div>
    </Layout>
  )
}
