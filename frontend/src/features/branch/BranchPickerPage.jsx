// Shown after a branch login: who is working? Pick your name, enter your PIN.
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../../lib/api'
import { useAuth } from '../../lib/auth'

export default function BranchPickerPage() {
  const { user, selectPba, logout } = useAuth()
  const nav = useNavigate()
  const [d, setD] = useState(null)
  const [pick, setPick] = useState(null)
  const [pin, setPin] = useState('')
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => { api.get('/branch/profiles').then((r) => setD(r.data)).catch(() => setD(false)) }, [])

  async function go(e) {
    e.preventDefault(); setErr(''); setBusy(true)
    try { await selectPba(pick.user_id, pin); nav('/dashboard', { replace: true }) }
    catch (ex) { setErr(ex.response?.data?.detail || 'Could not sign in.'); setPin('') }
    finally { setBusy(false) }
  }

  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg, #f4f6fa)', display: 'flex', flexDirection: 'column', alignItems: 'center', padding: '32px 16px' }}>
      <div style={{ width: '100%', maxWidth: 560 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
          <div><h2 style={{ margin: 0 }}>Who is working?</h2>
            <div className="muted-note">{d?.branch || user?.full_name}</div></div>
          <button className="btn btn-outline btn-sm" onClick={logout}>Sign out of branch</button>
        </div>
        {d === null && <div className="muted-note">Loading…</div>}
        {d === false && <div className="hint">Could not load the names.</div>}
        {d && d.pbas.length === 0 && <div className="hint">No PBA has been added to this branch yet. Ask Admin to add PBAs.</div>}
        {!pick && d && (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(160px,1fr))', gap: 12 }}>
            {d.pbas.map((p) => (
              <button key={p.user_id} className="card" disabled={!p.has_pin || p.locked}
                style={{ padding: 18, textAlign: 'center', cursor: p.has_pin && !p.locked ? 'pointer' : 'not-allowed', opacity: p.has_pin && !p.locked ? 1 : 0.55, border: '1px solid #e3e8ef' }}
                onClick={() => { setPick(p); setPin(''); setErr('') }}>
                <div style={{ width: 52, height: 52, borderRadius: '50%', background: '#e8eefc', margin: '0 auto 8px', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 700, fontSize: 18 }}>
                  {p.full_name.split(' ').map((w) => w[0]).slice(0, 2).join('').toUpperCase()}</div>
                <div style={{ fontWeight: 600 }}>{p.full_name}</div>
                {!p.has_pin && <div className="muted-note">No PIN set</div>}
                {p.locked && <div className="muted-note">Locked for a few minutes</div>}
              </button>))}
          </div>)}
        {pick && (
          <form className="card" onSubmit={go}><div className="card-pad">
            <h3 style={{ marginTop: 0 }}>{pick.full_name}</h3>
            <div className="field"><label>Enter your PIN</label>
              <input className="input" type="password" inputMode="numeric" autoComplete="off" autoFocus maxLength={6}
                style={{ fontSize: 24, letterSpacing: 8, textAlign: 'center' }} value={pin} onChange={(e) => setPin(e.target.value.replace(/\D/g, ''))} /></div>
            {err && <div className="hint" style={{ background: 'var(--red-light)', color: '#7a2318', marginBottom: 10 }}>{err}</div>}
            <div style={{ display: 'flex', gap: 10 }}>
              <button type="button" className="btn btn-outline" style={{ flex: 1 }} onClick={() => { setPick(null); setErr('') }}>Back</button>
              <button className="btn btn-primary" style={{ flex: 2 }} disabled={busy || pin.length < 4}>Continue</button>
            </div>
          </div></form>)}
      </div>
    </div>
  )
}
