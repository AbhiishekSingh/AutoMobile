// Insurance team home: a friendly "who is waiting for you" banner, the 8 counts as clickable filter chips, and one card per
// customer with 3 progress dots (Docs / Nominee / Policy) and ONE button (Start / Continue / View). Click a card to open the case.
import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../../lib/api'
import Layout from '../../components/Layout'
import { Empty, Loading, fmtDate } from '../../components/ui'

// chip -> what it filters (server filters go to the API; `only` is applied here on the loaded list)
const CHIPS = [
  { k: 'total', label: 'Booked', set: {} },
  { k: 'pending', label: 'Pending', set: { status: 'PENDING' } },
  { k: 'documents_pending', label: 'Documents pending', set: {}, only: (r) => r.status !== 'COMPLETED' && r.document_status !== 'COMPLETE' },
  { k: 'in_progress', label: 'In progress', set: { status: 'IN_PROGRESS' } },
  { k: 'completed', label: 'Completed', set: { status: 'COMPLETED' } },
  { k: 'pdf_not_uploaded', label: 'PDF missing', set: {}, only: (r) => !r.pdf_uploaded },
  { k: 'pba_notification_pending', label: 'PBA not notified', set: {}, only: (r) => r.status === 'COMPLETED' && !r.pba_notified },
  { k: 'whatsapp_failed', label: 'WhatsApp failed', set: {}, only: (r) => r.whatsapp_status === 'FAILED' },
]
const ST = { PENDING: ['Pending', '#eef0f4', '#6b7686'], IN_PROGRESS: ['In progress', '#fff1d6', '#8a5a00'], COMPLETED: ['Completed', '#e3f5ea', '#17673a'] }
const WA = { NOT_SENT: 'Not sent', PENDING: 'Pending', SENT: 'Sent', DELIVERED: 'Delivered', READ: 'Read', FAILED: 'Failed' }

function Dot({ done, label }) {
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
      <span style={{ width: 22, height: 22, borderRadius: 11, display: 'inline-flex', alignItems: 'center', justifyContent: 'center', fontSize: 11, fontWeight: 700,
                     background: done ? '#1f8a4c' : '#fff', color: '#fff', border: done ? 'none' : '2px solid #cfd5de' }}>{done ? '✓' : ''}</span>
      <span style={{ fontSize: 12, color: '#6b7686' }}>{label}</span>
    </span>)
}
const Line = () => <span style={{ width: 14, height: 2, background: '#d5dae2', display: 'inline-block' }} />

const policyShort = (l) => l || 'Not selected'

// responsive card: one row on a wide screen; on a laptop the progress dots drop to their own row under the details
const CSS = `
.ins-wrap{container-type:inline-size}
.ins-card{padding:14px 18px;margin-bottom:10px;cursor:pointer;display:grid;gap:10px 16px;align-items:center;
  grid-template-columns:minmax(0,1.5fr) minmax(0,1.1fr) auto minmax(0,1.1fr) auto;grid-template-areas:"who pol prog st act"}
.ins-card .who{grid-area:who;min-width:0}.ins-card .pol{grid-area:pol;min-width:0}.ins-card .prog{grid-area:prog}.ins-card .st{grid-area:st;min-width:0}.ins-card .act{grid-area:act;text-align:right}
.ins-card .nm{font-weight:700;font-size:15px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
@container (max-width: 1180px){
  .ins-card{grid-template-columns:minmax(0,1.4fr) minmax(0,1fr) minmax(0,1fr) auto;grid-template-areas:"who pol st act" "prog prog prog prog"}
  .ins-card .prog{padding-top:10px;border-top:1px solid #eef0f4}
}
@container (max-width: 700px){
  .ins-card{grid-template-columns:1fr auto;grid-template-areas:"who act" "pol pol" "st st" "prog prog"}
}`

function steps(r) {
  return { docs: r.document_status === 'COMPLETE', nominee: r.nominee_status === 'COMPLETE', policy: r.status === 'COMPLETED' || (!!r.policy_no && r.pdf_uploaded) }
}
function hint(r) {
  const s = steps(r)
  if (r.status === 'COMPLETED') {
    if (r.whatsapp_status === 'FAILED') return 'WhatsApp failed'
    if (['SENT', 'DELIVERED', 'READ'].includes(r.whatsapp_status)) return 'PDF sent on WhatsApp'
    return r.pba_notified ? 'PBA notified' : 'PBA notification pending'
  }
  if (r.document_status === 'NO_POLICY_TYPE') return 'Select the policy type'
  if (!s.docs) return 'Documents pending'
  if (!s.nominee) return 'Nominee details pending'
  if (!r.policy_no) return 'Add policy details'
  return 'Missing: policy PDF'
}

