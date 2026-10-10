import { describe, it, expect } from 'vitest';
import { sectionPrefix, isSuperPath, ADMIN_PREFIX, SUPER_PREFIX } from '../utils/section';

describe('section routing', () => {
  it('routes /super paths to the superadmin section', () => {
    expect(isSuperPath('/super')).toBe(true);
    expect(isSuperPath('/super/masters')).toBe(true);
    expect(sectionPrefix('/super/clients')).toBe(SUPER_PREFIX);
  });

  it('keeps everything else in the master section', () => {
    expect(isSuperPath('/admin/masters')).toBe(false);
    expect(isSuperPath('/')).toBe(false);
    expect(sectionPrefix('/admin/clients')).toBe(ADMIN_PREFIX);
    expect(sectionPrefix('/')).toBe(ADMIN_PREFIX);
  });
});
