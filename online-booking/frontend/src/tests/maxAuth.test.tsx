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
        deeplink: 'https://max.ru/test_bot?start=1_abcd',
        expires_in: 300,
        bot_username: 'test_bot',
        bot_url: 'https://max.ru/test_bot',
      },
    } as never);
    fireEvent.click(screen.getByText('Получить код в MAX'));
    expect(await screen.findByText(/бот сам встретит вас/)).toBeInTheDocument();
    expect(screen.getByText(/Открыть бота test_bot/)).toHaveAttribute(
      'href',
      'https://max.ru/test_bot?start=1_abcd',
    );
    expect(vi.mocked(mocked.maxStart)).toHaveBeenCalledWith(MASKED);
  });

  it('tells bound users the code is already in MAX', async () => {
    openMaxTab();
    fillPhone();
    vi.mocked(mocked.maxStart).mockResolvedValue({
      data: {
        delivered: true,
        deeplink: 'https://max.ru/test_bot?start=2_efgh',
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
      data: {
        delivered: false,
        deeplink: '',
        expires_in: 300,
        bot_username: 'b',
        bot_url: '',
      },
    } as never);
    fireEvent.click(screen.getByText('Получить код в MAX'));
    await screen.findByText(/бот сам встретит вас/);

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
      data: {
        delivered: false,
        deeplink: '',
        expires_in: 300,
        bot_username: 'b',
        bot_url: '',
      },
    } as never);
    fireEvent.click(screen.getByText('Получить код в MAX'));
    await screen.findByText(/бот сам встретит вас/);

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

describe('Login identifier validation (regression)', () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  function openLogin() {
    render(
      <MemoryRouter>
        <LoginModal isOpen onClose={vi.fn()} />
      </MemoryRouter>,
    );
  }

  function fillLogin(identifier: string) {
    fireEvent.change(screen.getByPlaceholderText(/email@example.com/), {
      target: { value: identifier },
    });
    fireEvent.change(screen.getByPlaceholderText('Введите пароль'), {
      target: { value: 'Secret123!' },
    });
  }

  function submitLogin() {
    fireEvent.click(screen.getByRole('button', { name: 'Войти' }));
  }

  it('blocks phone garbage locally without any request', async () => {
    openLogin();
    fillLogin('+7 (923) 521-12-321ghghghghghghgh');
    submitLogin();
    await vi.waitFor(() => {
      expect(vi.mocked(toast.error)).toHaveBeenCalled();
    });
    expect(vi.mocked(mocked.loginUnified)).not.toHaveBeenCalled();
  });

  it('blocks an incomplete phone locally', async () => {
    openLogin();
    fillLogin('+7 (923) 521-12-3');
    submitLogin();
    await vi.waitFor(() => {
      expect(vi.mocked(toast.error)).toHaveBeenCalled();
    });
    expect(vi.mocked(mocked.loginUnified)).not.toHaveBeenCalled();
  });

  it('blocks a malformed email locally', async () => {
    openLogin();
    fillLogin('not-an-email@');
    submitLogin();
    await vi.waitFor(() => {
      expect(vi.mocked(toast.error)).toHaveBeenCalled();
    });
    expect(vi.mocked(mocked.loginUnified)).not.toHaveBeenCalled();
  });

  it('sends a valid email through', async () => {
    openLogin();
    fillLogin('user@example.com');
    vi.mocked(mocked.loginUnified).mockResolvedValue({
      data: { access_token: 'tok', token_type: 'bearer' },
    } as never);
    submitLogin();
    await vi.waitFor(() => {
      expect(vi.mocked(mocked.loginUnified)).toHaveBeenCalledWith('user@example.com', 'Secret123!');
    });
  });

  it('normalizes raw digits to the masked phone before sending', async () => {
    openLogin();
    fillLogin('+79235211232');
    vi.mocked(mocked.loginUnified).mockResolvedValue({
      data: { access_token: 'tok', token_type: 'bearer' },
    } as never);
    submitLogin();
    await vi.waitFor(() => {
      expect(vi.mocked(mocked.loginUnified)).toHaveBeenCalledWith(
        '+7 (923) 521-12-32',
        'Secret123!',
      );
    });
  });

  it('accepts a 10-digit phone without country code', async () => {
    openLogin();
    fillLogin('9235211232');
    vi.mocked(mocked.loginUnified).mockResolvedValue({
      data: { access_token: 'tok', token_type: 'bearer' },
    } as never);
    submitLogin();
    await vi.waitFor(() => {
      expect(vi.mocked(mocked.loginUnified)).toHaveBeenCalledWith(
        '+7 (923) 521-12-32',
        'Secret123!',
      );
    });
  });

  it('masks live while the input starts with +/7/8', () => {
    openLogin();
    fireEvent.change(screen.getByPlaceholderText(/email@example.com/), {
      target: { value: '+7923' },
    });
    expect(screen.getByPlaceholderText(/email@example.com/)).toHaveValue('+7 (923');
  });

  it('leaves digit-led input unmasked until a letter proves email', () => {
    openLogin();
    const box = screen.getByPlaceholderText(/email@example.com/);
    fireEvent.change(box, { target: { value: '123' } });
    expect(box).toHaveValue('123');
    fireEvent.change(box, { target: { value: '123u' } });
    expect(box).toHaveValue('123u');
  });

  it('cleans mask artifacts when switching to email mode', () => {
    openLogin();
    const box = screen.getByPlaceholderText(/email@example.com/);
    fireEvent.change(box, { target: { value: '+7 (923' } });
    expect(box).toHaveValue('+7 (923');
    fireEvent.change(box, { target: { value: '+7 (923u' } });
    expect(box).toHaveValue('7923u');
  });
});

describe('Registration consent (152-FZ)', () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  function openRegister() {
    render(
      <MemoryRouter>
        <LoginModal isOpen onClose={vi.fn()} />
      </MemoryRouter>,
    );
    fireEvent.click(screen.getByText('Зарегистрироваться'));
  }

  it('blocks submit without consent', () => {
    openRegister();
    const btn = screen.getByText('Зарегистрироваться', { selector: '.btn-submit' });
    // jsdom doesn't submit forms on button click — submit the form directly.
    fireEvent.submit(btn.closest('form') as HTMLFormElement);
    expect(vi.mocked(mocked.registerUnified)).not.toHaveBeenCalled();
    expect(vi.mocked(toast.error)).toHaveBeenCalledWith(
      'Подтвердите согласие на обработку персональных данных',
    );
  });

  it('submits once consent is checked', async () => {
    openRegister();
    vi.mocked(mocked.registerUnified).mockResolvedValue({ data: {} } as never);
    fireEvent.click(screen.getByText(/Соглашаюсь на обработку/));
    const btn = screen.getByText('Зарегистрироваться', { selector: '.btn-submit' });
    fireEvent.submit(btn.closest('form') as HTMLFormElement);
    expect(await screen.findByText('Зарегистрироваться')).toBeInTheDocument();
    expect(vi.mocked(mocked.registerUnified)).toHaveBeenCalledTimes(1);
  });
});
