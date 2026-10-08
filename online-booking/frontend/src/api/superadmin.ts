import apiClient from './http'
import type {
  Master,
  Review,
  AdminLoginResponse,
  AdminStats,
  MasterDetail,
  BulkResult,
  AuditLogEntry,
  ImportResult,
  PaginatedResponse,
} from './types'

// ─── SuperAdmin API ────────────────────────────────────────────────

export const superAdminAuthApi = {
  register: (data: { name: string; email: string; password: string }) =>
    apiClient.post<AdminLoginResponse>('/api/v1/admin/register', data),
  login: (email: string, password: string) =>
    apiClient.post<AdminLoginResponse>('/api/v1/admin/login', { email, password }),
}

export const superAdminApi = {
  // Global dashboard stats
  getGlobalDashboard() {
    return apiClient.get<AdminStats>('/api/v1/admin/dashboard')
  },

  // Master management
  getAllMasters(params?: { search?: string; is_active?: boolean | string; is_admin?: boolean | string; sort_by?: string; sort_dir?: string }) {
    return apiClient.get<Master[]>('/api/v1/admin/masters', { params })
  },
  getMasterById(id: number) {
    return apiClient.get<Master>(`/api/v1/admin/masters/${id}`)
  },
  createMaster(data: { name: string; email: string; password: string; phone?: string; telegram_username?: string }) {
    return apiClient.post<Master>('/api/v1/admin/masters', data)
  },
  updateMaster(id: number, data: { name?: string; phone?: string; telegram_username?: string; description?: string; password?: string; tariff?: string; trial_ends_at?: string }) {
    return apiClient.patch<Master>(`/api/v1/admin/masters/${id}`, data)
  },
  deleteMaster(id: number) {
    return apiClient.delete(`/api/v1/admin/masters/${id}`)
  },
  toggleMasterActive(id: number) {
    return apiClient.post<Master>(`/api/v1/admin/masters/${id}/toggle-active`)
  },
  toggleMasterAdmin(id: number) {
    return apiClient.post<Master>(`/api/v1/admin/masters/${id}/toggle-admin`)
  },
  getMasterStats(id: number, params?: { date_from?: string; date_to?: string }) {
    return apiClient.get<AdminStats>(`/api/v1/admin/masters/${id}/stats`, { params })
  },

  // Global stats
  getGlobalStats() {
    return apiClient.get<AdminStats>('/api/v1/admin/global-stats')
  },

  // Master detail (full profile)
  getMasterFull(id: number) {
    return apiClient.get<MasterDetail>(`/api/v1/admin/masters/${id}/full`)
  },

  // Bulk operations
  bulkToggleActive(masterIds: number[]) {
    return apiClient.post<BulkResult>('/api/v1/admin/masters/bulk/toggle-active', masterIds)
  },
  bulkSuspend(masterIds: number[]) {
    return apiClient.post<BulkResult>('/api/v1/admin/masters/bulk/suspend', masterIds)
  },
  bulkUnsuspend(masterIds: number[]) {
    return apiClient.post<BulkResult>('/api/v1/admin/masters/bulk/unsuspend', masterIds)
  },

  // Individual master actions
  suspendMaster(masterId: number) {
    return apiClient.post(`/api/v1/admin/masters/${masterId}/suspend`)
  },
  unsuspendMaster(masterId: number) {
    return apiClient.post(`/api/v1/admin/masters/${masterId}/unsuspend`)
  },

  // Import
  importMasters(file: File) {
    const formData = new FormData()
    formData.append('file', file)
    return apiClient.post<ImportResult>('/api/v1/admin/masters/import', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },

  // Admin reviews
  getAdminReviews(params?: { master_id?: number; is_published?: boolean; page?: number; page_size?: number }) {
    return apiClient.get<PaginatedResponse<Review>>('/api/v1/admin/reviews', { params })
  },
  publishReview(reviewId: number) {
    return apiClient.patch<Review>(`/api/v1/admin/reviews/${reviewId}/publish`)
  },
  unpublishReview(reviewId: number) {
    return apiClient.patch<Review>(`/api/v1/admin/reviews/${reviewId}/unpublish`)
  },
  deleteReview(reviewId: number) {
    return apiClient.delete(`/api/v1/admin/reviews/${reviewId}`)
  },
  getMasterAverageRating(masterId: number) {
    return apiClient.get(`/api/v1/admin/reviews/average/${masterId}`)
  },

  // Master audit logs
  getMastersAudit(masterId: number, page?: number, pageSize?: number) {
    return apiClient.get<PaginatedResponse<AuditLogEntry>>('/api/v1/admin/audit-logs', {
      params: { master_id: masterId, page, page_size: pageSize },
    })
  },

  // Security actions (support)
  impersonateMaster(masterId: number) {
    return apiClient.post<{ access_token: string; user_id: number; name: string }>(
      `/api/v1/admin/masters/${masterId}/impersonate`,
    )
  },
  resetMasterPassword(masterId: number, password: string) {
    return apiClient.patch(`/api/v1/admin/masters/${masterId}/password`, { password })
  },
  getMasterSessions(masterId: number) {
    return apiClient.get<{ id: number; created_at: string; expires_at: string }[]>(
      `/api/v1/admin/masters/${masterId}/sessions`,
    )
  },
  revokeMasterSessions(masterId: number) {
    return apiClient.delete<{ revoked: number }>(
      `/api/v1/admin/masters/${masterId}/sessions`,
    )
  },
}
