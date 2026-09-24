// API type definitions

export type UserRole = 'master' | 'client' | 'admin';

export interface User {
  id: number
  name: string
  email?: string
  phone?: string
  role: UserRole
  city_id?: number
  is_active: boolean
  is_verified: boolean
  created_at?: string
  updated_at?: string
  master_profile?: MasterProfile
  client_profile?: ClientProfile
}

export interface MasterProfile {
  id: number
  user_id: number
  description?: string
  avatar_url?: string
  telegram_username?: string
  experience_years?: number
  is_active: boolean
  created_at?: string
  updated_at?: string
}

export interface ClientProfile {
  id: number
  user_id: number
  no_show_count: number
  preferred_service_ids?: number[]
  created_at?: string
  updated_at?: string
}

export interface Master {
  id: number
  name: string
  email: string
  phone?: string
  telegram_username?: string
  description?: string
  avatar_url?: string
  is_active: boolean
  is_admin: boolean
  city_id?: number
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
  no_show_count?: number
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
  master_id: number
  client_name: string
  client_phone: string
  rating: number
  comment?: string
  is_published: boolean
  created_at: string
}

export interface ReviewCreate {
  appointment_id: number
  rating: number
  comment?: string
}

export interface AverageRating {
  average_rating: number | null
  review_count: number
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
  active_masters?: number
  admin_masters?: number
  total_appointments: number
  status_counts: Record<string, number>
  total_clients: number
  total_services: number
  total_revenue: number
  recent_appointments?: Array<{
    id: number
    master_id: number
    master_name?: string | null
    client_name: string | null
    appointment_date: string
    status: string
    service_name?: string | null
    service_price?: number
  }>
  upcoming_appointments?: Array<{
    id: number
    master_name?: string | null
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

// ─── Geography ───────────────────────────────────────────────────────

export interface Country {
  id: number
  code: string
  name_ru: string
  name_en: string
  phone_prefix: string
  is_active: boolean
}

export interface City {
  id: number
  country_id: number
  name_ru: string
  name_en?: string
  slug: string
  is_active: boolean
}

export interface PaginatedCities {
  cities: City[]
  total: number
  page: number
  page_size: number
}

// ─── Unified Auth ────────────────────────────────────────────────────

export interface UnifiedLoginRequest {
  identifier: string  // email or phone
  password: string
}

export interface UnifiedRegisterRequest {
  name: string
  email: string
  phone: string
  password: string
  city_id?: number | null
  telegram_username?: string | null
  is_master: boolean
}

export interface UnifiedRegisterResponse {
  id: number
  name: string
  email: string
  phone: string
  role: string
  city_id?: number | null
  is_master: boolean
  telegram_username?: string | null
  is_active: boolean
  is_verified: boolean
  created_at?: string
}

// ─── Pagination ────────────────────────────────────────────────

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

// ─── Health ────────────────────────────────────────────────────

export interface HealthCheck {
  status: 'healthy' | 'degraded'
  database: string
  cache: Record<string, unknown>
  tasks: Record<string, unknown>
}

// ─── Changelog ─────────────────────────────────────────────────

export interface ChangelogEntry {
  version: string
  date: string
  type: string
  title: string
  changes: Array<{
    type: string
    description: string
    impact: string
  }>
}

export interface Changelog {
  current_version: string
  base_url: string
  entries: ChangelogEntry[]
}

// ─── Master Detail ───────────────────────────────────────────

export interface MasterStats {
  total_appointments: number
  status_counts: Record<string, number>
  total_clients: number
  total_services: number
  total_revenue: number
  avg_rating?: number | null
  review_count: number
}

export interface MasterDetail {
  id: number
  user_id: number
  name: string
  email: string
  phone?: string
  telegram_username?: string
  description?: string
  avatar_url?: string
  experience_years?: number
  status: string
  is_active: boolean
  is_admin: boolean
  created_at?: string
  updated_at?: string
  stats: MasterStats
  recent_reviews: Array<{
    id: number
    client_name: string
    client_phone: string
    rating: number
    comment?: string
    is_published: boolean
    created_at?: string
  }>
  recent_appointments: Array<{
    id: number
    client_name?: string
    appointment_date?: string
    status: string
    service_name?: string
    service_price: number
  }>
}

export interface BulkResult {
  toggled?: Array<{ master_id: number; name: string; new_status: string }>
  suspended?: Array<{ master_id: number; name: string }>
  unsuspended?: Array<{ master_id: number; name: string }>
  errors: Array<{ master_id: number; error: string }>
}

export interface AuditLogEntry {
  id: number
  master_id: number
  master_name?: string
  level: string
  action: string
  entity_type: string
  entity_id: number
  details?: string
  ip_address?: string
  created_at?: string
}

export interface ImportResult {
  imported: number
  errors: Array<{ row: number; error: string }>
  total_rows: number
}
