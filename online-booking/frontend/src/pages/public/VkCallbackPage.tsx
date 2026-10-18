import { useEffect, useRef, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { toast } from 'sonner';
import { authApi } from '../../api/client';
import { getCookie, decodeJwtPayload } from '../../utils/cookies';
import { takeReturnUrl } from '../../utils/redirect';
import { ADMIN_PREFIX, SUPER_PREFIX } from '../../utils/section';
import VkIcon from '../../components/common/icons/VkIcon';
import './VkCallbackPage.css';

/** sessionStorage keys stashed by LoginModal before the VK redirect. */
const VERIFIER_KEY = 'vk_code_verifier';
const STATE_KEY = 'vk_state';
const CONSENT_KEY = 'vk_consent';

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
  // React 18 StrictMode double-invokes effects; guard so we exchange once.
  const started = useRef(false);

  useEffect(() => {
    if (started.current) return;
    started.current = true;

    const oauthError = params.get('error');
    const code = params.get('code');
    const deviceId = params.get('device_id');
    const state = params.get('state');

    if (oauthError) {
      setError('Вы отклонили вход через VK');
      return;
    }
    if (!code || !deviceId || !state) {
      setError('Нет данных для подтверждения входа');
      return;
    }

    const verifier = takeKey(VERIFIER_KEY);
    const expectedState = takeKey(STATE_KEY);
    const consent = takeKey(CONSENT_KEY) === '1';

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
        const resp = await authApi.vkVerify(code, deviceId, state, verifier, consent);
        toast.success(
          resp.data.is_new_user ? 'Добро пожаловать! Аккаунт создан.' : 'Вход через VK выполнен!',
        );
        // Cookies are set by the backend; land by role (dual-role default
        // to the client cabinet, admins/master to their sections).
        const payload = decodeJwtPayload(getCookie('access_token') ?? '');
        if (payload?.is_admin === true) {
          navigate(`${SUPER_PREFIX}/dashboard`, { replace: true });
          return;
        }
        const from = takeReturnUrl();
        if (from) {
          navigate(from, { replace: true });
          return;
        }
        if (payload?.role === 'MASTER') {
          navigate(`${ADMIN_PREFIX}/dashboard`, { replace: true });
          return;
        }
        navigate('/cabinet', { replace: true });
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
