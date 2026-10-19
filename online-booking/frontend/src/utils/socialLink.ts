/**
 * Link-mode social roundtrips (profile «Привязать VK/Яндекс»).
 *
 * Regular social logins land by role; link-mode ones must return the user
 * to the profile page they started from. We stash that path in
 * sessionStorage before the redirect — its presence in the callback page
 * IS the link flag (no separate boolean to keep in sync).
 */

const RETURN_KEY = 'social_link_return';

export function stashSocialLinkReturn(path: string): void {
  try {
    sessionStorage.setItem(RETURN_KEY, path);
  } catch {
    /* storage unavailable — the callback falls back to the role landing */
  }
}

export function takeSocialLinkReturn(): string | null {
  try {
    const value = sessionStorage.getItem(RETURN_KEY);
    sessionStorage.removeItem(RETURN_KEY);
    return value;
  } catch {
    return null;
  }
}
