// RTO documents checklist: PDF only, max 100 KB each. PBA / CRE / RTO / Admin can upload; Owner / GM view.
import { useEffect, useRef, useState } from 'react'
import api from '../../lib/api'
import { useAuth } from '../../lib/auth'
import { Loading, fmtDateTime } from '../../components/ui'

export default function RtoDocsCard({ leadId, embedded = false, onChanged, refreshKey }) {
  const { user } = useAuth()
  const canEdit = ['PBA', 'CRE', 'RTO', 'ADMIN'].includes(user?.role)
  const [d, setD] = useState(null)
  const [msg, setMsg] = useState(null)
  const [busy, setBusy] = useState('')
  const refs = useRef({})
  const load = () => api.get(`/rto-docs/${leadId}`).then((r) => setD(r.data)).catch(() => setD(false))
  useEffect(() => { load() }, [leadId, refreshKey])

  async function save(patch) {
    setMsg(null)
    try { const r = await api.patch(`/rto-docs/${leadId}`, patch); setD(r.data) }
    catch (e) { setMsg(e.response?.data?.detail || 'Could not save.') }
  }
  async function upload(type, file) {
    if (!file) return
    setMsg(null)
    if (!file.name.toLowerCase().endsWith('.pdf')) { setMsg('Only PDF files are accepted.'); return }
    if (file.size > d.max_kb * 1024) { setMsg(`${file.name} is ${Math.ceil(file.size / 1024)} KB. The limit is ${d.max_kb} KB per file.`); return }
    setBusy(type)
    try {
      const fd = new FormData(); fd.append('doc_type', type); fd.append('file', file)
      const r = await api.post(`/rto-docs/${leadId}/documents`, fd, { headers: { 'Content-Type': 'multipart/form-data' } })
      setD(r.data)
      if (onChanged) onChanged()
    } catch (e) { setMsg(e.response?.data?.detail || 'Upload failed.') } finally { setBusy('') }
  }
  async function askCustomer() {
    if (!window.confirm('Send the RTO document request to the customer on WhatsApp?')) return
    setMsg(null)
    try {
      const r = await api.post(`/leads/${leadId}/whatsapp/rto-docs`)
      setMsg(r.data.status === 'FAILED' ? `WhatsApp failed: ${r.data.error || 'see the WhatsApp log'}` : 'Document request sent to the customer on WhatsApp.')
    } catch (e) { setMsg(e.response?.data?.detail || 'Could not send.') }
  }
  async function open(id, name) {
    try {
      const res = await api.get(`/documents/${id}/file`, { responseType: 'blob' })
      window.open(URL.createObjectURL(new Blob([res.data], { type: 'application/pdf' })), '_blank', 'noopener')
    } catch { setMsg('Could not open this file.') }
  }
  if (d === null) return <div className="card"><Loading /></div>
  if (d === false) return null
  const done = d.checklist.filter((c) => c.uploaded).length
  return (
    <div className={embedded ? '' : 'card'}>
      <div className={embedded ? 'sub-header' : 'card-header'} style={{ display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: 8 }}>
        <h3>RTO Documents <span className="muted-note">({done}/{d.checklist.length})</span></h3>
        {canEdit && <button type="button" className="btn btn-outline btn-sm" onClick={askCustomer}>Ask customer for documents (WhatsApp)</button>}
        {d.status === 'COMPLETE' ? <span className="badge badge-green">All RTO documents ready</span> : <span className="badge badge-amber">{d.missing.length} pending</span>}
      </div>
      <div className="card-pad">
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 12, marginBottom: 12 }}>
          <div className="field" style={{ marginBottom: 0 }}><label>Customer is staying in</label>
            <select className="input" disabled={!canEdit} value={d.residence || ''} onChange={(e) => save({ residence: e.target.value || null })}>
              <option value="">— select —</option><option value="OWN">Own house</option><option value="RENTED">Rented property</option></select></div>
          {d.residence === 'RENTED' && <div className="field" style={{ marginBottom: 0 }}><label>Rent agreement</label>
            <select className="input" disabled={!canEdit} value={d.rent_option || ''} onChange={(e) => save({ rent_option: e.target.value || null })}>
              <option value="">— select —</option><option value="REGISTERED">Option 1: Registered (+ Index II, Police NOC)</option>
              <option value="NOTARIZED">Option 2: Notarized (+ Police NOC, Electricity Bill)</option></select></div>}
          <label style={{ display: 'flex', gap: 8, alignItems: 'center', fontSize: 14 }}>
            <input type="checkbox" disabled={!canEdit} checked={d.aadhaar_mobile_linked} onChange={(e) => save({ aadhaar_mobile_linked: e.target.checked })} />
            Mobile number linked to Aadhaar Card (confirmed)</label>
        </div>
        <div className="hint" style={{ marginBottom: 10 }}>All documents must be PDF, maximum {d.max_kb} KB each, clear, valid and readable. Registration type (Regular / Choice / BH passing) is chosen with the invoice details.</div>
        {msg && <div className="hint" style={{ marginBottom: 10, background: 'var(--red-light)', color: '#7a2318' }}>{msg}</div>}
        <table className="data-table"><thead><tr><th>Document</th><th>Status</th><th>File</th><th>Uploaded</th><th></th></tr></thead>
          <tbody>{d.checklist.map((c) => (
            <tr key={c.doc_type}>
              <td className="cell-primary">{c.label}</td>
              <td>{c.uploaded ? <span className="badge badge-green">✓ Uploaded{c.via_kyc ? ' (from Customer documents)' : ''}</span> : <span className="badge badge-gray">○ Pending</span>}</td>
              <td>{c.uploaded ? <button type="button" className="btn btn-outline btn-sm" onClick={() => open(c.doc_id)}>{c.file_name} · {Math.ceil(c.size_bytes / 1024)} KB</button> : '—'}</td>
              <td className="cell-muted">{c.uploaded ? `${fmtDateTime(c.uploaded_at)}${c.uploaded_by ? ' · ' + c.uploaded_by : ''}` : '—'}</td>
              <td>{canEdit && <>
                <input ref={(el) => { refs.current[c.doc_type] = el }} type="file" accept=".pdf,application/pdf" style={{ display: 'none' }}
                  onChange={(e) => { upload(c.doc_type, e.target.files?.[0]); e.target.value = '' }} />
                <button type="button" className="btn btn-primary btn-sm" disabled={busy === c.doc_type} onClick={() => refs.current[c.doc_type]?.click()}>
                  {busy === c.doc_type ? 'Uploading…' : c.uploaded ? 'Replace' : 'Upload PDF'}</button></>}</td>
            </tr>))}</tbody></table>
      </div>
    </div>)
}
