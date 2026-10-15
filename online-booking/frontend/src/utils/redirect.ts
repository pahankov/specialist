/** Deep-link memory: dying sessions bounce to home, login continues back. */

const KEY = 'postLoginTo';

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
