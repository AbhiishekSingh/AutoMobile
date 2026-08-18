import axios from 'axios'

// All requests go through the Vite proxy: /api -> http://localhost:8000
const api = axios.create({ baseURL: '/api' })

// Attach the access token to every request
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// On 401, try to refresh the access token once, then retry
let refreshing = null
api.interceptors.response.use(
  (res) => res,
  async (error) => {
    const original = error.config
    if (error.response?.status === 401 && !original._retry) {
      original._retry = true
      const refresh = localStorage.getItem('refresh_token')
      if (!refresh) return Promise.reject(error)
      try {
        refreshing = refreshing || axios.post('/api/auth/refresh', { refresh_token: refresh })
        const { data } = await refreshing
        refreshing = null
        localStorage.setItem('access_token', data.access_token)
        localStorage.setItem('refresh_token', data.refresh_token)
        original.headers.Authorization = `Bearer ${data.access_token}`
        return api(original)
      } catch (e) {
        refreshing = null
        localStorage.clear()
        window.location.href = '/login'
        return Promise.reject(e)
      }
    }
    return Promise.reject(error)
  }
)

export default api
