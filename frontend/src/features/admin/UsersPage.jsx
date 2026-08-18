import { useEffect, useState } from 'react'
import Layout from '../../components/Layout'
import api from '../../lib/api'

const ROLES = ['OWNER', 'GM', 'PBA', 'CRE', 'RTO', 'ADMIN']
const EMPTY = { login_id: '', full_name: '', email: '', password: '', role: 'PBA', branch_id: '' }

export default function Users() {
  const [users, setUsers] = useState([])
  const [form, setForm] = useState(EMPTY)
  const [editingId, setEditingId] = useState(null)
  const [msg, setMsg] = useState('')

  const load = () => api.get('/users').then((r) => setUsers(r.data))
  useEffect(() => { load() }, [])

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value })

  async function save(e) {
    e.preventDefault()
    setMsg('')
    try {
      if (editingId) {
        const { password, login_id, ...rest } = form
        await api.put(`/users/${editingId}`, rest)
        setMsg('User updated.')
      } else {
        await api.post('/users', { ...form, branch_id: form.branch_id || null })
        setMsg('User created.')
      }
      setForm(EMPTY); setEditingId(null); load()
    } catch (err) {
      setMsg(err.response?.data?.detail || 'Save failed.')
    }
  }

  function edit(u) {
    setEditingId(u.user_id)
    setForm({ ...EMPTY, ...u, password: '' })
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
            <div className="field"><label>Branch ID</label>
              <input className="input" value={form.branch_id || ''} onChange={set('branch_id')} placeholder="e.g. 1" /></div>
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
                    <td>{u.branch_id || '—'}</td>
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
