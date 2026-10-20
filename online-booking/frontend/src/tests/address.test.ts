import { describe, expect, it } from 'vitest';
import { hasHouseNumber } from '../utils/address';

describe('hasHouseNumber', () => {
  it('accepts a house number in the trailing address part', () => {
    expect(hasHouseNumber('Москва, ул. Ленина, 5')).toBe(true);
    expect(hasHouseNumber('Москва, ул. Ленина 5А')).toBe(true);
    expect(hasHouseNumber('Москва, ул. Ленина, 5/1')).toBe(true);
    expect(hasHouseNumber('Москва, ул. Ленина, д. 5')).toBe(true);
    expect(hasHouseNumber('Москва, ул. Ленина, 5, кв. 3')).toBe(true);
  });

  it('rejects a street without a house', () => {
    expect(hasHouseNumber('')).toBe(false);
    expect(hasHouseNumber('Москва, ул. Ленина')).toBe(false);
    expect(hasHouseNumber('Москва, ул. 1-я Тверская-Ямская')).toBe(false);
    expect(hasHouseNumber('Москва, ул. Ленина, кв. 3')).toBe(false);
  });
});
