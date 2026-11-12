// A PBA under a branch login is signed out of their name after a period of no activity (back to the picker).
import { useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../../lib/auth'

const IDLE_MS = 10 * 60 * 1000

export default function IdleLock() {
  const { user, switchPba } = useAuth()
  const nav = useNavigate()
  const timer = useRef(null)
  useEffect(() => {
    if (!user?.via_branch) return
    const arm = () => {
      clearTimeout(timer.current)
      timer.current = setTimeout(async () => { await switchPba(); nav('/branch', { replace: true }) }, IDLE_MS)
    }
    const ev = ['mousemove', 'keydown', 'click', 'touchstart', 'scroll']
    ev.forEach((e) => window.addEventListener(e, arm, { passive: true }))
    arm()
    return () => { clearTimeout(timer.current); ev.forEach((e) => window.removeEventListener(e, arm)) }
  }, [user?.via_branch])
  return null
}
