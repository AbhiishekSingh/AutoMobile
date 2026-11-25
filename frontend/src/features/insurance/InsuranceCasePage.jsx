// One insurance case, top to bottom: customer (read-only) → policy type → documents → nominee → policy PDF → WhatsApp.
import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import api from '../../lib/api'
import Layout from '../../components/Layout'
import JourneyBar from '../ownerflow/JourneyBar'
import { Loading, fmtDate, fmtDateTime } from '../../components/ui'

// A collapsible step: header shows the number/title and Done / Pending; click to open or close.
function Step({ id, open, toggle, title, done, children }) {
  const isOpen = !!open[id]
  return (
    <div id={`step-${id}`} className="card" style={{ marginBottom: 12, overflow: 'hidden', scrollMarginTop: 90 }}>
      <div onClick={() => toggle(id)} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10, padding: '14px 18px', cursor: 'pointer', userSelect: 'none' }}>
        <h3 style={{ margin: 0, fontSize: 15 }}>{title}</h3>
        <span style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          {done !== undefined && <span className={'badge ' + (done ? 'badge-green' : 'badge-amber')}>{done ? 'Done' : 'Pending'}</span>}
          <span style={{ width: 8, height: 8, borderRight: '2px solid #6b7480', borderBottom: '2px solid #6b7480', transform: isOpen ? 'rotate(225deg)' : 'rotate(45deg)', marginBottom: isOpen ? -3 : 3, transition: 'transform .15s' }} />
        </span>
      </div>
      {isOpen && <div style={{ padding: '2px 18px 16px' }}>{children}</div>}
    </div>)
}

// The five steps in order, with whether each is finished (used for the first-open step and the progress stepper)
const stepList = (c) => [
  { id: 'type', label: 'Policy type', done: !!c.policy_type && !!c.customer_type },
  { id: 'docs', label: 'Documents', done: c.documents.length > 0 && c.documents.every((d) => d.uploaded) },
  { id: 'nom', label: 'Nominee', done: !c.nominee.missing.length },
  { id: 'ver', label: 'Verified', done: !!c.docs_verified?.at },
  { id: 'pol', label: 'Policy & PDF', done: c.status === 'COMPLETED' },
]
const NEXT_HINT = { type: 'Policy type (the PBA fills this in)', docs: 'Check the documents (upload any that are missing)', nom: 'Nominee details (the PBA fills these in)', ver: 'Confirm the documents are verified', pol: 'Enter the policy details and upload the policy PDF' }

const errText = (e) => e.response?.data?.detail || 'Something went wrong.'
async function openBlob(path) {
  const res = await api.get(path, { responseType: 'blob' })
  const url = URL.createObjectURL(res.data); window.open(url, '_blank', 'noopener'); setTimeout(() => URL.revokeObjectURL(url), 60000)
}

