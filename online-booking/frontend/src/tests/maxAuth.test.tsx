import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
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
    maxStatus: vi.fn(),
  },
}));

vi.mock('sonner', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
  Toaster: () => null,
}));

const mocked = vi.mocked(authApi);

function openMaxTab() {
  render(
    <MemoryRouter>
      <LoginModal isOpen onClose={vi.fn()} />
    </MemoryRouter>,
  );
  fireEvent.click(screen.getByText('Войти через MAX'));
}

describe('MAX chat-bot login', () => {
  beforeEach(() => {
    vi.mocked(mocked.maxStart).mockResolvedValue({
      data: {
        code: '482910',
        expires_in: 300,
        bot_username: 'test_bot',
        bot_url: 'https://max.ru/test_bot',
      },
    } as never);
    vi.mocked(mocked.maxStatus).mockResolvedValue({
      data: { status: 'pending', token_type: 'bearer' },
    } as never);
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.clearAllMocks();
  });

  async function startFlow() {
    openMaxTab();
    fireEvent.change(screen.getByPlaceholderText('+7 (999) 123-45-67'), {
      target: { value: '+79991234567' },
    });
    fireEvent.click(screen.getByText('Получить код'));
    await screen.findByText('482910');
  }

  it('shows the code and bot link after start', async () => {
    await startFlow();
    expect(screen.getByText(/Открыть бота/)).toHaveAttribute('href', 'https://max.ru/test_bot');
    // PhoneInput emits the masked value; backend normalizes it
    expect(vi.mocked(mocked.maxStart)).toHaveBeenCalledWith('+7 (999) 123-45-67');
  });

  it('auto-logins when the bot confirms the code', async () => {
    await startFlow();
    vi.mocked(mocked.maxStatus).mockResolvedValue({
      data: {
        status: 'verified',
        access_token: 'tok',
        token_type: 'bearer',
        is_new_user: true,
      },
    } as never);
    // polling interval is 3s real time
    await new Promise((r) => setTimeout(r, 3400));
    expect(vi.mocked(mocked.maxStatus)).toHaveBeenCalledWith('+7 (999) 123-45-67');
    expect(vi.mocked(toast.success)).toHaveBeenCalledWith('Вход через MAX выполнен!');
  }, 15000);
});
