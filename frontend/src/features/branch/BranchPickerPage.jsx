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
  const [sm, setSm] = useState(null)

  useEffect(() => { api.get('/branch/summary').then((r) => setSm(r.data)).catch(() => setSm(false)) }, [])
  useEffect(() => { api.get('/branch/profiles').then((r) => setD(r.data)).catch(() => setD(false)) }, [])

  async function go(e) {
    e.preventDefault(); setErr(''); setBusy(true)
    try { await selectPba(pick.user_id, pin); nav('/dashboard', { replace: true }) }
    catch (ex) { setErr(ex.response?.data?.detail || 'Could not sign in.'); setPin('') }
    finally { setBusy(false) }
  }

  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg, #f4f6fa)', display: 'flex', flexDirection: 'column', alignItems: 'center', padding: '32px 16px' }}>
      <div style={{ width: '100%', maxWidth: 760 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
          <div><h2 style={{ margin: 0 }}>Who is working?</h2>
            <div className="muted-note">{d?.branch || user?.full_name}</div></div>
          <button className="btn btn-outline btn-sm" onClick={logout}>Sign out of branch</button>
        </div>
        {sm && sm.has_data && !pick && (
          <div className="card" style={{ marginBottom: 18, overflow: 'hidden' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', padding: '14px 18px 4px' }}>
              <b style={{ fontSize: 15 }}>{d?.branch || 'This branch'} · {sm.label}</b>
              <span className="muted-note">updates every time you open this screen</span>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(130px,1fr))' }}>
              {[['Leads', sm.leads], ['Bookings', sm.bookings, sm.target ? `of ${sm.target} target` : (sm.bookings_growth == null ? '' : `${sm.bookings_growth >= 0 ? '▲' : '▼'} ${Math.abs(sm.bookings_growth)}% vs ${sm.previous_label}`)],
                ['Invoiced', sm.invoiced], ['Delivered', sm.delivered]].map(([l, v, sub], i) => (
                <div key={l} style={{ padding: '10px 18px 14px', borderLeft: i ? '1px solid #eef0f4' : 0 }}>
                  <div className="muted-note" style={{ fontWeight: 600 }}>{l}</div>
                  <div style={{ fontSize: 28, fontWeight: 800, color: '#1c2740' }}>{v}</div>
                  <div className="muted-note" style={{ fontSize: 12 }}>{sub || ' '}</div>
                </div>))}
            </div>
            {sm.target ? <div style={{ padding: '0 18px 12px' }}><div style={{ height: 8, borderRadius: 5, background: '#eef1f6', overflow: 'hidden' }}>
              <div style={{ width: `${Math.min(100, sm.achievement_pct || 0)}%`, height: '100%', background: '#2f80ed' }} /></div>
              <div className="muted-note" style={{ marginTop: 4 }}>Target achieved: <b style={{ color: '#1c2740' }}>{sm.achievement_pct ?? 0}%</b></div></div> : null}
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', padding: '10px 18px 14px', background: '#fafbfd', borderTop: '1px solid #f1f3f6' }}>
              {[['Invoice pending', sm.invoice_pending], ['Insurance pending', sm.ins_pending], ['RTO pending', sm.rto_pending], ['Delivery pending', sm.delivery_pending]].map(([l, v]) => (
                <span key={l} style={{ border: '1px solid #e5e9f0', background: '#fff', borderRadius: 99, padding: '4px 12px', fontSize: 13 }}>{l}: <b style={{ color: v ? '#b45309' : '#1c2740' }}>{v}</b></span>))}
            </div>
          </div>)}
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
