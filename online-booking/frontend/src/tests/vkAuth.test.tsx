import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { toast } from 'sonner';
import { authApi } from '../api/client';
import LoginModal from '../components/LoginModal';
import VkCallbackPage from '../pages/public/VkCallbackPage';

vi.mock('../api/client', () => ({
  authApi: {
    loginUnified: vi.fn(),
    registerUnified: vi.fn(),
    maxStart: vi.fn(),
    maxVerify: vi.fn(),
    vkStart: vi.fn(),
    vkVerify: vi.fn(),
  },
}));

// PKCE: deterministic verifier/challenge so the test doesn't depend on
// crypto.subtle availability in jsdom.
vi.mock('../utils/pkce', () => ({
  generateCodeVerifier: vi.fn(() => 'test-code-verifier-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'),
  generateCodeChallenge: vi.fn(async () => 'test-code-challenge'),
}));

// VK ID low-code SDK: mock OAuthList so we can simulate LOGIN_SUCCESS and
// assert Config.init + render without a real iframe / network.
const sdk = vi.hoisted(() => ({
  loginSuccess: null as ((p: { code: string; device_id: string }) => void) | null,
  configInit: null as Record<string, unknown> | null,
  rendered: false,
  reset() {
    this.loginSuccess = null;
    this.configInit = null;
    this.rendered = false;
  },
}));

vi.mock('@vkid/sdk', () => {
  class MockOAuthList {
    on(event: string, cb: (p: { code: string; device_id: string }) => void) {
      if (event === 'oauthlist: success login') sdk.loginSuccess = cb;
      return this;
    }
    render(params: { container: HTMLElement }) {
      sdk.rendered = true;
      params.container.setAttribute('data-mock-rendered', '1');
      return this;
    }
    close() {}
  }
  return {
    Config: { init: (cfg: Record<string, unknown>) => { sdk.configInit = cfg; } },
    ConfigResponseMode: { Callback: 'callback' },
    OAuthList: MockOAuthList,
    OAuthName: { VK: 'vkid', OK: 'ok_ru', MAIL: 'mail_ru' },
    OAuthListInternalEvents: { LOGIN_SUCCESS: 'oauthlist: success login' },
  };
});

vi.mock('sonner', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
  Toaster: () => null,
}));

const mocked = vi.mocked(authApi);

