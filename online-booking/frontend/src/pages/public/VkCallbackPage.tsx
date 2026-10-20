import { useEffect, useRef, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { toast } from 'sonner';
import { authApi } from '../../api/client';
import { getCookie, decodeJwtPayload } from '../../utils/cookies';
import { takeReturnUrl, safePostLoginTarget } from '../../utils/redirect';
import { takeSocialLinkReturn } from '../../utils/socialLink';
import { ADMIN_PREFIX, SUPER_PREFIX } from '../../utils/section';
import VkIcon from '../../components/common/icons/VkIcon';
import ConsentScreen from '../../components/common/ConsentScreen';
import './VkCallbackPage.css';

/** sessionStorage keys stashed by LoginModal before the VK redirect. */
const VERIFIER_KEY = 'vk_code_verifier';
const STATE_KEY = 'vk_state';

function takeKey(key: string): string | null {
  try {
    const v = sessionStorage.getItem(key);
    sessionStorage.removeItem(key);
    return v;
  } catch {
    return null;
  }
}

/**
 * OAuth landing page: VK redirects here with ?code&device_id&state after the
 * user approves. We exchange the code server-side (the backend holds the
 * service token) using the PKCE verifier stashed before the redirect, then
 * land the user by role.
 */
function VkCallbackPage() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [error, setError] = useState<string | null>(null);
  /** New account without consent → the consent overlay completes the flow. */
  const [challenge, setChallenge] = useState<string | null>(null);
  // React 18 StrictMode double-invokes effects; guard so we exchange once.
  const started = useRef(false);

  /** Cookies are set by the backend; land by role (dual-role default to the
      client cabinet, admins/master to their sections). */
  const finishLanding = () => {
    const payload = decodeJwtPayload(getCookie('access_token') ?? '');
    if (payload?.is_admin === true) {
      navigate(`${SUPER_PREFIX}/dashboard`, { replace: true });
      return;
    }
    const from = safePostLoginTarget(takeReturnUrl(), payload?.role);
    if (from) {
      navigate(from, { replace: true });
      return;
    }
    if (payload?.role === 'MASTER' && payload?.prefer_master === true) {
      navigate(`${ADMIN_PREFIX}/dashboard`, { replace: true });
      return;
    }
    navigate('/cabinet', { replace: true });
  };

  useEffect(() => {
    if (started.current) return;
    started.current = true;

    const oauthError = params.get('error');
    const code = params.get('code');
    const deviceId = params.get('device_id');
    const state = params.get('state');

    if (oauthError) {
      // Link mode: send the user back to the profile instead of stranding
      // them on this page after a cancelled bind.
      const linkReturn = takeSocialLinkReturn();
      if (linkReturn) {
        toast.error('Привязка VK отменена');
        navigate(linkReturn, { replace: true });
        return;
      }
      setError('Вы отклонили вход через VK');
      return;
    }
    if (!code || !deviceId || !state) {
      setError('Нет данных для подтверждения входа');
      return;
    }

    const verifier = takeKey(VERIFIER_KEY);
    const expectedState = takeKey(STATE_KEY);

    if (!verifier) {
      setError('Сессия входа истекла. Попробуйте снова.');
      return;
    }
    if (expectedState && expectedState !== state) {
      setError('Неверная сессия входа. Попробуйте снова.');
      return;
    }

    (async () => {
      try {
        // consent=false: a NEW account comes back as a challenge token
        // (no session, no cookies) — the ConsentScreen below collects the
        // 152-FZ consent, then /auth/consent/complete issues the session.
        const resp = await authApi.vkVerify(code, deviceId, state, verifier, false);
        // Link mode (profile «Привязать VK»): same account, back to the
        // profile it started from — no role landing, no new session toast.
        const linkReturn = takeSocialLinkReturn();
        if (linkReturn) {
          toast.success('VK привязан к аккаунту');
          navigate(linkReturn, { replace: true });
          return;
        }
        if (resp.data.challenge) {
          setChallenge(resp.data.challenge);
          return;
        }
        toast.success(
          resp.data.is_new_user ? 'Добро пожаловать! Аккаунт создан.' : 'Вход через VK выполнен!',
        );
        finishLanding();
      } catch (err: any) {
        const detail = err.response?.data?.detail;
        setError(typeof detail === 'string' ? detail : 'Не удалось войти через VK');
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (error) {
    return (
      <div className="vk-callback-page">
        <div className="vk-callback-card">
          <h1>Вход через VK</h1>
          <p className="vk-callback-error">{error}</p>
          <button className="btn btn-primary" onClick={() => navigate('/', { replace: true })}>
            На главную
          </button>
        </div>
      </div>
    );
  }

  if (challenge) {
    return (
      <ConsentScreen
        challenge={challenge}
        onSuccess={finishLanding}
        onError={(msg) => setError(msg)}
      />
    );
  }

  return (
    <div className="vk-callback-page">
      <div className="vk-callback-card">
        <span className="vk-callback-icon">
          <VkIcon size={40} />
        </span>
        <h1>Вход через VK…</h1>
        <p>Завершаем авторизацию, не закрывайте страницу.</p>
      </div>
    </div>
  );
}

export default VkCallbackPage;
