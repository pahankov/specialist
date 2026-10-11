import apiClient from './http';
import type { Appointment } from './types';

export interface ClientMe {
  id: number;
  name: string;
  phone?: string | null;
  email?: string | null;
  is_verified: boolean;
  city_id?: number | null;
  city_name?: string | null;
}

export interface ClientStats {
  total_spent: number;
  completed_visits: number;
  upcoming_count: number;
  cancelled_count: number;
  favorite_master?: { id: number; name?: string | null; visits: number } | null;
  favorite_service?: { id: number; name?: string | null; visits: number } | null;
}

// ─── Client cabinet API ────────────────────────────────────────────

export const cabinetApi = {
  me() {
    return apiClient.get<ClientMe>('/api/v1/client/me');
  },
  updateMe(data: { name?: string; city_id?: number }) {
    return apiClient.patch<ClientMe>('/api/v1/client/me', data);
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
  notificationsInbox(params?: { unread_only?: boolean; page?: number; page_size?: number }) {
    return apiClient.get<{
      items: {
        id: number;
        text: string;
        audience?: string | null;
        sender_name?: string | null;
        is_read: boolean;
        created_at?: string | null;
      }[];
      total: number;
      unread: number;
    }>('/api/v1/client/notifications/inbox', { params });
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
};
