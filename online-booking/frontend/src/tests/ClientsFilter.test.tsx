/** Integration: picking a master in ClientsPage must filter the list. */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

const { getClients, getAllMasters } = vi.hoisted(() => ({
  getClients: vi.fn(),
  getAllMasters: vi.fn(),
}));

vi.mock('../api/client', () => ({
  adminApi: { getClients },
  superAdminApi: { getAllMasters },
}));

import ClientsPage from '../pages/admin/ClientsPage';

const MASTERS = [
  { id: 77, name: 'Сергей Петров', is_active: true },
  { id: 78, name: 'Мария Иванова', is_active: true },
];

beforeEach(() => {
  getClients.mockReset();
  getAllMasters.mockReset();
  getAllMasters.mockResolvedValue({ data: MASTERS });
  getClients.mockResolvedValue({ data: { items: [], total: 0 } });
});

describe('ClientsPage master filter', () => {
  it('sends master_id after picking a master (super section)', async () => {
    render(
      <MemoryRouter initialEntries={['/super/clients']}>
        <ClientsPage />
      </MemoryRouter>,
    );

    await waitFor(() => expect(getAllMasters).toHaveBeenCalled());

    const box = screen.getByLabelText('Мастер');
    fireEvent.focus(box);
    fireEvent.click(await screen.findByText('Сергей Петров'));

    await waitFor(() => {
      const calls = getClients.mock.calls as { master_id?: number }[][];
      const withMaster = calls.filter(([params]) => params && params.master_id === 77);
      expect(withMaster.length).toBeGreaterThan(0);
    });
  });

  it('hides the master picker in the master section', async () => {
    render(
      <MemoryRouter initialEntries={['/admin/clients']}>
        <ClientsPage />
      </MemoryRouter>,
    );

    await waitFor(() => expect(getClients).toHaveBeenCalled());
    expect(screen.queryByLabelText('Мастер')).toBeNull();
  });
});
