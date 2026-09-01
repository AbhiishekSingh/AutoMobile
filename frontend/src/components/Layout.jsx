import { NavLink } from 'react-router-dom'
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

export default function Layout({ title, sub, back, children }) {
  const { user, logout } = useAuth()
  const MENU = MENU_BY_ROLE[user?.role] || null

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand-row">
          <span className="brand-logo">🏍️</span>
          <span className="brand-logo-text">CRM</span>
        </div>

        <nav className="nav">
          {MENU ? MENU.map((m) =>
            m.live ? (
              <NavLink key={m.label} to={m.to}
                className={({ isActive }) => 'nav-item' + (isActive ? ' active' : '')}>
                <span className="nav-ico">{m.icon}</span> {m.label}
              </NavLink>
            ) : (
              <span key={m.label} className="nav-item disabled">
                <span className="nav-ico">{m.icon}</span> {m.label}
                <span className="nav-soon">SOON</span>
              </span>
            )
          ) : (
            <span className="nav-item active"><span className="nav-ico">🏠</span> {user?.role} Home</span>
          )}
        </nav>

        <div className="sidebar-footer">
          <strong>{user?.full_name}</strong>{user?.role} · {user?.login_id}
          <div style={{ marginTop: 10 }}>
            <a onClick={logout} style={{ color: '#9FBBDE', fontWeight: 600, cursor: 'pointer' }}>← Sign out</a>
          </div>
        </div>
      </aside>

      <div className="main">
        <div className="topbar">
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