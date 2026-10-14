import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { adminApi } from '../api/client';
import AutoConfirmSwitch from '../components/common/AutoConfirmSwitch';

vi.mock('../api/client', () => ({
  adminApi: {
    getProfile: vi.fn(),
    updateProfile: vi.fn(),
  },
}));

vi.mock('sonner', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

const mocked = vi.mocked(adminApi);

describe('AutoConfirmSwitch', () => {
  it('loads state and flips on click', async () => {
    mocked.getProfile.mockResolvedValue({ data: { auto_confirm: false } } as never);
    mocked.updateProfile.mockResolvedValue({ data: {} } as never);

    render(<AutoConfirmSwitch />);
    const btn = await screen.findByRole('button', { name: /автоподтверждение/i });
    expect(btn.textContent).toMatch(/выкл/i);

    fireEvent.click(btn);
    await waitFor(() => {
      expect(mocked.updateProfile).toHaveBeenCalledWith({ auto_confirm: true });
    });
  });
});
