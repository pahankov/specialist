import axios from 'axios'
import type { DashboardStats, LoginResponse } from './types'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1'
const ADMIN_URL = 'http://localhost:8000/admin'

function getAuthHeader(): Record<string, string> {
  const token = localStorage.getItem('access_token')
  return token ? { Authorization: `Bearer ${token}` } : {}
}

export const adminApi = {
  login(email: string, password: string) {
    return axios.post<LoginResponse>(`${API_URL}/auth/login`, null, {
      params: { email, password }
    })
  },
  getDashboard() {
    return axios.get<DashboardStats>(`${ADMIN_URL}/dashboard`, { headers: getAuthHeader() })
  },
  getAppointments(status?: string, limit = 50) {
    return axios.get(`${ADMIN_URL}/appointments`, { headers: getAuthHeader(), params: { status, limit } })
  },
  confirmAppointment(id: number) {
    return axios.patch(`${ADMIN_URL}/appointments/${id}/confirm`, null, { headers: getAuthHeader() })
  },
  cancelAppointment(id: number, reason?: string) {
    return axios.patch(`${ADMIN_URL}/appointments/${id}/cancel`, null, { headers: getAuthHeader(), params: { reason } })
  },
  completeAppointment(id: number) {
    return axios.patch(`${ADMIN_URL}/appointments/${id}/complete`, null, { headers: getAuthHeader() })
  },
  deleteAppointment(id: number) {
    return axios.delete(`${ADMIN_URL}/appointments/${id}`, { headers: getAuthHeader() })
  },
  bookAppointment(data: {
    client_id: number
    service_id: number
    appointment_date: string
    status: string
    notes?: string
  }) {
    return axios.post(`${ADMIN_URL}/appointments/book`, data, { headers: getAuthHeader() })
  },
  getAppointmentsByDate(from: string, to: string) {
    return axios.get(`${ADMIN_URL}/appointments/by-date`, {
      headers: getAuthHeader(),
      params: { from, to }
    })
  },
  createService(data: { name: string; description?: string; duration_minutes: number; price: number }) {
    return axios.post(`${ADMIN_URL}/services`, data, { headers: getAuthHeader() })
  },
  updateService(id: number, data: any) {
    return axios.patch(`${ADMIN_URL}/services/${id}`, data, { headers: getAuthHeader() })
  },
  deleteService(id: number) {
    return axios.delete(`${ADMIN_URL}/services/${id}`, { headers: getAuthHeader() })
  },
  getServices() {
    return axios.get(`${ADMIN_URL}/services`, { headers: getAuthHeader() })
  },
  getAllServices() {
    return axios.get(`${ADMIN_URL}/services/all`, { headers: getAuthHeader() })
  },
  getClients() {
    return axios.get(`${ADMIN_URL}/clients`, { headers: getAuthHeader() })
  },
  createClient(data: { name: string; phone: string; email?: string }) {
    return axios.post(`${ADMIN_URL}/clients`, data, { headers: getAuthHeader() })
  },
  updateClient(id: number, data: { name?: string; phone?: string; email?: string }) {
    return axios.patch(`${ADMIN_URL}/clients/${id}`, data, { headers: getAuthHeader() })
  },
  deleteClient(id: number) {
    return axios.delete(`${ADMIN_URL}/clients/${id}`, { headers: getAuthHeader() })
  },
  getWorkingHours() {
    return axios.get(`${ADMIN_URL}/working-hours`, { headers: getAuthHeader() })
  },
  createWorkingHour(data: { day_of_week: number; start_time: string; end_time: string }) {
    return axios.post(`${ADMIN_URL}/working-hours`, data, { headers: getAuthHeader() })
  },
  updateWorkingHour(id: number, data: { day_of_week?: number; start_time?: string; end_time?: string }) {
    return axios.patch(`${ADMIN_URL}/working-hours/${id}`, data, { headers: getAuthHeader() })
  },
  deleteWorkingHour(id: number) {
    return axios.delete(`${ADMIN_URL}/working-hours/${id}`, { headers: getAuthHeader() })
  },
  getAuditLogs(params?: Record<string, any>) {
    return axios.get(`${ADMIN_URL}/audit-logs`, { headers: getAuthHeader(), params })
  }
}
