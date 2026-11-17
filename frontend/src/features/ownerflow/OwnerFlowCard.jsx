// Owner Portal workflow for one lead: shows every stage's status (visible to Owner, GM, PBA, CRE, Admin)
// and gives the Owner the two decision forms (initial + final). Rejection remark is mandatory.
// All rules are enforced by the server (app/modules/owner_flow/service.py).
import { useEffect, useState } from 'react'
import api from '../../lib/api'
import { useAuth } from '../../lib/auth'
import { errText, fmtDateTime } from '../../components/ui'

const rupees = (v) => (v === null || v === undefined || v === '') ? '—' : `₹ ${Number(v).toLocaleString('en-IN')}`
const TONE = { APPROVED: 'badge-green', DONE: 'badge-green', COMPLETED: 'badge-green', REGISTERED: 'badge-green', ENABLED: 'badge-green',
               PENDING: 'badge-amber', IN_PROGRESS: 'badge-amber', IN_PROCESS: 'badge-amber', REJECTED: 'badge-red', LOCKED: 'badge-gray' }
const pretty = (s) => (s || '').replace(/_/g, ' ').toLowerCase().replace(/^\w/, (c) => c.toUpperCase())
const Pill = ({ k, v }) => (<div style={{ minWidth: 110 }}><div className="muted-note">{k}</div>
  <span className={'badge ' + (TONE[v] || 'badge-gray')}>{v ? pretty(v) : 'Not started'}</span></div>)
const Row = ({ k, v }) => (<div><div className="muted-note">{k}</div><div style={{ fontWeight: 600 }}>{v ?? '—'}</div></div>)
const Grid = ({ children }) => (<div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(190px, 1fr))', gap: 12, alignItems: 'end', marginBottom: 12 }}>{children}</div>)
const YesNo = ({ label, value, onChange }) => (
  <div><div className="muted-note">{label}</div>
    <div style={{ display: 'flex', gap: 6 }}>{[[true, 'YES'], [false, 'NO']].map(([v, l]) => (
      <button type="button" key={l} className={'btn btn-sm ' + (value === v ? 'btn-primary' : 'btn-outline')} onClick={() => onChange(v)}>{l}</button>))}</div></div>)

