import { describe, it, expect } from 'vitest';
import { assetUrl } from '../api/http';

describe('assetUrl', () => {
  it('prefixes backend-relative paths with the API origin', () => {
    expect(assetUrl('/static/avatars/u_1.png')).toBe(
      'http://localhost:8000/static/avatars/u_1.png',
    );
  });

  it('passes absolute URLs through untouched', () => {
    expect(assetUrl('https://cdn.example.com/a.png')).toBe('https://cdn.example.com/a.png');
  });

  it('passes non-path values (emoji presets) through untouched', () => {
    expect(assetUrl('🐱')).toBe('🐱');
  });

  it('maps empty values to null', () => {
    expect(assetUrl(null)).toBeNull();
    expect(assetUrl(undefined)).toBeNull();
    expect(assetUrl('')).toBeNull();
  });
});
