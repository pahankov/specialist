import axios from 'axios'
import type { DashboardStats, LoginResponse } from './types'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

function getAuthHeader(): Record<string, string> {
  const token = localStorage.getItem('access_token')
  return token ? { Authorization: `Bearer ${token}` } : {}
}

export const adminApi = {
  login(email: string, password: string) {
    return axios.post<LoginResponse>('http://localhost:8000/api/v1/auth/login', null, {
      params: { email, password }
    })
  },
  getDashboard() {
    return axios.get<DashboardStats>(`${API_URL}/admin/dashboard`, { headers: getAuthHeader() })
  },
  getAppointments(status?: string, limit = 50) {
    return axios.get(`${API_URL}/admin/appointments`, { headers: getAuthHeader(), params: { status, limit } })
  },
  confirmAppointment(id: number) {
    return axios.patch(`${API_URL}/admin/appointments/${id}/confirm`, null, { headers: getAuthHeader() })
  },
  cancelAppointment(id: number, reason?: string) {
    return axios.patch(`${API_URL}/admin/appointments/${id}/cancel`, null, { headers: getAuthHeader(), params: { reason } })
  },
  createService(data: { name: string; description?: string; duration_minutes: number; price: number }) {
    return axios.post(`${API_URL}/admin/services`, data, { headers: getAuthHeader() })
  },
  updateService(id: number, data: any) {
    return axios.patch(`${API_URL}/admin/services/${id}`, data, { headers: getAuthHeader() })
  },
  deleteService(id: number) {
    return axios.delete(`${API_URL}/admin/services/${id}`, { headers: getAuthHeader() })
  },
  getWorkingHours() {
    return axios.get(`${API_URL}/admin/working-hours`, { headers: getAuthHeader() })
  },
  createWorkingHour(data: { day_of_week: number; start_time: string; end_time: string }) {
    return axios.post(`${API_URL}/admin/working-hours`, data, { headers: getAuthHeader() })
  },
  deleteWorkingHour(id: number) {
    return axios.delete(`${API_URL}/admin/working-hours/${id}`, { headers: getAuthHeader() })
  },
  getAppointmentsByDate(dateFrom: string, dateTo: string) {
    return axios.get(`${API_URL}/admin/appointments/by-date`, {
      headers: getAuthHeader(),
      params: { date_from: dateFrom, date_to: dateTo }
    })
  }
}
