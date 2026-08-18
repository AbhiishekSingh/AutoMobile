// Small shared presentational helpers used across the PBA screens.

const SLA_MAP = {
  GREEN: { cls: 'badge-green', label: 'On time' },
  YELLOW: { cls: 'badge-amber', label: 'Pending' },
  RED: { cls: 'badge-red', label: 'Overdue' },
}

export function Sla({ flag }) {
  const s = SLA_MAP[flag] || SLA_MAP.YELLOW
  return <span className={`badge ${s.cls}`}>{s.label}</span>
}

export function Empty({ children = 'No data yet.' }) {
  return (
    <div style={{ padding: '34px 18px', textAlign: 'center', color: 'var(--muted)' }}>
      {children}
    </div>
  )
}

export function Loading() {
  return <div style={{ padding: '34px 18px', textAlign: 'center', color: 'var(--muted)' }}>Loading…</div>
}

// The backend now stores business timestamps as IST wall-clock (see now_ist()
// on the server), returned as naive ISO strings (e.g. "2026-08-17T11:41:50").
// We display those values exactly as stored — no timezone shift — so the screen
// always matches the database, on any machine, regardless of its local timezone.
// Trick: read the naive string as UTC and format it in UTC, which renders the
// stored wall-clock numbers unchanged.
function parseLiteral(iso) {
  if (!iso) return null
  let s = String(iso)
  const hasTz = /[zZ]$/.test(s) || /[+-]\d{2}:?\d{2}$/.test(s)
  if (!hasTz) s = s.replace(' ', 'T') + 'Z'
  const d = new Date(s)
  return isNaN(d) ? null : d
}

// Formats an ISO datetime string as a date; returns '—' when empty.
export function fmtDate(iso) {
  const d = parseLiteral(iso)
  if (!d) return '—'
  return d.toLocaleDateString('en-IN', { timeZone: 'UTC', day: '2-digit', month: 'short', year: 'numeric' })
}

// Time only, e.g. "11:41 AM".
export function fmtTime(iso) {
  const d = parseLiteral(iso)
  if (!d) return '—'
  return d.toLocaleTimeString('en-IN', { timeZone: 'UTC', hour: '2-digit', minute: '2-digit' })
}

export function fmtDateTime(iso) {
  const d = parseLiteral(iso)
  if (!d) return '—'
  return d.toLocaleString('en-IN', {
    timeZone: 'UTC', day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit',
  })
}

// Simple prev/next pager. total, page, pageSize in; onPage(nextPage) out.
export function Pager({ total, page, pageSize, onPage }) {
  const pages = Math.max(1, Math.ceil((total || 0) / pageSize))
  if (total <= pageSize) return null
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '12px 16px' }}>
      <span style={{ color: 'var(--muted)', fontSize: 13 }}>
        Page {page} of {pages} · {total} total
      </span>
      <div style={{ display: 'flex', gap: 8 }}>
        <button className="btn btn-outline btn-sm" disabled={page <= 1} onClick={() => onPage(page - 1)}>← Prev</button>
        <button className="btn btn-outline btn-sm" disabled={page >= pages} onClick={() => onPage(page + 1)}>Next →</button>
      </div>
    </div>
  )
}