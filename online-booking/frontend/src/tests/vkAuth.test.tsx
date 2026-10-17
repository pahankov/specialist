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

function openVkTab() {
  renderLogin();
  fireEvent.click(screen.getByRole('button', { name: /Войти через VK/ }));
}

function acceptConsent() {
  fireEvent.click(screen.getByRole('checkbox'));
}

describe('VK ID widget (OAuthList: VK + OK + Mail)', () => {
  it('offers VK from the login screen as a branded button', () => {
    renderLogin();
    expect(screen.getByRole('button', { name: /Войти через VK/ })).toBeInTheDocument();
    // Second social icon on the login form (after MAX).
    expect(document.querySelectorAll('.social-auth-icon svg').length).toBeGreaterThanOrEqual(2);
  });

  it('offers VK registration from the register screen too', () => {
    renderLogin();
    fireEvent.click(screen.getByText('Зарегистрироваться'));
    fireEvent.click(screen.getByRole('button', { name: /Регистрация через VK/ }));
    // The widget panel shows the mandatory 152-FZ consent before rendering.
    expect(screen.getByRole('checkbox')).toBeInTheDocument();
    expect(screen.getByText('← Назад ко входу')).toBeInTheDocument();
  });

  it('does not render the widget until consent is checked', () => {
    openVkTab();
    // No container before consent (widget gated behind the checkbox).
    expect(screen.queryByTestId('vkid-widget-container')).toBeNull();
    expect(mocked.vkStart).not.toHaveBeenCalled();

    acceptConsent();
    expect(screen.getByTestId('vkid-widget-container')).toBeInTheDocument();
  });

  it('initializes the SDK and verifies the session on LOGIN_SUCCESS', async () => {
    openVkTab();
    vi.mocked(mocked.vkStart).mockResolvedValue({
      data: {
        authorize_url: 'https://id.vk.ru/authorize?client_id=54828785&state=s1',
        state: 's1',
        client_id: '54828785',
        redirect_uri: 'https://beauty-specialist.ru/auth/vk/callback',
      },
    } as never);
    vi.mocked(mocked.vkVerify).mockResolvedValue({
      data: { access_token: 't', token_type: 'bearer', is_new_user: true },
    } as never);

    acceptConsent();

    // The widget fetches a signed state + inits the SDK + renders the block.
    await waitFor(() => expect(mocked.vkStart).toHaveBeenCalledWith('test-code-challenge'));
    await waitFor(() => expect(sdk.rendered).toBe(true));
    expect(sdk.configInit).toMatchObject({
      app: 54828785,
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
    await waitFor(() => expect(toast.success).toHaveBeenCalledWith('Вход через VK выполнен!'));
  });

  it('reports a 503 as "not configured" and does not verify', async () => {
    openVkTab();
    vi.mocked(mocked.vkStart).mockRejectedValue({ response: { status: 503 } });

    acceptConsent();

    await waitFor(() => expect(toast.error).toHaveBeenCalledWith('Вход через VK не настроен'));
    expect(mocked.vkVerify).not.toHaveBeenCalled();
  });

  it('surfaces a backend verify error detail', async () => {
    openVkTab();
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

    acceptConsent();
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
    expect(screen.getByText('Вы отклонили вход через VK')).toBeInTheDocument();
    expect(mocked.vkVerify).not.toHaveBeenCalled();
  });

  it('requires the stashed verifier (session expired)', () => {
    // No verifier in sessionStorage — callback should refuse before calling the API.
    renderCallback('?code=c1&device_id=d1&state=st');
    expect(screen.getByText('Сессия входа истекла. Попробуйте снова.')).toBeInTheDocument();
    expect(mocked.vkVerify).not.toHaveBeenCalled();
  });
});
