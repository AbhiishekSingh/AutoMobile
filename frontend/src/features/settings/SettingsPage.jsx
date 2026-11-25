// Settings: My profile (everyone) + Users & roles, Departments, Branches (Owner / Admin).
import { useEffect, useState } from 'react'
import Layout from '../../components/Layout'
import Tabs, { Tab } from '../../components/Tabs'
import { useAuth } from '../../lib/auth'
import api from '../../lib/api'
import { errText } from '../../components/ui'
import { UsersPanel } from '../admin/UsersPage'
import { BranchesPanel } from '../admin/BranchesPage'

// Message box shown right under the button that was pressed
function Box({ m }) {
  if (!m) return null
  return <div style={{ marginTop: 10, padding: '9px 12px', borderRadius: 8, fontWeight: 600, fontSize: 13.5,
    background: m.ok ? '#e3f6ec' : 'var(--red-light)', color: m.ok ? '#0f6b3a' : '#7a2318', border: `1px solid ${m.ok ? '#a8e0c1' : '#f0b4ab'}` }}>
    {m.ok ? '✓ ' : '✕ '}{m.text}</div>
}

function MyProfile() {
  const { user, refreshUser } = useAuth()
  const locked = !!user?.via_branch || user?.login_enabled === false     // PBA working under a branch login
  const [f, setF] = useState({ full_name: user?.full_name || '', phone: user?.phone || '', email: user?.email || '' })
  const [pw, setPw] = useState({ current_password: '', new_password: '', again: '' })
  const [m1, setM1] = useState(null)
  const [m2, setM2] = useState(null)
  const [busy, setBusy] = useState(false)
  const dirty = f.full_name !== (user?.full_name || '') || f.phone !== (user?.phone || '') || f.email !== (user?.email || '')

  async function saveProfile(e) {
    e.preventDefault(); setM1(null)
    if (!f.full_name.trim()) { setM1({ ok: false, text: 'Please enter your name.' }); return }
    setBusy(true)
    try { await api.put('/auth/me', { full_name: f.full_name, phone: f.phone, email: f.email || null }); await refreshUser(); setM1({ ok: true, text: 'Your details are saved.' }) }
    catch (err) { setM1({ ok: false, text: errText(err) }) } finally { setBusy(false) }
  }
  async function changePw(e) {
    e.preventDefault(); setM2(null)
    if (pw.new_password.length < 6) { setM2({ ok: false, text: 'The new password must be at least 6 characters.' }); return }
    if (pw.new_password !== pw.again) { setM2({ ok: false, text: 'The two new passwords do not match.' }); return }
    setBusy(true)
    try { await api.post('/auth/change-password', { current_password: pw.current_password, new_password: pw.new_password }); setPw({ current_password: '', new_password: '', again: '' }); setM2({ ok: true, text: 'Password changed. Use the new one next time you sign in.' }) }
    catch (err) { setM2({ ok: false, text: errText(err) }) } finally { setBusy(false) }
  }
  const Row = ({ k, v }) => <div style={{ display: 'flex', gap: 8, padding: '4px 0' }}><span className="muted-note" style={{ width: 120 }}>{k}</span><span style={{ fontWeight: 600 }}>{v || '—'}</span></div>

  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(320px,1fr))', gap: 22, padding: 22, alignItems: 'start' }}>
      <div>
        <h3 style={{ margin: '0 0 10px', fontSize: 15 }}>My details</h3>
        <Row k="Login ID" v={user?.login_id} /><Row k="Role" v={user?.role} />
        <form onSubmit={saveProfile} style={{ marginTop: 12 }}>
          {locked && <div className="hint" style={{ marginBottom: 10 }}>You are working under your branch login, so your details can only be changed by an Admin.</div>}
          <div className="field"><label>Full name</label><input className="input" disabled={locked} value={f.full_name} onChange={(e) => setF({ ...f, full_name: e.target.value })} /></div>
          <div className="field"><label>Mobile (WhatsApp)</label><input className="input" disabled={locked} value={f.phone} onChange={(e) => setF({ ...f, phone: e.target.value })} placeholder="10-digit number" /></div>
          <div className="field"><label>E-mail</label><input className="input" type="email" disabled={locked} value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} /></div>
          {!locked && <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
            <button className={dirty ? 'btn btn-primary btn-sm' : 'btn btn-outline btn-sm'} disabled={busy}>Save details</button>
            {dirty && <span className="muted-note" style={{ color: '#b45309', fontWeight: 600 }}>● Not saved yet</span>}
          </div>}
          <Box m={m1} />
        </form>
      </div>
      <div>
        <h3 style={{ margin: '0 0 10px', fontSize: 15 }}>Change password</h3>
        {locked ? <div className="hint">Your password belongs to the branch login. Ask an Admin if your PIN needs changing.</div> : (
          <form onSubmit={changePw}>
            <div className="field"><label>Current password</label><input className="input" type="password" autoComplete="current-password" value={pw.current_password} onChange={(e) => setPw({ ...pw, current_password: e.target.value })} /></div>
            <div className="field"><label>New password <span className="muted-note">(at least 6 characters)</span></label><input className="input" type="password" autoComplete="new-password" value={pw.new_password} onChange={(e) => setPw({ ...pw, new_password: e.target.value })} /></div>
            <div className="field"><label>Type the new password again</label><input className="input" type="password" autoComplete="new-password" value={pw.again} onChange={(e) => setPw({ ...pw, again: e.target.value })} /></div>
            <button className="btn btn-primary btn-sm" disabled={busy || !pw.current_password || !pw.new_password}>Change password</button>
            <Box m={m2} />
          </form>)}
      </div>
    </div>)
}

