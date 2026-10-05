import { useEffect, useState } from 'react'
import Layout from '../../components/Layout'
import api from '../../lib/api'
import { CRE_MAX_BRANCHES } from '../../lib/roles'

const ROLES = ['OWNER', 'GM', 'PBA', 'CRE', 'RTO', 'ADMIN']
// branch_id: one branch (every role except CRE)
// branch_ids: the 1-2 branches a CRE covers
const EMPTY = { login_id: '', full_name: '', email: '', password: '', role: 'PBA', branch_id: '', branch_ids: [] }

export default function Users() {
  const [users, setUsers] = useState([])
  const [branches, setBranches] = useState([])
  const [form, setForm] = useState(EMPTY)
  const [editingId, setEditingId] = useState(null)
  const [msg, setMsg] = useState('')

  const load = () => api.get('/users').then((r) => setUsers(r.data))
  useEffect(() => {
    load()
    // Same endpoint the Import Leads page already uses — reused here so the
    // admin picks a branch by name instead of having to know its numeric id.
    api.get('/admin/branches').then((r) => setBranches(r.data)).catch(() => setBranches([]))
  }, [])

  // id -> name, so the Users table can show "S.K KTM Thane" instead of a bare "1".
  const branchName = (id) => branches.find((b) => b.branch_id === id)?.name || (id ? `#${id}` : '—')

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value })
  const isCreForm = form.role === 'CRE'

  // CRE branch checkboxes: tick up to CRE_MAX_BRANCHES
  function toggleCreBranch(id) {
    const ids = form.branch_ids || []
    setForm({ ...form, branch_ids: ids.includes(id) ? ids.filter((x) => x !== id) : [...ids, id] })
  }

  // What the API gets: CRE sends branch_ids, everyone else a single branch_id
  function payloadFrom(f) {
    const { branch_ids, ...rest } = f
    if (f.role === 'CRE') return { ...rest, branch_id: null, branch_ids: branch_ids || [] }
    return { ...rest, branch_id: f.branch_id ? Number(f.branch_id) : null }
  }

  async function save(e) {
    e.preventDefault()
    setMsg('')
    if (isCreForm && !(form.branch_ids || []).length) {
      setMsg('Please tick at least one branch for this CRE.')
      return
    }
    try {
      if (editingId) {
        const { password, login_id, ...rest } = payloadFrom(form)
        await api.put(`/users/${editingId}`, rest)
        setMsg('User updated.')
      } else {
        await api.post('/users', payloadFrom(form))
        setMsg('User created.')
      }
      setForm(EMPTY); setEditingId(null); load()
    } catch (err) {
      setMsg(err.response?.data?.detail || 'Save failed.')
    }
  }

  function edit(u) {
    setEditingId(u.user_id)
    setForm({ ...EMPTY, ...u, password: '', branch_id: u.branch_id ?? '', branch_ids: u.branch_ids || [] })
  }

  async function toggle(u) {
    const path = u.is_active ? 'deactivate' : 'activate'
    await api.patch(`/users/${u.user_id}/${path}`); load()
  }

  async function resetPw(u) {
    const pw = prompt(`New password for ${u.login_id}:`)
    if (!pw) return
    await api.post(`/users/${u.user_id}/reset-password`, { new_password: pw })
    setMsg(`Password reset for ${u.login_id}.`)
  }

  return (
    <Layout title="User Management" sub="Admin · create, edit, deactivate staff logins">
      <div className="grid" style={{ gridTemplateColumns: '1fr 1.6fr', gap: 22, alignItems: 'start', display: 'grid' }}>
        <div className="card">
          <div className="card-header"><h3>{editingId ? 'Edit user' : 'Add user'}</h3></div>
          <form className="card-pad" onSubmit={save}>
            <div className="field"><label>Login ID</label>
              <input className="input" value={form.login_id} onChange={set('login_id')} disabled={!!editingId} required /></div>
            <div className="field"><label>Full name</label>
              <input className="input" value={form.full_name} onChange={set('full_name')} required /></div>
            <div className="field"><label>Email</label>
              <input className="input" value={form.email || ''} onChange={set('email')} /></div>
            {!editingId && (
              <div className="field"><label>Password</label>
                <input className="input" type="password" value={form.password} onChange={set('password')} required /></div>
            )}
            <div className="field"><label>Role</label>
              <select className="input" value={form.role} onChange={set('role')}>
                {ROLES.map((r) => <option key={r}>{r}</option>)}
              </select></div>
            {isCreForm ? (
              <div className="field">
                <label>Branches covered * <span className="muted-note">(1–{CRE_MAX_BRANCHES})</span></label>
                {branches.map((b) => {
                  const ticked = (form.branch_ids || []).includes(b.branch_id)
                  const full = (form.branch_ids || []).length >= CRE_MAX_BRANCHES
                  return (
                    <label key={b.branch_id} className="checkbox-row" style={{ fontWeight: 400, opacity: !ticked && full ? 0.5 : 1 }}>
                      <input type="checkbox" checked={ticked} disabled={!ticked && full}
                             onChange={() => toggleCreBranch(b.branch_id)} />
                      {b.name}
                    </label>
                  )
                })}
                <div className="muted-note" style={{ fontSize: 11.5 }}>
                  This CRE sees every lead in the ticked branches.
                </div>
              </div>
            ) : (
              <div className="field"><label>Branch</label>
                <select className="input" value={form.branch_id || ''} onChange={set('branch_id')}>
                  <option value="">— No branch —</option>
                  {branches.map((b) => (
                    <option key={b.branch_id} value={b.branch_id}>{b.name}</option>
                  ))}
                </select></div>
            )}
            <div style={{ display: 'flex', gap: 10 }}>
              {editingId && <button type="button" className="btn btn-outline" style={{ flex: 1 }}
                onClick={() => { setEditingId(null); setForm(EMPTY) }}>Cancel</button>}
              <button className="btn btn-primary" style={{ flex: 2 }}>{editingId ? 'Save changes' : 'Create user'}</button>
            </div>
            {msg && <div className="hint" style={{ marginTop: 12 }}>{msg}</div>}
          </form>
        </div>

        <div className="card">
          <div className="card-header"><h3>Users <span className="muted-note">({users.length})</span></h3></div>
          <div className="table-wrap">
            <table className="data-table">
              <thead><tr><th>Login ID</th><th>Name</th><th>Role</th><th>Branch</th><th>Status</th><th></th></tr></thead>
              <tbody>
                {users.map((u) => (
                  <tr key={u.user_id}>
                    <td className="cell-muted">{u.login_id}</td>
                    <td className="cell-primary">{u.full_name}</td>
                    <td>{u.role}</td>
                    <td>{u.role === 'CRE'
                      ? (u.branch_ids?.length ? u.branch_ids.map(branchName).join(', ') : <span className="badge badge-amber">No branches</span>)
                      : branchName(u.branch_id)}</td>
                    <td>{u.is_active
                      ? <span className="badge badge-green">Active</span>
                      : <span className="badge badge-gray">Inactive</span>}</td>
                    <td style={{ whiteSpace: 'nowrap' }}>
                      <button className="btn btn-outline btn-sm" onClick={() => edit(u)}>Edit</button>{' '}
                      <button className="btn btn-outline btn-sm" onClick={() => resetPw(u)}>Reset PW</button>{' '}
                      <button className="btn btn-outline btn-sm" onClick={() => toggle(u)}>
                        {u.is_active ? 'Deactivate' : 'Activate'}</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </Layout>
  )
}
