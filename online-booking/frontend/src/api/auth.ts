import apiClient, { refreshClient } from './http';
import type { LoginResponse, UnifiedRegisterResponse } from './types';

// ─── Auth API ──────────────────────────────────────────────────────

export interface UnifiedRegisterData {
  phone: string;
  password: string;
  /** 152-FZ consent checkbox (offer + privacy policy). */
  consent: boolean;
  /** Challenge token from the 2-step flow (phone/status). When present,
      ``phone`` is ignored and the phone is extracted from the challenge. */
  challenge?: string;
}

export interface MaxStartResponse {
  delivered: boolean;
  deeplink: string;
  expires_in: number;
  bot_username: string;
  bot_url: string;
  /** Human-readable bot name for the button («Электронная запись»). */
  bot_name: string;
}

export interface MaxVerifyResponse {
  access_token: string;
  token_type: string;
  is_new_user?: boolean;
  challenge?: string;
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
  challenge?: string;
}

export interface YandexVerifyResponse {
  access_token: string;
  token_type: string;
  is_new_user?: boolean;
  challenge?: string;
}

export interface YandexStartResponse {
  /** Full Yandex consent URL — the browser is redirected here. */
  authorize_url: string;
  /** Signed state (stashed until Yandex echoes it back to the callback). */
  state: string;
  client_id: string;
  /** Canonical backend redirect_uri (must match at authorize + exchange). */
  redirect_uri: string;
  /** Helper page of the official instant-auth widget (sdk-suggest.js);
      empty = widget off, the plain redirect button is used instead. */
  suggest_redirect_uri: string;
}

export interface YandexVerifyResponse {
  access_token: string;
  token_type: string;
  is_new_user?: boolean;
}

/** Unified entry: what the entered phone number means (login vs register). */
export interface PhoneStatusResponse {
  /** "new" — no account; "password" — has a password; "social" — social-only. */
  state: 'new' | 'password' | 'social';
  phone: string;
}

/** Master application payload (1.82.0): full master profile on submit. */
export interface BecomeMasterData {
  name?: string;
  last_name?: string | null;
  cabinet_address?: string;
  city_id?: number | null;
  description?: string | null;
  experience_years?: number | null;
  telegram_username?: string | null;
  avatar_url?: string | null;
  certificates?: { name: string; url?: string }[];
  /** Land straight in the master panel after approval (default true). */
  prefer_master_cabinet?: boolean;
}

export interface MasterApplicationData {
  name: string;
  last_name?: string | null;
  city_id?: number | null;
  cabinet_address?: string | null;
  description?: string | null;
  experience_years?: number | null;
  telegram_username?: string | null;
  avatar_url?: string | null;
  certificates?: { name: string; url?: string }[];
  prefer_master_cabinet: boolean;
  created_at?: string | null;
}

/** GET /auth/become-master: none → no application, pending → awaiting
    approval, active → already a master. */
export interface MasterApplicationResponse {
  status: 'none' | 'pending' | 'active';
  application: MasterApplicationData | null;
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
  /** Re-mint the access token from the refresh cookie (fresh JWT claims:
      used after a name change so the sidebar picks it up without re-login).
      Bare client on purpose: a failed refresh must not hit the 401
      interceptor (that one logs the user out). */
  refreshSession: () => refreshClient.post<{ access_token: string }>('/api/v1/auth/refresh'),
  loginUnified: (identifier: string, password: string, consent = false) =>
    apiClient.post<LoginResponse>('/api/v1/auth/login-unified', {
      identifier,
      password,
      consent,
    }),
  /** Unified entry step 1: does this phone belong to an account, and which
      kind of login does it need? Enumeration-proof by design (the answer
      only routes the UI; no account details leak). */
  phoneStatus: (phone: string) =>
    apiClient.post<PhoneStatusResponse>('/api/v1/auth/phone/status', { phone }),
  forgotPassword: (email: string) =>
    apiClient.post<{ message: string }>('/api/v1/auth/password/forgot', { email }),
  /** Reset by emailed code + auto-login (cookies are set by the backend). */
  resetPassword: (email: string, code: string, newPassword: string) =>
    apiClient.post<LoginResponse>('/api/v1/auth/password/reset', {
      email,
      code,
      new_password: newPassword,
    }),
  changePassword: (currentPassword: string, newPassword: string) =>
    apiClient.post<{ message: string }>('/api/v1/auth/password/change', {
      current_password: currentPassword,
      new_password: newPassword,
    }),
  becomeMaster: (data: BecomeMasterData) =>
    apiClient.post<{ detail: string; status: string }>('/api/v1/auth/become-master', data),
  masterApplication: () => apiClient.get<MasterApplicationResponse>('/api/v1/auth/become-master'),
  /** Optional photo/certificate upload for a pending application. */
  uploadMasterPhoto: (file: File, kind: 'avatar' | 'cert' = 'avatar') => {
    const form = new FormData();
    form.append('file', file);
    return apiClient.post<{ avatar_url: string }>(
      `/api/v1/auth/become-master/photo?kind=${kind}`,
      form,
      { headers: { 'Content-Type': 'multipart/form-data' } },
    );
  },
  registerUnified: (data: UnifiedRegisterData) =>
    apiClient.post<UnifiedRegisterResponse>('/api/v1/auth/register-unified', data),
  maxStart: (phone: string) =>
    apiClient.post<MaxStartResponse>('/api/v1/auth/max/start', { phone }),
  maxVerify: (phone: string, code: string, consent = false) =>
    apiClient.post<MaxVerifyResponse>('/api/v1/auth/max/verify', { phone, code, consent }),
  /** link=true: attach VK to the CURRENT account (auth required) instead of
      logging in — the signed state carries the uid, conflicts answer 409. */
  vkStart: (codeChallenge: string, link = false) =>
    apiClient.post<VkStartResponse>('/api/v1/auth/vk/start', {
      code_challenge: codeChallenge,
      link,
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
  /** link=true: attach Yandex to the CURRENT account (auth required). */
  yandexStart: (link = false) =>
    apiClient.post<YandexStartResponse>('/api/v1/auth/yandex/start', { link }),
  yandexVerify: (code: string, state: string, consent = false) =>
    apiClient.post<YandexVerifyResponse>('/api/v1/auth/yandex/verify', {
      code,
      state,
      consent,
    }),
  /** Widget flow: the suggest SDK delivered an OAuth token — verified
      server-side (user_info) before the session is minted. */
  yandexVerifyToken: (accessToken: string, consent = false) =>
    apiClient.post<YandexVerifyResponse>('/api/v1/auth/yandex/verify', {
      access_token: accessToken,
      consent,
    }),
  /** Complete the 2-step consent flow (1.80.0). */
  consentComplete: (challenge: string, consent: boolean) =>
    apiClient.post<LoginResponse>('/api/v1/auth/consent/complete', {
      challenge,
      consent,
    }),
};
