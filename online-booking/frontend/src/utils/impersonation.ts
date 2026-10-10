/** Impersonation state (support "view as master").
 *
 * The admin access token is parked in sessionStorage (tab-scoped: closing
 * the tab can never leak the elevated session), the master's token goes
 * into the regular access_token cookie consumed by the api client.
 */

const KEY = 'impersonation';

export interface ImpersonationState {
  adminToken: string;
  masterName: string;
}

function readState(): ImpersonationState | null {
  try {
    const raw = sessionStorage.getItem(KEY);
    return raw ? (JSON.parse(raw) as ImpersonationState) : null;
  } catch {
    return null;
  }
}

export function isImpersonating(): boolean {
  return readState() !== null;
}

export function getImpersonation(): ImpersonationState | null {
  return readState();
}

export function startImpersonation(
  adminToken: string,
  masterToken: string,
  masterName: string,
): void {
  sessionStorage.setItem(KEY, JSON.stringify({ adminToken, masterName }));
  document.cookie = `access_token=${masterToken}; path=/; max-age=${30 * 60}`;
}

export function stopImpersonation(): void {
  const state = readState();
  sessionStorage.removeItem(KEY);
  if (state) {
    document.cookie = `access_token=${state.adminToken}; path=/; max-age=${30 * 60}`;
  } else {
    document.cookie = 'access_token=; path=/; max-age=0';
  }
}
