// API type definitions

export interface Master {
  id: number
  name: string
  phone?: string
  telegram_username?: string
  vk_id?: string
  max_id?: string
  description?: string
  avatar_url?: string
  is_active: boolean
  created_at: string
  updated_at?: string
}

export interface Service {
  id: number
  master_id: number
  name: string
  description?: string
  duration_minutes: number
  price: number
  is_active: boolean
}

export interface Appointment {
  id: number
  master_id: number
  service_id: number
  client_name: string
  client_phone: string
  appointment_date: string
  status: 'confirmed' | 'cancelled' | 'completed'
  created_at: string
  updated_at?: string
}

export interface AppointmentCreate {
  master_id: number
  service_id: number
  client_name: string
  client_phone: string
  appointment_date: string
}

export interface Review {
  id: number
  appointment_id: number
  client_name: string
  client_phone: string
  rating: number
  comment?: string
  created_at: string
  is_published: boolean
}

export interface WorkingHour {
  id: number
  master_id: number
  day_of_week: number
  start_time: string
  end_time: string
  is_active: boolean
}

export interface BlockedSlot {
  id: number
  master_id: number
  start_dt: string
  end_dt: string
  reason?: string
  created_at: string
}

export interface LoginResponse {
  access_token: string
  token_type: string
}

export interface DashboardStats {
  total_appointments: number
  status_counts: Record<string, number>
  total_clients: number
  total_services: number
  total_revenue: number
  recent_appointments: Array<{
    id: number
    client_id: number
    appointment_date: string
    status: string
    service_id: number
  }>
  upcoming_appointments: Array<{
    id: number
    appointment_date: string
    status: string
  }>
}

export interface AppointmentWithClient extends Appointment {
  client_name?: string
  client_phone?: string
  service_name?: string
}