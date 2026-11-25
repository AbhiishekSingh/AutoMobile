import { useEffect, useState } from 'react'
import { NavLink, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../lib/auth'
import NotificationBell from './NotificationBell'
import DeliveryReminderPopup from '../features/handoffs/DeliveryReminderPopup'
import IdleLock from '../features/branch/IdleLock'

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
const ActivityIcon = (p) => (
  <AdminIco {...p}>
    <path d="M8 3v3M16 3v3M4 8h16M5 5h14a1 1 0 0 1 1 1v13a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1z" />
    <path d="M8 13l2.5 2.5L16 10" />
  </AdminIco>
)
const LogoutIcon = (p) => (
  <AdminIco {...p}>
    <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
    <polyline points="16 17 21 12 16 7" />
    <line x1="21" y1="12" x2="9" y2="12" />
  </AdminIco>
)

// One distinct icon per menu item (so the collapsed sidebar is readable). Applied in the nav below to every item that
// would otherwise show the generic calendar-tick or users icon; the PBA menu keeps its own PNG icons.
const _i = (kids) => <AdminIco w={18} h={18}>{kids}</AdminIco>
const ICON_BY_LABEL = {
  'Dashboard': _i(<><rect x="3" y="3" width="7" height="7" rx="1" /><rect x="14" y="3" width="7" height="7" rx="1" /><rect x="14" y="14" width="7" height="7" rx="1" /><rect x="3" y="14" width="7" height="7" rx="1" /></>),
  'Approvals': _i(<><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" /><polyline points="22 4 12 14.01 9 11.01" /></>),
  'KPI view': _i(<><line x1="18" y1="20" x2="18" y2="10" /><line x1="12" y1="20" x2="12" y2="4" /><line x1="6" y1="20" x2="6" y2="14" /></>),
  'Deal workflow': _i(<><circle cx="18" cy="18" r="3" /><circle cx="6" cy="6" r="3" /><path d="M6 21V9a9 9 0 0 0 9 9" /></>),
  'Accounts': _i(<><rect x="2" y="5" width="20" height="14" rx="2" /><line x1="2" y1="10" x2="22" y2="10" /></>),
  'CRE reports': _i(<><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><polyline points="14 2 14 8 20 8" /><line x1="16" y1="13" x2="8" y2="13" /><line x1="16" y1="17" x2="8" y2="17" /></>),
  'Stock': _i(<><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z" /><polyline points="3.27 6.96 12 12.01 20.73 6.96" /><line x1="12" y1="22.08" x2="12" y2="12" /></>),
  'Targets': _i(<><circle cx="12" cy="12" r="10" /><circle cx="12" cy="12" r="6" /><circle cx="12" cy="12" r="2" /></>),
  'WhatsApp links': _i(<path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z" />),
  'Branches': _i(<><path d="M3 9l1-5h16l1 5" /><path d="M4 9v11h16V9" /><path d="M9 20v-6h6v6" /></>),
  'Activity Log': _i(<><circle cx="12" cy="12" r="10" /><polyline points="12 6 12 12 16 14" /></>),
  'Sync failures': _i(<><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" /><line x1="12" y1="9" x2="12" y2="13" /><line x1="12" y1="17" x2="12.01" y2="17" /></>),
  'Owner report': _i(<><path d="M21.21 15.89A10 10 0 1 1 8 2.83" /><path d="M22 12A10 10 0 0 0 12 2v10z" /></>),
  'Insurance': _i(<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />),
  'RTO': _i(<><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2" /><rect x="8" y="2" width="8" height="4" rx="1" /><polyline points="9 14 11 16 15 12" /></>),
  'Registrations': _i(<><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2" /><rect x="8" y="2" width="8" height="4" rx="1" /><polyline points="9 14 11 16 15 12" /></>),
  'Walkin': _i(<><path d="M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" /><circle cx="8.5" cy="7" r="4" /><line x1="20" y1="8" x2="20" y2="14" /><line x1="23" y1="11" x2="17" y2="11" /></>),
  'LeadSquare': _i(<><polygon points="12 2 2 7 12 12 22 7 12 2" /><polyline points="2 17 12 22 22 17" /><polyline points="2 12 12 17 22 12" /></>),
  'Test rides': _i(<><circle cx="5.5" cy="17.5" r="3.5" /><circle cx="18.5" cy="17.5" r="3.5" /><path d="M15 6a1 1 0 1 0 0-2 1 1 0 0 0 0 2zm-3 11.5V14l-3-3 4-3 2 3h3" /></>),
  'Follow Ups': _i(<path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z" />),
  'Final reviews': _i(<polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />),
}
const iconOf = (m) => ((m.icon?.type === ActivityIcon || m.icon?.type === UsersIcon) && ICON_BY_LABEL[m.label]) || m.icon

const KPI_ITEM = { to: '/owner/kpi', icon: <ActivityIcon w={18} h={18} />, label: 'KPI view', live: true }
const FLOW_ITEM = { to: '/workflow', icon: <ActivityIcon w={18} h={18} />, label: 'Deal workflow', live: true }
// PBA menu — matches the prototype. `live: true` items are wired routes;
// the rest are shown for the complete look but marked "SOON".
const PBA_MENU = [
  { to: '/dashboard', icon: <NavIco src="navbar/02-dashboard.png"  w={18} h={18} alt="dashboard"  />, label: 'Dashboard',  live: true },
  { to: '/leads',     icon: <NavIco src="navbar/03-leads.png"      w={20} h={20} alt="leads"       />, label: 'Leads',      live: true },
  { to: '/customers', icon: <NavIco src="navbar/04-customers.png"  w={20} h={20} alt="customers"   />, label: 'Customers',  live: true },
  { to: '/followups', icon: <NavIco src="navbar/05-follow-ups.png"  w={18} h={18} alt="follow ups"  />, label: 'Follow Ups', live: true },
  { to: '/quotations',icon: <NavIco src="navbar/07-quotes.png" w={18} h={18} alt="quotations"  />, label: 'Quotations', live: true },
  {                   icon: <NavIco src="navbar/06-bookings.png"   w={18} h={18} alt="bookings"    />, label: 'Bookings'  },
  { to: '/invoices', icon: <NavIco src="navbar/08-invoices.png"   w={18} h={18} alt="invoices"    />, label: 'Invoices', live: true },
  { to: '/rto-status', icon: <ActivityIcon w={18} h={18} />, label: 'RTO', live: true },
  FLOW_ITEM,
  {                   icon: <NavIco src="navbar/09-deliveries.png" w={18} h={18} alt="deliveries"  />, label: 'Deliveries'},
  { to: '/targets', icon: <NavIco src="navbar/10-targets.png"    w={18} h={18} alt="targets"     />, label: 'Targets', live: true },
  {                   icon: <NavIco src="navbar/11-reports.png"    w={18} h={18} alt="reports"     />, label: 'Reports'   },
]

// Admin menu
const ADMIN_MENU = [
  { to: '/admin',        icon: <UsersIcon w={20} h={18} />,  label: 'Users',        live: true },
  { to: '/admin/branches', icon: <UsersIcon w={20} h={18} />,  label: 'Branches',     live: true },
  { to: '/admin/import', icon: <ImportIcon w={18} h={20} />, label: 'Import Leads', live: true },
  { to: '/admin/activity-log', icon: <ActivityIcon w={18} h={18} />, label: 'Activity Log', live: true },
  { to: '/admin/sync-log', icon: <ActivityIcon w={18} h={18} />, label: 'Sync failures', live: true },
  { to: '/owner/dashboard', icon: <ActivityIcon w={18} h={18} />, label: 'Owner report', live: true },
  KPI_ITEM,
  FLOW_ITEM,
  { to: '/accounts', icon: <ActivityIcon w={18} h={18} />, label: 'Accounts', live: true },
  { to: '/cre-reports', icon: <ActivityIcon w={18} h={18} />, label: 'CRE reports', live: true },
  { to: '/stock', icon: <ActivityIcon w={18} h={18} />, label: 'Stock', live: true },
  { to: '/targets', icon: <ActivityIcon w={18} h={18} />, label: 'Targets', live: true },
  { to: '/whatsapp-settings', icon: <ActivityIcon w={18} h={18} />, label: 'WhatsApp links', live: true },
  { to: '/settings', icon: <SettingsIcon w={18} h={18} />, label: 'Settings', live: true },
]

// Owner and RTO: their worklist (approvals / registrations). More items come with their dashboards.
const STOCK_ITEM = { to: '/stock', icon: <ActivityIcon w={18} h={18} />, label: 'Stock', live: true }
const TARGET_ITEM = { to: '/targets', icon: <ActivityIcon w={18} h={18} />, label: 'Targets', live: true }
const WA_ITEM = { to: '/whatsapp-settings', icon: <ActivityIcon w={18} h={18} />, label: 'WhatsApp links', live: true }
const ACCOUNTS_ITEM = { to: '/accounts', icon: <ActivityIcon w={18} h={18} />, label: 'Accounts', live: true }
const CRE_REPORT_ITEM = { to: '/cre-reports', icon: <ActivityIcon w={18} h={18} />, label: 'CRE reports', live: true }
const OWNER_MENU = [{ to: '/owner/dashboard', icon: <ActivityIcon w={18} h={18} />, label: 'Dashboard', live: true }, { to: '/owner', icon: <ActivityIcon w={18} h={18} />, label: 'Approvals', live: true }, KPI_ITEM, FLOW_ITEM, ACCOUNTS_ITEM, CRE_REPORT_ITEM, STOCK_ITEM, TARGET_ITEM, WA_ITEM, { to: '/settings', icon: <SettingsIcon w={18} h={18} />, label: 'Settings', live: true }]
const GM_MENU = [{ to: '/gm', icon: <ActivityIcon w={18} h={18} />, label: 'Dashboard', live: true }, KPI_ITEM, FLOW_ITEM, ACCOUNTS_ITEM, CRE_REPORT_ITEM, STOCK_ITEM, TARGET_ITEM, WA_ITEM]
const RTO_MENU   = [{ to: '/rto',   icon: <ActivityIcon w={18} h={18} />, label: 'Registrations', live: true }]

const INSURANCE_MENU = [{ to: '/insurance', icon: <ActivityIcon w={18} h={18} />, label: 'Insurance', live: true }]
const CRE_MENU = [
  { to: '/dashboard', icon: <ActivityIcon w={18} h={18} />, label: 'Dashboard', live: true },
  { to: '/cre/walkin', icon: <ActivityIcon w={18} h={18} />, label: 'Walkin', live: true },
  { to: '/cre/leadsquare', icon: <ActivityIcon w={18} h={18} />, label: 'LeadSquare', live: true },
  { to: '/followups', icon: <ActivityIcon w={18} h={18} />, label: 'Follow Ups', live: true },
  { to: '/cre/test-rides', icon: <ActivityIcon w={18} h={18} />, label: 'Test rides', live: true },
  { to: '/final-reviews', icon: <ActivityIcon w={18} h={18} />, label: 'Final reviews', live: true },
  { to: '/insurance', icon: <ActivityIcon w={18} h={18} />, label: 'Insurance', live: true },
  FLOW_ITEM,
]
const MENU_BY_ROLE = { INSURANCE: INSURANCE_MENU, PBA: PBA_MENU, CRE: CRE_MENU, ADMIN: ADMIN_MENU, OWNER: OWNER_MENU, GM: GM_MENU, RTO: RTO_MENU }   // CRE uses the PBA screens
const COLLAPSE_KEY = 'sk-crm-sidebar-collapsed'

export default function Layout({ title, sub, back, children }) {
  const { user, logout, switchPba } = useAuth()
  const navigate = useNavigate()
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
        <div className="brand-row">
          <span className="brand-row-text">
            {/* TODO: swap for your logo → <NavIco src="brand-logo.svg" w={32} h={32} alt="SK CRM" /> */}
            <span className="brand-logo">
              <NavIco src="navbar/01-crm.png" w={33} h={33} alt="SK CRM" />
            </span>
            <span className="brand-logo-text">CRM</span>
          </span>

          {/* Only visible while expanded — sits beside the logo, no box/border. */}
          {!collapsed && (
            <button
              type="button"
              className="sidebar-toggle-arrow"
              onClick={() => setCollapsed((c) => !c)}
              title="Collapse sidebar"
              aria-label="Collapse sidebar"
            >
              ‹
            </button>
          )}
        </div>

        <nav className="nav">
          {MENU ? MENU.map((m) =>
            m.live ? (
              <NavLink key={m.label} to={m.to} end={m.to === '/owner'} title={m.label}
                className={({ isActive }) => 'nav-item' + (isActive ? ' active' : '')}>
                <span className="nav-ico">{iconOf(m)}</span>
                <span className="nav-label">{m.label}</span>
              </NavLink>
            ) : (
              <span key={m.label} className="nav-item disabled" title={m.label}>
                <span className="nav-ico">{iconOf(m)}</span>
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
          {/* Only visible while collapsed — moves the toggle down here so it
              stays reachable once the top-of-brand arrow disappears. */}
          {collapsed && (
            <button
              type="button"
              className="sidebar-toggle-arrow bottom"
              onClick={() => setCollapsed((c) => !c)}
              title="Expand sidebar"
              aria-label="Expand sidebar"
            >
              ›
            </button>
          )}

          

          <div className="sidebar-user" role="link" tabIndex={0} style={{ cursor: 'pointer' }} title="My profile & settings"
            onClick={() => navigate('/settings')} onKeyDown={(e) => { if (e.key === 'Enter') navigate('/settings') }}>
            <span className="avatar-sm">{initials(user?.full_name)}</span>
            <div className="sidebar-user-text">
              <div className="sidebar-user-name">{user?.full_name}</div>
              <div className="sidebar-user-role">{user?.role} · {user?.login_id}</div>
            </div>
          </div>

          <button type="button" className="nav-item signout-item" onClick={logout} title="Sign out">
            <span className="nav-ico"><LogoutIcon w={18} h={18} /></span>
            <span className="nav-label">Sign out</span>
          </button>
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
          <div style={{ display: 'flex', alignItems: 'center', gap: 18, minWidth: 0 }}>
            {back && <div className="tb-back" onClick={back.onClick}>← {back.label}</div>}
            <div style={{ minWidth: 0 }}>
              <h2 className="page-title">{title}</h2>
              {sub && <div className="page-sub">{sub}</div>}
            </div>
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
            {user?.via_branch && <button className="btn btn-outline btn-sm" onClick={async () => { await switchPba(); navigate('/branch', { replace: true }) }}>Switch PBA</button>}
            <button className="btn btn-outline btn-sm" onClick={logout}>Sign out</button>
          </div>
        </div>
        <div className="content">{children}</div>
        <DeliveryReminderPopup />
        <IdleLock />
      </div>
    </div>
  )
}
