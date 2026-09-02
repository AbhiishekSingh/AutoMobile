import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import Layout from '../../components/Layout'
import { Empty, Loading, Pager, fmtDateTime } from '../../components/ui'
import api from '../../lib/api'

const EMPTY_WALKIN = {
  full_name: '', phone: '', alt_phone: '', city: '', pincode: '',
  mode_id: '', model_id: '', color: '', lead_type: 'SALES', source: 'WALKIN',
}

// Icon + accent colour for each source tile, keyed by the mode name (lowercased).
// Source tile icon helper — same pattern as PipeIco
function SrcIco({ src, ext = 'svg', w = 20, h = 20, alt = '' }) {
  return (
    <img
      src={`/image/${src}.${ext}`}
      width={w}
      height={h}
      alt={alt}
      style={{ display: 'inline-block', verticalAlign: 'middle', flexShrink: 0 }}
    />
  )
}

const SOURCE_META = {
  total:           { icon: <SrcIco src="lead/01-total-leads"          ext="png" w={20} h={20} alt="total" />,          accent: '#7C3AED' },
  'walk-in':       { icon: <SrcIco src="lead/10-walk-in"        ext="png" w={20} h={20} alt="walk-in" />,        accent: '#059669' },
  hyperlocal:      { icon: <SrcIco src="lead/02-hyperlocal"     ext="png" w={20} h={20} alt="hyperlocal" />,     accent: '#D97706' },
  digital:         { icon: <SrcIco src="lead/03-digital"        ext="png" w={20} h={20} alt="digital" />,        accent: '#2563EB' },
  aggregators:     { icon: <SrcIco src="lead/04-aggregators"    ext="png" w={20} h={20} alt="aggregators" />,   accent: '#DC2626' },
  'dealer digital':{ icon: <SrcIco src="lead/05-dealer-digital" ext="png" w={20} h={20} alt="dealer digital" />, accent: '#2563EB' },
  'cross sell':    { icon: <SrcIco src="lead/06-cross-sell"     ext="png" w={20} h={20} alt="cross sell" />,     accent: '#0EA5E9' },
  activity:        { icon: <SrcIco src="lead/07-activity"       ext="png" w={20} h={20} alt="activity" />,       accent: '#7C3AED' },
  mbo:             { icon: <SrcIco src="lead/08-mbo"            ext="png" w={20} h={20} alt="mbo" />,            accent: '#D97706' },
  'tele-in':       { icon: <SrcIco src="lead/09-tele-in"        ext="png" w={20} h={20} alt="tele-in" />,        accent: '#DB2777' },
}
const sourceMeta = (key) => SOURCE_META[(key || '').toLowerCase()] || { icon: '•', accent: '#64748B' }

// Pipeline icon helper
function PipeIco({ src, w = 20, h = 20, alt = '' }) {
  return (
    <img
      src={`/image/${src}`}
      width={w}
      height={h}
      alt={alt}
      style={{ display: 'inline-block', verticalAlign: 'middle', flexShrink: 0 }}
    />
  )
}

const PIPELINE_META = {
  all:       { icon: <PipeIco src="pipeline/01-all-leads.png"            w={20} h={20} alt="all leads" />,         sub: 'every lead' },
  completed: { icon: <PipeIco src="pipeline/02-completed.png"            w={20} h={20} alt="completed" />,         sub: 'within 3 hrs' },
  pending:   { icon: <PipeIco src="pipeline/03-pending.png"              w={20} h={20} alt="pending" />,           sub: 'not done in 3 hrs' },
  overdue:   { icon: <PipeIco src="pipeline/04-overdue.png"              w={22} h={22} alt="overdue" />,           sub: 'not done in 24 hrs' },
  calllater: { icon: <PipeIco src="pipeline/05-call-later.png"           w={20} h={20} alt="call later" />,        sub: 'next follow-up set' },
  testride:  { icon: <PipeIco src="pipeline/06-test-ride.png"            w={24} h={16} alt="test ride" />,         sub: 'test ride done' },
  casual:    { icon: <PipeIco src="pipeline/07-casual-enquiry.png"       w={18} h={22} alt="casual enquiry" />,    sub: 'based on remark' },
  future:    { icon: <PipeIco src="pipeline/08-future-lead.png"          w={20} h={20} alt="future lead" />,       sub: 'future lead' },
  service:   { icon: <PipeIco src="pipeline/09-service-_-spare-part.png" w={22} h={22} alt="service / spare" />,   sub: 'service / spare' },
  // icon: <PipeIco src="pipeline/10-closed.png" w={20} h={20} alt="closed" />
  closed:    { icon: '🔒', sub: 'closed' },
}
const pipeMeta = (key) => PIPELINE_META[key] || { icon: '•', sub: '' }

