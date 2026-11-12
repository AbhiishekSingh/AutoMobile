// One insurance case, top to bottom: customer (read-only) → policy type → documents → nominee → policy PDF → WhatsApp.
import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import api from '../../lib/api'
import Layout from '../../components/Layout'
import { Loading, fmtDate, fmtDateTime } from '../../components/ui'

const errText = (e) => e.response?.data?.detail || 'Something went wrong.'
async function openBlob(path) {
  const res = await api.get(path, { responseType: 'blob' })
  const url = URL.createObjectURL(res.data); window.open(url, '_blank', 'noopener'); setTimeout(() => URL.revokeObjectURL(url), 60000)
}

export default function InsuranceCasePage() {
  const { leadId } = useParams()
  const nav = useNavigate()
  const back = { label: 'Insurance', onClick: () => nav('/insurance') }
  const [c, setC] = useState(null)
  const [msg, setMsg] = useState(null)
  const [busy, setBusy] = useState(false)
  const [nom, setNom] = useState({ nominee_name: '', nominee_age: '', nominee_relation: '', nominee_relation_other: '' })
  const [pol, setPol] = useState({ policy_no: '', policy_start: '', policy_expiry: '', premium: '' })
  const [polFile, setPolFile] = useState(null)
  const [wa, setWa] = useState(null)

  const load = useCallback(() => api.get(`/insurance/cases/${leadId}`).then((r) => {
    setC(r.data)
    setNom({ nominee_name: r.data.nominee.name || '', nominee_age: r.data.nominee.age || '', nominee_relation: r.data.nominee.relation || '', nominee_relation_other: r.data.nominee.relation_other || '' })
    api.get(`/leads/${leadId}/whatsapp`).then((w) => setWa(w.data.messages.filter((m) => m.kind === 'INSURANCE'))).catch(() => {})
  }).catch((e) => setMsg({ ok: false, text: errText(e) })), [leadId])
  useEffect(() => { load() }, [load])

  async function run(fn, ok) {
    setBusy(true); setMsg(null)
    try { await fn(); setMsg({ ok: true, text: ok }); await load() } catch (e) { setMsg({ ok: false, text: errText(e) }) } finally { setBusy(false) }
  }
  const setType = (v) => run(() => api.put(`/leads/${leadId}/insurance`, { policy_type: v }), 'Policy type saved.')
  const upDoc = (t, file) => file && run(() => { const fd = new FormData(); fd.append('doc_type', t); fd.append('file', file); return api.post(`/insurance/cases/${leadId}/documents`, fd, { headers: { 'Content-Type': 'multipart/form-data' } }) }, 'Document uploaded.')
  const saveNominee = () => run(() => api.put(`/leads/${leadId}/insurance`, { nominee_name: nom.nominee_name, nominee_age: Number(nom.nominee_age) || null, nominee_relation: nom.nominee_relation, nominee_relation_other: nom.nominee_relation === 'Other' ? nom.nominee_relation_other : null }), 'Nominee saved.')
  const savePolicy = () => run(() => { const fd = new FormData(); Object.entries(pol).forEach(([k, v]) => v !== '' && fd.append(k, v)); if (polFile) fd.append('file', polFile); return api.post(`/leads/${leadId}/insurance/policy`, fd, { headers: { 'Content-Type': 'multipart/form-data' } }) }, 'Insurance completed. The PBA has been notified.')
  const sendWa = () => run(() => api.post(`/leads/${leadId}/whatsapp/insurance`), 'WhatsApp request sent — see the log below.')

  if (!c) return <Layout title="Insurance case" back={back}>{msg ? <div className="hint">{msg.text}</div> : <Loading />}</Layout>
  const ed = c.can_edit
  const allDocs = c.documents.length > 0 && c.documents.every((d) => d.uploaded)
  const Row = ({ k, v }) => <div style={{ display: 'flex', gap: 8, padding: '3px 0' }}><span className="muted-note" style={{ width: 130 }}>{k}</span><span>{v || '—'}</span></div>
  return (
    <Layout title={`Insurance — ${c.customer_name}`} sub={c.booking_no ? `Booking ${c.booking_no}` : ''} back={back}>
      {msg && <div className="hint" style={{ marginBottom: 12, ...(msg.ok ? {} : { background: 'var(--red-light)', color: '#7a2318' }) }}>{msg.text}</div>}

      <div className="card" style={{ padding: 14, marginBottom: 12 }}>
        <h3 style={{ marginTop: 0 }}>Customer &amp; booking <span className="muted-note">(read-only)</span></h3>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(260px,1fr))', gap: '0 24px' }}>
          <div><Row k="Booking ID" v={c.booking_no} /><Row k="Customer" v={c.customer_name} /><Row k="Mobile" v={c.mobile} /><Row k="Branch" v={c.branch} /></div>
          <div><Row k="Vehicle" v={[c.model, c.color].filter(Boolean).join(' · ')} /><Row k="PBA" v={c.pba_name} /><Row k="PBA employee ID" v={c.pba_employee_id} /><Row k="Booking date" v={fmtDate(c.booking_date)} /></div>
        </div>
      </div>

      <div className="card" style={{ padding: 14, marginBottom: 12 }}>
        <h3 style={{ marginTop: 0 }}>1. Policy type *</h3>
        <select className="input" style={{ maxWidth: 360 }} disabled={!ed || busy} value={c.policy_type || ''} onChange={(e) => e.target.value && setType(e.target.value)}>
          <option value="">Select insurance policy type</option>
          {c.options.policy_types.map((p) => <option key={p.value} value={p.value}>{p.label}</option>)}</select>
      </div>

      <div className="card" style={{ padding: 14, marginBottom: 12 }}>
        <h3 style={{ marginTop: 0 }}>2. Documents</h3>
        {!c.policy_type && <div className="muted-note">Select the policy type to see the documents needed.</div>}
        {c.documents.map((d) => (
          <div key={d.doc_type} style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap', padding: '6px 0', borderBottom: '1px solid var(--border, #eee)' }}>
            <span style={{ width: 280 }}>{d.label} <b style={{ color: '#b42318' }}>*</b></span>
            {d.uploaded ? <><span className="badge badge-green">Uploaded</span>
              <button className="btn btn-outline btn-sm" onClick={() => openBlob(`/documents/${d.doc_id}/file`)}>View</button>
              <span className="muted-note">{d.file_name}</span></> : <span className="badge badge-amber">Pending</span>}
            {ed && <input type="file" disabled={busy} accept={d.pdf_only ? '.pdf' : '.pdf,.jpg,.jpeg,.png'} onChange={(e) => { upDoc(d.doc_type, e.target.files?.[0]); e.target.value = '' }} />}
          </div>))}
        {c.policy_type === 'CUSTOMER_BAGIC' && <div className="muted-note" style={{ marginTop: 6 }}>BAGIC: Aadhaar front and back must be ONE PDF.</div>}
      </div>

      <div className="card" style={{ padding: 14, marginBottom: 12 }}>
        <h3 style={{ marginTop: 0 }}>3. Nominee details *</h3>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(180px,1fr))', gap: 10 }}>
          <div className="field"><label>Nominee name</label><input className="input" disabled={!ed} value={nom.nominee_name} onChange={(e) => setNom({ ...nom, nominee_name: e.target.value })} /></div>
          <div className="field"><label>Nominee age</label><input className="input" type="number" min="1" max="120" disabled={!ed} value={nom.nominee_age} onChange={(e) => setNom({ ...nom, nominee_age: e.target.value })} /></div>
          <div className="field"><label>Relation</label><select className="input" disabled={!ed} value={nom.nominee_relation} onChange={(e) => setNom({ ...nom, nominee_relation: e.target.value })}>
            <option value="">Select</option>{c.options.nominee_relations.map((r) => <option key={r}>{r}</option>)}</select></div>
          {nom.nominee_relation === 'Other' && <div className="field"><label>Specify relation</label><input className="input" disabled={!ed} value={nom.nominee_relation_other} onChange={(e) => setNom({ ...nom, nominee_relation_other: e.target.value })} /></div>}
        </div>
        {ed && <button className="btn btn-outline btn-sm" disabled={busy} onClick={saveNominee}>Save nominee</button>}
      </div>

      <div className="card" style={{ padding: 14, marginBottom: 12 }}>
        <h3 style={{ marginTop: 0 }}>4. Policy &amp; PDF</h3>
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
          </div>
        ) : (
          <div>
            {!(allDocs && !c.nominee.missing.length) && <div className="muted-note" style={{ marginBottom: 8 }}>Finish the policy type, documents and nominee first{c.nominee.missing.length ? ` (nominee missing: ${c.nominee.missing.join(', ')})` : ''}.</div>}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(180px,1fr))', gap: 10 }}>
              <div className="field"><label>Policy number *</label><input className="input" disabled={!ed} value={pol.policy_no} onChange={(e) => setPol({ ...pol, policy_no: e.target.value })} /></div>
              <div className="field"><label>Start date *</label><input className="input" type="date" disabled={!ed} value={pol.policy_start} onChange={(e) => setPol({ ...pol, policy_start: e.target.value })} /></div>
              <div className="field"><label>Expiry date *</label><input className="input" type="date" disabled={!ed} value={pol.policy_expiry} onChange={(e) => setPol({ ...pol, policy_expiry: e.target.value })} /></div>
              <div className="field"><label>Premium (₹)</label><input className="input" type="number" min="0" disabled={!ed} value={pol.premium} onChange={(e) => setPol({ ...pol, premium: e.target.value })} /></div>
              <div className="field"><label>Insurance PDF *</label><input className="input" type="file" accept=".pdf" disabled={!ed} onChange={(e) => setPolFile(e.target.files?.[0] || null)} /></div>
            </div>
            {ed && <button className="btn btn-primary btn-sm" disabled={busy || !polFile || !pol.policy_no || !pol.policy_start || !pol.policy_expiry} onClick={savePolicy}>Complete insurance</button>}
          </div>)}
      </div>

      {wa && wa.length > 0 && (
        <div className="card" style={{ padding: 14 }}>
          <h3 style={{ marginTop: 0 }}>WhatsApp log</h3>
          <table className="data-table"><thead><tr><th>Sent</th><th>To</th><th>Status</th><th>Sent by</th><th>Reason</th></tr></thead>
            <tbody>{wa.map((m) => <tr key={m.id}><td>{fmtDateTime(m.at)}</td><td>{m.to}</td><td>{m.status}</td><td>{m.by || '—'}</td><td>{m.error || '—'}</td></tr>)}</tbody></table>
        </div>)}
    </Layout>
  )
}
