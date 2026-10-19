import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { toast } from 'sonner';
import { authApi } from '../api/client';
import LoginModal from '../components/LoginModal';
import YandexCallbackPage from '../pages/public/YandexCallbackPage';
import { __resetYandexSuggestForTests } from '../components/common/yandexSuggestSdk';

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
    yandexVerifyToken: vi.fn(),
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
  suggest_redirect_uri: '',
};

/** Same start payload, but the suggest widget is configured (prod-like). */
const SUGGEST_START_DATA = {
  ...START_DATA,
  suggest_redirect_uri: 'https://beauty-specialist.ru/suggest-token.html',
};

interface SuggestInitArgs {
  oauthParams: Record<string, unknown>;
  origin: string;
  suggestParams: Record<string, unknown>;
}

/**
 * Minimal fake of the sdk-suggest global (window.YaAuthSuggest). When it is
 * already present the component skips script injection, which jsdom cannot
 * load. `handler` resolves with the widget's postMessage payload.
 */
function installSuggestSdk() {
  const handler = vi.fn().mockResolvedValue({});
  const calls: SuggestInitArgs[] = [];
  const sdkInit = vi
    .fn()
    .mockImplementation(
      async (
        oauthParams: Record<string, unknown>,
        origin: string,
        suggestParams: Record<string, unknown>,
      ) => {
        calls.push({ oauthParams, origin, suggestParams });
        return { handler };
      },
    );
  (window as unknown as { YaAuthSuggest: unknown }).YaAuthSuggest = { init: sdkInit };
  return { sdkInit, handler, calls };
}

beforeEach(() => {
  sessionStorage.clear();
});

afterEach(() => {
  vi.clearAllMocks();
  delete (window as unknown as { YaAuthSuggest?: unknown }).YaAuthSuggest;
  __resetYandexSuggestForTests();
});

function renderLogin() {
  return render(
    <MemoryRouter>
      <LoginModal isOpen onClose={vi.fn()} />
    </MemoryRouter>,
  );
}

