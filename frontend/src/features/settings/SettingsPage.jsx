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
  const [rows, setRows] = useState(null)
  const [open, setOpen] = useState(null)
  useEffect(() => { api.get('/admin/branch-setup/departments').then((r) => setRows(r.data)).catch(() => setRows([])) }, [])
  if (!rows) return <div className="card-pad muted-note">Loading…</div>
  return (
    <div style={{ padding: 22 }}>
      <div className="muted-note" style={{ marginBottom: 12 }}>A department is a role. To add someone to a department, or move them, edit their role and branch in <b>Users &amp; roles</b>.</div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(280px,1fr))', gap: 14 }}>
        {rows.map((d) => (
          <div key={d.role} style={{ border: '1px solid #edf0f4', borderRadius: 14, padding: 16 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, alignItems: 'baseline' }}>
              <div style={{ fontWeight: 700, color: '#1c2740' }}>{d.label}</div>
              <span className="badge badge-green">{d.active} active</span>
            </div>
            <div className="muted-note" style={{ margin: '4px 0 10px' }}>{d.about}</div>
            {d.total === 0 ? <div className="muted-note">No one yet</div> : <>
              <button type="button" className="btn btn-outline btn-sm" onClick={() => setOpen(open === d.role ? null : d.role)}>{open === d.role ? 'Hide people' : `Show people (${d.total})`}</button>
              {open === d.role && <div style={{ marginTop: 10 }}>{d.members.map((u) => (
                <div key={u.user_id} style={{ padding: '6px 0', borderTop: '1px solid #f1f3f6', opacity: u.is_active ? 1 : 0.55 }}>
                  <span style={{ fontWeight: 600 }}>{u.full_name}</span> <span className="muted-note">{u.login_id}{!u.is_active ? ' · inactive' : ''}{!u.login_enabled ? ' · PIN only' : ''}</span>
                  {u.branches.length > 0 && <div className="muted-note">{u.branches.join(', ')}</div>}
                </div>))}</div>}
            </>}
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
