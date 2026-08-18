import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import Layout from '../../components/Layout'
import { Empty, Loading, Pager, fmtDate } from '../../components/ui'
import api from '../../lib/api'

export default function CustomersPage() {
  const nav = useNavigate()
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)
  const [data, setData] = useState(null)
  const pageSize = 10

  function load() {
    setData(null)
    api.get('/customers', { params: { search: search || undefined, page, page_size: pageSize } })
      .then((r) => setData(r.data))
      .catch(() => setData({ total: 0, page: 1, page_size: pageSize, rows: [] }))
  }
  useEffect(() => { load() }, [page])

  function submit(e) { e.preventDefault(); setPage(1); load() }

  return (
    <Layout title="Customers" sub="Everyone who has enquired, deduped by phone">
      <div className="card">
        <div className="card-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h3>Customers {data && <span className="muted-note">({data.total})</span>}</h3>
          <form onSubmit={submit} style={{ display: 'flex', gap: 8 }}>
            <input className="input" style={{ maxWidth: 240 }} placeholder="Search name / phone / city"
                   value={search} onChange={(e) => setSearch(e.target.value)} />
            <button className="btn btn-outline btn-sm">Search</button>
          </form>
        </div>
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr><th>Name</th><th>Contact</th><th>City</th><th>Pincode</th><th>Leads</th><th>Latest Model</th><th>Latest Enquiry</th></tr>
            </thead>
            <tbody>
              {data?.rows?.map((c) => (
                <tr key={c.customer_id} style={{ cursor: c.latest_lead_id ? 'pointer' : 'default' }}
                    onClick={() => c.latest_lead_id && nav(`/leads/${c.latest_lead_id}`)}>
                  <td className="cell-primary">{c.full_name}</td>
                  <td className="cell-muted">{c.contact_masked}</td>
                  <td>{c.city || '—'}</td>
                  <td>{c.pincode || '—'}</td>
                  <td>{c.leads_count}</td>
                  <td>{c.latest_model || '—'}</td>
                  <td>{fmtDate(c.latest_enquiry_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {!data && <Loading />}
          {data && data.rows.length === 0 && <Empty>No customers yet.</Empty>}
        </div>
        {data && <Pager total={data.total} page={page} pageSize={pageSize} onPage={setPage} />}
      </div>
    </Layout>
  )
}
