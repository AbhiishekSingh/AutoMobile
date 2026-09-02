import { useEffect, useState } from 'react'
import { NavLink, useLocation } from 'react-router-dom'
import { useAuth } from '../lib/auth'

const initials = (name) =>
  (name || '?').split(' ').map((w) => w[0]).slice(0, 2).join('').toUpperCase()

// PBA menu — matches the prototype. `live: true` items are wired routes;
// the rest are shown for the complete look but marked "SOON".
const PBA_MENU = [
  { to: '/dashboard', icon: '📊', label: 'Dashboard', live: true },
  { to: '/leads', icon: '🧾', label: 'Leads', live: true },
  { to: '/customers', icon: '👥', label: 'Customers', live: true },
  { to: '/followups', icon: '⏰', label: 'Follow Ups', live: true },
  { to: '/quotations', icon: '📝', label: 'Quotations', live: true },
  { icon: '📅', label: 'Bookings' },
  { icon: '🧾', label: 'Invoices' },
  { icon: '🚚', label: 'Deliveries' },
  { icon: '🎯', label: 'Targets' },
  { icon: '📈', label: 'Reports' },
]

// Admin menu
const ADMIN_MENU = [
  { to: '/admin', icon: '👥', label: 'Users', live: true },
  { to: '/admin/import', icon: '⬆️', label: 'Import Leads', live: true },
  { icon: '⚙️', label: 'Settings' },
]

const MENU_BY_ROLE = { PBA: PBA_MENU, ADMIN: ADMIN_MENU }
const COLLAPSE_KEY = 'sk-crm-sidebar-collapsed'

export default function Layout({ title, sub, back, children }) {
  const { user, logout } = useAuth()
  const location = useLocation()
  const MENU = MENU_BY_ROLE[user?.role] || null

  // Desktop icon-only collapse — persisted across sessions.
  const [collapsed, setCollapsed] = useState(() => {
    try { return localStorage.getItem(COLLAPSE_KEY) === '1' } catch { return false }
  })
  useEffect(() => {
    try { localStorage.setItem(COLLAPSE_KEY, collapsed ? '1' : '0') } catch { /* ignore */ }
  }, [collapsed])

  // Mobile drawer — closed by default, and auto-closes on navigation.
  const [mobileOpen, setMobileOpen] = useState(false)
  useEffect(() => { setMobileOpen(false) }, [location.pathname])

  return (
    <div className={`app-shell${collapsed ? ' sidebar-collapsed' : ''}`}>
      <aside className={`sidebar${collapsed ? ' collapsed' : ''}${mobileOpen ? ' open' : ''}`}>
        <button
          type="button"
          className="sidebar-collapse-btn"
          onClick={() => setCollapsed((c) => !c)}
          title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          {collapsed ? '›' : '‹'}
        </button>

        <div className="brand-row">
          <span className="brand-logo">🏍️</span>
          <span className="brand-logo-text">CRM</span>
        </div>

        <nav className="nav">
          {MENU ? MENU.map((m) =>
            m.live ? (
              <NavLink key={m.label} to={m.to} title={m.label}
                className={({ isActive }) => 'nav-item' + (isActive ? ' active' : '')}>
                <span className="nav-ico">{m.icon}</span>
                <span className="nav-label">{m.label}</span>
              </NavLink>
            ) : (
              <span key={m.label} className="nav-item disabled" title={m.label}>
                <span className="nav-ico">{m.icon}</span>
                <span className="nav-label">{m.label}</span>
                <span className="nav-soon">SOON</span>
              </span>
            )
          ) : (
            <span className="nav-item active">
              <span className="nav-ico">🏠</span>
              <span className="nav-label">{user?.role} Home</span>
            </span>
          )}
        </nav>

        <div className="sidebar-footer">
          <span className="sidebar-footer-text">
            <strong>{user?.full_name}</strong>{user?.role} · {user?.login_id}
          </span>
          <div style={{ marginTop: 10 }}>
            <a onClick={logout} title="Sign out"
               style={{ color: '#9FBBDE', fontWeight: 600, cursor: 'pointer' }}>
              ← <span className="sidebar-footer-text">Sign out</span>
            </a>
          </div>
        </div>
      </aside>

      {/* Mobile drawer overlay — click to close */}
      <div
        className={`sidebar-overlay${mobileOpen ? ' open' : ''}`}
        onClick={() => setMobileOpen(false)}
        aria-hidden="true"
      />

      <div className="main">
        <div className="topbar">
          <button
            type="button"
            className="mobile-toggle"
            onClick={() => setMobileOpen((o) => !o)}
            aria-label="Toggle menu"
          >
            ☰
          </button>
          <div>
            {back && <div className="tb-back" onClick={back.onClick}>← {back.label}</div>}
            <h2 className="page-title">{title}</h2>
            {sub && <div className="page-sub">{sub}</div>}
          </div>
          <div className="topbar-right">
            <div className="user-cluster">
              <span className="avatar-lg">{initials(user?.full_name)}</span>
              <div>
                <div className="user-name">{user?.full_name}</div>
                <div className="user-role">{user?.role}</div>
              </div>
            </div>
            <button className="btn btn-outline btn-sm" onClick={logout}>Sign out</button>
          </div>
        </div>
        <div className="content">{children}</div>
      </div>
    </div>
  )
}