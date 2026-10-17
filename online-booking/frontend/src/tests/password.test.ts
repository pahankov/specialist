import { describe, expect, it } from 'vitest';
import { passwordError } from '../utils/password';

describe('passwordError (mirror of backend policy)', () => {
  it('accepts a compliant password', () => {
    expect(passwordError('Qwerty1!x')).toBeNull();
    expect(passwordError('Пароль22222$')).toBeNull();
  });

  it('rejects short passwords', () => {
    expect(passwordError('Ab1!xyz')).toMatch(/8 символов/);
  });

  it('requires uppercase, lowercase, digit and special', () => {
    expect(passwordError('abcdefgh1!')).toMatch(/заглавную/);
    expect(passwordError('ABCDEFGH1!')).toMatch(/строчную/);
    expect(passwordError('Abcdefgh!')).toMatch(/цифру/);
    expect(passwordError('Abcdefg12')).toMatch(/спецсимвол/);
  });

  it('accepts the backend special-character set', () => {
    for (const special of [
      '!',
      '@',
      '#',
      '$',
      '%',
      '^',
      '&',
      '*',
      '(',
      ')',
      '_',
      '+',
      '-',
      '=',
      '[',
      ']',
      '{',
      '}',
      '|',
      ';',
      ':',
      ',',
      '.',
      '<',
      '>',
      '?',
    ]) {
      expect(passwordError(`Aa1xxx9${special}`)).toBeNull();
    }
  });
});
