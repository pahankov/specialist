// API type definitions

export interface Master {
  id: number
  name: string
  phone?: string
  telegram_username?: string
  description?: string
  avatar_url?: string
  is_active: boolean
  is_admin: boolean
  created_at: string
  updated_at?: string
}

export interface Service {
  id: number
  master_id: number
  name: string
  description?: string
  duration_minutes: number
  price: number | string
  is_active: boolean
}

export interface Client {
  id: number
  name: string
  phone: string
  email?: string
}

export interface Appointment {
  id: number
  master_id: number
  service_id: number
  client_id?: number
  appointment_date: string
  status: 'confirmed' | 'cancelled' | 'completed' | 'pending'
  notes?: string
  created_at: string
  updated_at?: string
  client_name?: string
  client_phone?: string
  service_name?: string
  service_price?: number | string
}

export interface AppointmentCreate {
  master_id: number
  service_id: number
  client_name: string
  client_phone: string
  appointment_date: string
  notes?: string
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
  schedule_date: string
  start_time: string
  end_time: string
  is_active?: boolean
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
    client_name: string | null
    client_phone: string | null
    appointment_date: string
    status: string
    service_id: number
    service_name: string | null
    service_price: number
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
  service_price?: number
}

export interface AdminLoginResponse {
  access_token: string
  token_type: string
}

export interface AdminStats {
  total_masters: number
  total_appointments: number
  total_clients: number
  total_services: number
  recent_appointments?: Array<{
    id: number
    master_id: number
    client_name: string | null
    appointment_date: string
    status: string
  }>
}

export interface MonthlyStats {
  confirmed_appointments: number
  total_minutes: number
  total_hours: number
  revenue: number
}

export interface CalendarDay {
  date: Date
  isCurrentMonth: boolean
}

export interface TimeSlot {
  hour: number
  status: 'free' | 'pending' | 'confirmed' | 'completed' | 'cancelled'
  appointments: Appointment[]
  isActive: boolean
}

export interface DaySchedule {
  start: number
  end: number
}

export interface BookingFormState {
  open: boolean
  date: Date | null
  hour: number | null
  clientId: number | null
  serviceId: number | null
  status: 'pending' | 'confirmed'
  notes: string
}
