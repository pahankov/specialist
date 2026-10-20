import { beforeEach, describe, expect, it } from 'vitest';
import {
  allowMasterDraftEntry,
  clearMasterDraftEntry,
  isMasterDraftEntryAllowed,
} from '../utils/masterDraftEntry';

describe('master draft entry ticket', () => {
  beforeEach(() => {
    clearMasterDraftEntry();
  });

  it('is closed by default, so a direct draft URL goes to the client cabinet', () => {
    expect(isMasterDraftEntryAllowed()).toBe(false);
  });

  it('opens only after «Стать мастером» marks the in-memory ticket', () => {
    allowMasterDraftEntry();
    expect(isMasterDraftEntryAllowed()).toBe(true);
  });

  it('is cleared when the session ends', async () => {
    allowMasterDraftEntry();
    const { clearAuthCookies } = await import('../utils/cookies');
    clearAuthCookies();
    expect(isMasterDraftEntryAllowed()).toBe(false);
  });
});
