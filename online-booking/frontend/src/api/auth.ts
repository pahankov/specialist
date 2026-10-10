import apiClient from './http';
import type { LoginResponse, UnifiedRegisterResponse } from './types';

// ─── Auth API ──────────────────────────────────────────────────────

export interface UnifiedRegisterData {
  name: string;
  email: string;
  phone: string;
  password: string;
  city_data?: Record<string, unknown> | null;
  telegram_username?: string | null;
  is_master: boolean;
}

export interface MaxStartResponse {
  code: string;
  expires_in: number;
  bot_username: string;
  bot_url: string;
}

export interface MaxStatusResponse {
  status: 'pending' | 'verified' | 'expired' | 'disabled';
  access_token?: string;
  token_type: string;
  is_new_user?: boolean;
}

export const authApi = {
  login: (email: string, password: string) =>
    apiClient.post<LoginResponse>('/api/v1/auth/login', { email, password }),
  register: (data: {
    name: string;
    email: string;
    password: string;
    phone?: string;
    telegram_username?: string;
    role: string;
    city_id?: number;
  }) => apiClient.post('/api/v1/auth/register', data),
  clientLogin: (phone: string) =>
    apiClient.post<LoginResponse>('/api/v1/auth/client/login', { phone }),
  sendOtp: (phone: string) => apiClient.post('/api/v1/auth/send-otp', { phone }),
  verifyOtp: (phone: string, code: string) =>
    apiClient.post<LoginResponse>('/api/v1/auth/verify-otp', { phone, code }),
  logout: () => apiClient.post('/api/v1/auth/logout'),
  loginUnified: (identifier: string, password: string) =>
    apiClient.post<LoginResponse>('/api/v1/auth/login-unified', { identifier, password }),
  registerUnified: (data: UnifiedRegisterData) =>
    apiClient.post<UnifiedRegisterResponse>('/api/v1/auth/register-unified', data),
  maxStart: (phone: string) =>
    apiClient.post<MaxStartResponse>('/api/v1/auth/max/start', { phone }),
  maxStatus: (phone: string) =>
    apiClient.post<MaxStatusResponse>('/api/v1/auth/max/status', { phone }),
};
