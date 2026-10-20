import axios, { AxiosInstance, InternalAxiosRequestConfig } from 'axios';
import { getCookie, clearAuthCookies } from '../utils/cookies';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export const API_BASE_URL = API_BASE;

/**
 * Backend-served file reference → absolute URL for <img src>.
 * Upload endpoints return same-origin paths ("/static/avatars/…"); used raw
 * they resolve against the FRONTEND origin and 404. Absolute http(s) URLs
 * (and non-path values like emoji presets) pass through untouched.
 */
export function assetUrl(path?: string | null): string | null {
  if (!path) return null;
  if (/^https?:\/\//i.test(path)) return path;
  if (path.startsWith('/')) return `${API_BASE}${path}`;
  // Plain values (emoji presets) pass through; exotic schemes
  // (javascript:, data:) never reach <img>/<a> (backend validates too).
  return /^[a-zA-Z][a-zA-Z0-9+.-]*:/.test(path) ? null : path;
}

// ─── Unified axios instance ────────────────────────────────────────

const apiClient: AxiosInstance = axios.create({
  baseURL: API_BASE,
  headers: { 'Content-Type': 'application/json' },
  withCredentials: true, // send cookies
});

// Attach access token from cookie to every request
apiClient.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = getCookie('access_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// ─── Bare instance for token refresh (NO interceptors) ─────────────
// Refresh must never go through apiClient: its 401 would re-enter the
// interceptor while isRefreshing=true and queue behind itself (deadlock).
// Exported for tests (authRefresh.test.ts drives it via defaults.adapter).
export const refreshClient: AxiosInstance = axios.create({
  baseURL: API_BASE,
  headers: { 'Content-Type': 'application/json' },
  withCredentials: true, // httpOnly refresh cookie is sent automatically
});

// Handle 401 — try refresh, then redirect to login
let isRefreshing = false;
let failedQueue: {
  resolve: (token: string) => void;
  reject: (error: unknown) => void;
}[] = [];

function processQueue(error: unknown, token: string | null = null) {
  failedQueue.forEach((prom) => {
    if (error) prom.reject(error);
    else prom.resolve(token as string);
  });
  failedQueue = [];
}

/**
 * Auth endpoints where a 401 is a normal answer for the form (wrong password,
 * expired code, unknown account), not a dead session. Sending them through
 * /auth/refresh and hard-redirecting to /admin/login used to reload the page
 * and throw the error toast away: a typo in the password "kicked the user to
 * the home page" instead of showing «Неверный email/телефон или пароль».
 *
 * Everything else (cabinet, admin, /auth/me, …) keeps refresh-and-retry.
 */
const AUTH_FORM_401 =
  /\/api\/v1\/auth\/(login-unified|register-unified|phone\/status|consent\/complete|send-otp|verify-otp|client\/login|login|register|password\/(forgot|reset)|refresh|logout|vk\/|yandex\/|max\/)/;

apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    if (
      error.response?.status === 401 &&
      !originalRequest._retry &&
      !AUTH_FORM_401.test(originalRequest.url ?? '')
    ) {
      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject });
        }).then((token) => {
          // Mark retried: a second 401 must not trigger another refresh storm
          originalRequest._retry = true;
          originalRequest.headers.Authorization = `Bearer ${token}`;
          return apiClient(originalRequest);
        });
      }

      originalRequest._retry = true;
      isRefreshing = true;

      try {
        // Bare instance: no interceptors, so a 401 here cannot deadlock
        const { data } = await refreshClient.post<{ access_token: string }>('/api/v1/auth/refresh');

        // Update access token in cookie (set via Set-Cookie header from backend)
        // Also update axios defaults
        apiClient.defaults.headers.common.Authorization = `Bearer ${data.access_token}`;

        processQueue(null, data.access_token);

        originalRequest.headers.Authorization = `Bearer ${data.access_token}`;
        return apiClient(originalRequest);
      } catch (refreshError) {
        processQueue(refreshError, null);
        // Not refreshed — logout, but remember where we were: home opens
        // the login modal and continues straight back after auth.
        clearAuthCookies();
        try {
          const target = window.location.pathname + window.location.search;
          if (target && target !== '/') sessionStorage.setItem('postLoginTo', target);
        } catch {
          /* ignore */
        }
        window.location.href = '/admin/login';
        return Promise.reject(refreshError);
      } finally {
        isRefreshing = false;
      }
    }

    return Promise.reject(error);
  },
);

export default apiClient;