// Colour a status/disposition badge by keyword.
function oppClass(name) {
  const n = (name || '').toUpperCase()
  if (n.includes('HOT') || n.includes('LOST')) return 'badge-red'
  if (n.includes('WARM')) return 'badge-amber'
  if (n.includes('BOOKING') || n.includes('DELIVERED') || n.includes('DELIVERY')) return 'badge-green'
  if (n.includes('COLD') || n.includes('FUTURE')) return 'badge-sky'
  if (n.includes('DEAD') || n.includes('CLOSED')) return 'badge-gray'
  return 'badge-gray'
}
function dispClass(name) {
  const n = (name || '').toUpperCase()
  if (n.includes('RINGING')) return 'badge-purple'
  if (n.includes('PLANNING') || n.includes('BOOKING')) return 'badge-green'
  if (n.includes('TEST RIDE')) return 'badge-amber'
  if (n.includes('SWITCH OFF') || n.includes('CANCEL') || n.includes('ISSUE')) return 'badge-red'
  return 'badge-sky'
}
const Badge = ({ name, kind }) =>
  name ? <span className={'badge ' + (kind === 'disp' ? dispClass(name) : oppClass(name))}>{name}</span> : <span style={{ color: '#94A3B8' }}>—</span>

export default function LeadsPage() {
  const nav = useNavigate()
  const [tiles, setTiles] = useState([])
  const [pipeline, setPipeline] = useState([])
  const [lookups, setLookups] = useState(null)

  const [mode, setMode] = useState('total')
  const [bucket, setBucket] = useState('all')
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)
  const [list, setList] = useState(null)

  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState(EMPTY_WALKIN)
  const [msg, setMsg] = useState('')

  const pageSize = 10

  function loadTiles() {
    api.get('/leads/tiles').then((r) => setTiles(r.data)).catch(() => setTiles([]))
    api.get('/leads/pipeline').then((r) => setPipeline(r.data)).catch(() => setPipeline([]))
  }

  useEffect(() => {
    loadTiles()
    api.get('/lookups').then((r) => setLookups(r.data)).catch(() => setLookups(null))
  }, [])

  function loadList() {
    setList(null)
    api.get('/leads', { params: { mode, bucket, search: search || undefined, page, page_size: pageSize } })
      .then((r) => setList(r.data))
      .catch(() => setList({ total: 0, page: 1, page_size: pageSize, rows: [] }))
  }

  // Re-fetch whenever a filter changes — this is what makes the tiles/pipeline clickable.
  useEffect(() => { loadList() }, [mode, bucket, page])

  function pickSource(key) { setMode(key); setPage(1) }
  function pickBucket(key) { setBucket(key); setPage(1) }
  function clearFilters() { setMode('total'); setBucket('all'); setSearch(''); setPage(1) }
  function submitSearch(e) { e.preventDefault(); setPage(1); loadList() }

  const setF = (k) => (e) => setForm({ ...form, [k]: e.target.value })

  async function addWalkin(e) {
    e.preventDefault()
    setMsg('')
    try {
      const payload = {
        ...form,
        mode_id: form.mode_id ? Number(form.mode_id) : null,
        model_id: form.model_id ? Number(form.model_id) : null,
      }
      const { data } = await api.post('/leads', payload)
      setMsg(`Lead ${data.enquiry_no} created.`)
      setForm(EMPTY_WALKIN); setShowForm(false)
      loadTiles(); setPage(1); loadList()
    } catch (err) {
      setMsg(err.response?.data?.detail || 'Could not create lead.')
    }
  }

  // Export the current filtered result set to CSV (fetches all matching rows, not just this page).
  async function exportCsv() {
    try {
      const { data } = await api.get('/leads', { params: { mode, bucket, search: search || undefined, page: 1, page_size: 100000 } })
      const rows = data.rows || []
      const head = ['Enquiry No', 'Enquiry Date', 'Enquiry Mode', 'Customer', 'Contact', 'Model', 'Opportunity Status', 'Disposition', 'SLA']
      const body = rows.map((l) => [
        l.enquiry_no, l.enquiry_at || '', l.enquiry_mode || '', l.customer_name || '',
        l.contact_masked || '', l.model_name || '', l.opportunity_status || '', l.disposition || '', l.sla_flag || '',
      ])
      const csv = [head, ...body].map((r) => r.map((c) => `"${String(c).replace(/"/g, '""')}"`).join(',')).join('\n')
      const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv' }))
      const a = document.createElement('a')
      a.href = url; a.download = 'leads.csv'; a.click()
      URL.revokeObjectURL(url)
    } catch { /* ignore */ }
  }

  const activeSourceLabel = tiles.find((t) => t.key === mode)?.label
  const activeBucketLabel = pipeline.find((p) => p.key === bucket)?.label
  const filtering = mode !== 'total' || bucket !== 'all' || !!search

  return (
    <Layout title="Lead Management" sub="Enquiry sources, pipeline & all leads">
      {/* ---------- source tiles (counts from DB) ---------- */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(210px, 1fr))', gap: 14 }}>
        {tiles.map((t) => {
          const meta = sourceMeta(t.key)
          const active = mode === t.key
          return (
            <div key={t.key} onClick={() => pickSource(t.key)}
              style={{
                background: '#fff', borderRadius: 14, padding: '16px 18px', cursor: 'pointer',
                boxShadow: '0 1px 2px rgba(16,24,40,.06)',
                border: active ? `2px solid ${meta.accent}` : '1px solid #E9EEF5',
              }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <span style={{
                  width: 40, height: 40, borderRadius: 10, display: 'inline-flex',
                  alignItems: 'center', justifyContent: 'center', fontSize: 20, background: `${meta.accent}1A`,
                }}>{meta.icon}</span>
                <span style={{ fontSize: 12, fontWeight: 700, letterSpacing: '.03em', color: '#64748B', textTransform: 'uppercase' }}>
                  {t.label}
                </span>
              </div>
              <div style={{ fontSize: 30, fontWeight: 800, color: '#0F172A', marginTop: 8 }}>
                {(t.count ?? 0).toLocaleString('en-IN')}
              </div>
              <div style={{ height: 3, width: 46, borderRadius: 3, background: meta.accent, marginTop: 8 }} />
            </div>
          )
        })}
        {tiles.length === 0 && <Empty>No source data yet.</Empty>}
      </div>

      {/* ---------- pipeline (counts from DB) ---------- */}
      <div className="card" style={{ marginTop: 18 }}>
        <div className="card-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h3>Pipeline <span className="muted-note">· click a status to filter the table below</span></h3>
          <button className="btn btn-primary btn-sm" onClick={() => setShowForm((s) => !s)}>
            {showForm ? 'Close' : '+ Add Walk-in'}
          </button>
        </div>
        <div className="card-pad" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(150px, 1fr))', gap: 12 }}>
          {pipeline.map((p) => {
            const meta = pipeMeta(p.key)
            const active = bucket === p.key
            return (
              <div key={p.key} onClick={() => pickBucket(p.key)}
                style={{
                  borderRadius: 12, padding: '14px 14px', cursor: 'pointer', background: active ? '#EFF4FF' : '#F8FAFC',
                  border: active ? '2px solid #2563EB' : '1px solid #E9EEF5',
                }}>
                <div style={{ fontSize: 12, fontWeight: 700, color: '#475569', display: 'flex', alignItems: 'center', gap: 6 }}>{meta.icon} {p.label}</div>
                <div style={{ fontSize: 24, fontWeight: 800, color: '#0F172A', marginTop: 4 }}>
                  {(p.count ?? 0).toLocaleString('en-IN')}
                </div>
                {meta.sub && <div style={{ fontSize: 11, color: '#94A3B8', marginTop: 2 }}>{meta.sub}</div>}
              </div>
            )
          })}
          {pipeline.length === 0 && <Empty>No pipeline data yet.</Empty>}
        </div>
      </div>

      {/* ---------- add walk-in ---------- */}
      {showForm && (
        <div className="card" style={{ marginTop: 16 }}>
          <div className="card-header"><h3>New Walk-in Lead</h3></div>
          <form className="card-pad" onSubmit={addWalkin}>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 14 }}>
              <div className="field"><label>Full name *</label>
                <input className="input" value={form.full_name} onChange={setF('full_name')} required /></div>
              <div className="field"><label>Mobile *</label>
                <input className="input" value={form.phone} onChange={setF('phone')} required /></div>
              <div className="field"><label>Alt. mobile</label>
                <input className="input" value={form.alt_phone} onChange={setF('alt_phone')} /></div>
              <div className="field"><label>City</label>
                <input className="input" value={form.city} onChange={setF('city')} /></div>
              <div className="field"><label>Pincode</label>
                <input className="input" value={form.pincode} onChange={setF('pincode')} /></div>
              <div className="field"><label>Enquiry mode</label>
                <select className="input" value={form.mode_id} onChange={setF('mode_id')}>
                  <option value="">— select —</option>
                  {lookups?.enquiry_modes?.map((mm) => <option key={mm.id} value={mm.id}>{mm.name}</option>)}
                </select></div>
              <div className="field"><label>Model interested</label>
                <select className="input" value={form.model_id} onChange={setF('model_id')}>
                  <option value="">— select —</option>
                  {lookups?.models?.map((mm) => <option key={mm.id} value={mm.id}>{mm.name}</option>)}
                </select></div>
              <div className="field"><label>Colour</label>
                <input className="input" value={form.color} onChange={setF('color')} /></div>
              <div className="field"><label>Lead type</label>
                <select className="input" value={form.lead_type} onChange={setF('lead_type')}>
                  <option value="SALES">SALES</option>
                  <option value="SERVICE">SERVICE</option>
                </select></div>
            </div>
            <div style={{ marginTop: 14, display: 'flex', gap: 10 }}>
              <button type="button" className="btn btn-outline" onClick={() => { setShowForm(false); setForm(EMPTY_WALKIN) }}>Cancel</button>
              <button className="btn btn-primary">Create lead</button>
            </div>
            {msg && <div className="hint" style={{ marginTop: 12 }}>{msg}</div>}
          </form>
        </div>
      )}

      {/* ---------- all leads table (rows from DB) ---------- */}
      <div className="card" style={{ marginTop: 16 }}>
        <div className="card-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
          <h3>All Leads {list && <span className="muted-note">({list.total})</span>}</h3>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <form onSubmit={submitSearch} style={{ display: 'flex', gap: 8 }}>
              <input className="input" style={{ maxWidth: 260 }} placeholder="Search by name, contact no. or enquiry"
                     value={search} onChange={(e) => setSearch(e.target.value)} />
              <button className="btn btn-outline btn-sm">Search</button>
            </form>
            <button className="btn btn-outline btn-sm" onClick={exportCsv}>↓ Export</button>
          </div>
        </div>

        {filtering && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '10px 16px', flexWrap: 'wrap' }}>
            <span style={{ fontSize: 12, color: '#64748B', fontWeight: 600 }}>Filtered by:</span>
            {mode !== 'total' && <span className="badge badge-sky">Source: {activeSourceLabel || mode}</span>}
            {bucket !== 'all' && <span className="badge badge-sky">Status: {activeBucketLabel || bucket}</span>}
            {search && <span className="badge badge-sky">Search: “{search}”</span>}
            <button className="btn btn-outline btn-sm" onClick={clearFilters}>Clear all</button>
          </div>
        )}

        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Enquiry No</th><th>Enquiry Date</th><th>Enquiry Mode</th><th>Customer Name</th>
                <th>Contact No</th><th>Model Name</th><th>Opportunity Sts</th><th>Followup Disposition</th><th>Details</th>
              </tr>
            </thead>
            <tbody>
              {list?.rows?.map((l) => (
                <tr key={l.lead_id}>
                  <td className="cell-muted">{l.enquiry_no}</td>
                  <td>{fmtDateTime(l.enquiry_at)}</td>
                  <td>{l.enquiry_mode || '—'}</td>
                  <td className="cell-primary">{l.customer_name}</td>
                  <td className="cell-muted">{l.contact_masked}</td>
                  <td>{l.model_name || '—'}</td>
                  <td><Badge name={l.opportunity_status} /></td>
                  <td><Badge name={l.disposition} kind="disp" /></td>
                  <td><button className="btn btn-outline btn-sm" title="View details" onClick={() => nav(`/leads/${l.lead_id}`)}>👁</button></td>
                  {/* <td><button className="btn btn-outline btn-sm" title="View details" onClick={() => nav(`/leads/${l.lead_id}`)}><img src="/image/eye.svg" width={16} height={12} alt="view" style={{ display: 'inline-block', verticalAlign: 'middle' }} /></button></td> */}
                </tr>
              ))}
            </tbody>
          </table>
          {!list && <Loading />}
          {list && list.rows.length === 0 && <Empty>No leads match this filter.</Empty>}
        </div>
        {list && <Pager total={list.total} page={page} pageSize={pageSize} onPage={setPage} />}
      </div>
    </Layout>
  )
}