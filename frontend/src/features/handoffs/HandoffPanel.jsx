// Insurance → RTO → Owner approval → ATW, for one lead. The same panel is used on the
// PBA/CRE lead page and on the Owner / RTO detail page; what each role can DO is decided by
// the role (and re-checked by the server — see app/modules/handoffs/router.py).
import { useEffect, useState } from 'react'
import api from '../../lib/api'
import { useAuth } from '../../lib/auth'
import { fmtDate, fmtDateTime } from '../../components/ui'

const BADGE = { PENDING: 'badge-gray', IN_PROGRESS: 'badge-amber', IN_PROCESS: 'badge-amber',
                COMPLETED: 'badge-green', REGISTERED: 'badge-green', APPROVED: 'badge-green', REJECTED: 'badge-red' }
const pretty = (s) => (s || '').replace(/_/g, ' ').toLowerCase().replace(/^\w/, (c) => c.toUpperCase())
const rupees = (v) => (v === null || v === undefined || v === '') ? '—' : `₹ ${Number(v).toLocaleString('en-IN')}`
const today = () => new Date(Date.now() + 330 * 60 * 1000).toISOString().slice(0, 10)
const Grid = ({ children }) => (
  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(190px, 1fr))', gap: 12, alignItems: 'end' }}>{children}</div>)
const Row = ({ k, v }) => (<div><div className="muted-note">{k}</div><div style={{ fontWeight: 600 }}>{v || '—'}</div></div>)

