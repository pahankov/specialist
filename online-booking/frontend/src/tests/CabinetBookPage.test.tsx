/** Cabinet booking wizard: city masters -> filters -> schedule -> slot. */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';

const {
  me,
  getBookSchedule,
  bookAppointment,
  getAllMasters,
  getAllServices,
  getBundles,
  myCoupons,
} = vi.hoisted(() => ({
  me: vi.fn(),
  getBookSchedule: vi.fn(),
  bookAppointment: vi.fn(),
  getAllMasters: vi.fn(),
  getAllServices: vi.fn(),
  getBundles: vi.fn(),
  myCoupons: vi.fn(),
}));

vi.mock('../api/client', () => ({
  cabinetApi: { me, getBookSchedule, bookAppointment, bundles: getBundles, myCoupons },
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

const SERVICES: Record<
  number,
  { id: number; master_id: number; name: string; duration_minutes: number; price: number }[]
> = {
  1: [{ id: 10, master_id: 1, name: 'Стрижка', duration_minutes: 60, price: 1500 }],
  2: [{ id: 20, master_id: 2, name: 'Маникюр', duration_minutes: 90, price: 1200 }],
};

const BUNDLES: Record<number, object[]> = {
  1: [
    {
      id: 100,
      master_id: 1,
      name: 'Сет',
      service_ids: [10],
      services: [{ id: 10, name: 'Стрижка', duration_minutes: 60, price: 1500 }],
      duration_total: 60,
      price_total: 1500,
      price: null,
      effective_price: 1500,
      is_active: true,
    },
  ],
  2: [],
};

function renderPage(entry = '/cabinet/book') {
  render(
    <MemoryRouter initialEntries={[entry]}>
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
  getBundles.mockImplementation((masterId: number) =>
    Promise.resolve({ data: BUNDLES[masterId] || [] }),
  );
  myCoupons.mockResolvedValue({ data: [] });
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
      expect(screen.getAllByText(/Елена/).length).toBeGreaterThan(0);
      expect(screen.getByText(/Мария/)).toBeInTheDocument();
    });

    fireEvent.change(screen.getByDisplayValue('Все услуги'), {
      target: { value: 'Маникюр' },
    });
    expect(screen.queryAllByText(/Елена/)).toHaveLength(0);
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
      expect(screen.getAllByText(/Елена/).length).toBeGreaterThan(0);
    });
    fireEvent.click(screen.getByText(/Елена/, { selector: 'strong' }));
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

    fireEvent.click(screen.getByText('Записаться', { selector: '.modal-actions .btn-primary' }));
    await waitFor(() => {
      expect(bookAppointment).toHaveBeenCalledWith(
        expect.objectContaining({ master_id: 1, service_id: 10 }),
      );
    });
    expect(await screen.findByText('cabinet home')).toBeInTheDocument();
  });

  it('books a complex from the modal select (complexes first)', async () => {
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
    bookAppointment.mockResolvedValue({ data: { id: 101 } });
    renderPage();
    await waitFor(() => {
      expect(screen.getAllByText(/Елена/).length).toBeGreaterThan(0);
    });
    // No standalone complexes list: complexes live in the booking modal.
    expect(screen.queryByText('🎁 Комплексы')).not.toBeInTheDocument();

    fireEvent.click(screen.getByText(/Елена/, { selector: 'strong' }));
    expect(await screen.findByText(/активное расписание/)).toBeInTheDocument();
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

    // Complexes optgroup comes first in the service select.
    fireEvent.change(screen.getByLabelText('Выбор услуги или комплекса'), {
      target: { value: 'bundle:100' },
    });
    expect(await screen.findByText('🎁 Сет')).toBeInTheDocument();

    fireEvent.click(screen.getByText('Записаться', { selector: '.modal-actions .btn-primary' }));
    await waitFor(() => {
      expect(bookAppointment).toHaveBeenCalledWith(
        expect.objectContaining({ master_id: 1, bundle_id: 100 }),
      );
    });
    expect(await screen.findByText('cabinet home')).toBeInTheDocument();
  });

  it('toasts "confirmed" at once for auto-confirm masters', async () => {
    const { toast } = await import('sonner');
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
    bookAppointment.mockResolvedValue({ data: { id: 103, status: 'confirmed' } });
    renderPage();
    await waitFor(() => {
      expect(screen.getAllByText(/Елена/).length).toBeGreaterThan(0);
    });
    fireEvent.click(screen.getByText(/Елена/, { selector: 'strong' }));
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

    fireEvent.click(screen.getByText('Записаться', { selector: '.modal-actions .btn-primary' }));
    await waitFor(() => {
      expect(bookAppointment).toHaveBeenCalled();
    });
    expect(toast.success).toHaveBeenCalledWith(expect.stringMatching(/подтверждена/));
    expect(toast.success).not.toHaveBeenCalledWith(expect.stringMatching(/подтвердит/));
  });

  it('deep link preselects the master and scrolls to the loaded schedule', async () => {
    const scrollIntoView = vi.fn();
    window.HTMLElement.prototype.scrollIntoView = scrollIntoView;
    const future = new Date();
    future.setDate(future.getDate() + 5);
    const pad = (n: number) => String(n).padStart(2, '0');
    const dateStr = `${future.getFullYear()}-${pad(future.getMonth() + 1)}-${pad(future.getDate())}`;
    let resolveSchedule!: (v: unknown) => void;
    getBookSchedule.mockReturnValue(
      new Promise((resolve) => {
        resolveSchedule = resolve;
      }),
    );
    renderPage('/cabinet/book?master_id=1');
    await waitFor(() => {
      expect(getBookSchedule).toHaveBeenCalledWith(1, expect.any(String));
    });
    // Schedule still loading: no scroll to the (skeleton) card yet.
    await new Promise((r) => setTimeout(r, 50));
    const earlyCalls = scrollIntoView.mock.calls.length;
    resolveSchedule({
      data: {
        master_id: 1,
        window: { start_hour: 9, end_hour: 12 },
        working_hours: [{ date: dateStr, start: '09:00', end: '12:00' }],
        busy: [],
      },
    });
    expect(await screen.findByText(/активное расписание/)).toBeInTheDocument();
    await waitFor(
      () => {
        expect(scrollIntoView.mock.calls.length).toBeGreaterThan(earlyCalls);
      },
      { timeout: 3000 },
    );
  });
});
