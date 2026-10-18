import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { toast } from 'sonner';
import { authApi } from '../api/client';
import LoginModal from '../components/LoginModal';
import YandexCallbackPage from '../pages/public/YandexCallbackPage';

vi.mock('../api/client', () => ({
  authApi: {
    loginUnified: vi.fn(),
    registerUnified: vi.fn(),
    maxStart: vi.fn(),
    maxVerify: vi.fn(),
    vkStart: vi.fn(),
    vkVerify: vi.fn(),
    yandexStart: vi.fn(),
    yandexVerify: vi.fn(),
  },
}));

// VK widget mounts inline with the login form — stub it so the Yandex tests
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

const START_DATA = {
  authorize_url: 'https://oauth.yandex.ru/authorize?response_type=code&client_id=c1&state=s1',
  state: 's1',
  client_id: 'c1',
  redirect_uri: 'https://beauty-specialist.ru/auth/yandex/callback',
};

beforeEach(() => {
  sessionStorage.clear();
});
afterEach(() => {
  vi.clearAllMocks();
});

function renderLogin() {
  return render(
    <MemoryRouter>
      <LoginModal isOpen onClose={vi.fn()} />
    </MemoryRouter>,
  );
}

describe('Yandex OAuth (redirect flow)', () => {
  it('offers Yandex from the login screen as a branded button', () => {
    renderLogin();
    expect(screen.getByRole('button', { name: /Войти через Яндекс/ })).toBeInTheDocument();
  });

  it('fetches a signed state, stashes it and hands the browser to Yandex', async () => {
    renderLogin();
    vi.mocked(mocked.yandexStart).mockResolvedValue({ data: START_DATA } as never);

    // Direct redirect button — no consent screen in between.
    fireEvent.click(screen.getByRole('button', { name: /Войти через Яндекс/ }));

    await waitFor(() => expect(mocked.yandexStart).toHaveBeenCalledTimes(1));
    // The signed state + implicit consent flag are staged for the callback.
    await waitFor(() => expect(sessionStorage.getItem('yandex_state')).toBe('s1'));
    expect(sessionStorage.getItem('yandex_consent')).toBe('1');
  });

  it('reports a 503 as "not configured"', async () => {
    renderLogin();
    vi.mocked(mocked.yandexStart).mockRejectedValue({ response: { status: 503 } });

    fireEvent.click(screen.getByRole('button', { name: /Войти через Яндекс/ }));

    await waitFor(() => expect(toast.error).toHaveBeenCalledWith('Вход через Яндекс не настроен'));
  });
});

describe('Yandex callback exchange', () => {
  function renderCallback(search: string) {
    return render(
      <MemoryRouter initialEntries={[`/auth/yandex/callback${search}`]}>
        <Routes>
          <Route path="/auth/yandex/callback" element={<YandexCallbackPage />} />
          <Route path="/" element={<div>HOME</div>} />
          <Route path="/cabinet" element={<div>CABINET</div>} />
        </Routes>
      </MemoryRouter>,
    );
  }

  it('exchanges the code and lands a client in the cabinet', async () => {
    sessionStorage.setItem('yandex_state', 'st');
    sessionStorage.setItem('yandex_consent', '1');
    vi.mocked(mocked.yandexVerify).mockResolvedValue({
      data: { access_token: 't', token_type: 'bearer', is_new_user: true },
    } as never);

    renderCallback('?code=c1&state=st');

    await waitFor(() => expect(mocked.yandexVerify).toHaveBeenCalledWith('c1', 'st', true));
    await waitFor(() => expect(screen.getByText('CABINET')).toBeInTheDocument());
    // One-shot keys are consumed.
    expect(sessionStorage.getItem('yandex_state')).toBeNull();
    expect(sessionStorage.getItem('yandex_consent')).toBeNull();
  });

  it('shows an error when the user declines on Yandex', () => {
    renderCallback('?error=access_denied');
    expect(screen.getByText('Вы отклонили вход через Яндекс')).toBeInTheDocument();
    expect(mocked.yandexVerify).not.toHaveBeenCalled();
  });

  it('rejects a state that does not match the stashed one', () => {
    sessionStorage.setItem('yandex_state', 'other');
    renderCallback('?code=c1&state=st');
    expect(screen.getByText('Неверная сессия входа. Попробуйте снова.')).toBeInTheDocument();
    expect(mocked.yandexVerify).not.toHaveBeenCalled();
  });

  it('requires code + state', () => {
    renderCallback('?state=st');
    expect(screen.getByText('Нет данных для подтверждения входа')).toBeInTheDocument();
    expect(mocked.yandexVerify).not.toHaveBeenCalled();
  });

  it('surfaces a backend verify error detail', async () => {
    sessionStorage.setItem('yandex_state', 'st');
    vi.mocked(mocked.yandexVerify).mockRejectedValue({
      response: {
        data: { detail: 'Неверная или просроченная сессия входа. Попробуйте снова.' },
      },
    });

    renderCallback('?code=c1&state=st');

    await waitFor(() =>
      expect(
        screen.getByText('Неверная или просроченная сессия входа. Попробуйте снова.'),
      ).toBeInTheDocument(),
    );
    expect(toast.success).not.toHaveBeenCalled();
  });
});
