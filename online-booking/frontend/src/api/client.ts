import axios, { AxiosInstance, InternalAxiosRequestConfig } from 'axios'
import type {
  Master,
  Service,
  Appointment,
  AppointmentCreate,
  Review,
  ReviewCreate,
  AverageRating,
  WorkingHour,
  BlockedSlot,
  Client,
  LoginResponse,
  DashboardStats,
  AdminLoginResponse,
  AdminStats,
  Country,
  City,
  UnifiedRegisterResponse,
  PaginatedResponse,
  HealthCheck,
  Changelog,
  MasterDetail,
  BulkResult,
  AuditLogEntry,
  ImportResult,
} from './types'

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
  withCredentials: true,  // send cookies
})

// Attach access token from cookie to every request
apiClient.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = getCookie('access_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// Handle 401 — try refresh, then redirect to login
let isRefreshing = false
let failedQueue: Array<{
  resolve: (token: string) => void
  reject: (error: any) => void
}> = []

function processQueue(error: any, token: string | null = null) {
  failedQueue.forEach(prom => {
    if (error) prom.reject(error)
    else prom.resolve(token!)
  })
  failedQueue = []
  isRefreshing = false
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
          originalRequest.headers.Authorization = `Bearer ${token}`
          return apiClient(originalRequest)
        })
      }

      originalRequest._retry = true
      isRefreshing = true

      try {
        // Call refresh endpoint — token comes from httpOnly cookie automatically
        const { data } = await apiClient.post<{ access_token: string }>('/api/v1/auth/refresh')
        
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
      }
    }

    return Promise.reject(error)
  }
)

// ─── Public API (no auth required) ──────────────────────────────────

export const servicesApi = {
  getAll: (masterId?: number) =>
    apiClient.get<Service[]>('/api/v1/services/', { params: { master_id: masterId } }),
  getById: (id: number) => apiClient.get<Service>(`/api/v1/services/${id}`),
  create: (data: Omit<Service, 'id'>) => apiClient.post<Service>('/api/v1/services/', data),
  update: (id: number, data: Partial<Service>) =>
    apiClient.patch<Service>(`/api/v1/services/${id}`, data),
  delete: (id: number) => apiClient.delete(`/api/v1/services/${id}`),
}

export const appointmentsApi = {
  getAll: (masterId?: number, status?: string) =>
    apiClient.get<Appointment[]>('/api/v1/appointments/', {
      params: { master_id: masterId, status },
    }),
  getById: (id: number) => apiClient.get<Appointment>(`/api/v1/appointments/${id}`),
  create: (data: AppointmentCreate) =>
    apiClient.post<Appointment>('/api/v1/appointments/', data),
  publicBooking: (data: AppointmentCreate) =>
    apiClient.post<Appointment>('/api/v1/appointments/public/', data),
  cancel: (id: number) => apiClient.post<Appointment>(`/api/v1/appointments/${id}/cancel/`),
  getAvailableDays: (masterId: number) =>
    apiClient.get(`/api/v1/appointments/available-days/`, { params: { master_id: masterId } }),
  getAvailableSlots: (masterId: number, date: string) =>
    apiClient.get(`/api/v1/appointments/available-slots/`, { params: { master_id: masterId, date } }),
}

export const reviewsApi = {
  getAll: (masterId?: number, onlyPublished = true) =>
    apiClient.get<Review[]>('/api/v1/reviews/', {
      params: { master_id: masterId, only_published: onlyPublished },
    }),
  getAverage: (masterId: number) =>
    apiClient.get<AverageRating>('/api/v1/reviews/average', { params: { master_id: masterId } }),
  create: (data: ReviewCreate) =>
    apiClient.post<Review>('/api/v1/reviews/', data),
  update: (id: number, data: { comment?: string; is_published?: boolean }) =>
    apiClient.patch<Review>(`/api/v1/reviews/${id}`, data),
  delete: (id: number) =>
    apiClient.delete(`/api/v1/reviews/${id}`),
}

export const workingHoursApi = {
  getAll: (masterId?: number) =>
    apiClient.get<WorkingHour[]>('/api/v1/working-hours/', { params: { master_id: masterId } }),
  create: (data: Omit<WorkingHour, 'id'>) =>
    apiClient.post<WorkingHour>('/api/v1/working-hours/', data),
  delete: (id: number) => apiClient.delete(`/api/v1/working-hours/${id}`),
}

