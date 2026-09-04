import { useEffect, useState } from 'react'
import { NavLink, useLocation } from 'react-router-dom'
import { useAuth } from '../lib/auth'

const initials = (name) =>
  (name || '?').split(' ').map((w) => w[0]).slice(0, 2).join('').toUpperCase()

// Nav icon helper — resolves to front-end/public/image/<src>
function NavIco({ src, w = 18, h = 18, alt = '' }) {
  return (
    <img
      src={`/image/${src}`}
      width={w}
      height={h}
      alt={alt}
      style={{ display: 'inline-block', verticalAlign: 'middle', flexShrink: 0 }}
    />
  )
}

// PBA menu — matches the prototype. `live: true` items are wired routes;
// the rest are shown for the complete look but marked "SOON".
const PBA_MENU = [
  { to: '/dashboard', icon: <NavIco src="navbar/02-dashboard.png"  w={25} h={25} alt="dashboard"  />, label: 'Dashboard',  live: true },
  { to: '/leads',     icon: <NavIco src="navbar/03-leads.png"      w={25} h={25} alt="leads"       />, label: 'Leads',      live: true },
  { to: '/customers', icon: <NavIco src="navbar/04-customers.png"  w={25} h={25} alt="customers"   />, label: 'Customers',  live: true },
  { to: '/followups', icon: <NavIco src="navbar/05-follow-ups.png"  w={25} h={25} alt="follow ups"  />, label: 'Follow Ups', live: true },
  { to: '/quotations',icon: <NavIco src="navbar/07-quotes.png" w={25} h={25} alt="quotations"  />, label: 'Quotations', live: true },
  {                   icon: <NavIco src="navbar/06-bookings.png"   w={25} h={25} alt="bookings"    />, label: 'Bookings'  },
  {                   icon: <NavIco src="navbar/08-invoices.png"   w={25} h={25} alt="invoices"    />, label: 'Invoices'  },
  {                   icon: <NavIco src="navbar/09-deliveries.png" w={25} h={25} alt="deliveries"  />, label: 'Deliveries'},
  {                   icon: <NavIco src="navbar/10-targets.png"    w={25} h={25} alt="targets"     />, label: 'Targets'   },
  {                   icon: <NavIco src="navbar/11-reports.png"    w={25} h={25} alt="reports"     />, label: 'Reports'   },
]

// Admin menu
const ADMIN_MENU = [
  { to: '/admin',        icon: <NavIco src="nav-users.svg"        w={20} h={18} alt="users"        />, label: 'Users',        live: true },
  { to: '/admin/import', icon: <NavIco src="nav-import-leads.svg" w={18} h={20} alt="import leads" />, label: 'Import Leads', live: true },
  {                      icon: <NavIco src="nav-settings.svg"     w={18} h={18} alt="settings"     />, label: 'Settings'                 },
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
          {/* TODO: swap for your logo → <NavIco src="brand-logo.svg" w={32} h={32} alt="SK CRM" /> */}
          <span className="brand-logo">
            <NavIco src="navbar/01-crm.png" w={33} h={33} alt="SK CRM" />
          </span>
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
              <span className="nav-ico">
                <NavIco src="nav-home.svg" w={18} h={18} alt="home" />
              </span>
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