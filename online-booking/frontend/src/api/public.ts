import apiClient from './http'
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
} from './types'

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
    apiClient.get('/api/v1/appointments/available-days/', { params: { master_id: masterId } }),
  getAvailableSlots: (masterId: number, date: string) =>
    apiClient.get('/api/v1/appointments/available-slots/', { params: { master_id: masterId, date } }),
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
