import { describe, it, expect } from 'vitest';
import { resolveTarget } from '../components/common/NotificationBell';

// Every bell link must land on a real route — a bad path hits the catch-all
// and dumps the user on home (the "eject" bug).
describe('resolveTarget', () => {
  it('panel booking bell with id highlights the row', () => {
    expect(resolveTarget('/admin/notifications', 'appointments:543')).toBe(
      '/admin/appointments?highlight=543',
    );
  });

  it('panel booking bell without id opens the list', () => {
    expect(resolveTarget('/admin/notifications', 'appointments')).toBe('/admin/appointments');
  });

  it('super section keeps its prefix', () => {
    expect(resolveTarget('/super/notifications', 'appointments:7')).toBe(
      '/super/appointments?highlight=7',
    );
  });

  it('panel review bell opens master reviews', () => {
    expect(resolveTarget('/admin/notifications', 'reviews')).toBe('/admin/profile#reviews');
  });

  it('activation bell opens the master profile', () => {
    expect(resolveTarget('/admin/notifications', 'profile')).toBe('/admin/profile');
    expect(resolveTarget('/cabinet/notifications', 'profile')).toBe('/cabinet/profile');
  });

  it('cabinet appointments bell opens the cabinet', () => {
    expect(resolveTarget('/cabinet/notifications', 'appointments:9')).toBe('/cabinet');
  });

  it('coupon bell preselects the master', () => {
    expect(resolveTarget('/cabinet/notifications', 'book:23')).toBe('/cabinet/book?master_id=23');
  });

  it('linkless bell opens the inbox page', () => {
    expect(resolveTarget('/admin/notifications', null)).toBe('/admin/notifications');
  });

  it('unknown links fall back to the inbox page', () => {
    expect(resolveTarget('/admin/notifications', 'zzz')).toBe('/admin/notifications');
  });
});
