import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { toast } from 'sonner';
import { authApi } from '../api/client';
import LoginModal from '../components/LoginModal';
import { PASSWORD_PLACEHOLDER } from '../constants';

vi.mock('../api/client', () => ({
  authApi: {
    loginUnified: vi.fn(),
    registerUnified: vi.fn(),
    phoneStatus: vi.fn(),
    forgotPassword: vi.fn(),
    resetPassword: vi.fn(),
    maxStart: vi.fn(),
    maxVerify: vi.fn(),
    vkStart: vi.fn(),
    vkVerify: vi.fn(),
    yandexStart: vi.fn(),
    yandexVerify: vi.fn(),
  },
}));

vi.mock('../components/common/VkIdWidget', () => ({
  __esModule: true,
  default: () => <div data-testid="vkid-widget-container" />,
}));

vi.mock('../api/dadata', () => ({
  dadataApi: {
    searchCities: vi.fn().mockResolvedValue([]),
    searchAddresses: vi.fn().mockResolvedValue([]),
  },
}));

vi.mock('sonner', () => ({
  toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
  Toaster: () => null,
}));

const mocked = vi.mocked(authApi);
const MASKED = '+7 (999) 123-45-67';

function openLogin() {
  return render(
    <MemoryRouter>
      <LoginModal isOpen onClose={vi.fn()} />
    </MemoryRouter>,
  );
}

function fillIdentifier(value: string) {
  fireEvent.change(screen.getByPlaceholderText('email@example.com или +7 (999) 123-45-67'), {
    target: { value },
  });
}

function submit() {
  fireEvent.click(screen.getByRole('button', { name: 'Войти' }));
}

describe('Unified entry — the phone decides (phone/status)', () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it('routes a NEW phone to the prefilled registration form', async () => {
    openLogin();
    vi.mocked(mocked.phoneStatus).mockResolvedValue({
      data: { state: 'new', phone: MASKED },
    } as never);

    fillIdentifier('+79991234567');
    submit();

    await waitFor(() => expect(mocked.phoneStatus).toHaveBeenCalledWith(MASKED));
    // Registration replaces the password form, phone already filled in.
    expect(await screen.findByText('Зарегистрироваться')).toBeInTheDocument();
    expect(screen.getByDisplayValue(MASKED)).toBeInTheDocument();
    expect(mocked.loginUnified).not.toHaveBeenCalled();
  });

  it('asks for the password when the phone belongs to a password account', async () => {
    openLogin();
    vi.mocked(mocked.phoneStatus).mockResolvedValue({
      data: { state: 'password', phone: MASKED },
    } as never);

    fillIdentifier('+79991234567');
    submit();

    await waitFor(() => expect(toast.info).toHaveBeenCalledWith('Аккаунт найден — введите пароль'));
    expect(mocked.loginUnified).not.toHaveBeenCalled();
  });

  it('hints at the social buttons for a social-only phone', async () => {
    openLogin();
    vi.mocked(mocked.phoneStatus).mockResolvedValue({
      data: { state: 'social', phone: MASKED },
    } as never);

    fillIdentifier('+79991234567');
    submit();

    expect(await screen.findByText(/войдите кнопкой выше/)).toBeInTheDocument();
    expect(mocked.loginUnified).not.toHaveBeenCalled();
  });

  it('does not ask phone/status for an email with an empty password', async () => {
    openLogin();

    fillIdentifier('user@example.com');
    submit();

    await waitFor(() => expect(toast.error).toHaveBeenCalledWith('Введите пароль'));
    expect(mocked.phoneStatus).not.toHaveBeenCalled();
  });

  it('keeps the plain login path when a password is typed', async () => {
    openLogin();
    vi.mocked(mocked.loginUnified).mockResolvedValue({ data: {} } as never);

    fillIdentifier('+79991234567');
    fireEvent.change(screen.getByPlaceholderText('Введите пароль'), {
      target: { value: 'Secret123!' },
    });
    submit();

    await waitFor(() => expect(mocked.loginUnified).toHaveBeenCalledWith(MASKED, 'Secret123!'));
    expect(mocked.phoneStatus).not.toHaveBeenCalled();
  });
});

