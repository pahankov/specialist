// API type definitions

export type UserRole = 'master' | 'client' | 'admin';

/** Token swap returned by /admin/.../impersonate. */
export interface ImpersonationResponse {
  access_token: string;
  token_type: string;
  user_id: number;
  name: string;
  role: 'MASTER' | 'CLIENT';
  redirect: string;
}

/** One P&L category line; zero amount means "no data for the period". */
export interface PnlCategoryTotal {
  category_id: number;
  name: string;
  amount: number;
  share: number;
}

/** Period P&L report from /admin/pnl/report. */
export interface PnlReport {
  date_from: string;
  date_to: string;
  currency: string;
  revenue: number;
  expenses: number;
  profit: number;
  margin: number;
  income_count: number;
  expense_count: number;
  has_data: boolean;
  revenue_by_category: PnlCategoryTotal[];
  expenses_by_category: PnlCategoryTotal[];
}

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
  avatar_preset?: string | null;
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
  last_name?: string | null;
  email: string;
  phone?: string;
  telegram_username?: string;
  description?: string;
  avatar_url?: string;
  avatar_preset?: string | null;
  certificates?: { name: string; url?: string }[];
  cabinet_address?: string | null;
  experience_years?: number | null;
  is_active: boolean;
  is_admin: boolean;
  status?: string;
  tariff?: string;
  trial_ends_at?: string | null;
  city_id?: number;
  city_name?: string | null;
  avg_rating?: number | null;
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
  category?: string | null;
  is_active: boolean;
  discount_percent?: number | null;
  effective_price?: number | string | null;
  discount_until?: string | null;
  discount_fixed?: number | string | null;
}

export interface Client {
  id: number;
  name: string;
  phone: string;
  email?: string;
  no_show_count?: number;
  is_active?: boolean;
  /** Master-scoped blacklist badge (clients list only). */
  is_blocked?: boolean;
  /** Archive visibility (clients list with ?include_hidden=true). */
  is_hidden?: boolean;
  hidden_reason?: string | null;
  /** Attribution: which masters hid/blocked, with causes and notes. */
  hidden_by?: {
    master_id: number;
    master_name?: string | null;
    is_blocked: boolean;
    reason?: string | null;
    block_reason?: string | null;
    note?: string | null;
  }[];
  city_id?: number | null;
  city_name?: string | null;
  address?: string | null;
}

export interface Appointment {
  id: number;
  master_id: number;
  service_id?: number | null;
  bundle_id?: number | null;
  bundle_name?: string | null;
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
  /** Coupon code used for this booking (master panel visibility). */
  coupon_code?: string | null;
  /** Discount provenance snapshot ("−20%", "купон XXXX −200 ₽"). */
  discount_label?: string | null;
  /** Duration minutes (by-date endpoint) — drives granule spans */
  service_duration?: number | null;
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
  top_clients?: { id: number; name: string | null; visits: number; spent: number }[];
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