export default function HandoffPanel({ leadId, onChanged }) {
  const { user } = useAuth()
  const role = user?.role
  const [p, setP] = useState(null)
  const [msg, setMsg] = useState(null)
  const [ins, setIns] = useState({})
  const [pol, setPol] = useState({ policy_no: '', policy_start: '', policy_expiry: '', premium: '' })
  const [polFile, setPolFile] = useState(null)
  const [rto, setRto] = useState({})
  const [ask, setAsk] = useState({ items: [], note: '', delivery_date: '' })
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  const [inv, setInv] = useState({})
  const [invFile, setInvFile] = useState(null)
  const [invRead, setInvRead] = useState(null)      // result of reading the invoice PDF
  async function pickInvoice(file) {
    setInvFile(file); setInvRead(null)
    if (!file || !file.name.toLowerCase().endsWith('.pdf')) return
    try {
      const fd = new FormData(); fd.append('file', file)
      const r = (await api.post(`/leads/${leadId}/invoice/read`, fd, { headers: { 'Content-Type': 'multipart/form-data' } })).data
      setInvRead(r)
      if (r.readable) {
        const x = r.fields
        setInv((cur) => ({ ...cur, invoice_no: x.invoice_no || cur.invoice_no, invoice_date: x.invoice_date || cur.invoice_date,
          chassis_no: x.chassis_no || cur.chassis_no, engine_no: x.engine_no || cur.engine_no, hypothecation: x.hypothecation || cur.hypothecation }))
      }
    } catch (e) { setInvRead({ readable: false, message: e.response?.data?.detail || 'Could not read the PDF. Fill the details by hand.' }) }
  }
  const [why, setWhy] = useState('')

  const canInsurance = ['CRE', 'ADMIN'].includes(role)
  const canRto = ['RTO', 'ADMIN'].includes(role)
  const isPba = role === 'PBA'
  const isOwner = role === 'OWNER'

  function apply(d) {
    setP(d)
    if (d.insurance) setIns({ policy_type: d.insurance.policy_type || '', nominee_name: d.insurance.nominee_name || '',
      nominee_age: d.insurance.nominee_age ?? '', nominee_relation: d.insurance.nominee_relation || '',
      nominee_relation_other: d.insurance.nominee_relation_other || '', hypothecation: d.insurance.hypothecation || '' })
    const v = d.invoice || {}
    setInv({ invoice_no: v.invoice_no || '', invoice_date: v.invoice_date || '', chassis_no: v.chassis_no || '',
      engine_no: v.engine_no || '', registration_type: v.registration_type || '', hypothecation: v.hypothecation || '',
      nominee_name: v.nominee_name || '', nominee_relation: v.nominee_relation || '', insurance_addon: v.insurance_addon || '',
      delivery_date: v.delivery_date || '' })
    if (d.rto) setRto({ status: d.rto.status, registration_type: d.rto.registration_type || '',
      registration_no: d.rto.registration_no || '', registration_date: d.rto.registration_date || '',
      delivery_date: d.rto.delivery_date || '' })
  }
  const load = () => api.get(`/leads/${leadId}/handoffs`).then((r) => apply(r.data)).catch(() => setP(false))
  useEffect(() => { load() }, [leadId])

  async function run(fn, okText) {
    setBusy(true); setMsg(null)
    try { const r = await fn(); if (r?.data) apply(r.data); setMsg({ type: 'ok', text: okText }); onChanged && onChanged() }
    catch (e) { setMsg({ type: 'error', text: e.response?.data?.detail || 'Could not save.' }) }
    finally { setBusy(false) }
  }
  async function openPdf(path) {
    try {
      const res = await api.get(`/leads/${leadId}/delivery/${path}`, { responseType: 'blob' })
      window.open(URL.createObjectURL(res.data), '_blank')
    } catch (e) { setMsg({ type: 'error', text: 'Could not open the file.' }) }
  }
  async function copyLink() {
    try {
      const r = await api.post(`/leads/${leadId}/delivery/link`)
      const url = r.data?.url || r.data?.link
      try { await navigator.clipboard.writeText(url) } catch (_) { window.prompt('Copy this link', url) }
      setMsg({ type: 'ok', text: 'Customer link copied.' }); load()
    } catch (e) { setMsg({ type: 'error', text: e.response?.data?.detail || 'Could not create the link.' }) }
  }
  async function openInvoice() {
    try {
      const res = await api.get(`/leads/${leadId}/invoice/file`, { responseType: 'blob' })
      const url = URL.createObjectURL(res.data); window.open(url, '_blank', 'noopener')
      setTimeout(() => URL.revokeObjectURL(url), 60000)
    } catch { setMsg({ type: 'error', text: 'Could not open the invoice.' }) }
  }
  function saveInvoice() {
    if (!inv.chassis_no.trim() || !inv.engine_no.trim()) { setMsg({ type: 'error', text: 'Chassis number and engine number are mandatory.' }); return }
    if (!p.invoice && !invFile) { setMsg({ type: 'error', text: 'Upload the invoice copy.' }); return }
    const fd = new FormData()
    Object.entries(inv).forEach(([k, val]) => { if (val !== '') fd.append(k, val) })
    if (invFile) fd.append('file', invFile)
    run(() => api.put(`/leads/${leadId}/invoice`, fd, { headers: { 'Content-Type': 'multipart/form-data' } }), 'Invoice details saved.')
  }
  async function openPolicy() {
    try {
      const res = await api.get(`/leads/${leadId}/insurance/policy.pdf`, { responseType: 'blob' })
      const url = URL.createObjectURL(res.data); window.open(url, '_blank', 'noopener')
      setTimeout(() => URL.revokeObjectURL(url), 60000)
    } catch { setMsg({ type: 'error', text: 'Could not open the policy.' }) }
  }

  if (p === null || p === false) return null
  if (!p.insurance && !p.rto && !p.approval && !p.booking_no) return null   // nothing started yet

  const note_ = msg && (<div className="hint" style={{ margin: '10px 0', ...(msg.type === 'error' ? { background: 'var(--red-light)', color: '#7a2318' } : {}) }}>{msg.text}</div>)
  const I = p.insurance, R = p.rto, A = p.approval, T = p.atw, D = p.delivery
  const setI = (k) => (e) => setIns({ ...ins, [k]: e.target.value })
  const toggleItem = (v) => setAsk({ ...ask, items: ask.items.includes(v) ? ask.items.filter((x) => x !== v) : [...ask.items, v] })

  return (
    <div className="card">
      <div className="card-header"><h3>Insurance, RTO &amp; Approvals</h3></div>
      <div className="card-pad">
        {note_}

        {/* ---------- INVOICE ---------- */}
        {(p.invoice || (isPba && p.booking_no)) && (<>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <b>1. Invoice details</b>{p.invoice && <span className="badge badge-green">Saved</span>}
          </div>
          {isPba ? (
            <div style={{ margin: '8px 0 14px' }}>
              {invRead && <div className="hint" style={{ marginBottom: 10 }}>
                <b>{invRead.readable ? 'Invoice read — details filled in below.' : 'Invoice not read automatically.'}</b> {invRead.message}
                {(invRead.checks || []).map((c) => <div key={c.field} style={{ color: c.level === 'warn' ? '#b42318' : '#067647' }}>{c.level === 'warn' ? '⚠' : '✓'} {c.field}: {c.text}</div>)}
                {invRead.readable && invRead.fields.total_amount && <div className="muted-note">Invoice total: ₹ {Number(invRead.fields.total_amount).toLocaleString('en-IN')}</div>}
              </div>}
              <Grid>
                <div className="field" style={{ marginBottom: 0 }}><label>Invoice copy {p.invoice ? '(replace)' : '*'}</label>
                  <input className="input" type="file" accept=".pdf,.jpg,.jpeg,.png" onChange={(e) => pickInvoice(e.target.files?.[0] || null)} />
                  {p.invoice?.has_file && <button type="button" className="btn btn-outline btn-sm" style={{ marginTop: 6 }} onClick={openInvoice}>View current copy</button>}</div>
                <div className="field" style={{ marginBottom: 0 }}><label>Invoice no.</label><input className="input" value={inv.invoice_no} onChange={(e) => setInv({ ...inv, invoice_no: e.target.value })} /></div>
                <div className="field" style={{ marginBottom: 0 }}><label>Invoice date</label><input className="input" type="date" max={today()} value={inv.invoice_date} onChange={(e) => setInv({ ...inv, invoice_date: e.target.value })} /></div>
                <div className="field" style={{ marginBottom: 0 }}><label>Chassis no. *</label><input className="input" value={inv.chassis_no} maxLength={20} onChange={(e) => setInv({ ...inv, chassis_no: e.target.value.toUpperCase() })} /></div>
                <div className="field" style={{ marginBottom: 0 }}><label>Engine no. *</label><input className="input" value={inv.engine_no} maxLength={25} onChange={(e) => setInv({ ...inv, engine_no: e.target.value.toUpperCase() })} /></div>
                <div className="field" style={{ marginBottom: 0 }}><label>Registration type</label>
                  <select className="input" value={inv.registration_type} onChange={(e) => setInv({ ...inv, registration_type: e.target.value })}>
                    <option value="">Select</option>{p.options.reg_types.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}</select></div>
                <div className="field" style={{ marginBottom: 0 }}><label>Hypothecation (HP) bank</label><input className="input" value={inv.hypothecation} onChange={(e) => setInv({ ...inv, hypothecation: e.target.value })} /></div>
                <div className="field" style={{ marginBottom: 0 }}><label>Nominee name</label><input className="input" value={inv.nominee_name} onChange={(e) => setInv({ ...inv, nominee_name: e.target.value })} /></div>
                <div className="field" style={{ marginBottom: 0 }}><label>Nominee relation</label>
                  <select className="input" value={inv.nominee_relation} onChange={(e) => setInv({ ...inv, nominee_relation: e.target.value })}>
                    <option value="">Select</option>{p.options.nominee_relations.map((o) => <option key={o}>{o}</option>)}</select></div>
                <div className="field" style={{ marginBottom: 0 }}><label>Insurance add-on</label><input className="input" value={inv.insurance_addon} onChange={(e) => setInv({ ...inv, insurance_addon: e.target.value })} placeholder="e.g. Zero depreciation" /></div>
                <div className="field" style={{ marginBottom: 0 }}><label>Bike delivery date</label><input className="input" type="date" min={p.invoice ? undefined : today()} value={inv.delivery_date} onChange={(e) => setInv({ ...inv, delivery_date: e.target.value })} /></div>
                <div><button className="btn btn-primary" disabled={busy} onClick={saveInvoice}>{p.invoice ? 'Update invoice details' : 'Save invoice details'}</button></div>
              </Grid>
              <div className="muted-note" style={{ marginTop: 6 }}>Chassis and engine numbers go to the Owner's ATW record, the insurance team and the RTO automatically.</div>
            </div>) : (
            <div style={{ margin: '8px 0 14px' }}><Grid>
              <Row k="Invoice no. / date" v={[p.invoice.invoice_no, fmtDate(p.invoice.invoice_date)].filter(Boolean).join(' · ')} />
              <Row k="Chassis no." v={p.invoice.chassis_no} /><Row k="Engine no." v={p.invoice.engine_no} />
              <Row k="Registration type" v={p.options.reg_types.find((o) => o.value === p.invoice.registration_type)?.label} />
              <Row k="Hypothecation (HP)" v={p.invoice.hypothecation} />
              <Row k="Nominee" v={[p.invoice.nominee_name, p.invoice.nominee_relation].filter(Boolean).join(', ')} />
              <Row k="Add-on" v={p.invoice.insurance_addon} /><Row k="Bike delivery date" v={fmtDate(p.invoice.delivery_date)} />
              {p.invoice.has_file && <div><button className="btn btn-outline btn-sm" onClick={openInvoice}>View invoice copy</button></div>}</Grid></div>)}
          <hr style={{ border: 0, borderTop: '1px solid #eee', margin: '8px 0 14px' }} />
        </>)}

        {/* ---------- INSURANCE ---------- */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <b>2. Insurance</b>{I && <span className={'badge ' + BADGE[I.status]}>{pretty(I.status)}</span>}
        </div>
        {!I && <div className="muted-note" style={{ margin: '6px 0 14px' }}>Starts automatically when the Opportunity Status is BOOKING DONE.</div>}
        {I && I.status === 'COMPLETED' && (
          <div style={{ margin: '8px 0 14px' }}>
            <Grid><Row k="Policy type" v={I.policy_type_label} /><Row k="Policy no." v={I.policy_no} />
              <Row k="Valid" v={`${fmtDate(I.policy_start)} → ${fmtDate(I.policy_expiry)}`} /><Row k="Premium" v={rupees(I.premium)} />
              <Row k="Nominee" v={`${I.nominee_name} (${I.nominee_age}), ${I.nominee_relation === 'Other' ? I.nominee_relation_other : I.nominee_relation}`} />
              <Row k="Hypothecation (HP)" v={I.hypothecation} />
              <Row k="Done by" v={`${I.completed_by || ''} · ${fmtDateTime(I.completed_at)}`} />
              <div><button className="btn btn-outline btn-sm" onClick={openPolicy}>View insurance PDF</button></div></Grid>
          </div>)}
        {I && I.status !== 'COMPLETED' && (canInsurance ? (
          <div style={{ margin: '8px 0 14px' }}>
            <Grid>
              <div className="field" style={{ marginBottom: 0 }}><label>Policy type *</label>
                <select className="input" value={ins.policy_type || ''} onChange={setI('policy_type')}>
                  <option value="">Select</option>{p.options.policy_types.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}</select></div>
              <div className="field" style={{ marginBottom: 0 }}><label>Nominee name *</label><input className="input" value={ins.nominee_name || ''} onChange={setI('nominee_name')} /></div>
              <div className="field" style={{ marginBottom: 0 }}><label>Nominee age *</label><input className="input" type="number" min="1" max="120" value={ins.nominee_age ?? ''} onChange={setI('nominee_age')} /></div>
              <div className="field" style={{ marginBottom: 0 }}><label>Nominee relation *</label>
                <select className="input" value={ins.nominee_relation || ''} onChange={setI('nominee_relation')}>
                  <option value="">Select</option>{p.options.nominee_relations.map((o) => <option key={o}>{o}</option>)}</select></div>
              {ins.nominee_relation === 'Other' && <div className="field" style={{ marginBottom: 0 }}><label>Specify relation *</label><input className="input" value={ins.nominee_relation_other || ''} onChange={setI('nominee_relation_other')} /></div>}
              <div className="field" style={{ marginBottom: 0 }}><label>Hypothecation (bank, if HP)</label><input className="input" value={ins.hypothecation || ''} onChange={setI('hypothecation')} /></div>
              <div><button className="btn btn-outline" disabled={busy} onClick={() => run(() => api.put(`/leads/${leadId}/insurance`, {
                policy_type: ins.policy_type || null, nominee_name: ins.nominee_name || null,
                nominee_age: ins.nominee_age === '' ? null : Number(ins.nominee_age), nominee_relation: ins.nominee_relation || null,
                nominee_relation_other: ins.nominee_relation_other || null, hypothecation: ins.hypothecation || null }), 'Insurance details saved.')}>Save details</button></div>
            </Grid>
            <div style={{ fontWeight: 600, fontSize: 13, margin: '14px 0 8px' }}>Policy created? Upload it to complete the insurance</div>
            <Grid>
              <div className="field" style={{ marginBottom: 0 }}><label>Policy no. *</label><input className="input" value={pol.policy_no} onChange={(e) => setPol({ ...pol, policy_no: e.target.value })} /></div>
              <div className="field" style={{ marginBottom: 0 }}><label>Start date *</label><input className="input" type="date" value={pol.policy_start} onChange={(e) => setPol({ ...pol, policy_start: e.target.value })} /></div>
              <div className="field" style={{ marginBottom: 0 }}><label>Expiry date *</label><input className="input" type="date" value={pol.policy_expiry} onChange={(e) => setPol({ ...pol, policy_expiry: e.target.value })} /></div>
              <div className="field" style={{ marginBottom: 0 }}><label>Premium (₹)</label><input className="input" type="number" min="0" value={pol.premium} onChange={(e) => setPol({ ...pol, premium: e.target.value })} /></div>
              <div className="field" style={{ marginBottom: 0 }}><label>Policy PDF *</label><input className="input" type="file" accept=".pdf" onChange={(e) => setPolFile(e.target.files?.[0] || null)} /></div>
              <div><button className="btn btn-primary" disabled={busy} onClick={() => {
                if (!polFile) { setMsg({ type: 'error', text: 'Choose the policy PDF.' }); return }
                const fd = new FormData(); fd.append('policy_no', pol.policy_no); fd.append('policy_start', pol.policy_start)
                fd.append('policy_expiry', pol.policy_expiry); if (pol.premium !== '') fd.append('premium', pol.premium); fd.append('file', polFile)
                run(() => api.post(`/leads/${leadId}/insurance/policy`, fd, { headers: { 'Content-Type': 'multipart/form-data' } }), 'Insurance completed. The PBA and RTO have been notified.')
              }}>Complete insurance</button></div>
            </Grid>
          </div>) : (
          <div className="muted-note" style={{ margin: '6px 0 14px' }}>The insurance team is processing this booking{I.policy_type ? ` (${I.policy_type_label})` : ''}.</div>))}

        {/* ---------- RTO ---------- */}
        <hr style={{ border: 0, borderTop: '1px solid #eee', margin: '8px 0 14px' }} />
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <b>3. RTO registration</b>{R && <span className={'badge ' + BADGE[R.status]}>{R.status_label}</span>}
        </div>
        {!R && <div className="muted-note" style={{ margin: '6px 0 14px' }}>Starts when the insurance policy is uploaded.</div>}
        {R && !canRto && (<div style={{ margin: '8px 0 14px' }}><Grid><Row k="Registration type" v={R.registration_type_label} />
          <Row k="Registration no." v={R.registration_no} /><Row k="Registered on" v={fmtDate(R.registration_date)} /><Row k="Bike delivery date" v={fmtDate(R.delivery_date)} /></Grid></div>)}
        {R && canRto && (
          <div style={{ margin: '8px 0 14px' }}><Grid>
            <div className="field" style={{ marginBottom: 0 }}><label>Status</label>
              <select className="input" value={rto.status || ''} onChange={(e) => setRto({ ...rto, status: e.target.value })}>
                {p.options.rto_statuses.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}</select></div>
            <div className="field" style={{ marginBottom: 0 }}><label>Registration type</label>
              <select className="input" value={rto.registration_type || ''} onChange={(e) => setRto({ ...rto, registration_type: e.target.value })}>
                <option value="">—</option>{p.options.reg_types.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}</select></div>
            <div className="field" style={{ marginBottom: 0 }}><label>Online registration no.</label><input className="input" value={rto.registration_no || ''} onChange={(e) => setRto({ ...rto, registration_no: e.target.value })} /></div>
            <div className="field" style={{ marginBottom: 0 }}><label>Registration date</label><input className="input" type="date" max={today()} value={rto.registration_date || ''} onChange={(e) => setRto({ ...rto, registration_date: e.target.value })} /></div>
            <div className="field" style={{ marginBottom: 0 }}><label>Bike delivery date</label><input className="input" type="date" value={rto.delivery_date || ''} onChange={(e) => setRto({ ...rto, delivery_date: e.target.value })} /></div>
            <div><button className="btn btn-primary" disabled={busy} onClick={() => run(() => api.patch(`/leads/${leadId}/rto`, {
              status: rto.status, registration_type: rto.registration_type || null, registration_no: rto.registration_no || null,
              registration_date: rto.registration_date || null, delivery_date: rto.delivery_date || null }), 'RTO details saved. The PBA has been notified of any new number or date.')}>Save RTO details</button></div>
          </Grid></div>)}

        {/* ---------- OWNER APPROVAL ---------- */}
        <hr style={{ border: 0, borderTop: '1px solid #eee', margin: '8px 0 14px' }} />
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <b>4. Owner approval</b>{A && <span className={'badge ' + BADGE[A.status]}>{pretty(A.status)}</span>}
        </div>
        {A && (<div style={{ margin: '8px 0' }}><Grid>
          <Row k="Special approvals" v={A.items.length ? A.items.map((i) => p.options.special_items.find((o) => o.value === i)?.label || i).join(', ') : 'None'} />
          <Row k="Final delivery date" v={fmtDate(A.delivery_date)} /><Row k="Asked by" v={`${A.requested_by || ''} · ${fmtDateTime(A.requested_at)}`} />
          {A.note && <Row k="PBA note" v={A.note} />}
          {A.decided_at && <Row k="Decision" v={`${A.decided_by || ''} · ${fmtDateTime(A.decided_at)}`} />}
          {A.decision_note && <Row k="Reason / note" v={A.decision_note} />}</Grid></div>)}
        {isOwner && A?.status === 'PENDING' && (<div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap', margin: '8px 0 14px' }}>
          <input className="input" style={{ flex: 1, minWidth: 200 }} placeholder="Note (required if rejecting)" value={note} onChange={(e) => setNote(e.target.value)} />
          <button className="btn btn-primary" disabled={busy} onClick={() => run(() => api.post(`/leads/${leadId}/approval/decision`, { approve: true, note: note || null }), 'Approved.')}>Approve</button>
          <button className="btn btn-outline" disabled={busy} onClick={() => run(() => api.post(`/leads/${leadId}/approval/decision`, { approve: false, note }), 'Rejected.')}>Reject</button></div>)}
        {isPba && p.booking_no && (!A || A.status === 'REJECTED') && (
          <div style={{ margin: '8px 0 14px' }}>
            <div className="muted-note" style={{ marginBottom: 6 }}>Tick anything that needs the Owner's special approval, then send.</div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 14, fontSize: 14, marginBottom: 10 }}>
              {p.options.special_items.map((o) => (<label key={o.value} style={{ display: 'flex', gap: 6 }}>
                <input type="checkbox" checked={ask.items.includes(o.value)} onChange={() => toggleItem(o.value)} />{o.label}</label>))}</div>
            <Grid>
              <div className="field" style={{ marginBottom: 0 }}><label>Final bike delivery date *</label><input className="input" type="date" min={today()} value={ask.delivery_date} onChange={(e) => setAsk({ ...ask, delivery_date: e.target.value })} /></div>
              <div className="field" style={{ marginBottom: 0 }}><label>Note to Owner</label><input className="input" value={ask.note} onChange={(e) => setAsk({ ...ask, note: e.target.value })} /></div>
              <div><button className="btn btn-primary" disabled={busy} onClick={() => run(() => api.post(`/leads/${leadId}/approval`, { items: ask.items, note: ask.note || null, delivery_date: ask.delivery_date || null }), 'Sent to the Owner for approval.')}>{A ? 'Send again' : 'Ask Owner to approve'}</button></div>
            </Grid></div>)}

        {/* ---------- ATW ---------- */}
        {(T.eligible || T.status) && (<>
          <hr style={{ border: 0, borderTop: '1px solid #eee', margin: '8px 0 14px' }} />
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <b>5. ATW – 10 years engine warranty</b>{T.status && <span className={'badge ' + BADGE[T.status]}>{T.label}</span>}
          </div>
          {T.status && (<div style={{ margin: '8px 0' }}><Grid><Row k="Vehicle" v={T.model_name} /><Row k="Chassis no." v={T.chassis_no || 'Not entered yet'} />
            {T.decided_at && <Row k="Decided" v={`${T.decided_by || ''} · ${fmtDateTime(T.decided_at)}`} />}{T.decision_note && <Row k="Reason" v={T.decision_note} />}</Grid></div>)}
          {isOwner && T.status === 'PENDING' && (<div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', margin: '8px 0' }}>
            <input className="input" style={{ flex: 1, minWidth: 200 }} placeholder="Note (required if rejecting)" value={note} onChange={(e) => setNote(e.target.value)} />
            <button className="btn btn-primary" disabled={busy} onClick={() => run(() => api.post(`/leads/${leadId}/atw/decision`, { approve: true, note: note || null }), 'ATW approved.')}>Approve ATW</button>
            <button className="btn btn-outline" disabled={busy} onClick={() => run(() => api.post(`/leads/${leadId}/atw/decision`, { approve: false, note }), 'ATW rejected.')}>Reject</button></div>)}
          {isPba && T.eligible && (!T.status || T.status === 'REJECTED') && (
            <button className="btn btn-outline" disabled={busy} style={{ marginTop: 6 }} onClick={() => run(() => api.post(`/leads/${leadId}/atw`), 'ATW sent to the Owner.')}>{T.status ? 'Request ATW again' : 'Request ATW approval'}</button>)}
        </>)}

        {/* ---------- DELIVERY ---------- */}
        {p.delivery && (<>
          <hr style={{ border: 0, borderTop: '1px solid #eee', margin: '8px 0 14px' }} />
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <b>6. Delivery receipt</b>{D.delivered && <span className="badge badge-green">Delivered</span>}
          </div>
          {D.delivered ? (<div style={{ margin: '8px 0' }}>
            <Grid><Row k="Receipt no." v={D.receipt_no} /><Row k="Delivery date" v={fmtDate(D.delivery_date)} />
              <Row k="Generated" v={`${D.generated_by || ''} · ${fmtDateTime(D.generated_at)}`} />
              <Row k="Customer acknowledgement" v={D.agreed_at ? `Agreed · ${fmtDateTime(D.agreed_at)}` : 'Not yet agreed'} /></Grid>
            {D.override && <div className="hint" style={{ margin: '8px 0' }}>Allowed by the Owner ({D.override.by}) despite: {D.override.pending_then}. Reason: {D.override.reason}</div>}
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 8 }}>
              <button className="btn btn-outline btn-sm" onClick={() => openPdf('receipt.pdf')}>View receipt</button>
              {D.has_accepted_pdf && <button className="btn btn-outline btn-sm" onClick={() => openPdf('accepted.pdf')}>View accepted copy</button>}
              {isPba && !D.agreed_at && <button className="btn btn-outline btn-sm" onClick={copyLink}>Copy customer I AGREE link</button>}
            </div></div>) : (<div style={{ margin: '8px 0' }}>
            {D.blockers_hard.length > 0 && (<div className="hint" style={{ background: 'var(--red-light)', color: '#7a2318', marginBottom: 8 }}>
              Not ready: {D.blockers_hard.join('; ')}.</div>)}
            {D.blockers_soft.length > 0 && !D.override && (<div className="hint" style={{ marginBottom: 8 }}>
              Pending: {D.blockers_soft.join('; ')}. The Owner can allow delivery as an exception.</div>)}
            {D.override && <div className="hint" style={{ marginBottom: 8 }}>Owner allowed delivery ({D.override.by}): {D.override.reason}</div>}
            {isOwner && D.can_override && (<div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 8 }}>
              <input className="input" style={{ flex: 1, minWidth: 200 }} placeholder="Reason for allowing delivery" value={why} onChange={(e) => setWhy(e.target.value)} />
              <button className="btn btn-primary" disabled={busy} onClick={() => run(async () => { const r = await api.post(`/leads/${leadId}/delivery/override`, { reason: why }); setWhy(''); await load(); return r }, 'Delivery allowed.')}>Allow delivery</button></div>)}
            {isPba && (<button className="btn btn-primary" disabled={busy || !D.can_generate}
              onClick={() => run(async () => { const r = await api.post(`/leads/${leadId}/delivery/generate`); await load(); return r }, 'Delivery receipt generated. The bike is marked delivered.')}>Generate receipt &amp; mark delivered</button>)}
          </div>)}
        </>)}
      </div>
    </div>
  )
}
