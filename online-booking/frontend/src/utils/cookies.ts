/** Cookie + JWT payload helpers (single copy; used by api client and layout). */

export function getCookie(name: string): string | null {
  const match = document.cookie.match(new RegExp('(^| )' + name + '=([^;]+)'))
  return match ? match[2] : null
}

export interface JwtPayload {
  sub?: string
  is_admin?: boolean
  name?: string
  exp?: number
}

export function decodeJwtPayload(token: string): JwtPayload | null {
  try {
    const payload = token.split('.')[1]
    return JSON.parse(atob(payload)) as JwtPayload
  } catch {
    return null
  }
}

export function clearAuthCookies(): void {
  // Both tokens: access_token is JS-readable, refresh_token is httpOnly
  // (JS delete is a best-effort — server revokes the session on logout).
  document.cookie = 'access_token=; path=/; max-age=0'
  document.cookie = 'refresh_token=; path=/; max-age=0'
}
