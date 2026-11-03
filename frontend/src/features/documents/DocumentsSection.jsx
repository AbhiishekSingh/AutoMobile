// Customer Documents — upload section on the Customer Details page.
//
// PBA / CRE upload the customer's KYC documents (Aadhaar, PAN, electricity
// bill or rent agreement, ...) against the lead. Owner / GM / Admin can view
// and download but not upload. Rules (size limit, file types, max files per
// lead) come from the server: app/modules/documents/service.py — the checks
// here only save the PBA a wasted upload; the server checks again.
import { useEffect, useRef, useState } from 'react'
import api from '../../lib/api'
import { isSales } from '../../lib/roles'
import { useAuth } from '../../lib/auth'
import { Empty, Loading, fmtDateTime } from '../../components/ui'

const fmtSize = (b) => (b >= 1024 * 1024 ? `${(b / 1024 / 1024).toFixed(1)} MB` : `${Math.max(1, Math.round(b / 1024))} KB`)

export default function DocumentsSection({ leadId }) {
  const { user } = useAuth()
  const canUpload = isSales(user)
  const fileRef = useRef(null)

  const [cfg, setCfg] = useState(null)          // { types, max_mb, allowed_extensions, max_files_per_lead }
  const [docs, setDocs] = useState(null)
  const [docType, setDocType] = useState('')
  const [note, setNote] = useState('')
  const [file, setFile] = useState(null)
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState(null)          // { type: 'ok' | 'error', text }

  function load() {
    api.get(`/leads/${leadId}/documents`).then((r) => setDocs(r.data)).catch(() => setDocs([]))
  }
  useEffect(() => {
    api.get('/documents/settings').then((r) => setCfg(r.data)).catch(() => {})
    load()
  }, [leadId])

  const label = (v) => cfg?.types.find((t) => t.value === v)?.label || v
  const accept = cfg ? cfg.allowed_extensions.join(',') : '.pdf,.jpg,.jpeg,.png'

  // Checklist: required KYC; electricity bill OR rent agreement counts as one.
  const have = new Set((docs || []).map((d) => d.doc_type))
  const checklist = []
  for (const t of cfg?.types || []) {
    if (!t.required) continue
    if (t.either_with) {
      if (checklist.some((c) => c.key === `${t.either_with}|${t.value}`)) continue
      checklist.push({ key: `${t.value}|${t.either_with}`, label: `${label(t.value).replace(/ \(.*\)/, '')} or ${label(t.either_with).replace(/ \(.*\)/, '')}`,
                       done: have.has(t.value) || have.has(t.either_with) })
    } else {
      checklist.push({ key: t.value, label: t.label, done: have.has(t.value) })
    }
  }
  const missing = checklist.filter((c) => !c.done).length

  function pick(e) {
    const f = e.target.files?.[0] || null
    setMsg(null)
    if (f && cfg && f.size > cfg.max_mb * 1024 * 1024) {
      setMsg({ type: 'error', text: `${f.name} is ${fmtSize(f.size)}. The limit is ${cfg.max_mb} MB per file.` })
      e.target.value = ''
      setFile(null)
      return
    }
    setFile(f)
  }

  async function upload(e) {
    e.preventDefault()
    if (!docType) { setMsg({ type: 'error', text: 'Please choose the document type.' }); return }
    if (!file) { setMsg({ type: 'error', text: 'Please choose a file.' }); return }
    setBusy(true); setMsg(null)
    try {
      const fd = new FormData()
      fd.append('doc_type', docType)
      if (note.trim()) fd.append('note', note.trim())
      fd.append('file', file)
      await api.post(`/leads/${leadId}/documents`, fd, { headers: { 'Content-Type': 'multipart/form-data' } })
      setMsg({ type: 'ok', text: `${label(docType)} uploaded.` })
      setFile(null); setNote(''); setDocType('')
      if (fileRef.current) fileRef.current.value = ''
      load()
    } catch (err) {
      setMsg({ type: 'error', text: err.response?.data?.detail || 'Upload failed. Please try again.' })
    } finally {
      setBusy(false)
    }
  }

  // Files need the login token, so fetch them as a blob instead of a plain link.
  async function openDoc(d, download = false) {
    try {
      const res = await api.get(`/documents/${d.id}/file`, { responseType: 'blob', params: { download } })
      const url = URL.createObjectURL(new Blob([res.data], { type: d.content_type }))
      if (download) {
        const a = document.createElement('a')
        a.href = url; a.download = d.original_name; a.click()
      } else {
        window.open(url, '_blank', 'noopener')
      }
      setTimeout(() => URL.revokeObjectURL(url), 60000)
    } catch {
      setMsg({ type: 'error', text: 'Could not open this file.' })
    }
  }

  async function remove(d) {
    if (!window.confirm(`Remove ${label(d.doc_type)} (${d.original_name})?`)) return
    try {
      await api.delete(`/documents/${d.id}`)
      setMsg({ type: 'ok', text: 'File removed.' })
      load()
    } catch (err) {
      setMsg({ type: 'error', text: err.response?.data?.detail || 'Could not remove this file.' })
    }
  }

  return (
    <div className="card">
      <div className="card-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 8 }}>
        <h3>Customer Documents <span className="muted-note">({docs ? docs.length : '…'})</span></h3>
        {cfg && docs && (missing === 0
          ? <span className="badge badge-green">All required KYC uploaded</span>
          : <span className="badge badge-amber">{missing} required document{missing > 1 ? 's' : ''} missing</span>)}
      </div>

      {/* required KYC checklist */}
      {cfg && (
        <div className="card-pad" style={{ display: 'flex', gap: 8, flexWrap: 'wrap', paddingBottom: 0 }}>
          {checklist.map((c) => (
            <span key={c.key} className={'badge ' + (c.done ? 'badge-green' : 'badge-gray')}>
              {c.done ? '✓' : '○'} {c.label}
            </span>
          ))}
        </div>
      )}

      {canUpload && (
        <form className="card-pad" onSubmit={upload}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 12, alignItems: 'end' }}>
            <div className="field" style={{ marginBottom: 0 }}><label>Document type *</label>
              <select className="input" value={docType} onChange={(e) => setDocType(e.target.value)}>
                <option value="">— select —</option>
                {cfg?.types.map((t) => <option key={t.value} value={t.value}>{t.label}{t.required ? ' *' : ''}</option>)}
              </select></div>
            <div className="field" style={{ marginBottom: 0 }}><label>File *</label>
              <input ref={fileRef} className="input" type="file" accept={accept} onChange={pick} /></div>
            <div className="field" style={{ marginBottom: 0 }}><label>Note</label>
              <input className="input" value={note} onChange={(e) => setNote(e.target.value)} placeholder="e.g. back side, cheque 2" maxLength={120} /></div>
            <div><button className="btn btn-primary" disabled={busy || !cfg}>{busy ? 'Uploading…' : 'Upload'}</button></div>
          </div>
          <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 8 }}>
            PDF, JPG or PNG · up to {cfg?.max_mb ?? 5} MB per file · * required for booking.
            Electricity bill (own house) or rent agreement (rented house) — either one is enough.
          </div>
          {msg && (
            <div className="hint" style={{ marginTop: 10, ...(msg.type === 'error' ? { background: 'var(--red-light)', color: '#7a2318' } : {}) }}>
              {msg.text}
            </div>
          )}
        </form>
      )}
      {!canUpload && msg && <div className="card-pad"><div className="hint">{msg.text}</div></div>}

      <div className="table-wrap">
        <table className="data-table">
          <thead><tr><th>Document</th><th>File</th><th>Size</th><th>Uploaded</th><th>By</th><th></th></tr></thead>
          <tbody>
            {docs?.map((d) => (
              <tr key={d.id}>
                <td className="cell-primary">{label(d.doc_type)}{d.note ? <div className="muted-note" style={{ fontSize: 12 }}>{d.note}</div> : null}</td>
                <td style={{ maxWidth: 220, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={d.original_name}>{d.original_name}</td>
                <td className="cell-muted">{fmtSize(d.size_bytes)}</td>
                <td className="cell-muted">{fmtDateTime(d.uploaded_at)}</td>
                <td>{d.uploaded_by || '—'}</td>
                <td style={{ whiteSpace: 'nowrap' }}>
                  <button type="button" className="btn btn-outline btn-sm" onClick={() => openDoc(d)}>View</button>{' '}
                  <button type="button" className="btn btn-outline btn-sm" onClick={() => openDoc(d, true)}>Download</button>{' '}
                  {d.uploaded_by_user_id === user?.user_id && (
                    <button type="button" className="btn btn-outline btn-sm" onClick={() => remove(d)}>Remove</button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {docs === null && <Loading />}
        {docs && docs.length === 0 && <Empty>No documents uploaded yet.</Empty>}
      </div>
    </div>
  )
}
