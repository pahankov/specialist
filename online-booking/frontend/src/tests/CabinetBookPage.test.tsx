/** Cabinet booking wizard: city masters -> filters -> schedule -> slot. */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';

const { me, getBookSchedule, bookAppointment, getAllMasters, getAllServices } = vi.hoisted(
  () => ({
    me: vi.fn(),
    getBookSchedule: vi.fn(),
    bookAppointment: vi.fn(),
    getAllMasters: vi.fn(),
    getAllServices: vi.fn(),
  }),
);

vi.mock('../api/client', () => ({
  cabinetApi: { me, getBookSchedule, bookAppointment },
  mastersApi: { getAll: getAllMasters },
  servicesApi: { getAll: getAllServices },
}));

vi.mock('sonner', () => ({
  toast: { success: vi.fn(), error: vi.fn(), warning: vi.fn() },
  Toaster: () => null,
}));

import CabinetBookPage from '../pages/cabinet/CabinetBookPage';

const MASTERS = [
  { id: 1, user_id: 11, name: 'Елена', avg_rating: 4.9, city_name: 'Уфа', is_active: true },
  { id: 2, user_id: 12, name: 'Мария', avg_rating: null, city_name: 'Уфа', is_active: true },
];

const SERVICES: Record<number, { id: number; master_id: number; name: string; duration_minutes: number; price: number }[]> = {
  1: [{ id: 10, master_id: 1, name: 'Стрижка', duration_minutes: 60, price: 1500 }],
  2: [{ id: 20, master_id: 2, name: 'Маникюр', duration_minutes: 90, price: 1200 }],
};

function renderPage() {
  render(
    <MemoryRouter initialEntries={['/cabinet/book']}>
      <Routes>
        <Route path="/cabinet/book" element={<CabinetBookPage />} />
        <Route path="/cabinet" element={<div>cabinet home</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  me.mockResolvedValue({
    data: { id: 7, name: 'Клиент', city_id: 5, city_name: 'Уфа' },
  });
  getAllMasters.mockResolvedValue({ data: MASTERS });
  getAllServices.mockImplementation((masterId: number) =>
    Promise.resolve({ data: SERVICES[masterId] || [] }),
  );
});

describe('CabinetBookPage', () => {
  it('loads masters of the client city and filters by service', async () => {
    renderPage();
    // The list re-renders (skeleton) while city/services load — re-query
    // inside waitFor so assertions never hit a detached node.
    await waitFor(() => {
      expect(getAllMasters).toHaveBeenCalledWith(5);
    });
    await waitFor(() => {
      expect(screen.getByText(/Елена/)).toBeInTheDocument();
      expect(screen.getByText(/Мария/)).toBeInTheDocument();
    });

    fireEvent.change(screen.getByDisplayValue('Все услуги'), {
      target: { value: 'Маникюр' },
    });
    expect(screen.queryByText(/Елена/)).not.toBeInTheDocument();
    expect(screen.getByText(/Мария/)).toBeInTheDocument();
  });

  it('opens the master schedule and books a free granule', async () => {
    // A working day safely in the future (navigates the calendar if needed).
    const future = new Date();
    future.setDate(future.getDate() + 5);
    const pad = (n: number) => String(n).padStart(2, '0');
    const dateStr = `${future.getFullYear()}-${pad(future.getMonth() + 1)}-${pad(future.getDate())}`;
    const monthStr = dateStr.slice(0, 7);
    getBookSchedule.mockResolvedValue({
      data: {
        master_id: 1,
        window: { start_hour: 9, end_hour: 12 },
        working_hours: [{ date: dateStr, start: '09:00', end: '12:00' }],
        busy: [],
      },
    });
    bookAppointment.mockResolvedValue({ data: { id: 100 } });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText(/Елена/)).toBeInTheDocument();
    });
    fireEvent.click(screen.getByText(/Елена/));
    expect(await screen.findByText(/активное расписание/)).toBeInTheDocument();

    // If the future day spilled into the next month, flip the calendar once.
    if (monthStr !== new Date().toISOString().slice(0, 7)) {
      fireEvent.click(screen.getByText('→'));
    }
    fireEvent.click(
      await screen.findByText(String(future.getDate()), {
        selector: '.calendar-day-number',
      }),
    );
    const bookButtons = await screen.findAllByText('+ Записаться');
    fireEvent.click(bookButtons[0]);
    expect(await screen.findByText(/Подтвердите запись/)).toBeInTheDocument();

    fireEvent.click(
      screen.getByText('Записаться', { selector: '.modal-actions .btn-primary' }),
    );
    await waitFor(() => {
      expect(bookAppointment).toHaveBeenCalledWith(
        expect.objectContaining({ master_id: 1, service_id: 10 }),
      );
    });
    expect(await screen.findByText('cabinet home')).toBeInTheDocument();
  });
});
