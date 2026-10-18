import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { toast } from 'sonner';
import { authApi } from '../api/client';
import LoginModal from '../components/LoginModal';
import { PASSWORD_PLACEHOLDER } from '../constants';

vi.mock('../api/client', () => ({
  authApi: {
    loginUnified: vi.fn(),
    registerUnified: vi.fn(),
    maxStart: vi.fn(),
    maxVerify: vi.fn(),
  },
}));

// Address suggestions: register only accepts an address picked from the list.
vi.mock('../api/dadata', () => ({
  dadataApi: {
    searchCities: vi.fn().mockResolvedValue([]),
    searchAddresses: vi
      .fn()
      .mockResolvedValue([{ value: 'Россия, г Москва, ул Тестовая, д 1', city: 'Москва' }]),
  },
}));

// VK widget mounts inline with the login form — stub it so the MAX tests
// don't fire a real /vk/start network call.
vi.mock('../components/common/VkIdWidget', () => ({
  __esModule: true,
  default: () => <div data-testid="vkid-widget-container" />,
}));

vi.mock('sonner', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
  Toaster: () => null,
}));

const mocked = vi.mocked(authApi);
const MASKED = '+7 (999) 123-45-67';

function openMaxTab() {
  const view = render(
    <MemoryRouter>
      <LoginModal isOpen onClose={vi.fn()} />
    </MemoryRouter>,
  );
  fireEvent.click(screen.getByRole('button', { name: /Войти через MAX/ }));
  return view;
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

  it('offers MAX from the login screen as a branded button', () => {
    render(
      <MemoryRouter>
        <LoginModal isOpen onClose={vi.fn()} />
      </MemoryRouter>,
    );
    expect(screen.getByRole('button', { name: /Войти через MAX/ })).toBeInTheDocument();
    // Modal portals into document.body — query globally.
    expect(document.querySelector('.social-auth-icon svg')).toBeTruthy(); // MAX icon
  });

  it('starts the MAX flow from the login button', () => {
    openMaxTab();
    // Same MAX flow — it both logs in and registers, no consent screen.
    expect(screen.getByText('Получить код в MAX')).toBeInTheDocument();
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
        bot_name: 'Электронная запись',
      },
    } as never);
    fireEvent.click(screen.getByText('Получить код в MAX'));
    expect(await screen.findByText(/бот попросит подтвердить номер/)).toBeInTheDocument();
    expect(screen.getByText(/Открыть бота «Электронная запись»/)).toHaveAttribute(
      'href',
      'https://max.ru/test_bot?start=1_abcd',
    );
    expect(vi.mocked(mocked.maxStart)).toHaveBeenCalledWith(MASKED);
  });

  it('falls back to the bot username when bot_name is missing', async () => {
    openMaxTab();
    fillPhone();
    vi.mocked(mocked.maxStart).mockResolvedValue({
      data: {
        delivered: false,
        deeplink: 'https://max.ru/test_bot?start=3_ijkl',
        expires_in: 300,
        bot_username: 'test_bot',
        bot_url: 'https://max.ru/test_bot',
      },
    } as never);
    fireEvent.click(screen.getByText('Получить код в MAX'));
    expect(await screen.findByText(/Открыть бота test_bot/)).toBeInTheDocument();
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
        bot_name: 'Электронная запись',
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
    await screen.findByText(/бот попросит подтвердить номер/);

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
    expect(vi.mocked(mocked.maxVerify)).toHaveBeenCalledWith(MASKED, '482910', true);
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
    await screen.findByText(/бот попросит подтвердить номер/);

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

  it('submits once consent is checked and every field is valid', async () => {
    openRegister();
    vi.mocked(mocked.registerUnified).mockResolvedValue({ data: {} } as never);

    fireEvent.change(screen.getByPlaceholderText('+7 (999) 123-45-67'), {
      target: { value: '+79991234567' },
    });
    fireEvent.change(screen.getByPlaceholderText(PASSWORD_PLACEHOLDER), {
      target: { value: 'Secret123!' },
    });
    fireEvent.click(screen.getByText(/Соглашаюсь с/));

    const btn = screen.getByText('Зарегистрироваться', { selector: '.btn-submit' });
    expect(btn).toBeEnabled();
    // jsdom doesn't submit forms on button click — submit the form directly.
    fireEvent.submit(btn.closest('form') as HTMLFormElement);
    expect(await screen.findByText('Зарегистрироваться')).toBeInTheDocument();
    expect(vi.mocked(mocked.registerUnified)).toHaveBeenCalledTimes(1);
  });

  it('keeps the submit button disabled until the form is valid', async () => {
    openRegister();
    fireEvent.click(screen.getByText(/Соглашаюсь с/));
    const btn = screen.getByText('Зарегистрироваться', { selector: '.btn-submit' });
    expect(btn).toBeDisabled();
    fireEvent.submit(btn.closest('form') as HTMLFormElement);
    expect(vi.mocked(mocked.registerUnified)).not.toHaveBeenCalled();
    expect(vi.mocked(toast.error)).toHaveBeenCalledWith(
      'Заполните все обязательные поля корректно',
    );
  });

  it('keeps the whole social block hidden until consent is ticked', () => {
    openRegister();
    // The gate stands in for VK/Yandex/MAX: no widget mount, no tiles.
    expect(screen.getByRole('button', { name: /Отметьте согласие/ })).toBeInTheDocument();
    expect(screen.queryByTestId('vkid-widget-container')).not.toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: 'Регистрация через Яндекс' }),
    ).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Регистрация через MAX' })).not.toBeInTheDocument();
  });

  it('reveals the VK widget and the Yandex/MAX tiles once consent is ticked', async () => {
    openRegister();
    fireEvent.click(screen.getByText(/Соглашаюсь с/));

    expect(screen.getByTestId('vkid-widget-container')).toBeInTheDocument();
    // Yandex mounts the official suggest widget; with no SDK/start mock in
    // this file it resolves to the redirect tile asynchronously.
    expect(
      await screen.findByRole('button', { name: 'Регистрация через Яндекс' }),
    ).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Регистрация через MAX' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Отметьте согласие/ })).not.toBeInTheDocument();
  });

  it('the gate hint only focuses the consent checkbox — it never ticks it', () => {
    openRegister();
    fireEvent.click(screen.getByRole('button', { name: /Отметьте согласие/ }));

    const box = screen.getByRole('checkbox') as HTMLInputElement;
    expect(box).toHaveFocus();
    expect(box).not.toBeChecked();
    expect(screen.queryByTestId('vkid-widget-container')).not.toBeInTheDocument();
  });
});
