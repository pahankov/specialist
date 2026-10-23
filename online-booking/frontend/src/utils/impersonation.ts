/** Impersonation state (support "view as participant").
 *
 * The admin access token is parked in sessionStorage (tab-scoped: closing
 * the tab can never leak the elevated session), the participant's token goes
 * into the regular access_token cookie consumed by the api client.
 */

const KEY = 'impersonation';

export type ImpersonationRole = 'MASTER' | 'CLIENT';

export interface ImpersonationState {
  adminToken: string;
  /** Display name of the participant (historical field name kept for
   *  existing sessions/tests; it holds client names too). */
  masterName: string;
  targetRole?: ImpersonationRole;
  /** Section to open after leaving support mode. */
  returnTo?: string;
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

/** Landing route for an impersonated participant. */
export function impersonationHome(role?: ImpersonationRole): string {
  return role === 'CLIENT' ? '/cabinet' : '/admin/dashboard';
}

/** Russian noun for the support banner. */
export function impersonationRoleLabel(role?: ImpersonationRole): string {
  return role === 'CLIENT' ? 'клиента' : 'мастера';
}

export function startImpersonation(
  adminToken: string,
  targetToken: string,
  targetName: string,
  targetRole: ImpersonationRole = 'MASTER',
  returnTo?: string,
): void {
  sessionStorage.setItem(
    KEY,
    JSON.stringify({ adminToken, masterName: targetName, targetRole, returnTo }),
  );
  document.cookie = `access_token=${targetToken}; path=/; max-age=${30 * 60}`;
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
