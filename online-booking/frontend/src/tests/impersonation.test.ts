import { describe, it, expect, beforeEach } from 'vitest';
import {
  isImpersonating,
  getImpersonation,
  impersonationHome,
  impersonationRoleLabel,
  startImpersonation,
  stopImpersonation,
} from '../utils/impersonation';

beforeEach(() => {
  sessionStorage.clear();
  document.cookie = 'access_token=; path=/; max-age=0';
});

describe('impersonation', () => {
  it('starts and stops, restoring the admin token', () => {
    expect(isImpersonating()).toBe(false);

    document.cookie = 'access_token=ADMIN; path=/';
    startImpersonation('ADMIN', 'MASTER', 'Ivan');

    expect(isImpersonating()).toBe(true);
    expect(getImpersonation()?.masterName).toBe('Ivan');
    expect(document.cookie).toContain('access_token=MASTER');

    stopImpersonation();

    expect(isImpersonating()).toBe(false);
    expect(document.cookie).toContain('access_token=ADMIN');
  });

  it('tracks the client role and landing route', () => {
    document.cookie = 'access_token=ADMIN; path=/';
    startImpersonation('ADMIN', 'CLIENT', 'Anna', 'CLIENT', '/super/clients');

    expect(getImpersonation()?.targetRole).toBe('CLIENT');
    expect(getImpersonation()?.returnTo).toBe('/super/clients');
    expect(impersonationHome('CLIENT')).toBe('/cabinet');
    expect(impersonationHome('MASTER')).toBe('/admin/dashboard');
    expect(impersonationRoleLabel('CLIENT')).toBe('клиента');
    expect(impersonationRoleLabel('MASTER')).toBe('мастера');

    stopImpersonation();
    expect(document.cookie).toContain('access_token=ADMIN');
  });

  it('stop without state clears the cookie', () => {
    document.cookie = 'access_token=X; path=/';
    stopImpersonation();
    expect(document.cookie).not.toContain('access_token=X');
  });

  it('survives malformed storage', () => {
    sessionStorage.setItem('impersonation', 'not-json{{{');
    expect(isImpersonating()).toBe(false);
    expect(getImpersonation()).toBeNull();
  });
});
