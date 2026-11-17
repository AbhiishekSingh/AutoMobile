// Admin: data-sync failures (LeadSquare import rows, WhatsApp sends). Resolve a row once it has been dealt with.
import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import api from '../../lib/api'
import Layout from '../../components/Layout'
import { Empty, Loading, fmtDateTime } from '../../components/ui'

const SOURCES = { LEADSQUARE_IMPORT: 'LeadSquare import', WHATSAPP: 'WhatsApp' }

export default function SyncLogPage() {
  const [source, setSource] = useState('')
  const [state, setState] = useState('OPEN')
  const [d, setD] = useState(null)
  const load = useCallback(() => { setD(null); api.get('/sync-failures', { params: { source: source || undefined, state } }).then((r) => setD(r.data)).catch(() => setD(false)) }, [source, state])
  useEffect(() => { load() }, [load])
  async function resolve(id) { await api.post(`/sync-failures/${id}/resolve`); load() }
  return (
    <Layout title="Sync failure log" sub="Data hand-overs that failed — LeadSquare imports and WhatsApp sends">
      <div className="card" style={{ marginBottom: 14 }}><div className="card-pad" style={{ display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'center' }}>
        <select className="input" style={{ maxWidth: 200 }} value={source} onChange={(e) => setSource(e.target.value)}>
          <option value="">All sources</option>{Object.entries(SOURCES).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select>
        <select className="input" style={{ maxWidth: 200 }} value={state} onChange={(e) => setState(e.target.value)}>
          <option value="OPEN">Open</option><option value="RESOLVED">Resolved</option><option value="ALL">All</option></select>
        {d && <span className="muted-note">{d.open} open · {d.resolved} resolved</span>}
      </div></div>
      <div className="card">
        {d === null ? <Loading /> : d === false ? <div className="hint">Could not load.</div> : (
          <div className="table-wrap"><table className="data-table">
            <thead><tr><th>When</th><th>Source</th><th>Reference</th><th>What failed</th><th>By</th><th></th></tr></thead>
            <tbody>{d.rows.map((r) => (
              <tr key={r.id}>
                <td className="cell-muted">{fmtDateTime(r.at)}</td><td>{SOURCES[r.source] || r.source}</td>
                <td>{r.ref_type === 'lead' && r.ref_id ? <Link to={`/leads/${r.ref_id}`}>{r.ref_label || `Lead ${r.ref_id}`}</Link> : (r.ref_label || '—')}</td>
                <td style={{ maxWidth: 420 }}>{r.message}</td><td>{r.by || 'System'}</td>
                <td>{r.resolved_at ? <span className="badge badge-green">Resolved {fmtDateTime(r.resolved_at)}</span> : <button className="btn btn-outline btn-sm" onClick={() => resolve(r.id)}>Mark resolved</button>}</td>
              </tr>))}</tbody></table>
            {!d.rows.length && <Empty>No failures.</Empty>}</div>)}
      </div>
    </Layout>)
}
