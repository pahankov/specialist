import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { toast } from 'sonner';
import { cabinetApi } from '../api/client';
import CabinetPage from '../pages/cabinet/CabinetPage';

vi.mock('../api/client', () => ({
  authApi: { logout: vi.fn() },
  cabinetApi: {
    me: vi.fn(),
    myAppointments: vi.fn(),
    cancelAppointment: vi.fn(),
    updateMe: vi.fn(),
    myReviews: vi.fn().mockResolvedValue({ data: [] }),
    createReview: vi.fn(),
    stats: vi.fn().mockResolvedValue({
      data: {
        total_spent: 0,
        completed_visits: 0,
        upcoming_count: 0,
        cancelled_count: 0,
        favorite_master: null,
        favorite_service: null,
      },
    }),
  },
}));

vi.mock('sonner', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
  Toaster: () => null,
}));

const mocked = vi.mocked(cabinetApi);

const APPTS = [
  {
    id: 1,
    master_id: 1,
    service_id: 1,
    client_id: 1,
    appointment_date: new Date(Date.now() + 86400000).toISOString(),
    status: 'confirmed',
    service_name: 'Стрижка',
    master_name: 'Мастер',
  },
  {
    id: 2,
    master_id: 1,
    service_id: 1,
    client_id: 1,
    appointment_date: new Date(Date.now() - 86400000).toISOString(),
    status: 'completed',
    service_name: 'Стрижка',
    master_name: 'Мастер',
  },
];

function renderCabinet() {
  render(
    <MemoryRouter>
      <CabinetPage />
    </MemoryRouter>,
  );
}

describe('CabinetPage', () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it('splits upcoming and history', async () => {
    vi.mocked(mocked.me).mockResolvedValue({
      data: { id: 1, name: 'Клиент', phone: '+7', is_verified: false },
    } as never);
    vi.mocked(mocked.myAppointments).mockResolvedValue({ data: APPTS } as never);
    renderCabinet();
    // One united list: upcoming first, chips on top, no section titles.
    expect(await screen.findByText('Все')).toBeInTheDocument();
    expect(screen.getByText('📅 Предстоящие')).toBeInTheDocument();
    expect(screen.queryByText('История')).not.toBeInTheDocument();
    expect(screen.getByText('Мои записи')).toBeInTheDocument();
  });

  it('cancels an upcoming appointment after confirm', async () => {
    vi.mocked(mocked.me).mockResolvedValue({
      data: { id: 1, name: 'Клиент', phone: '+7', is_verified: false },
    } as never);
    vi.mocked(mocked.myAppointments).mockResolvedValue({ data: APPTS } as never);
    vi.mocked(mocked.cancelAppointment).mockResolvedValue({ data: {} } as never);
    renderCabinet();
    await screen.findByText('Все');
    fireEvent.click(screen.getByText('Отменить'));
    fireEvent.click(screen.getByText('Отменить запись'));
    await vi.waitFor(() => {
      expect(vi.mocked(mocked.cancelAppointment)).toHaveBeenCalledWith(1);
    });
    expect(vi.mocked(toast.success)).toHaveBeenCalledWith('Запись отменена');
  });

  it('shows empty state without appointments', async () => {
    vi.mocked(mocked.me).mockResolvedValue({
      data: { id: 1, name: 'Клиент', phone: '+7', is_verified: false },
    } as never);
    vi.mocked(mocked.myAppointments).mockResolvedValue({ data: [] } as never);
    renderCabinet();
    expect(await screen.findByText('Нет записей')).toBeInTheDocument();
  });

  it('rates a completed visit from history', async () => {
    vi.mocked(mocked.me).mockResolvedValue({
      data: { id: 1, name: 'Клиент', phone: '+7', is_verified: false },
    } as never);
    vi.mocked(mocked.myAppointments).mockResolvedValue({ data: APPTS } as never);
    vi.mocked(mocked.createReview).mockResolvedValue({ data: { rating: 5 } } as never);
    renderCabinet();
    await screen.findByText('Все');
    fireEvent.click(screen.getByText('⭐ Оценить'));
    // Stars start empty: send is disabled until picked.
    expect(screen.getByText('Отправить отзыв')).toBeDisabled();
    fireEvent.click(screen.getByLabelText('Оценка 5'));
    fireEvent.click(screen.getByText('Отправить отзыв'));
    await vi.waitFor(() => {
      expect(vi.mocked(mocked.createReview)).toHaveBeenCalledWith(
        expect.objectContaining({ appointment_id: 2, rating: 5 }),
      );
    });
  });
});