describe('Unified entry — unknown identifier creates a cabinet after consent', () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it('shows the 152-FZ consent step and retries with consent=true', async () => {
    openLogin();
    vi.mocked(mocked.loginUnified).mockRejectedValueOnce({
      response: {
        status: 401,
        data: { detail: { code: 'registration_required', message: 'Аккаунта пока нет' } },
      },
    } as never);
    vi.mocked(mocked.loginUnified).mockResolvedValueOnce({ data: {} } as never);

    fillIdentifier('new@example.com');
    fireEvent.change(screen.getByPlaceholderText('Введите пароль'), {
      target: { value: 'Secret123!' },
    });
    submit();

    const create = await screen.findByRole('button', { name: 'Создать аккаунт и войти' });
    expect(create).toBeDisabled();
    // The legal documents must be real, visible links (owner review 1.81.1).
    expect(screen.getByRole('link', { name: 'Офертой' })).toHaveAttribute('href', '/offer');
    expect(screen.getByRole('link', { name: 'Политикой обработки ПДн' })).toHaveAttribute(
      'href',
      '/privacy',
    );
    fireEvent.click(screen.getByRole('checkbox'));
    expect(create).not.toBeDisabled();
    fireEvent.click(create);

    await waitFor(() =>
      expect(mocked.loginUnified).toHaveBeenLastCalledWith('new@example.com', 'Secret123!', true),
    );
  });

  it('keeps a wrong password as a plain error without the consent step', async () => {
    openLogin();
    vi.mocked(mocked.loginUnified).mockRejectedValueOnce({
      response: { status: 401, data: { detail: 'Неверный email/телефон или пароль' } },
    } as never);

    fillIdentifier('user@example.com');
    fireEvent.change(screen.getByPlaceholderText('Введите пароль'), {
      target: { value: 'Secret123!' },
    });
    submit();

    await waitFor(() =>
      expect(toast.error).toHaveBeenCalledWith('Неверный email/телефон или пароль'),
    );
    expect(
      screen.queryByRole('button', { name: 'Создать аккаунт и войти' }),
    ).not.toBeInTheDocument();
  });
});

describe('Forgot password — code by email', () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it('sends the code and resets the password with it (auto-login)', async () => {
    openLogin();
    fireEvent.click(screen.getByText('Забыли пароль?'));

    fireEvent.change(screen.getByPlaceholderText('email@example.com'), {
      target: { value: 'user@example.com' },
    });
    vi.mocked(mocked.forgotPassword).mockResolvedValue({
      data: { message: 'Код отправлен' },
    } as never);
    fireEvent.click(screen.getByRole('button', { name: 'Отправить код' }));

    await waitFor(() => expect(mocked.forgotPassword).toHaveBeenCalledWith('user@example.com'));

    // Step 2: the code from the letter + the new password.
    fireEvent.change(await screen.findByPlaceholderText('6 цифр'), {
      target: { value: '123456' },
    });
    fireEvent.change(screen.getByPlaceholderText(PASSWORD_PLACEHOLDER), {
      target: { value: 'NewPass123!' },
    });
    vi.mocked(mocked.resetPassword).mockResolvedValue({
      data: { access_token: 't', token_type: 'bearer' },
    } as never);
    fireEvent.click(screen.getByRole('button', { name: 'Сбросить пароль и войти' }));

    await waitFor(() =>
      expect(mocked.resetPassword).toHaveBeenCalledWith(
        'user@example.com',
        '123456',
        'NewPass123!',
      ),
    );
    expect(toast.success).toHaveBeenCalledWith('Пароль обновлён — вы вошли в аккаунт');
  });

  it('validates the code locally before any request', async () => {
    openLogin();
    fireEvent.click(screen.getByText('Забыли пароль?'));

    fireEvent.change(screen.getByPlaceholderText('email@example.com'), {
      target: { value: 'user@example.com' },
    });
    vi.mocked(mocked.forgotPassword).mockResolvedValue({
      data: { message: 'ok' },
    } as never);
    fireEvent.click(screen.getByRole('button', { name: 'Отправить код' }));

    fireEvent.change(await screen.findByPlaceholderText('6 цифр'), {
      target: { value: '12' },
    });
    fireEvent.change(screen.getByPlaceholderText(PASSWORD_PLACEHOLDER), {
      target: { value: 'NewPass123!' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Сбросить пароль и войти' }));

    await waitFor(() => expect(toast.error).toHaveBeenCalledWith('Код — 6 цифр из письма'));
    expect(mocked.resetPassword).not.toHaveBeenCalled();
  });
});
