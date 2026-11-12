// Admin: branches (name, code, branch WhatsApp number) and who works in each.
import { useEffect, useState } from 'react'
import Layout from '../../components/Layout'
import api from '../../lib/api'

const EMPTY = { name: '', dealer_code: '', city: '', address: '', contact_no: '', whatsapp_number: '', is_active: true }

export default function BranchesPage() {
  const [rows, setRows] = useState([])
  const [form, setForm] = useState(EMPTY)
  const [editing, setEditing] = useState(null)
  const [msg, setMsg] = useState('')
  const load = () => api.get('/admin/branch-setup').then((r) => setRows(r.data)).catch(() => setRows([]))
  useEffect(() => { load() }, [])
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value })

  async function save(e) {
    e.preventDefault(); setMsg('')
    try {
      if (editing) await api.put(`/admin/branch-setup/${editing}`, form)
      else await api.post('/admin/branch-setup', form)
      setMsg(editing ? 'Branch updated.' : 'Branch added.'); setForm(EMPTY); setEditing(null); load()
    } catch (err) { setMsg(err.response?.data?.detail || 'Save failed.') }
  }
  const edit = (b) => { setEditing(b.branch_id); setForm({ ...EMPTY, ...Object.fromEntries(Object.entries(b).map(([k, v]) => [k, v ?? ''])), is_active: b.is_active }) }

  return (
    <Layout title="Branches" sub="Admin · branch names, codes and branch WhatsApp numbers">
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(300px,1fr))', gap: 22, alignItems: 'start' }}>
        <div className="card">
          <div className="card-header"><h3>{editing ? 'Edit branch' : 'Add branch'}</h3></div>
          <form className="card-pad" onSubmit={save}>
            <div className="field"><label>Branch name *</label><input className="input" value={form.name} onChange={set('name')} required /></div>
            <div className="field"><label>Branch code</label><input className="input" value={form.dealer_code} onChange={set('dealer_code')} placeholder="e.g. C12746" /></div>
            <div className="field"><label>City</label><input className="input" value={form.city} onChange={set('city')} /></div>
            <div className="field"><label>Address</label><input className="input" value={form.address} onChange={set('address')} /></div>
            <div className="field"><label>Branch phone</label><input className="input" value={form.contact_no} onChange={set('contact_no')} /></div>
            <div className="field"><label>Branch WhatsApp number <span className="muted-note">(receives PBA alerts)</span></label>
              <input className="input" value={form.whatsapp_number} onChange={set('whatsapp_number')} placeholder="10-digit number" /></div>
            {editing && <label className="checkbox-row"><input type="checkbox" checked={form.is_active} onChange={(e) => setForm({ ...form, is_active: e.target.checked })} /> Active</label>}
            <div style={{ display: 'flex', gap: 10, marginTop: 8 }}>
              {editing && <button type="button" className="btn btn-outline" style={{ flex: 1 }} onClick={() => { setEditing(null); setForm(EMPTY) }}>Cancel</button>}
              <button className="btn btn-primary" style={{ flex: 2 }}>{editing ? 'Save changes' : 'Add branch'}</button>
            </div>
            {msg && <div className="hint" style={{ marginTop: 12 }}>{msg}</div>}
          </form>
        </div>
        <div className="card">
          <div className="card-header"><h3>Branches <span className="muted-note">({rows.length})</span></h3></div>
          <div className="table-wrap">
            <table className="data-table"><thead><tr><th>Branch</th><th>Code</th><th>WhatsApp</th><th>Branch login</th><th>PBAs</th><th /></tr></thead>
              <tbody>{rows.map((b) => (
                <tr key={b.branch_id}>
                  <td className="cell-primary">{b.name}{!b.is_active && <span className="badge badge-gray" style={{ marginLeft: 6 }}>Inactive</span>}<div className="muted-note">{b.city}</div></td>
                  <td>{b.dealer_code || '—'}</td><td>{b.whatsapp_number || '—'}</td>
                  <td>{b.branch_login || <span className="badge badge-amber">None yet</span>}</td>
                  <td>{b.pbas.length === 0 ? '—' : b.pbas.map((p) => (
                    <div key={p.user_id}>{p.full_name} <span className="muted-note">{p.login_enabled ? 'own login' : p.has_pin ? 'PIN' : 'no PIN'}</span></div>))}</td>
                  <td><button className="btn btn-outline btn-sm" onClick={() => edit(b)}>Edit</button></td></tr>))}</tbody></table>
          </div>
        </div>
      </div>
    </Layout>
  )
}