function Departments() {
  const { user } = useAuth()
  const [data, setData] = useState(null)
  const [open, setOpen] = useState(null)       // department id whose people are shown
  const [form, setForm] = useState(null)       // {id?, name, description, head_user_id} while adding / editing
  const [msg, setMsg] = useState(null)
  const [showOff, setShowOff] = useState(false)
  const base = '/admin/branch-setup/departments'
  const load = () => api.get(base).then((r) => setData(r.data)).catch(() => setData({ departments: [], people: [] }))
  useEffect(() => { load() }, [])
  if (!data) return <div className="card-pad muted-note">Loading…</div>

  const run = async (fn, ok) => {
    setMsg(null)
    try { await fn(); setMsg({ ok: true, text: ok }); await load(); return true }
    catch (e) { setMsg({ ok: false, text: errText(e) }); return false }
  }
  const save = async (e) => {
    e.preventDefault()
    const body = { name: form.name, description: form.description || null, head_user_id: form.head_user_id ? Number(form.head_user_id) : null }
    const done = await run(() => (form.id ? api.put(`${base}/${form.id}`, body) : api.post(base, body)), form.id ? 'Department saved' : 'Department added')
    if (done) setForm(null)
  }
  const assign = (user_id, department_id) => run(() => api.post(`${base}/assign`, { user_id, department_id: department_id ? Number(department_id) : null }), 'Moved')

  const active = data.departments.filter((d) => d.is_active)
  const off = data.departments.filter((d) => !d.is_active)
  const shown = showOff ? data.departments : active
  const peopleFor = (d) => data.people.filter((p) => p.is_active && p.department_id !== d.id && (p.role !== 'ADMIN' || user?.role === 'ADMIN'))

  return (
    <div style={{ padding: 22 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 10, flexWrap: 'wrap', marginBottom: 12 }}>
        <div className="muted-note" style={{ maxWidth: 640 }}>A department is the team a person belongs to. Their <b>role</b> still decides what they can do in the CRM; the department is for organising people and naming a head.</div>
        <div style={{ display: 'flex', gap: 8 }}>
          {off.length > 0 && <button type="button" className="btn btn-outline btn-sm" onClick={() => setShowOff(!showOff)}>{showOff ? 'Hide inactive' : `Show inactive (${off.length})`}</button>}
          <button type="button" className="btn btn-primary btn-sm" onClick={() => { setMsg(null); setForm({ name: '', description: '', head_user_id: '' }) }}>+ New department</button>
        </div>
      </div>

      {form && (
        <form onSubmit={save} style={{ border: '1px solid #dfe5ee', borderRadius: 14, padding: 16, marginBottom: 14, background: '#fafbfd' }}>
          <div style={{ fontWeight: 700, marginBottom: 10 }}>{form.id ? 'Edit department' : 'New department'}</div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(220px,1fr))', gap: 12 }}>
            <div className="field"><label>Name *</label><input className="input" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></div>
            <div className="field"><label>What the team does</label><input className="input" value={form.description || ''} onChange={(e) => setForm({ ...form, description: e.target.value })} /></div>
            <div className="field"><label>Department head (optional)</label>
              <select className="input" value={form.head_user_id || ''} onChange={(e) => setForm({ ...form, head_user_id: e.target.value })}>
                <option value="">— None —</option>
                {data.people.filter((p) => p.is_active && (p.role !== 'ADMIN' || user?.role === 'ADMIN')).map((p) => <option key={p.user_id} value={p.user_id}>{p.full_name} ({p.role})</option>)}
              </select></div>
          </div>
          <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
            <button type="submit" className="btn btn-primary btn-sm">{form.id ? 'Save changes' : 'Add department'}</button>
            <button type="button" className="btn btn-outline btn-sm" onClick={() => setForm(null)}>Cancel</button>
          </div>
          <Box m={msg} />
        </form>)}
      {!form && <Box m={msg} />}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(300px,1fr))', gap: 14, marginTop: msg && !form ? 12 : 0 }}>
        {shown.map((d) => (
          <div key={d.id} style={{ border: '1px solid #edf0f4', borderRadius: 14, padding: 16, opacity: d.is_active ? 1 : 0.6 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, alignItems: 'baseline' }}>
              <div style={{ fontWeight: 700, color: '#1c2740' }}>{d.name}</div>
              {d.is_active ? <span className="badge badge-green">{d.active} active</span> : <span className="badge badge-amber">Inactive</span>}
            </div>
            <div className="muted-note" style={{ margin: '4px 0 6px' }}>{d.description || 'No description'}</div>
            <div style={{ fontSize: 13, marginBottom: 10 }}>Head: {d.head_name ? <b>{d.head_name}</b> : <span className="muted-note">not set</span>}</div>
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              <button type="button" className="btn btn-outline btn-sm" onClick={() => setOpen(open === d.id ? null : d.id)}>{open === d.id ? 'Hide people' : `People (${d.total})`}</button>
              <button type="button" className="btn btn-outline btn-sm" onClick={() => { setMsg(null); setForm({ id: d.id, name: d.name, description: d.description || '', head_user_id: d.head_user_id || '' }) }}>Edit</button>
              {d.is_active
                ? <button type="button" className="btn btn-outline btn-sm" onClick={() => run(() => api.post(`${base}/${d.id}/deactivate`), 'Department deactivated')}>Deactivate</button>
                : <button type="button" className="btn btn-outline btn-sm" onClick={() => run(() => api.post(`${base}/${d.id}/activate`), 'Department reactivated')}>Reactivate</button>}
            </div>
            {open === d.id && <div style={{ marginTop: 10 }}>
              {d.members.length === 0 && <div className="muted-note">No one yet</div>}
              {d.members.map((u) => (
                <div key={u.user_id} style={{ padding: '7px 0', borderTop: '1px solid #f1f3f6', opacity: u.is_active ? 1 : 0.55 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, alignItems: 'center' }}>
                    <div><span style={{ fontWeight: 600 }}>{u.full_name}</span>{d.head_user_id === u.user_id && <span className="badge badge-green" style={{ marginLeft: 6 }}>Head</span>}
                      <div className="muted-note">{u.role}{u.branches.length ? ` · ${u.branches.join(', ')}` : ''}{!u.is_active ? ' · inactive' : ''}</div></div>
                    {u.is_active && (u.role !== 'ADMIN' || user?.role === 'ADMIN') && (
                      <select className="input" style={{ maxWidth: 150, fontSize: 12 }} value="" onChange={(e) => e.target.value && assign(u.user_id, e.target.value)}>
                        <option value="">Move to…</option>
                        {active.filter((x) => x.id !== d.id).map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}
                      </select>)}
                  </div>
                </div>))}
              {d.is_active && peopleFor(d).length > 0 && (
                <select className="input" style={{ marginTop: 10 }} value="" onChange={(e) => e.target.value && assign(Number(e.target.value), d.id)}>
                  <option value="">+ Add a person to {d.name}…</option>
                  {peopleFor(d).map((p) => <option key={p.user_id} value={p.user_id}>{p.full_name} ({p.role})</option>)}
                </select>)}
            </div>}
          </div>))}
      </div>
    </div>)
}

export default function SettingsPage() {
  const { user } = useAuth()
  const manager = ['OWNER', 'ADMIN'].includes(user?.role)
  const tabs = [{ key: 'me', label: 'My profile' }, ...(manager ? [{ key: 'users', label: 'Users & roles' }, { key: 'dept', label: 'Departments' }, { key: 'branches', label: 'Branches' }] : [])]
  return (
    <Layout title="Settings" sub={manager ? 'Your profile, staff, departments and branches' : 'Your profile and password'}>
      <Tabs tabs={tabs}>
        <Tab k="me"><MyProfile /></Tab>
        {manager && <Tab k="users"><div style={{ padding: 22 }}><UsersPanel /></div></Tab>}
        {manager && <Tab k="dept"><Departments /></Tab>}
        {manager && <Tab k="branches"><div style={{ padding: 22 }}><BranchesPanel /></div></Tab>}
      </Tabs>
    </Layout>)
}
