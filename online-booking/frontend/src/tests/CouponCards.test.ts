import { describe, it, expect } from 'vitest';
import { isCouponArchived } from '../components/coupons/CouponCards';

const base = {
  id: 1,
  code: 'AAA-BBB',
  kind: 'percent',
  value: 10,
  max_uses: null,
  used_count: 0,
  audience: 'my_clients',
  user_ids: [],
  valid_until: null,
  is_active: true,
};

describe('isCouponArchived', () => {
  it('keeps live coupons out of the archive', () => {
    expect(isCouponArchived(base, Date.now())).toBe(false);
  });

  it('archives spent-out codes', () => {
    expect(isCouponArchived({ ...base, max_uses: 2, used_count: 2 }, Date.now())).toBe(true);
    expect(isCouponArchived({ ...base, max_uses: 2, used_count: 1 }, Date.now())).toBe(false);
  });

  it('archives switched-off and expired codes', () => {
    expect(isCouponArchived({ ...base, is_active: false }, Date.now())).toBe(true);
    expect(isCouponArchived({ ...base, valid_until: '2020-01-01T00:00:00' }, Date.now())).toBe(
      true,
    );
    expect(isCouponArchived({ ...base, valid_until: '2030-01-01T00:00:00' }, Date.now())).toBe(
      false,
    );
  });
});
