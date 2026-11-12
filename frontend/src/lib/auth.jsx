import { createContext, useContext, useEffect, useState } from 'react'
import api from './api'

const AuthContext = createContext(null)

// Where each role lands after login
export const ROLE_HOME = {
  OWNER: '/owner/dashboard',
  GM: '/gm',
  PBA: '/dashboard',
  CRE: '/dashboard',   // same screens as PBA, scoped to the CRE's branches
  RTO: '/rto',
  INSURANCE: '/insurance',
  ADMIN: '/admin',
  BRANCH: '/branch',   // shared branch login (PBA name + PIN picker comes next)
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    const raw = localStorage.getItem('user')
    return raw ? JSON.parse(raw) : null
  })
  const [loading, setLoading] = useState(false)

  async function login(loginId, password) {
    const { data } = await api.post('/auth/login', { login_id: loginId, password })
    localStorage.setItem('access_token', data.access_token)
    localStorage.setItem('refresh_token', data.refresh_token)
    localStorage.setItem('user', JSON.stringify(data.user))
    setUser(data.user)
    return data.user
  }

  function store(data) {
    localStorage.setItem('access_token', data.access_token)
    localStorage.setItem('refresh_token', data.refresh_token)
    localStorage.setItem('user', JSON.stringify(data.user))
    setUser(data.user)
    return data.user
  }

  // Branch login: choose which PBA is working (name + PIN), or go back to the picker.
  async function selectPba(userId, pin) {
    const { data } = await api.post('/branch/select', { user_id: userId, pin })
    return store(data)
  }
  async function switchPba() {
    try { const { data } = await api.post('/branch/lock'); return store(data) } catch (_) { logout() }
  }

  function logout() {
    localStorage.clear()
    setUser(null)
  }

  // Optional: verify the session on load
  useEffect(() => {
    if (localStorage.getItem('access_token') && !user) {
      setLoading(true)
      api.get('/auth/me')
        .then((r) => { setUser(r.data); localStorage.setItem('user', JSON.stringify(r.data)) })
        .catch(() => logout())
        .finally(() => setLoading(false))
    }
  }, [])

  return (
    <AuthContext.Provider value={{ user, login, logout, loading, selectPba, switchPba }}>
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = () => useContext(AuthContext)
