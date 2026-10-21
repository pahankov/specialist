import apiClient from './http';
import type { Appointment } from './types';

/** One phone/email of the account (1.79.0 contact model). */
export interface ClientContact {
  id: number;
  contact_type: 'phone' | 'email' | string;
  value: string;
  is_verified: boolean;
  /** Verification level: null (self-typed) | "social" | "code". */
  verified_via?: string | null;
  is_primary: boolean;
}

export interface ClientMe {
  id: number;
  name: string;
  last_name?: string | null;
  phone?: string | null;
  email?: string | null;
  is_verified: boolean;
  /** All phones/emails with verify flags (contact model, 1.79.0). */
  contacts?: ClientContact[];
  /** Whether a password is set (password section visibility). */
  has_password?: boolean;
  /** Bound MAX account (chat-bot login available). */
  max_bound?: boolean;
  /** Public MAX nickname (@username) for support. */
  max_username?: string | null;
  /** Bound VK ID account (login via VK/OK/Mail widget). */
  vk_bound?: boolean;
  /** Bound Yandex ID account (login via Yandex redirect). */
  yandex_bound?: boolean;
  /** Social avatar (VK/Yandex CDN URL) brought over by a social login. */
  avatar_url?: string | null;
  city_id?: number | null;
  city_name?: string | null;
  address?: string | null;
}

export interface ClientStats {
  total_spent: number;
  completed_visits: number;
  upcoming_count: number;
  cancelled_count: number;
  favorite_master?: { id: number; name?: string | null; visits: number } | null;
  favorite_service?: { id: number; name?: string | null; visits: number } | null;
}

export interface BundleService {
  id: number;
  name: string;
  duration_minutes: number;
  base_duration_minutes: number;
  price: number;
}

export interface Bundle {
  id: number;
  master_id: number;
  name: string;
  service_ids: number[];
  durations: Record<string, number>;
  services: BundleService[];
  duration_total: number;
  /** Manual total (NULL = member sum). */
  duration_override?: number | null;
  /** Percentage discount 0-90 on the bundle total. */
  discount_percent?: number | null;
  /** Discount expiry ISO (null = no expiry). */
  discount_until?: string | null;
  /** Fixed RUB off, applied after the percentage. */
  discount_fixed?: number | null;
  price_total: number;
  price: number | null;
  effective_price: number;
  is_active: boolean;
}

// ─── Client cabinet API ────────────────────────────────────────────

export const cabinetApi = {
  me() {
    return apiClient.get<ClientMe>('/api/v1/client/me');
  },
  updateMe(data: {
    name?: string;
    last_name?: string | null;
    city_id?: number;
    address?: string | null;
  }) {
    return apiClient.patch<ClientMe>('/api/v1/client/me', data);
  },
  deleteMe() {
    return apiClient.delete<{ detail: string; cancelled_appointments: number }>(
      '/api/v1/client/me',
    );
  },
  // ── Contacts (contact model): add / remove / promote ──────────────
  addContact(data: { contact_type: 'phone' | 'email'; value: string }) {
    return apiClient.post<ClientContact>('/api/v1/client/contacts', data);
  },
  removeContact(id: number) {
    return apiClient.delete<{ ok: boolean }>(`/api/v1/client/contacts/${id}`);
  },
  makeContactPrimary(id: number) {
    return apiClient.post<ClientContact>(`/api/v1/client/contacts/${id}/primary`);
  },
  /** «Подтвердить почту»: письмо с кодом на собственный email-контакт. */
  sendContactCode(id: number) {
    return apiClient.post<{ ok: boolean }>(`/api/v1/client/contacts/${id}/send-code`);
  },
  verifyContactCode(id: number, code: string) {
    return apiClient.post<ClientContact>(`/api/v1/client/contacts/${id}/verify-code`, { code });
  },
  stats() {
    return apiClient.get<ClientStats>('/api/v1/client/stats');
  },
  myAppointments() {
    return apiClient.get<Appointment[]>('/api/v1/client/appointments');
  },
  cancelAppointment(id: number) {
    return apiClient.post<Appointment>(`/api/v1/client/appointments/${id}/cancel`);
  },
  bookAppointment(data: {
    master_id: number;
    service_id?: number;
    bundle_id?: number;
    appointment_date: string;
    notes?: string;
    coupon_code?: string;
  }) {
    return apiClient.post<Appointment>('/api/v1/client/appointments', data);
  },
  previewCoupon(data: {
    master_id: number;
    service_id?: number;
    bundle_id?: number;
    code: string;
  }) {
    return apiClient.post<{
      ok: boolean;
      code: string;
      terms: string;
      base_price: number;
      discount: number;
      new_price: number;
    }>('/api/v1/client/coupons/preview', data);
  },
  myCoupons(masterId?: number) {
    return apiClient.get<
      {
        id: number;
        code: string;
        kind: string;
        value: number;
        uses_left: number | null;
        valid_until: string | null;
        is_active: boolean;
        terms: string;
        master_id: number;
      }[]
    >('/api/v1/client/coupons/mine', {
      params: masterId ? { master_id: masterId } : undefined,
    });
  },
  bundles(masterId: number) {
    return apiClient.get<Bundle[]>('/api/v1/client/bundles', {
      params: { master_id: masterId },
    });
  },
  getBookSchedule(masterId: number, month: string) {
    return apiClient.get<{
      master_id: number;
      window: { start_hour: number; end_hour: number };
      working_hours: { date: string; start: string; end: string }[];
      busy: { appointment_date: string; status: string; service_duration?: number | null }[];
    }>('/api/v1/client/booking/schedule', { params: { master_id: masterId, month } });
  },
  notificationsInbox(params?: { unread_only?: boolean; page?: number; page_size?: number }) {
    return apiClient.get<{
      items: {
        id: number;
        text: string;
        audience?: string | null;
        link?: string | null;
        kind?: string | null;
        appointment_id?: number | null;
        resolved_at?: string | null;
        sender_name?: string | null;
        is_read: boolean;
        created_at?: string | null;
      }[];
      total: number;
      unread: number;
    }>('/api/v1/client/notifications/inbox', { params });
  },
  confirmVisit(appointmentId: number, status: 'confirmed' | 'disputed') {
    return apiClient.post<{
      ok: boolean;
      appointment_id: number;
      status: string;
      review_url?: string | null;
    }>(`/api/v1/client/appointments/${appointmentId}/visit-confirmation`, { status });
  },
  notificationsUnread() {
    return apiClient.get<{ unread: number }>('/api/v1/client/notifications/unread-count');
  },
  readNotification(id: number) {
    return apiClient.post(`/api/v1/client/notifications/${id}/read`);
  },
  readAllNotifications() {
    return apiClient.post('/api/v1/client/notifications/read-all');
  },
  clearNotifications() {
    return apiClient.delete<{ deleted: number }>('/api/v1/client/notifications');
  },
  myReviews() {
    return apiClient.get<
      {
        id: number;
        appointment_id: number;
        master_id: number;
        rating: number;
        comment?: string | null;
      }[]
    >('/api/v1/client/reviews/mine');
  },
  createReview(data: { appointment_id: number; rating: number; comment?: string }) {
    return apiClient.post('/api/v1/client/reviews', data);
  },
};
