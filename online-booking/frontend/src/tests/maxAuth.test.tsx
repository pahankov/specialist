import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { toast } from 'sonner';
import { authApi } from '../api/client';
import LoginModal from '../components/LoginModal';

vi.mock('../api/client', () => ({
  authApi: {
    loginUnified: vi.fn(),
    registerUnified: vi.fn(),
    maxStart: vi.fn(),
    maxVerify: vi.fn(),
  },
}));

vi.mock('sonner', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
  Toaster: () => null,
}));

const mocked = vi.mocked(authApi);
const MASKED = '+7 (999) 123-45-67';

function openMaxTab() {
  render(
    <MemoryRouter>
      <LoginModal isOpen onClose={vi.fn()} />
    </MemoryRouter>,
  );
  fireEvent.click(screen.getByText('Войти через MAX'));
}

function fillPhone() {
  fireEvent.change(screen.getByPlaceholderText('+7 (999) 123-45-67'), {
    target: { value: '+79991234567' },
  });
}

describe('MAX chat-bot login (SMS-style)', () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it('requests a code and shows the bot step', async () => {
    openMaxTab();
    fillPhone();
    vi.mocked(mocked.maxStart).mockResolvedValue({
      data: {
        delivered: false,
        expires_in: 300,
        bot_username: 'test_bot',
        bot_url: 'https://max.ru/test_bot',
      },
    } as never);
    fireEvent.click(screen.getByText('Получить код в MAX'));
    expect(await screen.findByText(/поделитесь номером/)).toBeInTheDocument();
    expect(vi.mocked(mocked.maxStart)).toHaveBeenCalledWith(MASKED);
  });

  it('tells bound users the code is already in MAX', async () => {
    openMaxTab();
    fillPhone();
    vi.mocked(mocked.maxStart).mockResolvedValue({
      data: {
        delivered: true,
        expires_in: 300,
        bot_username: 'test_bot',
        bot_url: 'https://max.ru/test_bot',
      },
    } as never);
    fireEvent.click(screen.getByText('Получить код в MAX'));
    expect(await screen.findByText(/Код уже отправлен в MAX/)).toBeInTheDocument();
  });

  it('verifies the dialog code and logs in', async () => {
    openMaxTab();
    fillPhone();
    vi.mocked(mocked.maxStart).mockResolvedValue({
      data: { delivered: false, expires_in: 300, bot_username: 'b', bot_url: '' },
    } as never);
    fireEvent.click(screen.getByText('Получить код в MAX'));
    await screen.findByText(/поделитесь номером/);

    vi.mocked(mocked.maxVerify).mockResolvedValue({
      data: { access_token: 'tok', token_type: 'bearer', is_new_user: true },
    } as never);
    fireEvent.change(screen.getByPlaceholderText('––––––'), {
      target: { value: '482910' },
    });
    fireEvent.click(screen.getByText('Войти'));
    await vi.waitFor(() => {
      expect(vi.mocked(toast.success)).toHaveBeenCalledWith('Добро пожаловать! Аккаунт создан.');
    });
    expect(vi.mocked(mocked.maxVerify)).toHaveBeenCalledWith(MASKED, '482910');
  });

  it('shows the error on wrong code', async () => {
    openMaxTab();
    fillPhone();
    vi.mocked(mocked.maxStart).mockResolvedValue({
      data: { delivered: false, expires_in: 300, bot_username: 'b', bot_url: '' },
    } as never);
    fireEvent.click(screen.getByText('Получить код в MAX'));
    await screen.findByText(/поделитесь номером/);

    vi.mocked(mocked.maxVerify).mockRejectedValue({
      response: { data: { detail: 'Неверный код' } },
    });
    fireEvent.change(screen.getByPlaceholderText('––––––'), {
      target: { value: '000000' },
    });
    fireEvent.click(screen.getByText('Войти'));
    await vi.waitFor(() => {
      expect(vi.mocked(toast.error)).toHaveBeenCalledWith('Неверный код');
    });
  });
});
