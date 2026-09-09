import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../lib/api'
import { useAuth } from '../lib/auth'

const POLL_MS = 30000 // refresh the unread badge every 30s

function timeAgo(iso) {
  const then = new Date(iso).getTime()
  if (Number.isNaN(then)) return ''
  const diffSec = Math.max(0, Math.floor((Date.now() - then) / 1000))
  if (diffSec < 60) return 'just now'
  const diffMin = Math.floor(diffSec / 60)
  if (diffMin < 60) return `${diffMin}m ago`
  const diffHr = Math.floor(diffMin / 60)
  if (diffHr < 24) return `${diffHr}h ago`
  const diffDay = Math.floor(diffHr / 24)
  if (diffDay < 7) return `${diffDay}d ago`
  return new Date(iso).toLocaleDateString()
}

export default function NotificationBell() {
  const { user } = useAuth()
  const navigate = useNavigate()

  const [open, setOpen] = useState(false)
  const [unreadCount, setUnreadCount] = useState(0)
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(false)
  const [loaded, setLoaded] = useState(false) // have we fetched the list at least once?
  const [error, setError] = useState(false)

  const wrapRef = useRef(null)
  const pollRef = useRef(null)

  // Poll just the badge count — cheap, and keeps the bell accurate even if
  // the dropdown is never opened. Stops immediately if there's no logged-in
  // user (e.g. right after logout) so we never poll on someone else's behalf.
  useEffect(() => {
    if (!user) {
      setUnreadCount(0)
      setRows([])
      setLoaded(false)
      return undefined
    }

    let cancelled = false
    const fetchCount = async () => {
      try {
        const { data } = await api.get('/notifications/unread-count')
        if (!cancelled) setUnreadCount(data.unread_count)
      } catch {
        // Silent: a transient failure here shouldn't show an error banner for
        // a background poll — the dropdown will surface its own error if the
        // user actually opens it.
      }
    }

    fetchCount()
    pollRef.current = setInterval(fetchCount, POLL_MS)
    return () => {
      cancelled = true
      clearInterval(pollRef.current)
    }
  }, [user?.user_id])

  // Close on outside click / Escape.
  useEffect(() => {
    if (!open) return undefined
    const onDown = (e) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target)) setOpen(false)
    }
    const onKey = (e) => { if (e.key === 'Escape') setOpen(false) }
    document.addEventListener('mousedown', onDown)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDown)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  async function loadList() {
    setLoading(true)
    setError(false)
    try {
      const { data } = await api.get('/notifications', { params: { page_size: 20 } })
      setRows(data.rows)
      setUnreadCount(data.unread_count) // keep badge in sync with the authoritative value
      setLoaded(true)
    } catch {
      setError(true)
    } finally {
      setLoading(false)
    }
  }

  function toggleOpen() {
    const next = !open
    setOpen(next)
    if (next && !loading) loadList() // always refetch on open so it's never stale
  }

  async function handleItemClick(n) {
    setOpen(false)
    // Optimistic UI: reflect "read" immediately, but don't let a failed
    // request desync the badge — reconcile from the server response.
    if (!n.is_read) {
      setRows((prev) => prev.map((r) => (r.id === n.id ? { ...r, is_read: true } : r)))
      setUnreadCount((c) => Math.max(0, c - 1))
      try {
        const { data } = await api.patch(`/notifications/${n.id}/read`)
        setUnreadCount(data.unread_count)
      } catch {
        // If this fails the badge may be off by one until the next poll
        // (<=30s) — acceptable, and far better than blocking navigation.
      }
    }
    if (n.reference_type === 'lead' && n.reference_id) {
      navigate(`/leads/${n.reference_id}`)
    }
  }

  async function handleMarkAllRead() {
    const hadUnread = rows.some((r) => !r.is_read)
    if (!hadUnread && unreadCount === 0) return
    setRows((prev) => prev.map((r) => ({ ...r, is_read: true })))
    setUnreadCount(0)
    try {
      await api.patch('/notifications/read-all')
    } catch {
      // Reconcile on next open/poll if this failed silently.
    }
  }

  if (!user) return null

  return (
    <div className="notif-bell-wrap" ref={wrapRef}>
      <button
        type="button"
        className="notif-bell-btn"
        onClick={toggleOpen}
        aria-label="Notifications"
        aria-haspopup="true"
        aria-expanded={open}
      >
        <span className="notif-bell-icon" aria-hidden="true">🔔</span>
        {unreadCount > 0 && (
          <span className="notif-badge">{unreadCount > 9 ? '9+' : unreadCount}</span>
        )}
      </button>

      {open && (
        <div className="notif-dropdown" role="menu">
          <div className="notif-dropdown-header">
            <span>Notifications</span>
            {rows.length > 0 && (
              <button type="button" className="notif-markall" onClick={handleMarkAllRead}>
                Mark all read
              </button>
            )}
          </div>

          <div className="notif-dropdown-body">
            {loading && !loaded && <div className="notif-empty">Loading…</div>}
            {!loading && error && <div className="notif-empty">Couldn't load notifications.</div>}
            {!loading && !error && loaded && rows.length === 0 && (
              <div className="notif-empty">You're all caught up.</div>
            )}
            {!loading && !error && rows.map((n) => (
              <button
                type="button"
                key={n.id}
                className={`notif-item${n.is_read ? '' : ' unread'}`}
                onClick={() => handleItemClick(n)}
              >
                {!n.is_read && <span className="notif-dot" aria-hidden="true" />}
                <span className="notif-item-body">
                  <span className="notif-item-title">{n.title}</span>
                  {n.message && <span className="notif-item-msg">{n.message}</span>}
                  <span className="notif-item-time">{timeAgo(n.created_at)}</span>
                </span>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
