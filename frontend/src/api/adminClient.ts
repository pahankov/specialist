import axios, { AxiosError, InternalAxiosRequestConfig, AxiosInstance } from 'axios'
import type { DashboardStats, LoginResponse, Service, Client } from './types'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

// Create a dedicated axios instance for admin API
const adminAxios: AxiosInstance = axios.create({
  baseURL: API_URL,
  timeout: 10000
})

let isRefreshing = false
let failedQueue: Array<{
  resolve: (value?: unknown) => void
  reject: (reason?: unknown) => void
}> = []

const processQueue = (error: Error | null, token: string | null = null) => {
  failedQueue.forEach(prom => {
    if (error) {
      prom.reject(error)
    } else {
      prom.resolve(token)
    }
  })
  failedQueue = []
}

// Axios interceptor for refresh token
adminAxios.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = localStorage.getItem('access_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

adminAxios.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean }
    
    if (error.response?.status === 401 && !originalRequest._retry) {
      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject })
        }).then((token) => {
          if (originalRequest.headers) {
            originalRequest.headers.Authorization = `Bearer ${token}`
          }
          return adminAxios(originalRequest)
        }).catch((err) => Promise.reject(err))
      }

      originalRequest._retry = true
      isRefreshing = true

      try {
        const storedToken = localStorage.getItem('access_token')
        if (!storedToken) {
          localStorage.removeItem('access_token')
          window.location.href = '/admin/login'
          return Promise.reject(error)
        }

        const email = localStorage.getItem('login_email')
        const password = localStorage.getItem('login_password')
        
        if (!email || !password) {
          localStorage.removeItem('access_token')
          window.location.href = '/admin/login'
          return Promise.reject(error)
        }

        const resp = await axios.post<LoginResponse>(`${API_URL}/api/v1/auth/login`, { email, password })
        const newToken = resp.data.access_token
        localStorage.setItem('access_token', newToken)
        
        processQueue(null, newToken)
        
        if (originalRequest.headers) {
          originalRequest.headers.Authorization = `Bearer ${newToken}`
        }

        return adminAxios(originalRequest)
      } catch (refreshError: any) {
        processQueue(refreshError, null)
        localStorage.removeItem('access_token')
        window.location.href = '/admin/login'
        return Promise.reject(refreshError)
      } finally {
        isRefreshing = false
      }
    }

    return Promise.reject(error)
  }
)

export const adminApi = {
  login(email: string, password: string) {
    return adminAxios.post<LoginResponse>('/api/v1/auth/login', { email, password })
  },
  getDashboard() {
    return adminAxios.get<DashboardStats>('/admin/dashboard')
  },
  getAppointments(status?: string, limit = 20, offset = 0) {
    return adminAxios.get('/admin/appointments', { params: { status, limit, offset } })
  },
  confirmAppointment(id: number) {
    return adminAxios.patch(`/admin/appointments/${id}/confirm`)
  },
  cancelAppointment(id: number, reason?: string) {
    return adminAxios.patch(`/admin/appointments/${id}/cancel`, null, { params: { reason } })
  },
  completeAppointment(id: number) {
    return adminAxios.patch(`/admin/appointments/${id}/complete`)
  },
  deleteAppointment(id: number) {
    return adminAxios.delete(`/admin/appointments/${id}`)
  },
  // ── Services ──
  getServices() {
    return adminAxios.get<Service[]>('/admin/services')
  },
  getAllServices() {
    return adminAxios.get<Service[]>('/admin/services/all')
  },
  createService(data: { name: string; description?: string; duration_minutes: number; price: number }) {
    return adminAxios.post('/admin/services', data)
  },
  updateService(id: number, data: { name?: string; description?: string; duration_minutes?: number; price?: number }) {
    return adminAxios.patch(`/admin/services/${id}`, data)
  },
  deleteService(id: number) {
    return adminAxios.delete(`/admin/services/${id}`)
  },
  // ── Clients ──
  getClients() {
    return adminAxios.get<Client[]>('/admin/clients')
  },
  createClient(data: { name: string; phone: string; email?: string }) {
    return adminAxios.post('/admin/clients', data)
  },
  updateClient(id: number, data: { name?: string; phone?: string; email?: string }) {
    return adminAxios.patch(`/admin/clients/${id}`, data)
  },
  deleteClient(id: number) {
    return adminAxios.delete(`/admin/clients/${id}`)
  },
  // ── Working Hours ──
  getWorkingHours() {
    return adminAxios.get('/admin/working-hours')
  },
  createWorkingHour(data: { day_of_week: number; start_time: string; end_time: string }) {
    return adminAxios.post('/admin/working-hours', data)
  },
  deleteWorkingHour(id: number) {
    return adminAxios.delete(`/admin/working-hours/${id}`)
  },
  updateWorkingHour(id: number, data: { day_of_week?: number; start_time?: string; end_time?: string }) {
    return adminAxios.patch(`/admin/working-hours/${id}`, data)
  },
  // ── Appointments by date ──
  getAppointmentsByDate(dateFrom: string, dateTo: string) {
    return adminAxios.get('/admin/appointments/by-date', {
      params: { date_from: dateFrom, date_to: dateTo }
    })
  },
  // ── Manual booking ──
  bookAppointment(data: { client_id: number; service_id: number; appointment_date: string; status?: string; notes?: string }) {
    return adminAxios.post('/admin/appointments/book', data)
  },
  // ─── Audit Logs ──
  getAuditLogs(params: { limit?: number; offset?: number; entity_type?: string }) {
    return adminAxios.get('/admin/audit-logs', { params })
  },
  // ─── Blocked Slots ──
  getBlockedSlots() {
    return adminAxios.get('/admin/blocked-slots')
  },
  createBlockedSlot(data: { master_id: number; start_dt: string; end_dt: string; reason?: string }) {
    return adminAxios.post('/admin/blocked-slots', data)
  },
  deleteBlockedSlot(id: number) {
    return adminAxios.delete(`/admin/blocked-slots/${id}`)
  }
}
