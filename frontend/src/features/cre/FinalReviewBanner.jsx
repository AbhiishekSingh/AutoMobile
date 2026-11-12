// CRE dashboard strip: how many delivered customers wait for a final review.
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import api from '../../lib/api'
import { useAuth } from '../../lib/auth'

export default function FinalReviewBanner() {
  const { user } = useAuth()
  const [n, setN] = useState(0)
  useEffect(() => { if (user?.role === 'CRE') api.get('/final-reviews').then((r) => setN(r.data.due.length)).catch(() => {}) }, [user?.role])
  if (user?.role !== 'CRE' || !n) return null
  return <div className="hint" style={{ marginBottom: 14, background: '#fff4d6', color: '#7a5a00' }}>
    <b>{n}</b> delivered customer{n > 1 ? 's' : ''} waiting for the final review. <Link to="/final-reviews">Open the list</Link></div>
}
