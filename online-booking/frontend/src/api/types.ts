// API type definitions

export type UserRole = 'master' | 'client' | 'admin';

export interface User {
  id: number;
  name: string;
  email?: string;
  phone?: string;
  role: UserRole;
  city_id?: number;
  is_active: boolean;
  is_verified: boolean;
  created_at?: string;
  updated_at?: string;
  master_profile?: MasterProfile;
  client_profile?: ClientProfile;
}

export interface MasterProfile {
  id: number;
  user_id: number;
  description?: string;
  avatar_url?: string;
  telegram_username?: string;
  experience_years?: number;
  is_active: boolean;
  created_at?: string;
  updated_at?: string;
}

export interface ClientProfile {
  id: number;
  user_id: number;
  no_show_count: number;
  preferred_service_ids?: number[];
  created_at?: string;
  updated_at?: string;
}

export interface Master {
  id: number;
  user_id: number;
  name: string;
  email: string;
  phone?: string;
  telegram_username?: string;
  description?: string;
  avatar_url?: string;
  is_active: boolean;
  is_admin: boolean;
  status?: string;
  tariff?: string;
  trial_ends_at?: string | null;
  city_id?: number;
  created_at: string;
  updated_at?: string;
}

export interface Service {
  id: number;
  master_id: number;
  name: string;
  description?: string;
  duration_minutes: number;
  price: number | string;
  is_active: boolean;
}

export interface Client {
  id: number;
  name: string;
  phone: string;
  email?: string;
  no_show_count?: number;
  is_active?: boolean;
  city_id?: number | null;
  city_name?: string | null;
}

export interface Appointment {
  id: number;
  master_id: number;
  service_id: number;
  client_id?: number;
  appointment_date: string;
  status: 'confirmed' | 'cancelled' | 'completed' | 'pending';
  notes?: string;
  created_at: string;
  updated_at?: string;
  client_name?: string;
  client_phone?: string;
  service_name?: string;
  service_price?: number | string;
  master_name?: string | null;
}

export interface AppointmentCreate {
  master_id: number;
  service_id: number;
  client_name: string;
  client_phone: string;
  appointment_date: string;
  notes?: string;
}

export interface Review {
  id: number;
  appointment_id: number;
  master_id: number;
  client_name: string;
  client_phone: string;
  rating: number;
  comment?: string;
  is_published: boolean;
  created_at: string;
}

export interface ReviewCreate {
  appointment_id: number;
  rating: number;
  comment?: string;
}

export interface AverageRating {
  average_rating: number | null;
  review_count: number;
}

export interface WorkingHour {
  id: number;
  master_id: number;
  schedule_date: string;
  start_time: string;
  end_time: string;
  is_active?: boolean;
}

export interface BlockedSlot {
  id: number;
  master_id: number;
  start_dt: string;
  end_dt: string;
  reason?: string;
  created_at: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
}

/** Shared counters — single copy (was repeated in Dashboard/Admin/Master stats). */
export interface StatsBase {
  total_appointments: number;
  status_counts: Record<string, number>;
  total_clients: number;
  total_services: number;
  total_revenue: number;
}

export interface DashboardStats extends StatsBase {
  recent_appointments: {
    id: number;
    client_id: number;
    client_name: string | null;
    client_phone: string | null;
    appointment_date: string;
    status: string;
    service_id: number;
    service_name: string | null;
    service_price: number;
  }[];
  upcoming_appointments: {
    id: number;
    appointment_date: string;
    status: string;
  }[];
}

// NOTE: AppointmentWithClient removed — Appointment already carries optional
// client_name/client_phone/service_name/service_price (lines above).

/** Identical to LoginResponse — kept as alias so superadmin imports don't churn. */
export type AdminLoginResponse = LoginResponse;

export interface AdminStats extends StatsBase {
  total_masters: number;
  active_masters?: number;
  admin_masters?: number;
  recent_appointments?: {
    id: number;
    master_id: number;
    master_name?: string | null;
    client_name: string | null;
    appointment_date: string;
    status: string;
    service_name?: string | null;
    service_price?: number;
  }[];
  upcoming_appointments?: {
    id: number;
    master_name?: string | null;
    appointment_date: string;
    status: string;
  }[];
}

// ─── Schedule UI types live in components/schedule/types.ts ───
// (moved out of api/types: they describe view state, not API contracts).
// Re-exported here for backward compatibility of existing imports.
export type {
  MonthlyStats,
  CalendarDay,
  TimeSlot,
  DaySchedule,
  BookingFormState,
} from '../components/schedule/types';

// ─── Geography ───────────────────────────────────────────────────────

export interface Country {
  id: number;
  code: string;
  name_ru: string;
  name_en: string;
  phone_prefix: string;
  is_active: boolean;
}

export interface City {
  id: number;
  country_id: number;
  name_ru: string;
  name_en?: string;
  slug: string;
  is_active: boolean;
}

export interface PaginatedCities {
  cities: City[];
  total: number;
  page: number;
  page_size: number;
}

// ─── Unified Auth ────────────────────────────────────────────────────

export interface UnifiedLoginRequest {
  identifier: string; // email or phone
  password: string;
}

// NOTE: UnifiedRegisterRequest removed — the live contract is
// UnifiedRegisterData in api/auth.ts (city_data, used by LoginModal).

export interface UnifiedRegisterResponse {
  id: number;
  name: string;
  email: string;
  phone: string;
  role: string;
  city_id?: number | null;
  is_master: boolean;
  telegram_username?: string | null;
  is_active: boolean;
  is_verified: boolean;
  created_at?: string;
}

// ─── Pagination ────────────────────────────────────────────────

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

// ─── Health ────────────────────────────────────────────────────

export interface HealthCheck {
  status: 'healthy' | 'degraded';
  database: string;
  cache: Record<string, unknown>;
  tasks: Record<string, unknown>;
}

// ─── Changelog ─────────────────────────────────────────────────

export interface ChangelogEntry {
  version: string;
  date: string;
  type: string;
  title: string;
  changes: {
    type: string;
    description: string;
    impact: string;
  }[];
}

export interface Changelog {
  current_version: string;
  base_url: string;
  entries: ChangelogEntry[];
}

// ─── Master Detail ───────────────────────────────────────────

export interface MasterStats extends StatsBase {
  avg_rating?: number | null;
  review_count: number;
}

export interface MasterDetail extends Master {
  experience_years?: number;
  status: string;
  stats: MasterStats;
  recent_reviews: {
    id: number;
    client_name: string;
    client_phone: string;
    rating: number;
    comment?: string;
    is_published: boolean;
    created_at?: string;
  }[];
  recent_appointments: {
    id: number;
    client_name?: string;
    appointment_date?: string;
    status: string;
    service_name?: string;
    service_price: number;
  }[];
}

export interface BulkResult {
  toggled?: { master_id: number; name: string; new_status: string }[];
  suspended?: { master_id: number; name: string }[];
  unsuspended?: { master_id: number; name: string }[];
  errors: { master_id: number; error: string }[];
}

export interface AuditLogEntry {
  id: number;
  master_id: number;
  master_name?: string;
  level: string;
  action: string;
  entity_type: string;
  entity_id: number;
  details?: string;
  ip_address?: string;
  created_at?: string;
}

export interface AuditLogList {
  total: number;
  logs: AuditLogEntry[];
}

export interface ImportResult {
  imported: number;
  errors: { row: number; error: string }[];
  total_rows: number;
}
