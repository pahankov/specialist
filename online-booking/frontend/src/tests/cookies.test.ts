import { describe, it, expect, beforeEach } from 'vitest';
import { getUserRole, getCookie } from '../utils/cookies';

function jwtWith(payload: object): string {
  const b64 = (o: object) =>
    btoa(JSON.stringify(o)).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
  return `h.${b64(payload)}.s`;
}

describe('getUserRole', () => {
  beforeEach(() => {
    document.cookie = 'access_token=; path=/; max-age=0';
  });

  it('returns null without a token', () => {
    expect(getCookie('access_token')).toBeNull();
    expect(getUserRole()).toBeNull();
  });

  it('returns CLIENT for client tokens (MAX/OTP login landing)', () => {
    document.cookie = `access_token=${jwtWith({ sub: '7', role: 'CLIENT' })}; path=/`;
    expect(getUserRole()).toBe('CLIENT');
  });

  it('returns MASTER for master tokens', () => {
    document.cookie = `access_token=${jwtWith({ sub: '1', role: 'MASTER' })}; path=/`;
    expect(getUserRole()).toBe('MASTER');
  });
});