export default function InsuranceDashboardPage() {
  const nav = useNavigate()
  const [kpi, setKpi] = useState(null)
  const [rows, setRows] = useState(null)
  const [pbas, setPbas] = useState([])
  const [chip, setChip] = useState('total')
  const [more, setMore] = useState(false)
  const [f, setF] = useState({ q: '', status: '', customer_type: '', policy_type: '', pba_id: '', document_status: '', date_from: '', date_to: '' })
  useEffect(() => { api.get('/insurance/dashboard').then((r) => setKpi(r.data)).catch(() => setKpi({})); api.get('/insurance/pbas').then((r) => setPbas(r.data)).catch(() => {}) }, [])
  useEffect(() => {
    const params = Object.fromEntries(Object.entries(f).filter(([, v]) => v))
    api.get('/insurance/cases', { params }).then((r) => setRows(r.data)).catch(() => setRows([]))
  }, [f])
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value })
  const pick = (c) => { setChip(c.k); setF({ ...f, status: '', document_status: '', ...c.set }) }
  const only = CHIPS.find((c) => c.k === chip)?.only
  const shown = useMemo(() => (rows || []).filter((r) => (only ? only(r) : true)), [rows, only])

  // banner: the customers still needing work; start with one whose documents are missing
  const waiting = (rows || []).filter((r) => r.status !== 'COMPLETED')
  const first = waiting.find((r) => r.document_status !== 'COMPLETE') || waiting[0]

  return (
    <Layout title="Insurance" sub="Booked customers waiting for insurance">
      <style>{CSS}</style>
      <div className="card" style={{ padding: '16px 20px', marginBottom: 16, display: 'flex', gap: 14, alignItems: 'center', background: '#eef4ff', borderColor: '#cfe0fb', flexWrap: 'wrap' }}>
        <span style={{ fontSize: 26 }}>{waiting.length ? '👋' : '🎉'}</span>
        <div>
          <b>{rows === null ? 'Loading…' : waiting.length ? `${waiting.length} customer${waiting.length > 1 ? 's are' : ' is'} waiting for you` : 'All caught up — no customer is waiting'}</b>
          <div className="muted-note">{waiting.length ? 'Start with the ones whose documents are still missing.' : 'New booked customers appear here automatically.'}</div>
        </div>
        {first && <button className="btn btn-primary" style={{ marginLeft: 'auto' }} onClick={() => nav(`/insurance/${first.lead_id}`)}>Start with {first.customer_name} →</button>}
      </div>

      {kpi && (() => {
        const total = kpi.total || 0, done = kpi.completed || 0, waitN = total - done
        const attn = (kpi.pba_notification_pending || 0) + (kpi.whatsapp_failed || 0)
        const pct = total ? Math.round((done / total) * 100) : 0
        const tile = (k, label, n, color, hint) => (
          <button key={k} type="button" onClick={() => pick(CHIPS.find((c) => c.k === k))}
            style={{ flex: '1 1 150px', textAlign: 'left', border: 0, background: 'none', cursor: 'pointer', padding: '2px 18px', borderLeft: '1px solid #eef0f4' }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: '#6b7686', letterSpacing: '.04em', textTransform: 'uppercase' }}>{label}</div>
            <div style={{ fontSize: 26, fontWeight: 800, color, lineHeight: 1.2 }}>{n}</div>
            <div className="muted-note" style={{ fontSize: 11.5 }}>{hint}</div>
          </button>)
        return (
          <div className="card" style={{ padding: '14px 4px', marginBottom: 14 }}>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10, alignItems: 'stretch' }}>
              {tile('total', 'Booked', total, '#1c2740', 'all customers')}
              {tile('documents_pending', 'Documents pending', kpi.documents_pending || 0, '#8a5a00', 'waiting on documents')}
              {tile('in_progress', 'In progress', kpi.in_progress || 0, '#2459c4', `${kpi.pending || 0} not started`)}
              {tile('completed', 'Completed', done, '#17673a', `${pct}% done`)}
              {tile(attn ? (kpi.whatsapp_failed ? 'whatsapp_failed' : 'pba_notification_pending') : 'completed', 'Needs attention', attn, attn ? '#b3261e' : '#17673a', attn ? 'PBA not notified / WhatsApp failed' : 'nothing stuck')}
            </div>
            <div style={{ margin: '12px 18px 0', height: 6, borderRadius: 99, background: '#eef0f4', overflow: 'hidden' }} title={`${done} of ${total} completed`}>
              <div style={{ width: `${pct}%`, height: '100%', background: '#1f8a4c' }} />
            </div>
          </div>)
      })()}

      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 12 }}>
        {CHIPS.map((c) => (
          <button key={c.k} type="button" onClick={() => pick(c)}
            style={{ border: 0, cursor: 'pointer', padding: '5px 11px', borderRadius: 99, fontSize: 12, fontWeight: 700,
                     background: chip === c.k ? '#e6f0ff' : '#eef0f4', color: chip === c.k ? '#2459c4' : '#6b7686' }}>
            {c.label} · {kpi ? (kpi[c.k] ?? 0) : '…'}</button>))}
      </div>

      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginBottom: 16, alignItems: 'center' }}>
        <input className="input" style={{ maxWidth: 320, flex: '1 1 220px' }} placeholder="🔍 Search name, mobile, booking or policy no." value={f.q} onChange={set('q')} />
        <select className="input" style={{ maxWidth: 170 }} value={f.customer_type} onChange={set('customer_type')}><option value="">All customer types</option>
          <option value="MBO">MBO</option><option value="CUSTOMER">Customer</option></select>
        <select className="input" style={{ maxWidth: 190 }} value={f.policy_type} onChange={set('policy_type')}><option value="">All policy types</option>
          <option value="ACKO">ACKO</option><option value="BAGIC">BAGIC (Bajaj General)</option><option value="NATIONAL">National Insurance</option><option value="POLICYBAZAR">Policy Bazar</option></select>
        <select className="input" style={{ maxWidth: 170 }} value={f.pba_id} onChange={set('pba_id')}><option value="">All PBAs</option>
          {pbas.map((p) => <option key={p.user_id} value={p.user_id}>{p.full_name}</option>)}</select>
        <button type="button" className="btn btn-outline btn-sm" onClick={() => setMore((v) => !v)}>{more ? 'Fewer filters ▴' : 'More filters ▾'}</button>
        {more && (<>
          <input className="input" type="date" style={{ maxWidth: 150 }} value={f.date_from} onChange={set('date_from')} title="Booked from" />
          <input className="input" type="date" style={{ maxWidth: 150 }} value={f.date_to} onChange={set('date_to')} title="Booked to" /></>)}
      </div>

      {rows === null && <Loading />}
      {rows && shown.length === 0 && <Empty>No customers match.</Empty>}
      <div className="ins-wrap">
      {shown.map((r) => {
        const s = steps(r), done = r.status === 'COMPLETED', started = s.docs || s.nominee || !!r.policy_no
        const [stLabel, stBg, stFg] = ST[r.status] || ST.PENDING
        return (
          <div key={r.lead_id} className="card ins-card" onClick={() => nav(`/insurance/${r.lead_id}`)}>
            <div className="who">
              <div className="nm" title={r.customer_name}>{r.customer_name}</div>
              <div className="muted-note" style={{ marginTop: 2 }}>{r.mobile} · {r.model || '—'}</div>
              <div className="muted-note" style={{ marginTop: 1 }}>PBA {r.pba_name || '—'}{r.booking_no ? ` · ${r.booking_no}` : ''}{r.booking_date ? ` · ${fmtDate(r.booking_date)}` : ''}</div>
            </div>
            <div className="pol">
              <div className="muted-note" style={{ fontSize: 11 }}>POLICY</div>
              <div style={{ fontWeight: 600 }}>{policyShort(r.policy_type_label)}</div>
              {r.policy_no && <div className="muted-note" style={{ fontSize: 12 }}>No. {r.policy_no}</div>}
            </div>
            <div className="prog" style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
              <Dot done={s.docs} label="Docs" /><Line /><Dot done={s.nominee} label="Nominee" /><Line /><Dot done={s.policy} label="Policy" />
            </div>
            <div className="st">
              <span style={{ display: 'inline-block', padding: '3px 11px', borderRadius: 99, fontSize: 12, fontWeight: 700, background: stBg, color: stFg }}>{stLabel}</span>
              <div className="muted-note" style={{ fontSize: 12, marginTop: 4, ...(hint(r) === 'WhatsApp failed' ? { color: '#b3261e', fontWeight: 600 } : {}) }}>{hint(r)}</div>
              {done && <div className="muted-note" style={{ fontSize: 11.5 }}>PBA notified: {r.pba_notified ? 'Yes' : 'Pending'} · WhatsApp: {WA[r.whatsapp_status]}</div>}
            </div>
            <div className="act">
              <button type="button" className={'btn btn-sm ' + (done ? 'btn-outline' : 'btn-primary')} onClick={(e) => { e.stopPropagation(); nav(`/insurance/${r.lead_id}`) }}>
                {done ? 'View' : started ? 'Continue' : 'Start'}</button>
            </div>
          </div>)
      })}
      </div>
    </Layout>
  )
}
