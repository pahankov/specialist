import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { mastersApi, servicesApi, appointmentsApi, cabinetApi } from '../api/client';
import BookingPage from '../pages/public/BookingPage';

vi.mock('../api/client', () => ({
  mastersApi: { getAll: vi.fn() },
  servicesApi: { getAll: vi.fn() },
  appointmentsApi: { publicBooking: vi.fn(), create: vi.fn() },
  cabinetApi: { me: vi.fn() },
}));

vi.mock('sonner', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
  Toaster: () => null,
}));

const MASTERS = [
  { id: 1, user_id: 1, name: 'Anna', city_name: 'Alpha', avg_rating: 4.5 },
  { id: 2, user_id: 2, name: 'Boris', city_name: 'Beta', avg_rating: null },
];

const SERVICES = [
  { id: 1, master_id: 1, name: 'Маникюр', duration_minutes: 60, price: 2000, category: 'Ногти' },
  {
    id: 2,
    master_id: 1,
    name: 'Шугаринг ног',
    duration_minutes: 30,
    price: 1500,
    category: 'Шугаринг',
  },
  { id: 3, master_id: 1, name: 'Без категории', duration_minutes: 30, price: 1000, category: null },
];

function renderBooking() {
  render(
    <MemoryRouter initialEntries={['/booking']}>
      <BookingPage />
    </MemoryRouter>,
  );
}

describe('BookingPage wizard', () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it('lists masters with city and rating, groups services by category', async () => {
    vi.mocked(cabinetApi.me).mockRejectedValue({ response: { status: 401 } });
    vi.mocked(mastersApi.getAll).mockResolvedValue({ data: MASTERS } as never);
    vi.mocked(servicesApi.getAll).mockResolvedValue({ data: SERVICES } as never);
    renderBooking();

    expect(await screen.findByText('Anna')).toBeInTheDocument();
    expect(screen.getByText(/Alpha/)).toBeInTheDocument();
    expect(screen.getByText(/4,5|4.5/)).toBeInTheDocument();

    fireEvent.click(screen.getByText('Anna'));
    expect(await screen.findByText('Ногти')).toBeInTheDocument();
    expect(screen.getByText('Шугаринг')).toBeInTheDocument();
    expect(screen.getByText('Прочее')).toBeInTheDocument();
    expect(vi.mocked(servicesApi.getAll)).toHaveBeenCalledWith(1);
  });

  it('shows empty state when the city has no masters', async () => {
    vi.mocked(cabinetApi.me).mockRejectedValue({ response: { status: 401 } });
    vi.mocked(mastersApi.getAll).mockResolvedValue({ data: [] } as never);
    renderBooking();
    expect(await screen.findByText(/мастеров нет|Мастеров пока нет/)).toBeInTheDocument();
  });

  it('books via public endpoint and shows cabinet link when logged in', async () => {
    document.cookie = 'access_token=test-token; path=/';
    vi.mocked(cabinetApi.me).mockResolvedValue({
      data: { id: 1, name: 'Клиент', phone: '+7 (999) 123-45-67', is_verified: false },
    } as never);
    vi.mocked(mastersApi.getAll).mockResolvedValue({ data: MASTERS } as never);
    vi.mocked(servicesApi.getAll).mockResolvedValue({ data: SERVICES } as never);
    vi.mocked(appointmentsApi.publicBooking).mockResolvedValue({ data: {} } as never);
    renderBooking();

    await screen.findByText('Anna');
    fireEvent.click(screen.getByText('Anna'));
    await screen.findByText('Ногти');
    fireEvent.click(screen.getByText('Маникюр'));
    const dateInput = document.querySelector('input[type="datetime-local"]') as HTMLInputElement;
    fireEvent.change(dateInput, { target: { value: '2026-12-01T10:00' } });
    fireEvent.click(screen.getByText('Записаться', { selector: 'button[type="submit"]' }));

    await vi.waitFor(() => {
      expect(vi.mocked(appointmentsApi.publicBooking)).toHaveBeenCalled();
    });
    const payload = vi.mocked(appointmentsApi.publicBooking).mock.calls[0][0] as {
      master_id: number;
      service_id: number;
      client_phone: string;
    };
    expect(payload.master_id).toBe(1);
    expect(payload.service_id).toBe(1);
    expect(payload.client_phone).toContain('999');
    expect(vi.mocked(appointmentsApi.create)).not.toHaveBeenCalled();
    expect(await screen.findByText('Мои записи')).toBeInTheDocument();
  });
});
