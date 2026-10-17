import apiClient from './http';
import type { LoginResponse, UnifiedRegisterResponse } from './types';

// ─── Auth API ──────────────────────────────────────────────────────

export interface UnifiedRegisterData {
  phone: string;
  password: string;
  /** 152-FZ consent checkbox (offer + privacy policy). */
  consent: boolean;
}

export interface MaxStartResponse {
  delivered: boolean;
  deeplink: string;
  expires_in: number;
  bot_username: string;
  bot_url: string;
}

export interface MaxVerifyResponse {
  access_token: string;
  token_type: string;
  is_new_user?: boolean;
}

export interface VkStartResponse {
  /** Full VK consent URL — the browser is redirected here. */
  authorize_url: string;
  state: string;
  client_id: string;
  /** Canonical backend redirect_uri (must match at authorize + exchange). */
  redirect_uri: string;
}

export interface VkVerifyResponse {
  access_token: string;
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
  becomeMaster: (data?: {
    cabinet_address?: string;
    description?: string;
    experience_years?: number;
  }) => apiClient.post<{ detail: string }>('/api/v1/auth/become-master', data ?? {}),
  registerUnified: (data: UnifiedRegisterData) =>
    apiClient.post<UnifiedRegisterResponse>('/api/v1/auth/register-unified', data),
  maxStart: (phone: string) =>
    apiClient.post<MaxStartResponse>('/api/v1/auth/max/start', { phone }),
  maxVerify: (phone: string, code: string, consent = false) =>
    apiClient.post<MaxVerifyResponse>('/api/v1/auth/max/verify', { phone, code, consent }),
  vkStart: (codeChallenge: string) =>
    apiClient.post<VkStartResponse>('/api/v1/auth/vk/start', {
      code_challenge: codeChallenge,
    }),
  vkVerify: (
    code: string,
    deviceId: string,
    state: string,
    codeVerifier: string,
    consent = false,
  ) =>
    apiClient.post<VkVerifyResponse>('/api/v1/auth/vk/verify', {
      code,
      device_id: deviceId,
      state,
      code_verifier: codeVerifier,
      consent,
    }),
};
