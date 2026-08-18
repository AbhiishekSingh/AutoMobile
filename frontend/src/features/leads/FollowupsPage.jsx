import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import Layout from '../../components/Layout'
import { Sla, Empty, Loading, Pager, fmtDateTime } from '../../components/ui'
import api from '../../lib/api'

const BUCKETS = [
  { key: 'all', label: 'All' },
  { key: 'overdue', label: 'Overdue' },
  { key: 'today', label: 'Today' },
  { key: 'upcoming', label: 'Upcoming' },
]

const BUCKET_BADGE = {
  overdue: 'badge-red',
  today: 'badge-amber',
  upcoming: 'badge-green',
}

export default function FollowupsPage() {
  const nav = useNavigate()
  const [bucket, setBucket] = useState('all')
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)
  const [data, setData] = useState(null)
  const pageSize = 10

  function load() {
    setData(null)
    api.get('/followups', { params: { bucket, search: search || undefined, page, page_size: pageSize } })
      .then((r) => setData(r.data))
      .catch(() => setData({ total: 0, page: 1, page_size: pageSize, counts: {}, rows: [] }))
  }
  useEffect(() => { load() }, [bucket, page])

  function submit(e) { e.preventDefault(); setPage(1); load() }
  const counts = data?.counts || {}

  return (
    <Layout title="Follow Ups" sub="Scheduled calls & next actions">
      <div className="card">
        <div className="card-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {BUCKETS.map((b) => (
              <button key={b.key}
                      className={'btn btn-sm ' + (bucket === b.key ? 'btn-primary' : 'btn-outline')}
                      onClick={() => { setBucket(b.key); setPage(1) }}>
                {b.label} <strong style={{ marginLeft: 6 }}>{counts[b.key] ?? 0}</strong>
              </button>
            ))}
          </div>
          <form onSubmit={submit} style={{ display: 'flex', gap: 8 }}>
            <input className="input" style={{ maxWidth: 220 }} placeholder="Search name / phone / enquiry"
                   value={search} onChange={(e) => setSearch(e.target.value)} />
            <button className="btn btn-outline btn-sm">Search</button>
          </form>
        </div>
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr><th>When</th><th>Enquiry No</th><th>Customer</th><th>Contact</th><th>Model</th><th>Status</th><th>Disposition</th><th>SLA</th></tr>
            </thead>
            <tbody>
              {data?.rows?.map((f) => (
                <tr key={f.lead_id} style={{ cursor: 'pointer' }} onClick={() => nav(`/leads/${f.lead_id}`)}>
                  <td>
                    <span className={'badge ' + (BUCKET_BADGE[f.bucket] || 'badge-gray')} style={{ marginRight: 8 }}>
                      {f.bucket}
                    </span>
                    {fmtDateTime(f.next_followup_at)}
                  </td>
                  <td className="cell-muted">{f.enquiry_no}</td>
                  <td className="cell-primary">{f.customer_name}</td>
                  <td className="cell-muted">{f.contact_masked}</td>
                  <td>{f.model_name || '—'}</td>
                  <td>{f.opportunity_status || '—'}</td>
                  <td>{f.disposition || '—'}</td>
                  <td><Sla flag={f.sla_flag} /></td>
                </tr>
              ))}
            </tbody>
          </table>
          {!data && <Loading />}
          {data && data.rows.length === 0 && <Empty>No follow-ups in this view.</Empty>}
        </div>
        {data && <Pager total={data.total} page={page} pageSize={pageSize} onPage={setPage} />}
      </div>
    </Layout>
  )
}
