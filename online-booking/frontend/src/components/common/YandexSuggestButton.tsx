import { useEffect, useState } from 'react';
import { toast } from 'sonner';
import { authApi } from '../../api/client';
import { SOCIAL_BTN_HEIGHT, SOCIAL_BTN_RADIUS } from './SocialAuthButton';
import {
  initSuggest,
  loadSuggestConfig,
  loadSuggestSdk,
  type YandexSuggestTokenPayload,
} from './yandexSuggestSdk';
import './YandexSuggestButton.css';
import ConsentScreen from './ConsentScreen';

/**
 * Official Yandex ID instant-auth block («мгновенная авторизация»).
 *
 * Instead of our own button + redirect this mounts Yandex's official
 * sdk-suggest.js INLINE (docs: yandex.ru/dev/id, suggest):
 *   1. The SDK renders the official button (main / icon) into our container.
 *   2. On click the user approves inside Yandex's own UI; the OAuth token is
 *      handed to the helper page (frontend/public/suggest-token.html), which
 *      postMessages it back — the SDK promise resolves with
 *      {access_token, expires_in, cid}.
 *   3. The token is verified SERVER-SIDE (/yandex/verify -> user_info) before
 *      the account is created/bound and the session cookie is set.
 *
 * Availability is first-class: the SDK refuses to init when third-party
 * cookies are blocked (docs: «без cookie можно подключить только кнопку»)
 * or the setup is off — the component then calls onUnavailable() and the
 * parent renders the plain redirect button instead.
 */
type SuggestVariant = 'login' | 'register';

interface YandexSuggestButtonProps {
  /** 'login' — the full-width official button; 'register' — the icon tile
      that continues the VK OAuthList row. */
  variant: SuggestVariant;
  /** Session established (cookies already set) — the parent lands the user. */
  onSuccess: () => void;
  /** The widget cannot run here — the parent switches to the redirect button. */
  onUnavailable: () => void;
}

function YandexSuggestButton({ variant, onSuccess, onUnavailable }: YandexSuggestButtonProps) {
  const parentId = variant === 'login' ? 'yandex-suggest-login' : 'yandex-suggest-register';
  const [showConsent, setShowConsent] = useState<string | null>(null);

  const handleConsentSuccess = () => {
    setShowConsent(null);
    onSuccess();
  };

  const handleConsentError = (_msg: string) => {
    setShowConsent(null);
    // Fall back to redirect button on consent error.
    onUnavailable();
  };

  useEffect(() => {
    let disposed = false;

    (async () => {
      try {
        const cfg = await loadSuggestConfig();
        if (disposed) return;
        if (!cfg.suggest_redirect_uri) {
          onUnavailable(); // widget not configured — redirect button it is
          return;
        }
        const sdk = await loadSuggestSdk();
        if (disposed) return;

        const { handler } = await initSuggest(sdk, cfg, {
          view: 'button',
          parentId,
          // login: the official title button; register: the bare logo tile.
          buttonView: variant === 'login' ? 'main' : 'icon',
          buttonTheme: 'light',
          // 44px (size m) matches SOCIAL_BTN_HEIGHT for the login button; the
          // icon tile sits inside our 44px tile, so size s (40px) fits.
          buttonSize: variant === 'login' ? 'm' : 's',
          buttonBorderRadius: SOCIAL_BTN_RADIUS,
        });
        if (disposed) return;

        const data = (await handler()) as
          (YandexSuggestTokenPayload & { data?: YandexSuggestTokenPayload }) | null;
        if (disposed) return;
        const accessToken = data?.access_token ?? data?.data?.access_token;
        if (!accessToken) {
          // Empty payload = the user closed the Yandex UI; the button stays
          // for a retry. A non-empty unknown shape is a real failure.
          if (data && Object.keys(data).length > 0) onUnavailable();
          return;
        }

        // Server-side validation + account create/bind; sets the cookies.
        // consent=false: a NEW account gets a challenge instead of a session
        // (ConsentScreen collects the 152-FZ consent first).
        const resp = await authApi.yandexVerifyToken(accessToken, false);
        // New/pending account without consent → ConsentScreen overlay.
        if (resp.data.challenge) {
          setShowConsent(resp.data.challenge);
          return;
        }
        if (disposed) return;
        toast.success(
          resp.data.is_new_user
            ? 'Добро пожаловать! Аккаунт создан.'
            : 'Вход через Яндекс выполнен!',
        );
        onSuccess();
      } catch (err: unknown) {
        if (disposed) return;
        const e = err as {
          code?: string;
          response?: { data?: { detail?: unknown } };
        };
        if (e?.code === 'in_progress') return; // the pending init owns the flow
        if (e?.response) {
          // The widget worked, the backend refused (expired token, 503, ...):
          // surface it and give the redirect button as the way out.
          const detail = e.response.data?.detail;
          toast.error(typeof detail === 'string' ? detail : 'Не удалось войти через Яндекс');
          onUnavailable();
          return;
        }
        // SDK/env failure (no cookie, CDN down, page setup): fall back to our
        // own redirect button silently — it works without cookies.
        onUnavailable();
      }
    })();

    return () => {
      disposed = true;
    };
  }, []);

  return (
    <>
      {variant === 'register' ? (
        <div
          className="social-icon-btn"
          style={{
            height: SOCIAL_BTN_HEIGHT,
            borderRadius: SOCIAL_BTN_RADIUS,
          }}
          data-testid="yandex-suggest-container"
        >
          <div id={parentId} className="yandex-suggest-slot" />
        </div>
      ) : (
        <div className="yandex-suggest-login" data-testid="yandex-suggest-container">
          <div id={parentId} className="yandex-suggest-slot" />
        </div>
      )}
      {showConsent && (
        <ConsentScreen
          challenge={showConsent}
          onSuccess={handleConsentSuccess}
          onError={handleConsentError}
        />
      )}
    </>
  );
}

export default YandexSuggestButton;
