import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { adminApi } from '../api/client';
import NotificationBell from '../components/common/NotificationBell';

vi.mock('../api/client', () => ({
  adminApi: {
    getNotificationsInbox: vi.fn(),
    readNotification: vi.fn(),
    readAllNotifications: vi.fn(),
  },
  cabinetApi: {
    notificationsInbox: vi.fn(),
    readNotification: vi.fn(),
    readAllNotifications: vi.fn(),
  },
}));

const mocked = vi.mocked(adminApi);

const ITEMS = [
  {
    id: 7,
    text: 'Новая запись: Петр — Стрижка',
    link: 'appointments',
    sender_name: 'Клиент',
    is_read: false,
    created_at: '2026-10-12T10:00:00',
  },
  {
    id: 8,
    text: 'Напоминание',
    link: null,
    sender_name: null,
    is_read: false,
    created_at: null,
  },
];

function renderBell(unread = 1) {
  render(
    <MemoryRouter
      initialEntries={['/admin/schedule']}
      future={{ v7_startTransition: true, v7_relativeSplatPath: true }}
    >
      <NotificationBell unread={unread} bellLink="/admin/notifications" scope="panel" />
    </MemoryRouter>,
  );
}

describe('NotificationBell', () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it('opens a dropdown list on click and fetches unread only', async () => {
    vi.mocked(mocked.getNotificationsInbox).mockResolvedValue({
      data: { items: ITEMS, total: 2, unread: 2 },
    } as never);
    renderBell(2);
    fireEvent.click(screen.getByRole('button', { name: /Уведомления/ }));
    expect(await screen.findByText('Новая запись: Петр — Стрижка')).toBeInTheDocument();
    expect(screen.getByText('Напоминание')).toBeInTheDocument();
    expect(mocked.getNotificationsInbox).toHaveBeenCalledWith({
      page: 1,
      page_size: 10,
      unread_only: true,
    });
  });

  it('marks a linked row read on click (navigates to the sibling page)', async () => {
    vi.mocked(mocked.getNotificationsInbox).mockResolvedValue({
      data: { items: ITEMS, total: 2, unread: 2 },
    } as never);
    vi.mocked(mocked.readNotification).mockResolvedValue({ data: {} } as never);
    renderBell(2);
    fireEvent.click(screen.getByRole('button', { name: /Уведомления/ }));
    fireEvent.click(await screen.findByText('Новая запись: Петр — Стрижка'));
    await waitFor(() => {
      expect(mocked.readNotification).toHaveBeenCalledWith(7);
    });
    // Linked rows navigate away, closing the whole tray (history page keeps it).
    await waitFor(() => {
      expect(screen.queryByText('Новая запись: Петр — Стрижка')).not.toBeInTheDocument();
    });
  });

  it('drops a linkless row from the tray on click (stays open)', async () => {
    vi.mocked(mocked.getNotificationsInbox).mockResolvedValue({
      data: { items: ITEMS, total: 2, unread: 2 },
    } as never);
    vi.mocked(mocked.readNotification).mockResolvedValue({ data: {} } as never);
    renderBell(2);
    fireEvent.click(screen.getByRole('button', { name: /Уведомления/ }));
    fireEvent.click(await screen.findByText('Напоминание'));
    await waitFor(() => {
      expect(mocked.readNotification).toHaveBeenCalledWith(8);
    });
    // Read rows leave the tray at once; the sibling stays visible.
    await waitFor(() => {
      expect(screen.queryByText('Напоминание')).not.toBeInTheDocument();
    });
    expect(screen.getByText('Новая запись: Петр — Стрижка')).toBeInTheDocument();
  });

  it('shows an empty state and a retry on failure', async () => {
    vi.mocked(mocked.getNotificationsInbox).mockRejectedValueOnce(new Error('down'));
    renderBell(0);
    fireEvent.click(screen.getByRole('button', { name: /Уведомления/ }));
    expect(await screen.findByText(/Нет связи с сервером/)).toBeInTheDocument();
    vi.mocked(mocked.getNotificationsInbox).mockResolvedValue({
      data: { items: [], total: 0, unread: 0 },
    } as never);
    fireEvent.click(screen.getByText('Повторить'));
    expect(await screen.findByText('🔕 Пока тихо')).toBeInTheDocument();
  });
});