export default function OwnerFlowCard({ leadId, onChanged }) {
  const { user } = useAuth()
  const role = user?.role
  const [d, setD] = useState(null)
  const [msg, setMsg] = useState(null)
  const [busy, setBusy] = useState(false)
  const [f, setF] = useState({ price: '', cp: null, atw: null, remark: '' })
  const [fr, setFr] = useState('')
  const [changing, setChanging] = useState(false)   // Owner pressed 'Change decision' on an already-decided initial approval
  const [rerr, setRerr] = useState('')      // 'remark needed' message for the reject buttons

  function load() { api.get(`/leads/${leadId}/owner-flow`).then((r) => { setD(r.data); setF((x) => ({ ...x, price: x.price || r.data.initial?.discounted_price || '' })) }).catch(() => setD(false)) }
  useEffect(load, [leadId])
  async function run(call, ok) {
    setBusy(true); setMsg(null)
    try { const r = await call(); setD(r.data); setChanging(false); setMsg({ type: 'ok', text: ok }); onChanged && onChanged() }
    catch (e) { setMsg({ type: 'error', text: errText(e) }) }
    finally { setBusy(false) }
  }
  function reject(url, remark, ok) {
    if (!remark.trim()) { setRerr('To reject, first write the reason in the red Remark box, then press Reject again.'); return }
    setRerr(''); run(() => api.post(url, { approve: false, remark }), ok)
  }
  async function openPolicy() {
    try { const res = await api.get(`/leads/${leadId}/insurance/policy.pdf`, { responseType: 'blob' })
      const url = URL.createObjectURL(res.data); window.open(url, '_blank', 'noopener'); setTimeout(() => URL.revokeObjectURL(url), 60000)
    } catch { setMsg({ type: 'error', text: 'Could not open the policy.' }) }
  }

  if (!d) return null
  if (d.workflow.current === 'NO_BOOKING') return (   // no booking yet: explain instead of a blank tab
    <div className="card"><div className="card-pad">
      <b>Approvals &amp; delivery have not started yet</b>
      <div className="muted-note" style={{ marginTop: 6 }}>They begin after the booking: Owner approval of the price, payment and documents, insurance, final approval, RTO and then delivery. The journey bar above shows where this customer is now.</div>
    </div></div>)
  const W = d.workflow, S = W.stages, I = d.initial, Fn = d.final, P = d.payment, isOwner = role === 'OWNER', isPba = role === 'PBA'
  const canRedecideInitial = isOwner && I && !d.insurance
  const flash = (rerr || msg) && (<div className="hint" style={{ margin: '10px 0', ...(rerr || msg.type === 'error' ? { background: 'var(--red-light)', color: '#7a2318' } : {}) }}>{rerr || msg.text}</div>)

  return (
    <div className="card" style={{ marginBottom: 16 }}>
      <div className="card-header"><h3>Owner approval workflow <span className="muted-note">· {W.label}</span></h3></div>
      <div className="card-pad">
        {flash}
        <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap', marginBottom: 14 }}>
          <Pill k="1 Initial approval" v={S.initial} /><Pill k="2 Payment (DP / full)" v={S.payment} /><Pill k="3 Documents" v={S.documents} />
          <Pill k="4 Insurance" v={S.insurance} /><Pill k="5 Final approval" v={S.final} /><Pill k="6 RTO" v={S.rto} /><Pill k="7 Delivery challan" v={S.challan} />
        </div>

        <h4 style={{ margin: '4px 0 8px' }}>Initial approval {I && I.round > 1 ? `(round ${I.round})` : ''}</h4>
        <Grid>
          <Row k="Bike price (on-road)" v={rupees(d.bike_price)} />
          <Row k="Approved discounted price" v={I?.status === 'APPROVED' ? rupees(I.discounted_price) : '—'} />
          <Row k="Customer processing" v={I?.customer_processing == null ? '—' : I.customer_processing ? 'YES' : 'NO'} />
          <Row k="ATW" v={I?.atw_allowed == null ? '—' : I.atw_allowed ? 'YES' : 'NO'} />
          <Row k="Decided by" v={I?.decided_by ? `${I.decided_by} · ${fmtDateTime(I.decided_at)}` : null} />
        </Grid>
        {I?.status === 'REJECTED' && <div className="hint">Rejected: {I.remark}</div>}
        {I?.status === 'APPROVED' && !I.customer_processing && <div className="hint">Customer processing is NO — the file will not move to Insurance.</div>}
        {isPba && I?.status === 'REJECTED' && (<button className="btn btn-outline btn-sm" disabled={busy}
          onClick={() => run(() => api.post(`/leads/${leadId}/owner-flow/initial/resubmit`), 'Sent to the Owner again.')}>Send to Owner again</button>)}
        {canRedecideInitial && I?.status !== 'PENDING' && !changing && (
          <button type="button" className="btn btn-outline btn-sm" style={{ marginTop: 8 }} onClick={() => { setF({ price: I.discounted_price || '', cp: I.customer_processing ?? null, atw: I.atw_allowed ?? null, remark: '' }); setChanging(true) }}>Change decision</button>)}
        {(I?.status === 'PENDING' || (canRedecideInitial && changing)) && isOwner && (
          <div style={{ border: '1px solid var(--border, #ddd)', borderRadius: 8, padding: 12, marginTop: 8 }}>
            <Grid>
              <div><div className="muted-note">Approved discounted price (₹)</div>
                <input className="input" type="number" value={f.price} onChange={(e) => setF({ ...f, price: e.target.value })} /></div>
              <YesNo label="Customer processing" value={f.cp} onChange={(v) => setF({ ...f, cp: v })} />
              <YesNo label="ATW (10-yr engine warranty)" value={f.atw} onChange={(v) => setF({ ...f, atw: v })} />
            </Grid>
            <div className="muted-note" style={rerr ? { color: '#b3261e', fontWeight: 600 } : {}}>Remark — required only when rejecting</div>
            <input className="input" placeholder="Reason for rejection" value={f.remark} onChange={(e) => { setF({ ...f, remark: e.target.value }); setRerr('') }} style={{ marginBottom: 8, ...(rerr ? { borderColor: '#d64545', background: '#fff5f5' } : {}) }} />
            <div style={{ display: 'flex', gap: 8 }}>
              <button className="btn btn-primary btn-sm" disabled={busy} onClick={() => run(() => api.post(`/leads/${leadId}/owner-flow/initial/decision`,
                { approve: true, discounted_price: f.price ? Number(f.price) : null, customer_processing: f.cp, atw_allowed: f.atw, remark: f.remark }), 'Initial approval saved.')}>Approve</button>
              <button className="btn btn-outline btn-sm" disabled={busy} onClick={() => reject(`/leads/${leadId}/owner-flow/initial/decision`, f.remark, 'Rejected. The PBA has been notified.')}>Reject</button>
              {changing && <button className="btn btn-outline btn-sm" disabled={busy} onClick={() => { setChanging(false); setRerr('') }}>Cancel</button>}
            </div>
          </div>)}

        <h4 style={{ margin: '18px 0 8px' }}>PBA: payment &amp; documents</h4>
        <Grid>
          <Row k={P.kind === 'DOWN_PAYMENT' ? 'Down payment required' : 'Full payment required'} v={rupees(P.required)} />
          <Row k="Paid by customer" v={rupees(P.paid_by_customer)} />
          <Row k="Finance disbursed" v={`${rupees(P.finance_received)}${P.finance_bank ? ' · ' + P.finance_bank : ''}`} />
          <Row k="Outstanding" v={rupees(P.outstanding)} />
          <Row k="Documents" v={d.documents.ok ? 'Complete' : 'Missing: ' + d.documents.missing.join(', ')} />
        </Grid>
        {S.insurance == null && I?.status === 'APPROVED' && I.customer_processing && <div className="hint">Waiting for the PBA — the file moves to Insurance automatically once the payment and all documents are in.</div>}

        <h4 style={{ margin: '18px 0 8px' }}>Final approval {Fn && Fn.round > 1 ? `(round ${Fn.round})` : ''}</h4>
        {!Fn && <div className="muted-note">Starts when Insurance uploads the policy PDF.</div>}
        {Fn && (<>
          <Grid>
            <Row k="Bike price / discounted" v={`${rupees(d.bike_price)} / ${rupees(d.discounted_price)}`} />
            <Row k="Policy" v={d.insurance ? `${d.insurance.company || ''} ${d.insurance.policy_no || ''}` : null} />
            <Row k="ATW" v={d.atw.quoted ? (d.atw.status ? pretty(d.atw.status) : 'Pending') : 'Not quoted'} />
            <Row k="RTO" v={d.rto ? pretty(d.rto.status) + (d.rto.registration_no ? ' · ' + d.rto.registration_no : '') : 'Not yet'} />
            <Row k="Decided by" v={Fn.decided_by ? `${Fn.decided_by} · ${fmtDateTime(Fn.decided_at)}` : null} />
          </Grid>
          {d.insurance?.has_pdf && <button className="btn btn-outline btn-sm" onClick={openPolicy} style={{ marginBottom: 10 }}>View policy PDF</button>}
          {Fn.status === 'REJECTED' && <div className="hint">Rejected: {Fn.remark}</div>}
          {isPba && Fn.status === 'REJECTED' && (<button className="btn btn-outline btn-sm" disabled={busy}
            onClick={() => run(() => api.post(`/leads/${leadId}/owner-flow/final/resubmit`), 'Sent to the Owner again.')}>Send to Owner again</button>)}
          {isOwner && Fn.status === 'PENDING' && (
            <div style={{ border: '1px solid var(--border, #ddd)', borderRadius: 8, padding: 12 }}>
              <div className="muted-note" style={rerr ? { color: '#b3261e', fontWeight: 600 } : {}}>Remark — required only when rejecting</div>
              <input className="input" placeholder="Reason for rejection" value={fr} onChange={(e) => { setFr(e.target.value); setRerr('') }} style={{ marginBottom: 8, ...(rerr ? { borderColor: '#d64545', background: '#fff5f5' } : {}) }} />
              <div style={{ display: 'flex', gap: 8 }}>
                <button className="btn btn-primary btn-sm" disabled={busy} onClick={() => run(() => api.post(`/leads/${leadId}/owner-flow/final/decision`, { approve: true, remark: fr }), 'Approved. The file is now with the RTO.')}>Final approve</button>
                <button className="btn btn-outline btn-sm" disabled={busy} onClick={() => reject(`/leads/${leadId}/owner-flow/final/decision`, fr, 'Rejected. The PBA has been notified.')}>Reject</button>
              </div>
            </div>)}
        </>)}
      </div>
    </div>
  )
}
