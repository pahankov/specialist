import { describe, expect, it } from 'vitest';
import { safePostLoginTarget } from '../utils/redirect';

describe('safePostLoginTarget', () => {
  it('drops the inactive-master shell for clients', () => {
    expect(safePostLoginTarget('/admin/become-master', 'CLIENT')).toBeNull();
    expect(safePostLoginTarget('/admin/become-master/', 'CLIENT')).toBeNull();
    expect(safePostLoginTarget('/admin/become-master?tab=services', 'CLIENT')).toBeNull();
  });

  it('keeps the draft shell for an active master', () => {
    expect(safePostLoginTarget('/admin/become-master', 'MASTER')).toBe('/admin/become-master');
  });

  it('keeps ordinary deep links and empty targets', () => {
    expect(safePostLoginTarget('/cabinet/book?master_id=7', 'CLIENT')).toBe(
      '/cabinet/book?master_id=7',
    );
    expect(safePostLoginTarget(null, 'CLIENT')).toBeNull();
    expect(safePostLoginTarget('/admin/appointments', 'CLIENT')).toBe('/admin/appointments');
  });
});
