import { useEffect, useState } from 'react'
import Layout from '../../components/Layout'
import { Empty, Loading, Pager, fmtDateTime } from '../../components/ui'
import api from '../../lib/api'

const ENTITY_TYPES = [
  { value: '', label: 'All types' },
  { value: 'customer', label: 'Customer' },
  { value: 'lead', label: 'Lead' },
  { value: 'user', label: 'User' },
]

// "full_name" -> "Full Name"
const fieldLabel = (f) => f.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())

const entityBadgeClass = (t) => (
  t === 'customer' ? 'badge-sky' : t === 'lead' ? 'badge-green' : 'badge-amber'
)

export default function ActivityLogPage() {
  const pageSize = 25
  const [page, setPage] = useState(1)
  const [entityType, setEntityType] = useState('')
  const [staffId, setStaffId] = useState('')
  const [data, setData] = useState(null)
  const [err, setErr] = useState('')

  function load() {
    setData(null)
    setErr('')
    api.get('/audit-log', {
      params: {
        page, page_size: pageSize,
        entity_type: entityType || undefined,
        changed_by_user_id: staffId || undefined,
      },
    }).then((r) => setData(r.data)).catch(() => setErr('Could not load activity log.'))
  }
  useEffect(() => { load() }, [page, entityType, staffId])

  function onFilterChange(setter) {
    return (e) => { setPage(1); setter(e.target.value) }
  }

  return (
    <Layout title="Activity Log" sub="Every field change, across every customer, lead, and staff account">
      <div className="card">
        <div className="card-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 8 }}>
          <h3>Recent Changes {data && <span className="muted-note">({data.total})</span>}</h3>
          <div style={{ display: 'flex', gap: 8 }}>
            <select className="input" style={{ maxWidth: 160 }} value={entityType} onChange={onFilterChange(setEntityType)}>
              {ENTITY_TYPES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
            </select>
            <select className="input" style={{ maxWidth: 200 }} value={staffId} onChange={onFilterChange(setStaffId)}>
              <option value="">All staff</option>
              {data?.staff?.map((s) => <option key={s.user_id} value={s.user_id}>{s.full_name}</option>)}
            </select>
          </div>
        </div>

        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr><th>Date &amp; Time</th><th>Type</th><th>Record ID</th><th>Field</th><th>Changed From</th><th>Changed To</th><th>By</th></tr>
            </thead>
            <tbody>
              {data?.rows?.map((h) => (
                <tr key={h.id}>
                  <td className="cell-muted">{fmtDateTime(h.changed_at)}</td>
                  <td><span className={'badge ' + entityBadgeClass(h.entity_type)}>{h.entity_type}</span></td>
                  <td className="cell-muted">#{h.entity_id}</td>
                  <td>{fieldLabel(h.field_name)}</td>
                  <td className="cell-muted">{h.old_value || '—'}</td>
                  <td>{h.new_value || '—'}</td>
                  <td>{h.changed_by_name || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {!data && !err && <Loading />}
          {err && <Empty>{err}</Empty>}
          {data && data.rows.length === 0 && <Empty>No changes logged yet.</Empty>}
        </div>
        {data && <Pager total={data.total} page={page} pageSize={pageSize} onPage={setPage} />}
      </div>
    </Layout>
  )
}
