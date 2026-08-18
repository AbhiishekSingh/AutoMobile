import { useEffect, useRef, useState } from 'react'
import Layout from '../../components/Layout'
import api from '../../lib/api'

function Stat({ label, value, accent = '#0F172A' }) {
  return (
    <div className="card" style={{ margin: 0 }}>
      <div className="card-pad">
        <div style={{ fontSize: 12, color: 'var(--muted)', fontWeight: 600 }}>{label}</div>
        <div style={{ fontSize: 26, fontWeight: 800, color: accent, marginTop: 4 }}>{value}</div>
      </div>
    </div>
  )
}

export default function ImportPage() {
  const fileRef = useRef(null)
  const [file, setFile] = useState(null)
  const [branchId, setBranchId] = useState('')
  const [branches, setBranches] = useState([])
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    api.get('/admin/branches').then((r) => setBranches(r.data)).catch(() => setBranches([]))
  }, [])

  function pick(e) {
    const f = e.target.files?.[0]
    setFile(f || null); setResult(null); setError('')
  }

  async function upload(e) {
    e.preventDefault()
    if (!file) { setError('Please choose a .csv file first.'); return }
    setBusy(true); setError(''); setResult(null)
    try {
      const fd = new FormData()
      fd.append('file', file)
      if (branchId) fd.append('branch_id', branchId)
      const { data } = await api.post('/admin/leads/import', fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      setResult(data)
    } catch (err) {
      setError(err.response?.data?.detail || 'Upload failed. Check the file and try again.')
    } finally {
      setBusy(false)
      if (fileRef.current) fileRef.current.value = ''
      setFile(null)
    }
  }

  return (
    <Layout title="Import Leads" sub="Upload a LeadSquared Enquiry Statement CSV">
      <div className="card">
        <div className="card-header"><h3>Upload CSV</h3></div>
        <form className="card-pad" onSubmit={upload}>
          <div className="field">
            <label>LeadSquared CSV file</label>
            <input ref={fileRef} className="input" type="file" accept=".csv" onChange={pick} />
          </div>

          <div className="field" style={{ maxWidth: 360 }}>
            <label>Assign all leads to branch <span style={{ color: 'var(--muted)', fontWeight: 400 }}>(optional)</span></label>
            <select className="input" value={branchId} onChange={(e) => setBranchId(e.target.value)}>
              <option value="">Use branch from the CSV file</option>
              {branches.map((b) => <option key={b.branch_id} value={b.branch_id}>{b.name}</option>)}
            </select>
            <div style={{ fontSize: 11.5, color: 'var(--muted)', marginTop: 6 }}>
              Pick a branch so the leads are visible to that branch's PBA. Leave as-is to keep each row's own branch.
            </div>
          </div>

          <button className="btn btn-primary" disabled={busy}>
            {busy ? 'Importing…' : '⬆️ Upload & Import'}
          </button>
          {file && !busy && <span style={{ marginLeft: 12, color: 'var(--muted)', fontSize: 12.5 }}>Selected: {file.name}</span>}
          {error && <div className="hint" style={{ marginTop: 14, background: 'var(--red-light)', color: '#7a2318' }}>{error}</div>}
        </form>
      </div>

      {busy && (
        <div className="card"><div className="card-pad" style={{ color: 'var(--muted)' }}>
          Importing — large files (a few thousand rows) can take a few seconds. Please wait…
        </div></div>
      )}

      {result && (
        <>
          <div className="card">
            <div className="card-header"><h3>Import Summary <span className="muted-note">· {result.filename}</span></h3></div>
            <div className="card-pad" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))', gap: 14 }}>
              <Stat label="Rows read" value={result.rows_read} />
              <Stat label="Leads created" value={result.leads_created} accent="#059669" />
              <Stat label="New customers" value={result.customers_new} accent="#2563EB" />
              <Stat label="Matched customers" value={result.customers_matched} accent="#2563EB" />
              <Stat label="Test rides created" value={result.test_rides_created} />
              <Stat label="Skipped (duplicates)" value={result.skipped_duplicates} accent="#D97706" />
              <Stat label="Skipped (invalid)" value={result.skipped_invalid} accent="#DC2626" />
            </div>
          </div>

          {result.errors?.length > 0 && (
            <div className="card">
              <div className="card-header"><h3>Rows with issues <span className="muted-note">({result.errors.length})</span></h3></div>
              <div className="card-pad">
                <ul style={{ margin: 0, paddingLeft: 18, color: '#7a2318', fontSize: 13 }}>
                  {result.errors.map((e, i) => <li key={i} style={{ marginBottom: 4 }}>{e}</li>)}
                </ul>
              </div>
            </div>
          )}

          <div className="hint">
            Done. The imported leads now appear in the PBA Leads, Customers, and Follow-Up screens
            (for the assigned branch). You can safely re-upload the same file — existing enquiry numbers are skipped.
          </div>
        </>
      )}
    </Layout>
  )
}