export const blockedSlotsApi = {
  getAll: (masterId?: number) =>
    apiClient.get<BlockedSlot[]>('/api/v1/blocked-slots/', { params: { master_id: masterId } }),
  create: (data: Omit<BlockedSlot, 'id' | 'created_at'>) =>
    apiClient.post<BlockedSlot>('/api/v1/blocked-slots/', data),
  delete: (id: number) => apiClient.delete(`/api/v1/blocked-slots/${id}`),
}

export const mastersApi = {
  getAll: () => apiClient.get<Master[]>('/api/v1/masters/'),
  getById: (id: number) => apiClient.get<Master>(`/api/v1/masters/${id}`),
  create: (data: { name: string; email: string; password: string; phone?: string; telegram_username?: string }) =>
    apiClient.post<Master>('/api/v1/masters/', data),
}

export const clientsPublicApi = {
  getAll: () => apiClient.get<Client[]>('/api/v1/clients/'),
  getById: (id: number) => apiClient.get<Client>(`/api/v1/clients/${id}`),
  create: (data: Omit<Client, 'id'>) => apiClient.post<Client>('/api/v1/clients/', data),
  delete: (id: number) => apiClient.delete(`/api/v1/clients/${id}`),
}

// ─── Auth API ──────────────────────────────────────────────────────

export const authApi = {
  login: (email: string, password: string) =>
    apiClient.post<LoginResponse>('/api/v1/auth/login', { email, password }),
  register: (data: { name: string; email: string; password: string; phone?: string; telegram_username?: string; role: string; city_id?: number }) =>
    apiClient.post('/api/v1/auth/register', data),
  clientLogin: (phone: string) =>
    apiClient.post<LoginResponse>('/api/v1/auth/client/login', { phone }),
  sendOtp: (phone: string) =>
    apiClient.post('/api/v1/auth/send-otp', { phone }),
  verifyOtp: (phone: string, code: string) =>
    apiClient.post<LoginResponse>('/api/v1/auth/verify-otp', { phone, code }),
  logout: () => apiClient.post('/api/v1/auth/logout'),
  loginUnified: (identifier: string, password: string) =>
    apiClient.post<LoginResponse>('/api/v1/auth/login-unified', { identifier, password }),
  registerUnified: (data: {
    name: string
    email: string
    phone: string
    password: string
    city_id?: number | null
    telegram_username?: string | null
    is_master: boolean
  }) =>
    apiClient.post<UnifiedRegisterResponse>('/api/v1/auth/register-unified', data),
}

// ─── Geography API ─────────────────────────────────────────────────

export const citiesApi = {
  getCountries: () => apiClient.get<Country[]>('/api/v1/countries/'),
  getCities: (params?: { country_id?: number; search?: string; page?: number; page_size?: number }) =>
    apiClient.get<City[]>('/api/v1/cities/', { params }),
  searchCities: (q: string, countryId?: number, limit = 20) =>
    apiClient.get<City[]>('/api/v1/cities/search/', { params: { q, country_id: countryId, limit } }),
  getCity: (id: number) => apiClient.get<City>(`/api/v1/cities/${id}`),
}