beforeEach(() => {
  sdk.reset();
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

describe('VK ID widget (inline OAuthList: VK + OK + Mail)', () => {
  it('renders the widget container immediately on the login screen', () => {
    renderLogin();
    // No separate screen and no consent gate — the container mounts inline.
    expect(screen.getByTestId('vkid-widget-container')).toBeInTheDocument();
  });

  it('initializes the SDK and verifies the session on LOGIN_SUCCESS', async () => {
    renderLogin();
    // VK ID uses a HEX client_id — the widget must pass it to the SDK verbatim
    // (Number(hex) === NaN would fail the SDK's isNumber validator).
    const HEX_CLIENT_ID = '3772ca16b2de4376bc632dd4fcd6341a';
    vi.mocked(mocked.vkStart).mockResolvedValue({
      data: {
        authorize_url: `https://id.vk.ru/authorize?client_id=${HEX_CLIENT_ID}&state=s1`,
        state: 's1',
        client_id: HEX_CLIENT_ID,
        redirect_uri: 'https://beauty-specialist.ru/auth/vk/callback',
      },
    } as never);
    vi.mocked(mocked.vkVerify).mockResolvedValue({
      data: { access_token: 't', token_type: 'bearer', is_new_user: true },
    } as never);

    // The widget fetches a signed state + inits the SDK + renders the block.
    await waitFor(() => expect(mocked.vkStart).toHaveBeenCalledWith('test-code-challenge'));
    await waitFor(() => expect(sdk.rendered).toBe(true));
    expect(sdk.configInit).toMatchObject({
      app: HEX_CLIENT_ID, // verbatim string, never Number()
      redirectUrl: 'https://beauty-specialist.ru/auth/vk/callback',
      state: 's1',
      codeVerifier: 'test-code-verifier-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
    });

    // Simulate the user approving inside VK's popup.
    sdk.loginSuccess?.({ code: 'c1', device_id: 'd1' });

    // Server-side exchange reuses the existing /vk/verify with our state+verifier.
    await waitFor(() =>
      expect(mocked.vkVerify).toHaveBeenCalledWith(
        'c1',
        'd1',
        's1',
        'test-code-verifier-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
        true,
      ),
    );
    await waitFor(() =>
      expect(toast.success).toHaveBeenCalledWith('Добро пожаловать! Аккаунт создан.'),
    );
  });

  it('reports a 503 as "not configured" inline and does not verify', async () => {
    renderLogin();
    vi.mocked(mocked.vkStart).mockRejectedValue({ response: { status: 503 } });

    await waitFor(() =>
      expect(screen.getByText('Вход через VK не настроен')).toBeInTheDocument(),
    );
    expect(mocked.vkVerify).not.toHaveBeenCalled();
  });

  it('surfaces a backend verify error detail', async () => {
    renderLogin();
    vi.mocked(mocked.vkStart).mockResolvedValue({
      data: {
        authorize_url: 'https://id.vk.ru/authorize?client_id=54828785&state=s1',
        state: 's1',
        client_id: '54828785',
        redirect_uri: 'https://beauty-specialist.ru/auth/vk/callback',
      },
    } as never);
    vi.mocked(mocked.vkVerify).mockRejectedValue({
      response: { data: { detail: 'Неверная или просроченная сессия входа. Попробуйте снова.' } },
    });

    await waitFor(() => expect(sdk.rendered).toBe(true));
    sdk.loginSuccess?.({ code: 'c1', device_id: 'd1' });

    await waitFor(() =>
      expect(
        screen.getByText('Неверная или просроченная сессия входа. Попробуйте снова.'),
      ).toBeInTheDocument(),
    );
    expect(toast.success).not.toHaveBeenCalled();
  });
});

describe('VK callback exchange', () => {
  function renderCallback(search: string) {
    return render(
      <MemoryRouter initialEntries={[`/auth/vk/callback${search}`]}>
        <Routes>
          <Route path="/auth/vk/callback" element={<VkCallbackPage />} />
          <Route path="/" element={<div>HOME</div>} />
          <Route path="/cabinet" element={<div>CABINET</div>} />
        </Routes>
      </MemoryRouter>,
    );
  }

  it('exchanges the code and lands a client in the cabinet', async () => {
    sessionStorage.setItem('vk_code_verifier', 'ver');
    sessionStorage.setItem('vk_state', 'st');
    sessionStorage.setItem('vk_consent', '1');
    vi.mocked(mocked.vkVerify).mockResolvedValue({
      data: { access_token: 't', token_type: 'bearer', is_new_user: true },
    } as never);

    renderCallback('?code=c1&device_id=d1&state=st');

    await waitFor(() =>
      expect(mocked.vkVerify).toHaveBeenCalledWith('c1', 'd1', 'st', 'ver', true),
    );
    await waitFor(() => expect(screen.getByText('CABINET')).toBeInTheDocument());
    // One-shot keys are consumed.
    expect(sessionStorage.getItem('vk_code_verifier')).toBeNull();
  });

  it('shows an error when the user declines on VK', async () => {
    renderCallback('?error=access_denied');
    await waitFor(() =>
      expect(screen.getByText('Вы отклонили вход через VK')).toBeInTheDocument(),
    );
    expect(mocked.vkVerify).not.toHaveBeenCalled();
  });

  it('requires the stashed verifier (session expired)', () => {
    // No verifier in sessionStorage — callback should refuse before calling the API.
    renderCallback('?code=c1&device_id=d1&state=st');
    expect(screen.getByText('Сессия входа истекла. Попробуйте снова.')).toBeInTheDocument();
    expect(mocked.vkVerify).not.toHaveBeenCalled();
  });
});
