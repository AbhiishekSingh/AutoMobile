import { useEffect, useState } from 'react'
import { NavLink, useLocation } from 'react-router-dom'
import { useAuth } from '../lib/auth'
import NotificationBell from './NotificationBell'

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

// Inline SVG icons for the Admin menu — drawn directly instead of pointing at
// image files, because /public/image only ever shipped the PBA navbar PNGs
// (navbar/01-*.png … 11-*.png). nav-users.svg / nav-import-leads.svg /
// nav-settings.svg were referenced by the Admin menu below but never actually
// added to the project, so the browser rendered its broken-image placeholder
// for every Admin nav item. These render the same on every machine, so that
// class of "icon just isn't there" bug can't happen again for this menu.
function AdminIco({ children, w = 18, h = 18 }) {
  return (
    <svg width={w} height={h} viewBox="0 0 24 24" fill="none" stroke="currentColor"
         strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
         style={{ display: 'inline-block', verticalAlign: 'middle', flexShrink: 0 }}>
      {children}
    </svg>
  )
}
const UsersIcon = (p) => (
  <AdminIco {...p}>
    <path d="M17 21v-2a4 4 0 0 0-4-4H7a4 4 0 0 0-4 4v2" />
    <circle cx="10" cy="7" r="4" />
    <path d="M22 21v-2a4 4 0 0 0-3-3.87" />
    <path d="M16 3.13a4 4 0 0 1 0 7.75" />
  </AdminIco>
)
const ImportIcon = (p) => (
  <AdminIco {...p}>
    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
    <path d="M14 2v6h6" />
    <path d="M12 18v-6" />
    <path d="M9.5 14.5 12 12l2.5 2.5" />
  </AdminIco>
)
const SettingsIcon = (p) => (
  <AdminIco {...p}>
    <circle cx="12" cy="12" r="3" />
    <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09a1.65 1.65 0 0 0-1-1.51 1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09a1.65 1.65 0 0 0 1.51-1 1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33h0A1.65 1.65 0 0 0 10 4.09V4a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82v0a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
  </AdminIco>
)
const HomeIcon = (p) => (
  <AdminIco {...p}>
    <path d="M3 10.5 12 3l9 7.5" />
    <path d="M5 9.5V21h14V9.5" />
    <path d="M9 21v-6h6v6" />
  </AdminIco>
)

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
  { to: '/admin',        icon: <UsersIcon w={20} h={18} />,  label: 'Users',        live: true },
  { to: '/admin/import', icon: <ImportIcon w={18} h={20} />, label: 'Import Leads', live: true },
  {                      icon: <SettingsIcon w={18} h={18} />, label: 'Settings'                 },
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
                <HomeIcon w={18} h={18} />
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
            <NotificationBell />
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