export const adminApi = {
  // Dashboard
  getDashboard() {
    return apiClient.get<DashboardStats>('/api/v1/admin/dashboard')
  },
  getMonthlyStats(year: number, month: number) {
    return apiClient.get('/api/v1/admin/monthly-stats', { params: { year, month } })
  },

  // Appointments
  getAppointments(status?: string, limit = 50, offset = 0) {
    return apiClient.get('/api/v1/admin/appointments', { params: { status, limit, offset } })
  },
  confirmAppointment(id: number) {
    return apiClient.patch(`/api/v1/admin/appointments/${id}/confirm`)
  },
  cancelAppointment(id: number, reason?: string) {
    return apiClient.patch(`/api/v1/admin/appointments/${id}/cancel`, null, { params: { reason } })
  },
  completeAppointment(id: number) {
    return apiClient.patch(`/api/v1/admin/appointments/${id}/complete`)
  },
  noShowAppointment(id: number) {
    return apiClient.patch(`/api/v1/admin/appointments/${id}/no-show`)
  },
  deleteAppointment(id: number) {
    return apiClient.delete(`/api/v1/admin/appointments/${id}`)
  },
  bookAppointment(data: {
    client_id: number
    service_id: number
    appointment_date: string
    status: string
    notes?: string
  }) {
    return apiClient.post('/api/v1/admin/appointments/book', data)
  },
  getAppointmentsByDate(from: string, to: string) {
    return apiClient.get('/api/v1/admin/appointments/by-date', { params: { date_from: from, date_to: to } })
  },

  // Clients
  getClients(params?: { page?: number; page_size?: number; search?: string }) {
    return apiClient.get<PaginatedResponse<Client>>('/api/v1/admin/clients', { params })
  },
  createClient(data: { name: string; phone: string; email?: string }) {
    return apiClient.post<Client>('/api/v1/admin/clients', data)
  },
  updateClient(id: number, data: { name?: string; phone?: string; email?: string }) {
    return apiClient.patch<Client>(`/api/v1/admin/clients/${id}`, data)
  },
  deleteClient(id: number) {
    return apiClient.delete(`/api/v1/admin/clients/${id}`)
  },

  // Services
  getServices(params?: { page?: number; page_size?: number; active_only?: boolean }) {
    return apiClient.get<PaginatedResponse<Service>>('/api/v1/admin/services', { params })
  },
  getAllServices(params?: { page?: number; page_size?: number }) {
    return apiClient.get<PaginatedResponse<Service>>('/api/v1/admin/services/all', { params })
  },
  createService(data: { name: string; description?: string; duration_minutes: number; price: number }) {
    return apiClient.post<Service>('/api/v1/admin/services', data)
  },
  updateService(id: number, data: { name?: string; description?: string; duration_minutes?: number; price?: number }) {
    return apiClient.patch<Service>(`/api/v1/admin/services/${id}`, data)
  },
  deleteService(id: number) {
    return apiClient.delete(`/api/v1/admin/services/${id}`)
  },

  // Working Hours
  getWorkingHours() {
    return apiClient.get('/api/v1/admin/working-hours')
  },
  createWorkingHour(data: { schedule_date: string; start_time: string; end_time: string }) {
    return apiClient.post('/api/v1/admin/working-hours', data)
  },
  updateWorkingHour(id: number, data: { schedule_date?: string; start_time?: string; end_time?: string }) {
    return apiClient.patch(`/api/v1/admin/working-hours/${id}`, data)
  },
  deleteWorkingHour(id: number) {
    return apiClient.delete(`/api/v1/admin/working-hours/${id}`)
  },

  // Audit Logs
  getAuditLogs(params?: Record<string, any>) {
    return apiClient.get('/api/v1/admin/audit-logs', { params })
  },
  getAuditLogsAll(params?: Record<string, any>) {
    return apiClient.get('/api/v1/admin/audit-logs/all', { params })
  },

  // Blocked Slots
  getBlockedSlots() {
    return apiClient.get('/api/v1/admin/blocked-slots')
  },
  createBlockedSlot(data: { master_id: number; start_dt: string; end_dt: string; reason?: string }) {
    return apiClient.post('/api/v1/admin/blocked-slots', data)
  },
  deleteBlockedSlot(id: number) {
    return apiClient.delete(`/api/v1/admin/blocked-slots/${id}`)
  },

  // Health check
  getHealth() {
    return apiClient.get<HealthCheck>('/api/v1/admin/health')
  },
  getHealthVerbose() {
    return apiClient.get<HealthCheck>('/api/v1/admin/health/verbose')
  },

  // Changelog
  getChangelog() {
    return apiClient.get<Changelog>('/api/v1/admin/changelog')
  },

  // Export with background task support
  exportAppointmentsBackground(status?: string) {
    return apiClient.post('/api/v1/admin/export/appointments', null, { params: { background: true, status } })
  },
  getExportStatus(jobId: string) {
    return apiClient.get(`/api/v1/admin/export/appointments/status/${jobId}`)
  },
  exportClientsBackground() {
    return apiClient.post('/api/v1/admin/export/clients', null, { params: { background: true } })
  },
  getClientsExportStatus(jobId: string) {
    return apiClient.get(`/api/v1/admin/export/clients/status/${jobId}`)
  },
  getExportStats() {
    return apiClient.get('/api/v1/admin/export/stats')
  },

  // Dashboard cache management
  clearDashboardCache() {
    return apiClient.post('/api/v1/admin/dashboard/cache/clear')
  },

  // Generic HTTP methods (for endpoints without named methods)
  get(url: string, config?: Record<string, any>) {
    return apiClient.get(url, config)
  },
  post(url: string, data?: any) {
    return apiClient.post(url, data)
  },
  patch(url: string, data?: any, config?: Record<string, any>) {
    return apiClient.patch(url, data, config)
  },
  delete(url: string) {
    return apiClient.delete(url)
  },
}

