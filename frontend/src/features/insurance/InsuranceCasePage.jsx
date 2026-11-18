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
    <div className="card" style={{ marginBottom: 12, overflow: 'hidden' }}>
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
  const [open, setOpen] = useState({})
  const toggle = (id) => setOpen((o) => ({ ...o, [id]: !o[id] }))
  const opened = useRef(false)
  useEffect(() => {          // first time the case loads: open only the first unfinished step
    if (!c || opened.current) return
    opened.current = true
    const docsOk = c.documents.length > 0 && c.documents.every((d) => d.uploaded)
    const order = [['type', !!c.policy_type], ['docs', docsOk], ['nom', !c.nominee.missing.length], ['ver', !!c.docs_verified?.at], ['pol', c.status === 'COMPLETED']]
    setOpen({ [(order.find(([, done]) => !done) || ['pol'])[0]]: true })
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
  const upDoc = (t, file) => file && run(() => { const fd = new FormData(); fd.append('doc_type', t); fd.append('file', file); return api.post(`/insurance/cases/${leadId}/documents`, fd, { headers: { 'Content-Type': 'multipart/form-data' } }) }, 'Document uploaded.')
  const saveNominee = () => run(() => api.put(`/leads/${leadId}/insurance`, { nominee_name: nom.nominee_name, nominee_age: Number(nom.nominee_age) || null, nominee_relation: nom.nominee_relation, nominee_relation_other: nom.nominee_relation === 'Other' ? nom.nominee_relation_other : null }), 'Nominee saved.', 'nom')
  const savePolicy = () => run(() => { const fd = new FormData(); Object.entries(pol).forEach(([k, v]) => v !== '' && fd.append(k, v)); if (polFile) fd.append('file', polFile); return api.post(`/leads/${leadId}/insurance/policy`, fd, { headers: { 'Content-Type': 'multipart/form-data' } }) }, 'Insurance completed. The PBA has been notified.', 'pol')
  const verify = () => run(() => api.post(`/insurance/cases/${leadId}/verify-documents`), 'Documents marked as verified.', 'ver')
  const sendWa = () => run(() => api.post(`/leads/${leadId}/whatsapp/insurance`), 'WhatsApp request sent — see the log below.', 'pol')

  if (!c) return <Layout title="Insurance case" back={back}>{msg ? <div className="hint">{msg.text}</div> : <Loading />}</Layout>
  const ed = c.can_edit
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

      <Step id="cust" open={open} toggle={toggle} title={<>Customer &amp; booking <span className="muted-note">(read-only)</span></>}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(260px,1fr))', gap: '0 24px' }}>
          <div><Row k="Booking ID" v={c.booking_no} /><Row k="Customer" v={c.customer_name} /><Row k="Mobile" v={c.mobile} /><Row k="Branch" v={c.branch} /></div>
          <div><Row k="Vehicle" v={[c.model, c.color].filter(Boolean).join(' · ')} /><Row k="PBA" v={c.pba_name} /><Row k="PBA employee ID" v={c.pba_employee_id} /><Row k="Booking date" v={fmtDate(c.booking_date)} /></div>
        </div>
      </Step>

      <Step id="type" open={open} toggle={toggle} title={<>1. Policy type *</>} done={!!c.policy_type}>
        <select className="input" style={{ maxWidth: 360 }} disabled={!ed || busy} value={c.policy_type || ''} onChange={(e) => e.target.value && setType(e.target.value)}>
          <option value="">Select insurance policy type</option>
          {c.options.policy_types.map((p) => <option key={p.value} value={p.value}>{p.label}</option>)}</select>
      </Step>

      <Step id="docs" open={open} toggle={toggle} title={<>2. Documents</>} done={allDocs}>
        {!c.policy_type && <div className="muted-note">Select the policy type to see the documents needed.</div>}
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
        {c.policy_type === 'CUSTOMER_BAGIC' && <div className="muted-note" style={{ marginTop: 6 }}>BAGIC: Aadhaar front and back must be ONE PDF. If the PBA&apos;s file is only one side, upload the full Aadhaar PDF here.</div>}
      </Step>

      <Step id="nom" open={open} toggle={toggle} title={<>3. Nominee details *</>} done={!c.nominee.missing.length}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(180px,1fr))', gap: 10 }}>
          <div className="field"><label>Nominee name</label><input className="input" disabled={!ed} value={nom.nominee_name} onChange={(e) => setNom({ ...nom, nominee_name: e.target.value })} /></div>
          <div className="field"><label>Nominee age</label><input className="input" type="number" min="1" max="120" disabled={!ed} value={nom.nominee_age} onChange={(e) => setNom({ ...nom, nominee_age: e.target.value })} /></div>
          <div className="field"><label>Relation</label><select className="input" disabled={!ed} value={nom.nominee_relation} onChange={(e) => setNom({ ...nom, nominee_relation: e.target.value })}>
            <option value="">Select</option>{c.options.nominee_relations.map((r) => <option key={r}>{r}</option>)}</select></div>
          {nom.nominee_relation === 'Other' && <div className="field"><label>Specify relation</label><input className="input" disabled={!ed} value={nom.nominee_relation_other} onChange={(e) => setNom({ ...nom, nominee_relation_other: e.target.value })} /></div>}
        </div>
        {ed && <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
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
            <Row k="Created" v={fmtDateTime(c.policy.created_at)} /><Row k="Executive" v={c.policy.executive} /><Row k="Status" v="COMPLETED" />
            <div style={{ display: 'flex', gap: 8, marginTop: 8, flexWrap: 'wrap' }}>
              <button className="btn btn-outline btn-sm" onClick={() => openBlob(`/leads/${leadId}/insurance/policy.pdf`)}>View policy PDF</button>
              {c.can_send_whatsapp && <button className="btn btn-primary btn-sm" disabled={busy} onClick={() => { if (window.confirm(`Send the insurance PDF to ${c.customer_name} (${c.mobile}) on WhatsApp?`)) sendWa() }}>Send via WhatsApp</button>}
            </div>
            {c.can_send_whatsapp && <div className="muted-note" style={{ marginTop: 4 }}>Goes to {c.customer_name} · {c.mobile}</div>}
            <Msg area="pol" />
          </div>
        ) : (
          <div>
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
      </Step>

      {wa && wa.length > 0 && (
        <Step id="wa" open={open} toggle={toggle} title="WhatsApp log">
          <table className="data-table"><thead><tr><th>Sent</th><th>To</th><th>Status</th><th>Sent by</th><th>Reason</th></tr></thead>
            <tbody>{wa.map((m) => <tr key={m.id}><td>{fmtDateTime(m.at)}</td><td>{m.to}</td><td>{m.status}</td><td>{m.by || '—'}</td><td>{m.error || '—'}</td></tr>)}</tbody></table>
        </Step>)}
    </Layout>
  )
}
