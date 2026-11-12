import { useEffect, useState } from 'react'
import Layout from '../../components/Layout'
import api from '../../lib/api'
import { CRE_MAX_BRANCHES } from '../../lib/roles'

const ROLES = ['OWNER', 'GM', 'PBA', 'CRE', 'RTO', 'INSURANCE', 'ADMIN', 'BRANCH']
const ROLE_LABEL = { BRANCH: 'BRANCH (shared branch login)' }
// branch_id: one branch (every role except CRE)
// branch_ids: the 1-2 branches a CRE covers
const EMPTY = { login_id: '', full_name: '', email: '', phone: '', password: '', role: 'PBA', login_enabled: true, pin: '', ls_email: '', ls_name: '', branch_id: '', branch_ids: [] }

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
  const isPba = form.role === 'PBA'
  const profile = isPba && !form.login_enabled     // PBA who works under the branch login

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
    if (form.role === 'BRANCH' && !form.branch_id) { setMsg('A branch login needs its branch.'); return }
    if (profile && !editingId && !/^\d{4,6}$/.test(form.pin || '')) { setMsg('Give the PBA a PIN of 4 to 6 digits.'); return }
    if (form.pin && !/^\d{4,6}$/.test(form.pin)) { setMsg('The PIN must be 4 to 6 digits.'); return }
    try {
      if (editingId) {
        const { password, login_id, ...rest } = payloadFrom(form)
        if (!rest.pin) delete rest.pin
        await api.put(`/users/${editingId}`, rest)
        setMsg('User updated.')
      } else {
        const body = payloadFrom(form)
        if (!body.pin) delete body.pin
        if (profile) delete body.password
        await api.post('/users', body)
        setMsg('User created.')
      }
      setForm(EMPTY); setEditingId(null); load()
    } catch (err) {
      setMsg(err.response?.data?.detail || 'Save failed.')
    }
  }

  function edit(u) {
    setEditingId(u.user_id)
    setForm({ ...EMPTY, ...u, password: '', pin: '', ls_email: u.ls_email || '', ls_name: u.ls_name || '', branch_id: u.branch_id ?? '', branch_ids: u.branch_ids || [] })
  }

  async function toggle(u) {
    const path = u.is_active ? 'deactivate' : 'activate'
    await api.patch(`/users/${u.user_id}/${path}`); load()
  }

  async function setPin(u) {
    const pin = prompt(`New 4–6 digit PIN for ${u.full_name}:`)
    if (!pin) return
    try { await api.post(`/users/${u.user_id}/set-pin`, { pin }); setMsg(`PIN set for ${u.full_name}.`); load() }
    catch (err) { setMsg(err.response?.data?.detail || 'Could not set the PIN.') }
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
            <div className="field"><label>Mobile (WhatsApp alerts)</label>
              <input className="input" value={form.phone || ''} onChange={set('phone')} placeholder="10-digit number" /></div>
            {!editingId && !profile && (
              <div className="field"><label>Password</label>
                <input className="input" type="password" value={form.password} onChange={set('password')} required /></div>
            )}
            <div className="field"><label>Role</label>
              <select className="input" value={form.role} onChange={set('role')}>
                {ROLES.map((r) => <option key={r} value={r}>{ROLE_LABEL[r] || r}</option>)}
              </select></div>
            {isPba && (
              <div className="field"><label>How does this PBA sign in?</label>
                <select className="input" value={form.login_enabled ? 'own' : 'branch'}
                  onChange={(e) => setForm({ ...form, login_enabled: e.target.value === 'own' })}>
                  <option value="own">Own login ID and password</option>
                  <option value="branch">Under the branch login (name + PIN only)</option>
                </select>
                {profile && <div className="muted-note" style={{ fontSize: 11.5 }}>No separate login. This PBA signs in with the branch account and picks their name.</div>}
              </div>)}
            {isPba && (
              <div className="field"><label>PIN {profile ? '*' : ''} <span className="muted-note">(4–6 digits{editingId ? ', leave blank to keep' : ''})</span></label>
                <input className="input" inputMode="numeric" maxLength={6} value={form.pin || ''} onChange={set('pin')} autoComplete="off" /></div>)}
            {isPba && (<>
              <div className="field"><label>LeadSquared email <span className="muted-note">(as it appears in the export, if different)</span></label>
                <input className="input" value={form.ls_email || ''} onChange={set('ls_email')} placeholder="salesperson email in LeadSquared" /></div>
              <div className="field"><label>LeadSquared name <span className="muted-note">(if different)</span></label>
                <input className="input" value={form.ls_name || ''} onChange={set('ls_name')} /></div>
            </>)}
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
              <div className="field"><label>Branch{form.role === 'BRANCH' || profile ? ' *' : ''}</label>
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
                    <td>{u.role}{u.role === 'PBA' && !u.login_enabled && <div><span className="badge badge-amber">Under branch login{u.has_pin ? '' : ' · no PIN'}</span></div>}</td>
                    <td>{u.role === 'CRE'
                      ? (u.branch_ids?.length ? u.branch_ids.map(branchName).join(', ') : <span className="badge badge-amber">No branches</span>)
                      : branchName(u.branch_id)}</td>
                    <td>{u.is_active
                      ? <span className="badge badge-green">Active</span>
                      : <span className="badge badge-gray">Inactive</span>}</td>
                    <td style={{ whiteSpace: 'nowrap' }}>
                      <button className="btn btn-outline btn-sm" onClick={() => edit(u)}>Edit</button>{' '}
                      {u.login_enabled
                        ? <><button className="btn btn-outline btn-sm" onClick={() => resetPw(u)}>Reset PW</button>{' '}</>
                        : null}
                      {u.role === 'PBA' && <><button className="btn btn-outline btn-sm" onClick={() => setPin(u)}>{u.has_pin ? 'Reset PIN' : 'Set PIN'}</button>{' '}</>}
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
