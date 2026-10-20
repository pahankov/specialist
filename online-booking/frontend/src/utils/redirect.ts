/** Deep-link memory: dying sessions bounce to home, login continues back. */

const KEY = 'postLoginTo';
const DRAFT_MASTER_ROOT = '/admin/become-master';

/**
 * Deep links into the inactive-master shell are not a client landing target.
 * A guest who opened /admin/become-master must return to the client cabinet
 * after login; only an already active MASTER may continue into /admin.
 */
export function safePostLoginTarget(target: string | null, role?: string | null): string | null {
  if (!target || role === 'MASTER') return target;
  if (
    target === DRAFT_MASTER_ROOT ||
    target.startsWith(`${DRAFT_MASTER_ROOT}/`) ||
    target.startsWith(`${DRAFT_MASTER_ROOT}?`)
  ) {
    return null;
  }
  return target;
}

export function stashReturnUrl(path?: string) {
  try {
    const target = path ?? window.location.pathname + window.location.search;
    if (target && target !== '/') sessionStorage.setItem(KEY, target);
  } catch {
    /* private mode */
  }
}

export function takeReturnUrl(): string | null {
  try {
    const v = sessionStorage.getItem(KEY);
    if (v) sessionStorage.removeItem(KEY);
    return v;
  } catch {
    return null;
  }
}

/** Stash the current page and go to the login gateway (home modal). */
export function goLogin() {
  stashReturnUrl();
  window.location.href = '/admin/login';
}
