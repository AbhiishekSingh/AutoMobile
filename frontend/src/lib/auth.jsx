import { createContext, useContext, useEffect, useState } from 'react'
import api from './api'

const AuthContext = createContext(null)

// Where each role lands after login
export const ROLE_HOME = {
  OWNER: '/owner',
  GM: '/gm',
  PBA: '/dashboard',
  CRE: '/cre',
  RTO: '/rto',
  ADMIN: '/admin',
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
    <AuthContext.Provider value={{ user, login, logout, loading }}>
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = () => useContext(AuthContext)
