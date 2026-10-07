import axios, { AxiosInstance, InternalAxiosRequestConfig } from 'axios'

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

// ─── Cookie helper ──────────────────────────────────────────────────

function getCookie(name: string): string | null {
  const match = document.cookie.match(new RegExp('(^| )' + name + '=([^;]+)'))
  return match ? match[2] : null
}

// ─── Unified axios instance ────────────────────────────────────────

const apiClient: AxiosInstance = axios.create({
  baseURL: API_BASE,
  headers: { 'Content-Type': 'application/json' },
  withCredentials: true, // send cookies
})

// Attach access token from cookie to every request
apiClient.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = getCookie('access_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// ─── Bare instance for token refresh (NO interceptors) ─────────────
// Refresh must never go through apiClient: its 401 would re-enter the
// interceptor while isRefreshing=true and queue behind itself (deadlock).
// Exported for tests (authRefresh.test.ts drives it via defaults.adapter).
export const refreshClient: AxiosInstance = axios.create({
  baseURL: API_BASE,
  headers: { 'Content-Type': 'application/json' },
  withCredentials: true, // httpOnly refresh cookie is sent automatically
})

// Handle 401 — try refresh, then redirect to login
let isRefreshing = false
let failedQueue: {
  resolve: (token: string) => void
  reject: (error: unknown) => void
}[] = []

function processQueue(error: unknown, token: string | null = null) {
  failedQueue.forEach(prom => {
    if (error) prom.reject(error)
    else prom.resolve(token as string)
  })
  failedQueue = []
}

apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config

    if (error.response?.status === 401 && !originalRequest._retry) {
      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject })
        }).then(token => {
          // Mark retried: a second 401 must not trigger another refresh storm
          originalRequest._retry = true
          originalRequest.headers.Authorization = `Bearer ${token}`
          return apiClient(originalRequest)
        })
      }

      originalRequest._retry = true
      isRefreshing = true

      try {
        // Bare instance: no interceptors, so a 401 here cannot deadlock
        const { data } = await refreshClient.post<{ access_token: string }>('/api/v1/auth/refresh')

        // Update access token in cookie (set via Set-Cookie header from backend)
        // Also update axios defaults
        apiClient.defaults.headers.common.Authorization = `Bearer ${data.access_token}`

        processQueue(null, data.access_token)

        originalRequest.headers.Authorization = `Bearer ${data.access_token}`
        return apiClient(originalRequest)
      } catch (refreshError) {
        processQueue(refreshError, null)
        // Not refreshed — logout
        document.cookie = 'access_token=; path=/; max-age=0'
        document.cookie = 'refresh_token=; path=/; max-age=0'
        window.location.href = '/admin/login'
        return Promise.reject(refreshError)
      } finally {
        isRefreshing = false
      }
    }

    return Promise.reject(error)
  }
)

export default apiClient
