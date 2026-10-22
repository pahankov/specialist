import apiClient from './http';

/** Sidebar support contact - delivered to the superadmin bell. */
export const supportApi = {
  send(data: { message: string; page?: string }) {
    return apiClient.post<{ delivered: number }>('/api/v1/support/request', data);
  },
};