// ─── SuperAdmin API ────────────────────────────────────────────────

export const superAdminAuthApi = {
  register: (data: { name: string; email: string; password: string }) =>
    apiClient.post<AdminLoginResponse>('/api/v1/admin/register', data),
  login: (email: string, password: string) =>
    apiClient.post<AdminLoginResponse>('/api/v1/admin/login', { email, password }),
}

export const superAdminApi = {
  // Global dashboard stats
  getGlobalDashboard() {
    return apiClient.get<AdminStats>('/api/v1/admin/dashboard')
  },

  // Master management
  getAllMasters(params?: { search?: string; is_active?: boolean; is_admin?: boolean }) {
    return apiClient.get<Master[]>('/api/v1/admin/masters', { params })
  },
  getMasterById(id: number) {
    return apiClient.get<Master>(`/api/v1/admin/masters/${id}`)
  },
  createMaster(data: { name: string; email: string; password: string; phone?: string; telegram_username?: string }) {
    return apiClient.post<Master>('/api/v1/admin/masters', data)
  },
  updateMaster(id: number, data: { name?: string; phone?: string; telegram_username?: string; description?: string; password?: string }) {
    return apiClient.patch<Master>(`/api/v1/admin/masters/${id}`, data)
  },
  deleteMaster(id: number) {
    return apiClient.delete(`/api/v1/admin/masters/${id}`)
  },
  toggleMasterActive(id: number) {
    return apiClient.post<Master>(`/api/v1/admin/masters/${id}/toggle-active`)
  },
  toggleMasterAdmin(id: number) {
    return apiClient.post<Master>(`/api/v1/admin/masters/${id}/toggle-admin`)
  },
  getMasterStats(id: number) {
    return apiClient.get<AdminStats>(`/api/v1/admin/masters/${id}/stats`)
  },

  // Global stats
  getGlobalStats() {
    return apiClient.get<AdminStats>('/api/v1/admin/global-stats')
  },

  // Master detail (full profile)
  getMasterFull(id: number) {
    return apiClient.get<MasterDetail>(`/api/v1/admin/masters/${id}/full`)
  },

  // Bulk operations
  bulkToggleActive(masterIds: number[]) {
    return apiClient.post<BulkResult>('/api/v1/admin/masters/bulk/toggle-active', masterIds)
  },
  bulkSuspend(masterIds: number[]) {
    return apiClient.post<BulkResult>('/api/v1/admin/masters/bulk/suspend', masterIds)
  },
  bulkUnsuspend(masterIds: number[]) {
    return apiClient.post<BulkResult>('/api/v1/admin/masters/bulk/unsuspend', masterIds)
  },

  // Individual master actions
  suspendMaster(masterId: number) {
    return apiClient.post(`/api/v1/admin/masters/${masterId}/suspend`)
  },
  unsuspendMaster(masterId: number) {
    return apiClient.post(`/api/v1/admin/masters/${masterId}/unsuspend`)
  },

  // Import
  importMasters(file: File) {
    const formData = new FormData()
    formData.append('file', file)
    return apiClient.post<ImportResult>('/api/v1/admin/masters/import', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },

  // Admin reviews
  getAdminReviews(params?: { master_id?: number; is_published?: boolean; page?: number; page_size?: number }) {
    return apiClient.get<PaginatedResponse<Review>>('/api/v1/admin/reviews', { params })
  },
  publishReview(reviewId: number) {
    return apiClient.patch<Review>(`/api/v1/admin/reviews/${reviewId}/publish`)
  },
  unpublishReview(reviewId: number) {
    return apiClient.patch<Review>(`/api/v1/admin/reviews/${reviewId}/unpublish`)
  },
  deleteReview(reviewId: number) {
    return apiClient.delete(`/api/v1/admin/reviews/${reviewId}`)
  },
  getMasterAverageRating(masterId: number) {
    return apiClient.get(`/api/v1/admin/reviews/average/${masterId}`)
  },

  // Master audit logs
  getMastersAudit(masterId: number, page?: number, pageSize?: number) {
    return apiClient.get<PaginatedResponse<AuditLogEntry>>('/api/v1/admin/audit-logs', {
      params: { master_id: masterId, page, page_size: pageSize },
    })
  },
}

export default apiClient
