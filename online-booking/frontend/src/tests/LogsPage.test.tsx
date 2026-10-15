import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

vi.mock('../api/client', () => ({
  adminApi: {
    getAuditLogsAll: vi.fn().mockResolvedValue({ data: { logs: [], total: 0 } }),
    getAuditLogs: vi.fn().mockResolvedValue({ data: { logs: [], total: 0 } }),
  },
}));

vi.mock('../utils/cookies', () => ({
  getCookie: () => 'token',
  decodeJwtPayload: () => ({ is_admin: true }),
}));

import LogsPage from '../pages/admin/LogsPage';

describe('LogsPage', () => {
  it('renders after loading without hook errors', async () => {
    render(
      <MemoryRouter>
        <LogsPage />
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(screen.getByText('📋 Журнал действий')).toBeInTheDocument();
    });
  });
});
