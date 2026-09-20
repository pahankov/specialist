import axios, { AxiosInstance, InternalAxiosRequestConfig, AxiosResponse } from 'axios'
import type {
  Master,
  Service,
  Appointment,
  AppointmentCreate,
  Review,
  WorkingHour,
  BlockedSlot,
  Client,
  LoginResponse,
  DashboardStats,
  AppointmentWithClient,
  AdminLoginResponse,
  AdminStats,
} from './types'

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

// ─── Unified axios instance with auth interceptor ───────────────────

const apiClient: AxiosInstance = axios.create({
  baseURL: API_BASE,
  headers: { 'Content-Type': 'application/json' },
})

// Attach auth token to every request automatically
apiClient.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = localStorage.getItem('access_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// Handle 401 globally — redirect to login
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('access_token')
      // Only redirect if not already on login page
      if (!window.location.pathname.includes('/admin/login')) {
        window.location.href = '/admin/login'
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
  create: (data: { appointment_id: number; rating: number; comment?: string }) =>
    apiClient.post<Review>('/api/v1/reviews/', data),
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

// ─── Auth API (public + admin) ──────────────────────────────────────

export const authApi = {
  // Master login
  login: (email: string, password: string) =>
    apiClient.post<LoginResponse>('/api/v1/auth/login', { email, password }),
  // Master registration
  register: (data: { name: string; email: string; password: string; phone?: string; telegram_username?: string }) =>
    apiClient.post<Master>('/api/v1/auth/register', data),
  // Client login by phone
  clientLogin: (phone: string) =>
    apiClient.post<LoginResponse>('/api/v1/auth/client/login', { phone }),
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

  // Services
  getServices() {
    return apiClient.get('/api/v1/admin/services')
  },
  getAllServices() {
    return apiClient.get('/api/v1/admin/services/all')
  },
  createService(data: { name: string; description?: string; duration_minutes: number; price: number }) {
    return apiClient.post('/api/v1/admin/services', data)
  },
  updateService(id: number, data: { name?: string; description?: string; duration_minutes?: number; price?: number }) {
    return apiClient.patch(`/api/v1/admin/services/${id}`, data)
  },
  deleteService(id: number) {
    return apiClient.delete(`/api/v1/admin/services/${id}`)
  },

  // Clients
  getClients() {
    return apiClient.get('/api/v1/admin/clients')
  },
  createClient(data: { name: string; phone: string; email?: string }) {
    return apiClient.post('/api/v1/admin/clients', data)
  },
  updateClient(id: number, data: { name?: string; phone?: string; email?: string }) {
    return apiClient.patch(`/api/v1/admin/clients/${id}`, data)
  },
  deleteClient(id: number) {
    return apiClient.delete(`/api/v1/admin/clients/${id}`)
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

  // Exports
  exportAppointments(status?: string) {
    return `${API_BASE}/api/v1/admin/export/appointments${status ? `?status=${status}` : ''}`
  },
  exportClients() {
    return `${API_BASE}/api/v1/admin/export/clients`
  },
}

// ─── SuperAdmin API (auth required, uses interceptor) ───────────────

export const superAdminAuthApi = {
  register: (data: { name: string; email: string; password: string }) =>
    apiClient.post<AdminLoginResponse>('/api/v1/admin/register', data),
  login: (email: string, password: string) =>
    apiClient.post<AdminLoginResponse>('/api/v1/admin/login', { email, password }),
}

export const superAdminApi = {
  // Global dashboard
  getGlobalDashboard() {
    return apiClient.get<AdminStats>('/api/v1/admin/dashboard')
  },

  // Masters management
  getAllMasters(search?: string, isActive?: boolean) {
    return apiClient.get<Master[]>('/api/v1/masters/', { params: { search, is_active: isActive } })
  },
  getMasterById(id: number) {
    return apiClient.get<Master>(`/api/v1/masters/${id}`)
  },
  createMaster(data: { name: string; email: string; password: string; phone?: string; telegram_username?: string }) {
    return apiClient.post<Master>('/api/v1/masters/', data)
  },
  updateMaster(id: number, data: { name?: string; phone?: string; telegram_username?: string; description?: string; password?: string }) {
    return apiClient.patch<Master>(`/api/v1/masters/${id}`, data)
  },
  deleteMaster(id: number) {
    return apiClient.delete(`/api/v1/masters/${id}`)
  },
  getMasterStats(id: number) {
    return apiClient.get<AdminStats>(`/api/v1/masters/${id}/stats`)
  },
}

export default apiClient