describe('Yandex official widget («мгновенная авторизация», sdk-suggest)', () => {
  it('mounts the official widget on the login form as the main button', async () => {
    const { sdkInit } = installSuggestSdk();
    vi.mocked(mocked.yandexStart).mockResolvedValue({ data: SUGGEST_START_DATA } as never);
    renderLogin();

    await waitFor(() => expect(sdkInit).toHaveBeenCalledTimes(1));
    expect(sdkInit).toHaveBeenCalledWith(
      {
        client_id: 'c1',
        response_type: 'token',
        redirect_uri: 'https://beauty-specialist.ru/suggest-token.html',
      },
      window.location.origin,
      expect.objectContaining({
        view: 'button',
        parentId: 'yandex-suggest-login',
        buttonView: 'main',
        buttonSize: 'm',
        buttonBorderRadius: 10,
      }),
    );
    // The slot the SDK renders into is present on the login tab.
    expect(screen.getByTestId('yandex-suggest-container')).toBeInTheDocument();
    // And the plain redirect button is NOT rendered next to it.
    expect(screen.queryByRole('button', { name: /Войти через Яндекс/ })).not.toBeInTheDocument();
  });

  it('delivers the widget token to the backend and completes the login', async () => {
    const { handler } = installSuggestSdk();
    handler.mockResolvedValue({ access_token: 'ya-tok', expires_in: 3600, cid: 'c1' });
    vi.mocked(mocked.yandexStart).mockResolvedValue({ data: SUGGEST_START_DATA } as never);
    vi.mocked(mocked.yandexVerifyToken).mockResolvedValue({
      data: { access_token: 't', token_type: 'bearer', is_new_user: true },
    } as never);

    renderLogin();

    await waitFor(() => expect(mocked.yandexVerifyToken).toHaveBeenCalledWith('ya-tok', true));
    await waitFor(() =>
      expect(toast.success).toHaveBeenCalledWith('Добро пожаловать! Аккаунт создан.'),
    );
  });

  it('keeps the widget button when the user just closes the Yandex UI', async () => {
    const { handler } = installSuggestSdk();
    handler.mockResolvedValue({}); // empty payload = closed/declined
    vi.mocked(mocked.yandexStart).mockResolvedValue({ data: SUGGEST_START_DATA } as never);
    renderLogin();

    await waitFor(() => expect(handler).toHaveBeenCalledTimes(1));
    // No backend call, no fallback swap — the button stays for a retry.
    expect(mocked.yandexVerifyToken).not.toHaveBeenCalled();
    expect(screen.getByTestId('yandex-suggest-container')).toBeInTheDocument();
  });

  it('mounts the icon variant on the register form only after consent', async () => {
    const { sdkInit } = installSuggestSdk();
    vi.mocked(mocked.yandexStart).mockResolvedValue({ data: SUGGEST_START_DATA } as never);
    // The register tab is opened by the unified entry itself (no footer link
    // since 1.79.3) — render it directly.
    render(
      <MemoryRouter>
        <LoginModal isOpen onClose={vi.fn()} initialMode="register" />
      </MemoryRouter>,
    );

    // 152-FZ gate: nothing social until the box is ticked.
    expect(screen.queryByTestId('yandex-suggest-container')).not.toBeInTheDocument();

    fireEvent.click(screen.getByText(/Соглашаюсь с/));
    await waitFor(() =>
      expect(sdkInit).toHaveBeenLastCalledWith(
        expect.anything(),
        window.location.origin,
        expect.objectContaining({
          buttonView: 'icon',
          parentId: 'yandex-suggest-register',
          buttonSize: 's',
        }),
      ),
    );
  });

  it('falls back to the plain redirect button when the widget cannot init', async () => {
    const sdkInit = vi.fn().mockRejectedValue({ code: 'no_cookie' });
    (window as unknown as { YaAuthSuggest: unknown }).YaAuthSuggest = { init: sdkInit };
    vi.mocked(mocked.yandexStart).mockResolvedValue({ data: SUGGEST_START_DATA } as never);
    renderLogin();

    const btn = await screen.findByRole('button', { name: /Войти через Яндекс/ });
    expect(btn).toBeInTheDocument();

    // The fallback is the same tested redirect flow: click → state + redirect.
    fireEvent.click(btn);
    await waitFor(() => expect(sessionStorage.getItem('yandex_state')).toBe('s1'));
    expect(sessionStorage.getItem('yandex_consent')).toBe('1');
  });

  it('falls back when the widget is not configured server-side', async () => {
    installSuggestSdk();
    vi.mocked(mocked.yandexStart).mockResolvedValue({ data: START_DATA } as never);
    renderLogin();

    expect(await screen.findByRole('button', { name: /Войти через Яндекс/ })).toBeInTheDocument();
  });

  it('falls back (with an error toast) when the backend refuses the token', async () => {
    const { handler } = installSuggestSdk();
    handler.mockResolvedValue({ access_token: 'stale-tok' });
    vi.mocked(mocked.yandexStart).mockResolvedValue({ data: SUGGEST_START_DATA } as never);
    vi.mocked(mocked.yandexVerifyToken).mockRejectedValue({
      response: { data: { detail: 'Не удалось подтвердить вход через Яндекс. Попробуйте снова.' } },
    });
    renderLogin();

    await waitFor(() =>
      expect(toast.error).toHaveBeenCalledWith(
        'Не удалось подтвердить вход через Яндекс. Попробуйте снова.',
      ),
    );
    expect(await screen.findByRole('button', { name: /Войти через Яндекс/ })).toBeInTheDocument();
  });
});

describe('Yandex OAuth redirect (fallback path)', () => {
  it('fetches a signed state, stashes it and hands the browser to Yandex', async () => {
    installSuggestSdk();
    // Empty suggest_redirect_uri → the widget is off, the fallback shows.
    vi.mocked(mocked.yandexStart).mockResolvedValue({ data: START_DATA } as never);
    renderLogin();

    const btn = await screen.findByRole('button', { name: /Войти через Яндекс/ });
    fireEvent.click(btn);

    await waitFor(() => expect(sessionStorage.getItem('yandex_state')).toBe('s1'));
    expect(sessionStorage.getItem('yandex_consent')).toBe('1');
  });

  it('reports a 503 as "not configured"', async () => {
    vi.mocked(mocked.yandexStart).mockRejectedValue({ response: { status: 503 } });
    renderLogin();

    const btn = await screen.findByRole('button', { name: /Войти через Яндекс/ });
    fireEvent.click(btn);

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
