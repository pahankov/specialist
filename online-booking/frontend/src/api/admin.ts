import apiClient from './http';
import type {
  Service,
  Client,
  DashboardStats,
  PaginatedResponse,
  HealthCheck,
  Changelog,
} from './types';

export const adminApi = {
  // Own panel profile (id/name/city — form defaults)
  getProfile() {
    return apiClient.get<{
      id: number;
      name: string;
      last_name?: string | null;
      city_id?: number | null;
      city_name?: string | null;
      telegram_username?: string | null;
      description?: string | null;
      avatar_url?: string | null;
      experience_years?: number | null;
      cabinet_address?: string | null;
      certificates?: { name: string; url?: string }[];
    }>('/api/v1/admin/profile');
  },
  updateProfile(data: {
    name?: string;
    last_name?: string | null;
    city_id?: number | null;
    telegram_username?: string | null;
    description?: string | null;
    experience_years?: number | null;
    cabinet_address?: string | null;
    certificates?: { name: string; url?: string }[];
  }) {
    return apiClient.patch('/api/v1/admin/profile', data);
  },
  uploadAvatar(file: File) {
    const form = new FormData();
    form.append('file', file);
    return apiClient.post<{ avatar_url: string }>('/api/v1/admin/profile/avatar', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
  // Dashboard
  getDashboard() {
    return apiClient.get<DashboardStats>('/api/v1/admin/dashboard');
  },
  getMonthlyStats(year: number, month: number, master_id?: number) {
    return apiClient.get('/api/v1/admin/monthly-stats', { params: { year, month, master_id } });
  },

  // Appointments
  getAppointments(params?: {
    status?: string;
    master_id?: number;
    client_id?: number;
    service_id?: number;
    date_from?: string;
    date_to?: string;
    page?: number;
    page_size?: number;
  }) {
    return apiClient.get('/api/v1/admin/appointments', { params });
  },
  confirmAppointment(id: number) {
    return apiClient.patch(`/api/v1/admin/appointments/${id}/confirm`);
  },
  cancelAppointment(id: number, reason?: string) {
    return apiClient.patch(`/api/v1/admin/appointments/${id}/cancel`, null, { params: { reason } });
  },
  completeAppointment(id: number) {
    return apiClient.patch(`/api/v1/admin/appointments/${id}/complete`);
  },
  noShowAppointment(id: number) {
    return apiClient.patch(`/api/v1/admin/appointments/${id}/no-show`);
  },
  deleteAppointment(id: number) {
    return apiClient.delete(`/api/v1/admin/appointments/${id}`);
  },
  bookAppointment(data: {
    client_id: number;
    service_id: number;
    appointment_date: string;
    status: string;
    notes?: string;
    master_id?: number;
  }) {
    return apiClient.post('/api/v1/admin/appointments/book', data);
  },
  getAppointmentsByDate(from: string, to: string, master_id?: number) {
    return apiClient.get('/api/v1/admin/appointments/by-date', {
      params: { date_from: from, date_to: to, master_id },
    });
  },

  // Clients
  getClients(params?: {
    page?: number;
    page_size?: number;
    search?: string;
    master_id?: number;
    sort_by?: string;
    sort_dir?: string;
  }) {
    return apiClient.get<PaginatedResponse<Client>>('/api/v1/admin/clients', { params });
  },
  createClient(data: {
    name: string;
    phone: string;
    email?: string;
    city_id?: number | null;
    city_name?: string | null;
    address?: string | null;
  }) {
    return apiClient.post<Client>('/api/v1/admin/clients', data);
  },
  updateClient(
    id: number,
    data: {
      name?: string;
      phone?: string;
      email?: string;
      city_id?: number | null;
      city_name?: string | null;
      address?: string | null;
    },
  ) {
    return apiClient.patch<Client>(`/api/v1/admin/clients/${id}`, data);
  },
  bulkSetClientCity(data: { city_id: number; search?: string; master_id?: number }) {
    return apiClient.post<{ updated: number; city_id: number; city_name: string }>(
      '/api/v1/admin/clients/bulk-city',
      data,
    );
  },
  deleteClient(id: number) {
    return apiClient.delete(`/api/v1/admin/clients/${id}`);
  },
  toggleClientActive(id: number) {
    return apiClient.post(`/api/v1/admin/clients/${id}/toggle-active`);
  },

  // Services
  getServices(params?: { page?: number; page_size?: number; active_only?: string | boolean }) {
    const processedParams = params ? { ...params } : undefined;
    if (processedParams?.active_only !== undefined) {
      processedParams.active_only = String(processedParams.active_only);
    }
    return apiClient.get<PaginatedResponse<Service>>('/api/v1/admin/services', {
      params: processedParams,
    });
  },
  getAllServices(params?: { page?: number; page_size?: number; master_id?: number }) {
    return apiClient.get<PaginatedResponse<Service>>('/api/v1/admin/services/all', { params });
  },
  createService(data: {
    name: string;
    description?: string;
    duration_minutes: number;
    price: number;
    category?: string;
  }) {
    return apiClient.post<Service>('/api/v1/admin/services', data);
  },
  updateService(
    id: number,
    data: {
      name?: string;
      description?: string;
      duration_minutes?: number;
      price?: number;
      category?: string;
    },
  ) {
    return apiClient.patch<Service>(`/api/v1/admin/services/${id}`, data);
  },
  deleteService(id: number) {
    return apiClient.delete(`/api/v1/admin/services/${id}`);
  },

  // Working Hours
  getWorkingHours(master_id?: number) {
    return apiClient.get('/api/v1/admin/working-hours', {
      params: master_id ? { master_id } : undefined,
    });
  },
  createWorkingHour(data: {
    schedule_date: string;
    start_time: string;
    end_time: string;
    master_id?: number;
  }) {
    return apiClient.post('/api/v1/admin/working-hours', data);
  },
  updateWorkingHour(
    id: number,
    data: { schedule_date?: string; start_time?: string; end_time?: string },
  ) {
    return apiClient.patch(`/api/v1/admin/working-hours/${id}`, data);
  },
  deleteWorkingHour(id: number) {
    return apiClient.delete(`/api/v1/admin/working-hours/${id}`);
  },
  getWorkWindow(master_id?: number) {
    return apiClient.get<{ master_id: number; start_hour: number; end_hour: number }>(
      '/api/v1/admin/work-window',
      { params: master_id ? { master_id } : undefined },
    );
  },
  updateWorkWindow(data: { master_id?: number; start_hour: number; end_hour: number }) {
    return apiClient.patch<{ master_id: number; start_hour: number; end_hour: number }>(
      '/api/v1/admin/work-window',
      data,
    );
  },

  // Notifications (internal bell — no messenger binding)
  getNotificationCounts(audience: string, user_ids?: string) {
    return apiClient.get<{
      audience: string;
      total: number;
      skipped_not_allowed: number;
    }>('/api/v1/admin/notifications/audience-counts', { params: { audience, user_ids } });
  },
  broadcastNotification(data: { audience: string; user_ids?: number[]; text: string }) {
    return apiClient.post<{
      total: number;
      created: number;
      skipped_not_allowed: number;
    }>('/api/v1/admin/notifications/broadcast', data);
  },
  getNotificationsInbox(params?: { unread_only?: boolean; page?: number; page_size?: number }) {    return apiClient.get<{
      items: {
        id: number;
        text: string;
        audience?: string | null;
        link?: string | null;
        sender_name?: string | null;
        is_read: boolean;
        created_at?: string | null;
      }[];
      total: number;
      unread: number;
    }>('/api/v1/admin/notifications/inbox', { params });
  },
  getNotificationsUnread() {
    return apiClient.get<{ unread: number }>('/api/v1/admin/notifications/unread-count');
  },
  readNotification(id: number) {
    return apiClient.post(`/api/v1/admin/notifications/${id}/read`);
  },
  readAllNotifications() {
    return apiClient.post('/api/v1/admin/notifications/read-all');
  },
  getSentBroadcasts(params?: { page?: number; page_size?: number }) {
    return apiClient.get<{
      items: {
        id: number;
        audience: string;
        text: string;
        recipients: { id: number; name: string }[];
        recipient_count: number;
        created_at?: string | null;
      }[];
      total: number;
      page: number;
      page_size: number;
    }>('/api/v1/admin/notifications/sent', { params });
  },

  // Audit Logs
  getAuditLogs(params?: Record<string, string | number | boolean | undefined>) {
    return apiClient.get('/api/v1/admin/audit-logs', { params });
  },
  getAuditLogsAll(params?: Record<string, string | number | boolean | undefined>) {
    return apiClient.get('/api/v1/admin/audit-logs/all', { params });
  },

  // Blocked Slots
  getBlockedSlots() {
    return apiClient.get('/api/v1/admin/blocked-slots');
  },
  createBlockedSlot(data: {
    master_id: number;
    start_dt: string;
    end_dt: string;
    reason?: string;
  }) {
    return apiClient.post('/api/v1/admin/blocked-slots', data);
  },
  deleteBlockedSlot(id: number) {
    return apiClient.delete(`/api/v1/admin/blocked-slots/${id}`);
  },

  // Health check
  getHealth() {
    return apiClient.get<HealthCheck>('/api/v1/admin/health');
  },
  getHealthVerbose() {
    return apiClient.get<HealthCheck>('/api/v1/admin/health/verbose');
  },

  // Changelog
  getChangelog() {
    return apiClient.get<Changelog>('/api/v1/admin/changelog');
  },

  // Revenue breakdown
  getRevenueBreakdown(params?: {
    by_master?: boolean;
    by_service?: boolean;
    date_from?: string;
    date_to?: string;
  }) {
    return apiClient.get('/api/v1/admin/revenue-breakdown', { params });
  },

  // Dashboard cache management
  clearDashboardCache() {
    return apiClient.post('/api/v1/admin/dashboard/cache/clear');
  },
};
