import { useLocation } from 'react-router-dom';

/** URL sections: masters live under /admin, superadmin under /super. */
export const ADMIN_PREFIX = '/admin';
export const SUPER_PREFIX = '/super';

export function isSuperPath(pathname: string): boolean {
  return pathname === SUPER_PREFIX || pathname.startsWith(`${SUPER_PREFIX}/`);
}

/** Section prefix for a pathname (defaults to the master section). */
export function sectionPrefix(pathname: string): string {
  return isSuperPath(pathname) ? SUPER_PREFIX : ADMIN_PREFIX;
}

/** Current section prefix from the router location. */
export function useSectionPrefix(): string {
  const { pathname } = useLocation();
  return sectionPrefix(pathname);
}