export default function InsuranceCasePage() {
  const { leadId } = useParams()
  const nav = useNavigate()
  const back = { label: 'Insurance', onClick: () => nav('/insurance') }
  const [replacing, setReplacing] = useState({})     // doc types where the Insurance user chose "Replace file"
  const [c, setC] = useState(null)
  const [msg, setMsg] = useState(null)
  const [busy, setBusy] = useState(false)
  const [nom, setNom] = useState({ nominee_name: '', nominee_age: '', nominee_relation: '', nominee_relation_other: '' })
  const [pol, setPol] = useState({ policy_no: '', policy_start: '', policy_expiry: '', premium: '' })
  const [polFile, setPolFile] = useState(null)
  const [wa, setWa] = useState(null)
  const [cx, setCx] = useState(null)          // the cancel-policy form while it is open
  const [react, setReact] = useState(null)    // the reason box while 'make active again' is open
  const [open, setOpen] = useState({})
  const toggle = (id) => setOpen((o) => ({ ...o, [id]: !o[id] }))
  const opened = useRef(false)
  useEffect(() => {          // first time the case loads: open only the first unfinished step
    if (!c || opened.current) return
    opened.current = true
    setOpen({ [(stepList(c).find((x) => !x.done) || { id: 'pol' }).id]: true })
  }, [c])

  const load = useCallback(() => api.get(`/insurance/cases/${leadId}`).then((r) => {
    setC(r.data)
    setNom({ nominee_name: r.data.nominee.name || '', nominee_age: r.data.nominee.age || '', nominee_relation: r.data.nominee.relation || '', nominee_relation_other: r.data.nominee.relation_other || '' })
    api.get(`/leads/${leadId}/whatsapp`).then((w) => setWa(w.data.messages.filter((m) => m.kind === 'INSURANCE'))).catch(() => {})
  }).catch((e) => setMsg({ ok: false, text: errText(e) })), [leadId])
  useEffect(() => { load() }, [load])

  // area = which section the message belongs to, so it is shown right next to the button the user pressed
  async function run(fn, ok, area = 'top') {
    setBusy(true); setMsg(null)
    try { await fn(); setMsg({ ok: true, text: ok, area }); await load() } catch (e) { setMsg({ ok: false, text: errText(e), area }) } finally { setBusy(false) }
  }
  const setType = (v) => run(() => api.put(`/leads/${leadId}/insurance`, { policy_type: v }), 'Policy type saved.')
  const setCt = (v) => run(() => api.put(`/leads/${leadId}/insurance`, { customer_type: v }), 'Customer type saved.')
  const upDoc = (t, file) => file && run(() => { const fd = new FormData(); fd.append('doc_type', t); fd.append('file', file); return api.post(`/insurance/cases/${leadId}/documents`, fd, { headers: { 'Content-Type': 'multipart/form-data' } }) }, 'Document uploaded.')
  const saveNominee = () => run(() => api.put(`/leads/${leadId}/insurance`, { nominee_name: nom.nominee_name, nominee_age: Number(nom.nominee_age) || null, nominee_relation: nom.nominee_relation, nominee_relation_other: nom.nominee_relation === 'Other' ? nom.nominee_relation_other : null }), 'Nominee saved.', 'nom')
  const savePolicy = () => run(() => { const fd = new FormData(); Object.entries(pol).forEach(([k, v]) => v !== '' && fd.append(k, v)); if (polFile) fd.append('file', polFile); return api.post(`/leads/${leadId}/insurance/policy`, fd, { headers: { 'Content-Type': 'multipart/form-data' } }) }, 'Insurance completed. The PBA has been notified.', 'pol')
  const verify = () => run(() => api.post(`/insurance/cases/${leadId}/verify-documents`), 'Documents marked as verified.', 'ver')
  const cancelPolicy = () => run(() => api.post(`/insurance/cases/${leadId}/cancel-policy`, {
    cancel_date: cx.cancel_date, remark: cx.remark, refund_amount: cx.refund_amount === '' ? null : Number(cx.refund_amount),
    refund_expected_date: cx.refund_expected_date || null }).then(() => setCx(null)), 'Policy cancelled. The refund details are saved.', 'pol')
  const addNew = () => run(() => api.post(`/insurance/cases/${leadId}/new-policy`), 'The cancelled policy is saved in the history. Enter the new policy below.', 'pol')
  const reactivate = () => run(() => api.post(`/insurance/cases/${leadId}/reactivate-policy`, { remark: react }).then(() => setReact(null)), 'Policy is active again.', 'pol')
  const sendWa = () => run(() => api.post(`/leads/${leadId}/whatsapp/insurance`), 'WhatsApp request sent — see the log below.', 'pol')

  if (!c) return <Layout title="Insurance case" back={back}>{msg ? <div className="hint">{msg.text}</div> : <Loading />}</Layout>
  const ed = c.can_edit
  const edd = c.can_edit_details          // policy type + nominee are filled by the PBA; the Insurance login only views them
  const allSteps = stepList(c)
  const allDocs = c.documents.length > 0 && c.documents.every((d) => d.uploaded)
  const Msg = ({ area }) => msg && msg.area === area
    ? <div style={{ marginTop: 10, padding: '9px 12px', borderRadius: 8, fontWeight: 600, fontSize: 13.5, background: msg.ok ? 'var(--green-light, #e3f6ec)' : 'var(--red-light)', color: msg.ok ? '#0f6b3a' : '#7a2318', border: `1px solid ${msg.ok ? '#a8e0c1' : '#f0b4ab'}` }}>{msg.ok ? '✓ ' : '✕ '}{msg.text}</div>
    : null
  const sv = c.nominee || {}
  const nomDirty = String(nom.nominee_name || '') !== String(sv.name || '') || String(nom.nominee_age || '') !== String(sv.age || '') || String(nom.nominee_relation || '') !== String(sv.relation || '') || (nom.nominee_relation === 'Other' && String(nom.nominee_relation_other || '') !== String(sv.relation_other || ''))
  const Row = ({ k, v }) => <div style={{ display: 'flex', gap: 8, padding: '3px 0' }}><span className="muted-note" style={{ width: 130 }}>{k}</span><span>{v || '—'}</span></div>
  return (
    <Layout title={`Insurance — ${c.customer_name}`} sub={c.booking_no ? `Booking ${c.booking_no}` : ''} back={back}>
      <JourneyBar leadId={leadId} />
      {msg && (!msg.area || msg.area === 'top') && <div className="hint" style={{ marginBottom: 12, ...(msg.ok ? {} : { background: 'var(--red-light)', color: '#7a2318' }) }}>{msg.text}</div>}

      {/* who and what: every booking detail, read-only */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(230px,1fr))', gap: 12, marginBottom: 14 }}>
        {[['Customer', c.customer_name, [c.mobile, c.branch]],
          ['Vehicle', [c.model, c.color].filter(Boolean).join(' · ') || '—', [c.booking_no ? `Booking ${c.booking_no}` : null, c.booking_date ? `Booked ${fmtDate(c.booking_date)}` : null]],
          ['PBA', c.pba_name || '—', [c.pba_employee_id ? `Employee ID ${c.pba_employee_id}` : null]],
          ['Insurance', (c.options.policy_types.find((p) => p.value === c.policy_type) || {}).label || 'Policy type not chosen yet',
            [c.policy_type ? `Customer type: ${(c.options.customer_types.find((p) => p.value === c.customer_type) || {}).label || '—'}` : 'Waiting for the PBA to fill it in', c.policy_type ? `Insurance company: ${c.policy.company || '—'}` : null,
             c.status === 'COMPLETED' ? `Policy ${c.policy.policy_no || ''}` : 'Not completed yet', (c.addons || []).length ? `Add-ons asked: ${c.addons.join(', ')}` : null, c.policy.status === 'CANCELLED' ? 'POLICY CANCELLED' : null]]].map(([l, v, sub]) => (
          <div key={l} className="card" style={{ padding: '14px 18px', marginBottom: 0 }}>
            <div className="muted-note" style={{ fontWeight: 600, fontSize: 12 }}>{l}</div>
            <div style={{ fontSize: 17, fontWeight: 800, color: '#1c2740', margin: '3px 0 4px' }}>{v}</div>
            {sub.filter(Boolean).map((t) => <div key={t} className="muted-note" style={{ fontSize: 12.5 }}>{t}</div>)}
          </div>))}
      </div>

      {/* progress: where the case stands and what to do next */}
      <div className="card" style={{ padding: '16px 18px', marginBottom: 14 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: 8, marginBottom: 12 }}>
          <b>{allSteps.every((x) => x.done) ? 'All steps are done' : `Step ${allSteps.findIndex((x) => !x.done) + 1} of 5`}</b>
          <span className="muted-note">{allSteps.every((x) => x.done) ? 'The policy is complete.' : <>Next: <b style={{ color: '#1c2740' }}>{NEXT_HINT[(allSteps.find((x) => !x.done)).id]}</b></>}</span>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(130px,1fr))', gap: 8 }}>
          {allSteps.map((x, i) => {
            const cur = !x.done && allSteps.slice(0, i).every((y) => y.done)
            return (
              <button key={x.id} type="button" onClick={() => { setOpen((o) => ({ ...o, [x.id]: true })); setTimeout(() => document.getElementById(`step-${x.id}`)?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 30) }}
                style={{ display: 'flex', alignItems: 'center', gap: 9, textAlign: 'left', padding: '9px 12px', borderRadius: 12, cursor: 'pointer', font: 'inherit',
                  border: `1px solid ${x.done ? '#a8e0c1' : cur ? '#2f80ed' : '#e5e9f0'}`, background: x.done ? '#effaf4' : cur ? '#f3f8ff' : '#fff' }}>
                <span style={{ width: 24, height: 24, borderRadius: 12, flexShrink: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 12.5, fontWeight: 800,
                  background: x.done ? '#1f8a4c' : cur ? '#2f80ed' : '#e8ebf1', color: x.done || cur ? '#fff' : '#6b7480' }}>{x.done ? '✓' : i + 1}</span>
                <span style={{ fontWeight: 600, fontSize: 13.5, color: '#1c2740' }}>{x.label}</span>
              </button>)
          })}
        </div>
      </div>

      <Step id="type" open={open} toggle={toggle} title={<>1. Customer &amp; policy type {!edd && <span className="muted-note">(filled by the PBA)</span>}</>} done={!!c.policy_type}>
        {edd ? (
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
            <select className="input" style={{ maxWidth: 220 }} disabled={busy} value={c.customer_type || ''} onChange={(e) => e.target.value && setCt(e.target.value)}>
              <option value="">Customer type</option>{c.options.customer_types.map((p) => <option key={p.value} value={p.value}>{p.label}</option>)}</select>
            <select className="input" style={{ maxWidth: 280 }} disabled={busy} value={c.policy_type || ''} onChange={(e) => e.target.value && setType(e.target.value)}>
              <option value="">Policy type</option>{c.options.policy_types.map((p) => <option key={p.value} value={p.value}>{p.label}</option>)}</select>
          </div>
        ) : c.policy_type ? (
          <div><Row k="Customer type" v={(c.options.customer_types.find((p) => p.value === c.customer_type) || {}).label} />
            <Row k="Policy type" v={(c.options.policy_types.find((p) => p.value === c.policy_type) || {}).label} />
            <Row k="Add-ons asked" v={(c.addons || []).join(', ')} /></div>
        ) : <div className="muted-note">Waiting for the PBA to fill in the customer type and policy type.</div>}
      </Step>

      <Step id="docs" open={open} toggle={toggle} title={<>2. Documents {c.documents.length > 0 && <span className="muted-note">({c.documents.filter((d) => d.uploaded).length} of {c.documents.length} received)</span>}</>} done={allDocs}>
        {!c.policy_type && <div className="muted-note">Waiting for the PBA to choose the policy type; the documents needed depend on it.</div>}
        {c.policy_type && <div className="hint" style={{ marginBottom: 8 }}>These documents are uploaded by the PBA, so they appear here automatically. Check them, and upload a document only if one is missing.</div>}
        {c.documents.map((d) => (
          <div key={d.doc_type} style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap', padding: '6px 0', borderBottom: '1px solid var(--border, #eee)' }}>
            <span style={{ width: 280 }}>{d.label} <b style={{ color: '#b42318' }}>*</b></span>
            {d.uploaded ? <><span className="badge badge-green">{d.from_pba_documents || d.uploaded_by ? 'Received' : 'Uploaded'}</span>
              <button className="btn btn-outline btn-sm" onClick={() => openBlob(`/documents/${d.doc_id}/file`)}>View</button>
              <span className="muted-note">{d.file_name}{d.uploaded_by ? ` · by ${d.uploaded_by}` : ''}</span>
              {ed && !replacing[d.doc_type] && <button type="button" className="btn btn-outline btn-sm" onClick={() => setReplacing({ ...replacing, [d.doc_type]: true })}>Replace file</button>}</>
              : <span className="badge badge-amber">Missing</span>}
            {ed && (!d.uploaded || replacing[d.doc_type]) && <input type="file" disabled={busy} accept={d.pdf_only ? '.pdf' : '.pdf,.jpg,.jpeg,.png'}
              onChange={(e) => { upDoc(d.doc_type, e.target.files?.[0]); setReplacing({ ...replacing, [d.doc_type]: false }); e.target.value = '' }} />}
          </div>))}
        {c.policy_type === 'BAGIC' && <div className="muted-note" style={{ marginTop: 6 }}>BAGIC: Aadhaar front and back must be ONE PDF. If the PBA&apos;s file is only one side, upload the full Aadhaar PDF here.</div>}
      </Step>

      <Step id="nom" open={open} toggle={toggle} title={<>3. Nominee details * {!edd && <span className="muted-note">(filled by the PBA)</span>}</>} done={!c.nominee.missing.length}>
        {!edd && (c.nominee.missing.length
          ? <div className="muted-note">Waiting for the PBA to fill in the nominee details{c.nominee.name || c.nominee.age || c.nominee.relation ? ` (missing: ${c.nominee.missing.join(', ')})` : ''}.</div>
          : <div><Row k="Nominee name" v={c.nominee.name} /><Row k="Nominee age" v={c.nominee.age} />
              <Row k="Relation" v={c.nominee.relation === 'Other' ? `Other: ${c.nominee.relation_other || ''}` : c.nominee.relation} /></div>)}
        {edd && <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(180px,1fr))', gap: 10 }}>
          <div className="field"><label>Nominee name</label><input className="input" disabled={!ed} value={nom.nominee_name} onChange={(e) => setNom({ ...nom, nominee_name: e.target.value })} /></div>
          <div className="field"><label>Nominee age</label><input className="input" type="number" min="1" max="120" disabled={!ed} value={nom.nominee_age} onChange={(e) => setNom({ ...nom, nominee_age: e.target.value })} /></div>
          <div className="field"><label>Relation</label><select className="input" disabled={!ed} value={nom.nominee_relation} onChange={(e) => setNom({ ...nom, nominee_relation: e.target.value })}>
            <option value="">Select</option>{c.options.nominee_relations.map((r) => <option key={r}>{r}</option>)}</select></div>
          {nom.nominee_relation === 'Other' && <div className="field"><label>Specify relation</label><input className="input" disabled={!ed} value={nom.nominee_relation_other} onChange={(e) => setNom({ ...nom, nominee_relation_other: e.target.value })} /></div>}
        </div>}
        {edd && <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
          <button className={nomDirty ? 'btn btn-primary btn-sm' : 'btn btn-outline btn-sm'} disabled={busy} onClick={saveNominee}>Save nominee</button>
          {nomDirty ? <span className="muted-note" style={{ color: '#b45309', fontWeight: 600 }}>● You have not saved these details yet</span>
            : !c.nominee.missing.length && <span className="muted-note" style={{ color: '#0f6b3a', fontWeight: 600 }}>✓ Nominee details saved</span>}
        </div>}
        <Msg area="nom" />
      </Step>

      <Step id="ver" open={open} toggle={toggle} title={<>4. Documents verified *</>} done={!!c.docs_verified?.at}>
        {c.docs_verified?.at
          ? <div><span className="badge badge-green">Verified</span> <span className="muted-note">by {c.docs_verified.by || '—'} · {fmtDateTime(c.docs_verified.at)}</span></div>
          : <div>
              <div className="muted-note" style={{ marginBottom: 8 }}>Check the uploaded documents and the nominee details, then confirm. Uploading a document again needs a new verification.</div>
              {ed && <button className="btn btn-primary btn-sm" disabled={busy || !(allDocs && !c.nominee.missing.length)} onClick={verify}>Mark documents verified</button>}
              <Msg area="ver" />
            </div>}
      </Step>

      <Step id="pol" open={open} toggle={toggle} title={<>5. Policy &amp; PDF</>} done={c.status === 'COMPLETED'}>
        {c.status === 'COMPLETED' ? (
          <div>
            <Row k="Company" v={c.policy.company} /><Row k="Policy no." v={c.policy.policy_no} /><Row k="Start" v={fmtDate(c.policy.start)} />
            <Row k="Expiry" v={fmtDate(c.policy.expiry)} /><Row k="Premium" v={c.policy.premium != null ? `₹ ${Number(c.policy.premium).toLocaleString('en-IN')}` : null} />
            <Row k="Created" v={fmtDateTime(c.policy.created_at)} /><Row k="Executive" v={c.policy.executive} />
            <Row k="Policy status" v={c.policy.status === 'CANCELLED' ? <span className="badge badge-red">Cancelled</span> : <span className="badge badge-green">Active</span>} />
            {c.policy.status === 'CANCELLED' && (
              <div style={{ margin: '8px 0', padding: '10px 14px', borderRadius: 10, background: '#fdf1ef', border: '1px solid #f2c9c3' }}>
                <Row k="Cancelled on" v={fmtDate(c.policy.cancel_date)} /><Row k="Reason" v={c.policy.cancel_remark} />
                <Row k="Refund amount" v={c.policy.refund_amount != null ? `₹ ${Number(c.policy.refund_amount).toLocaleString('en-IN')}` : null} />
                <Row k="Refund expected on" v={c.policy.refund_expected_date ? fmtDate(c.policy.refund_expected_date) : null} />
                <Row k="Recorded by" v={`${c.policy.cancelled_by || ''} · ${fmtDateTime(c.policy.cancelled_at)}`} />
              </div>)}
            <div style={{ display: 'flex', gap: 8, marginTop: 8, flexWrap: 'wrap' }}>
              <button className="btn btn-outline btn-sm" onClick={() => openBlob(`/leads/${leadId}/insurance/policy.pdf`)}>View policy PDF</button>
              {c.can_send_whatsapp && <button className="btn btn-primary btn-sm" disabled={busy} onClick={() => { if (window.confirm(`Send the insurance PDF to ${c.customer_name} (${c.mobile}) on WhatsApp?`)) sendWa() }}>Send via WhatsApp</button>}
            </div>
            {c.can_send_whatsapp && <div className="muted-note" style={{ marginTop: 4 }}>Goes to {c.customer_name} · {c.mobile}</div>}
            {c.can_cancel_policy && c.policy.status !== 'CANCELLED' && !cx && <div style={{ marginTop: 12 }}><button type="button" className="btn btn-outline btn-sm" style={{ color: '#b3261e', borderColor: '#e8b4ae' }} onClick={() => { setMsg(null); setCx({ cancel_date: '', remark: '', refund_amount: '', refund_expected_date: '' }) }}>Cancel this policy</button></div>}
            {cx && (
              <div style={{ marginTop: 12, padding: 14, border: '1px solid #f2c9c3', borderRadius: 12, background: '#fffafa' }}>
                <div style={{ fontWeight: 700, marginBottom: 8 }}>Cancel policy {c.policy.policy_no}</div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(190px,1fr))', gap: 10 }}>
                  <div className="field"><label>Cancellation date *</label><input className="input" type="date" value={cx.cancel_date} onChange={(e) => setCx({ ...cx, cancel_date: e.target.value })} /></div>
                  <div className="field"><label>Refund amount (₹)</label><input className="input" type="number" min="0" value={cx.refund_amount} onChange={(e) => setCx({ ...cx, refund_amount: e.target.value })} /></div>
                  <div className="field"><label>Expected refund date</label><input className="input" type="date" value={cx.refund_expected_date} onChange={(e) => setCx({ ...cx, refund_expected_date: e.target.value })} /></div>
                </div>
                <div className="field"><label>Remark / reason *</label><textarea className="input" rows={2} value={cx.remark} onChange={(e) => setCx({ ...cx, remark: e.target.value })} /></div>
                <div style={{ display: 'flex', gap: 8 }}>
                  <button type="button" className="btn btn-primary btn-sm" disabled={busy} onClick={() => { if (window.confirm('Cancel this policy? It will be shown as Cancelled everywhere.')) cancelPolicy() }}>Confirm cancellation</button>
                  <button type="button" className="btn btn-outline btn-sm" onClick={() => setCx(null)}>Keep policy active</button>
                </div>
              </div>)}
            {c.can_cancel_policy && c.policy.status === 'CANCELLED' && (react === null
              ? <div style={{ marginTop: 10 }}><button type="button" className="btn btn-outline btn-sm" onClick={() => { setMsg(null); setReact('') }}>Make policy active again</button></div>
              : <div style={{ marginTop: 10, display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
                  <input className="input" style={{ maxWidth: 340 }} placeholder="Why is it active again? *" value={react} onChange={(e) => setReact(e.target.value)} />
                  <button type="button" className="btn btn-primary btn-sm" disabled={busy} onClick={reactivate}>Confirm</button>
                  <button type="button" className="btn btn-outline btn-sm" onClick={() => setReact(null)}>Cancel</button></div>)}
            {c.can_add_new_policy && (
              <div style={{ marginTop: 12, padding: '12px 14px', borderRadius: 10, background: '#f3f8ff', border: '1px solid #cfe0fa' }}>
                <div style={{ fontWeight: 600, marginBottom: 6 }}>Was this policy rejected or replaced? Add a new one.</div>
                <div className="muted-note" style={{ marginBottom: 8 }}>The cancelled policy and its refund details move to &quot;Previous policies&quot;. The documents and nominee stay, so you only enter the new policy and its PDF.</div>
                <button type="button" className="btn btn-primary btn-sm" disabled={busy} onClick={() => { if (window.confirm('Add a new policy? The cancelled policy moves to the history.')) addNew() }}>Add new policy</button>
              </div>)}
            <Msg area="pol" />
          </div>
        ) : (
          <div>
            {(c.previous_policies || []).length > 0 && <div className="hint" style={{ marginBottom: 8 }}>The earlier policy was cancelled. Enter the new policy&apos;s details and upload its PDF.</div>}
            {!(allDocs && !c.nominee.missing.length) && <div className="muted-note" style={{ marginBottom: 8 }}>Finish the policy type, documents, nominee and document verification first{c.nominee.missing.length ? ` (nominee missing: ${c.nominee.missing.join(', ')})` : ''}.</div>}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(180px,1fr))', gap: 10 }}>
              <div className="field"><label>Policy number *</label><input className="input" disabled={!ed} value={pol.policy_no} onChange={(e) => setPol({ ...pol, policy_no: e.target.value })} /></div>
              <div className="field"><label>Start date *</label><input className="input" type="date" disabled={!ed} value={pol.policy_start} onChange={(e) => setPol({ ...pol, policy_start: e.target.value })} /></div>
              <div className="field"><label>Expiry date *</label><input className="input" type="date" disabled={!ed} value={pol.policy_expiry} onChange={(e) => setPol({ ...pol, policy_expiry: e.target.value })} /></div>
              <div className="field"><label>Premium (₹)</label><input className="input" type="number" min="0" disabled={!ed} value={pol.premium} onChange={(e) => setPol({ ...pol, premium: e.target.value })} /></div>
              <div className="field"><label>Insurance PDF *</label><input className="input" type="file" accept=".pdf" disabled={!ed} onChange={(e) => setPolFile(e.target.files?.[0] || null)} /></div>
            </div>
            {ed && <button className="btn btn-primary btn-sm" disabled={busy || !c.docs_verified?.at || !polFile || !pol.policy_no || !pol.policy_start || !pol.policy_expiry} onClick={savePolicy}>Complete insurance</button>}
            <Msg area="pol" />
          </div>)}
        {(c.previous_policies || []).length > 0 && (
          <div style={{ marginTop: 18 }}>
            <div style={{ fontWeight: 700, marginBottom: 8 }}>Previous policies <span className="muted-note">(cancelled)</span></div>
            {c.previous_policies.map((h) => (
              <div key={h.id} style={{ padding: '10px 14px', border: '1px solid #ecd9d6', borderRadius: 10, background: '#fffafa', marginBottom: 8 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
                  <div><b>{h.company}</b> · {h.policy_no} <span className="badge badge-red" style={{ marginLeft: 6 }}>Cancelled</span></div>
                  {h.has_pdf && <button type="button" className="btn btn-outline btn-sm" onClick={() => openBlob(`/insurance/cases/${leadId}/previous-policies/${h.id}/pdf`)}>View PDF</button>}
                </div>
                <div className="muted-note" style={{ marginTop: 4 }}>Valid {fmtDate(h.start)} → {fmtDate(h.expiry)}{h.premium != null ? ` · Premium ₹ ${Number(h.premium).toLocaleString('en-IN')}` : ''}</div>
                <div style={{ marginTop: 6, fontSize: 13.5 }}>Cancelled on {fmtDate(h.cancel_date)}: {h.cancel_remark}</div>
                <div style={{ fontSize: 13.5 }}>Refund {h.refund_amount != null ? `₹ ${Number(h.refund_amount).toLocaleString('en-IN')}` : '—'}{h.refund_expected_date ? ` · expected by ${fmtDate(h.refund_expected_date)}` : ''}
                  <span className="muted-note"> · recorded by {h.cancelled_by || '—'}</span></div>
              </div>))}
          </div>)}
      </Step>

      {wa && wa.length > 0 && (
        <Step id="wa" open={open} toggle={toggle} title="WhatsApp log">
          <table className="data-table"><thead><tr><th>Sent</th><th>To</th><th>Status</th><th>Sent by</th><th>Reason</th></tr></thead>
            <tbody>{wa.map((m) => <tr key={m.id}><td>{fmtDateTime(m.at)}</td><td>{m.to}</td><td>{m.status}</td><td>{m.by || '—'}</td><td>{m.error || '—'}</td></tr>)}</tbody></table>
        </Step>)}
    </Layout>
  )
}
