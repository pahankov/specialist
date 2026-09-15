import axios from 'axios'
import type { DashboardStats, LoginResponse } from './types'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1'

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
    return axios.get<DashboardStats>(`${API_URL}/admin/dashboard`, {
      headers: getAuthHeader()
    })
  },

  getAppointments(status?: string, limit = 50) {
    return axios.get(`${API_URL}/admin/appointments`, {
      headers: getAuthHeader(),
      params: { status, limit }
    })
  },

  confirmAppointment(appointmentId: number) {
    return axios.patch(
      `${API_URL}/admin/appointments/${appointmentId}/confirm`,
      null,
      { headers: getAuthHeader() }
    )
  },

  cancelAppointment(appointmentId: number, reason?: string) {
    return axios.patch(
      `${API_URL}/admin/appointments/${appointmentId}/cancel`,
      null,
      { headers: getAuthHeader(), params: { reason } }
    )
  },

  createService(data: {
    name: string
    description?: string
    duration_minutes: number
    price: number
  }) {
    return axios.post(`${API_URL}/admin/services`, data, {
      headers: getAuthHeader()
    })
  },

  updateService(serviceId: number, data: Partial<{
    name: string
    description: string
    duration_minutes: number
    price: number
  }>) {
    return axios.patch(
      `${API_URL}/admin/services/${serviceId}`,
      data,
      { headers: getAuthHeader() }
    )
  },

  deleteService(serviceId: number) {
    return axios.delete(`${API_URL}/admin/services/${serviceId}`, {
      headers: getAuthHeader()
    })
  },

  getWorkingHours() {
    return axios.get(`${API_URL}/admin/working-hours`, {
      headers: getAuthHeader()
    })
  },

  createWorkingHour(data: {
    day_of_week: number
    start_time: string
    end_time: string
  }) {
    return axios.post(`${API_URL}/admin/working-hours`, data, {
      headers: getAuthHeader()
    })
  },

  deleteWorkingHour(hourId: number) {
    return axios.delete(`${API_URL}/admin/working-hours/${hourId}`, {
      headers: getAuthHeader()
    })
  }
}
