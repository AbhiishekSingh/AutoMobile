import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth, ROLE_HOME } from '../../lib/auth'

export default function Login() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [loginId, setLoginId] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function onSubmit(e) {
    e.preventDefault()
    setError('')
    setBusy(true)
    try {
      const user = await login(loginId.trim(), password)
      navigate(ROLE_HOME[user.role] || '/dashboard', { replace: true })
    } catch (err) {
      setError(err.response?.data?.detail || 'Login failed. Please try again.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="login-shell" style={{ minHeight: '100vh', display: 'grid', gridTemplateColumns: '1.1fr 1fr' }}>
      <div className="login-story" style={{
        background: 'linear-gradient(160deg,#0F3057,#0B2543 60%,#0A2038)', color: '#fff',
        padding: 56, display: 'flex', flexDirection: 'column', justifyContent: 'space-between',
      }}>
        <div>
          <div className="brand-name" style={{ fontSize: 20 }}>S.K. AUTOMOBILES</div>
          <span className="brand-tag">CRM &amp; Sales Automation</span>
        </div>
        <div>
          <div style={{ fontWeight: 700, fontSize: 32, lineHeight: 1.25, maxWidth: 460 }}>
            Every enquiry contacted. Every flag tracked. Nothing falls through.
          </div>
          <div style={{ color: '#B7CDE8', fontSize: 14, marginTop: 14, maxWidth: 430 }}>
            Sign in with your staff Login ID. Access is scoped to your role and branch.
          </div>
          <div style={{ color: '#8FB4E0', fontSize: 12.5, marginTop: 22, fontWeight: 600 }}>
            6 showrooms · Owner · GM · PBA · CRE · RTO · Admin
          </div>
        </div>
        <div style={{ color: '#6E90BB', fontSize: 12 }}>© 2026 S.K. Automobiles · Internal use only</div>
      </div>

      <div className="login-panel" style={{ background: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 40 }}>
        <form className="login-card" style={{ width: '100%', maxWidth: 380 }} onSubmit={onSubmit}>
          <h1 style={{ fontSize: 23, margin: '0 0 6px' }}>Welcome back</h1>
          <p style={{ color: 'var(--muted)', fontSize: 13.5, margin: '0 0 24px' }}>Sign in to your showroom dashboard.</p>

          {error && (
            <div style={{ background: 'var(--red-light)', color: 'var(--red)', padding: '9px 12px', borderRadius: 9, fontSize: 12.5, marginBottom: 14, fontWeight: 600 }}>
              {error}
            </div>
          )}

          <div className="field">
            <label>Login ID</label>
            <input className="input" value={loginId} onChange={(e) => setLoginId(e.target.value)}
                   placeholder="e.g. PBA-014" autoFocus />
          </div>
          <div className="field">
            <label>Password</label>
            <input className="input" type="password" value={password}
                   onChange={(e) => setPassword(e.target.value)} placeholder="••••••••" />
          </div>
          <button className="btn btn-primary" style={{ width: '100%', padding: 11 }} type="submit" disabled={busy}>
            {busy ? 'Signing in…' : 'Sign in'}
          </button>
        </form>
      </div>
    </div>
  )
}
