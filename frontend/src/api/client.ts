import axios from 'axios'
import type {
  Master,
  Service,
  Appointment,
  AppointmentCreate,
  Review,
  WorkingHour,
  BlockedSlot,
} from './types'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1'

const client = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Services API
export const servicesApi = {
  getAll: (masterId?: number) =>
    client.get<Service[]>('/services', { params: { master_id: masterId } }),
  getById: (id: number) => client.get<Service>(`/services/${id}`),
  create: (data: Omit<Service, 'id'>) => client.post<Service>('/services/', data),
  update: (id: number, data: Partial<Service>) =>
    client.patch<Service>(`/services/${id}`, data),
  delete: (id: number) => client.delete(`/services/${id}`),
}

// Appointments API
export const appointmentsApi = {
  getAll: (masterId?: number, status?: string) =>
    client.get<Appointment[]>('/appointments/', {
      params: { master_id: masterId, status },
    }),
  getById: (id: number) => client.get<Appointment>(`/appointments/${id}`),
  create: (data: AppointmentCreate) =>
    client.post<Appointment>('/appointments/', data),
  cancel: (id: number) => client.post<Appointment>(`/appointments/${id}/cancel`),
}

// Reviews API
export const reviewsApi = {
  getAll: (masterId?: number, onlyPublished = true) =>
    client.get<Review[]>('/reviews/', {
      params: { master_id: masterId, only_published: onlyPublished },
    }),
  create: (data: { appointment_id: number; rating: number; comment?: string }) =>
    client.post<Review>('/reviews/', data),
}

// Working Hours API
export const workingHoursApi = {
  getAll: (masterId?: number) =>
    client.get<WorkingHour[]>('/working-hours/', { params: { master_id: masterId } }),
  create: (data: Omit<WorkingHour, 'id'>) =>
    client.post<WorkingHour>('/working-hours/', data),
  delete: (id: number) => client.delete(`/working-hours/${id}`),
}

// Blocked Slots API
export const blockedSlotsApi = {
  getAll: (masterId?: number) =>
    client.get<BlockedSlot[]>('/blocked-slots/', { params: { master_id: masterId } }),
  create: (data: Omit<BlockedSlot, 'id' | 'created_at'>) =>
    client.post<BlockedSlot>('/blocked-slots/', data),
  delete: (id: number) => client.delete(`/blocked-slots/${id}`),
}

// Masters API
export const mastersApi = {
  getAll: () => client.get<Master[]>('/masters/'),
  getById: (id: number) => client.get<Master>(`/masters/${id}`),
}

export default client