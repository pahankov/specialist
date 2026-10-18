import { useEffect, useRef, useState } from 'react';
import {
  Config,
  ConfigResponseMode,
  OAuthList,
  OAuthName,
  OAuthListInternalEvents,
} from '@vkid/sdk';
import { authApi } from '../../api/client';
import { toast } from 'sonner';
import { generateCodeVerifier, generateCodeChallenge } from '../../utils/pkce';

/**
 * VK ID low-code widget (VK + Одноклассники + Mail in one OAuthList block),
 * rendered INLINE in the login form — no separate consent screen. 152-FZ
 * consent is taken once at registration; a first social login IS a
 * registration and stamps it implicitly server-side.
 *
 * Flow — the backend exchange stays server-side, so tokens never touch the
 * browser:
 *   1. Generate a PKCE code_verifier here; send only its SHA-256 (challenge)
 *      to /vk/start, which returns a signed HMAC `state` + the canonical
 *      redirect_uri + client_id.
 *   2. Init the SDK Config with that same `state` + `code_verifier` +
 *      responseMode=Callback. The SDK renders the widget; on click the user
 *      approves inside VK's own popup, and LOGIN_SUCCESS fires with `code` +
 *      `device_id`.
 *   3. Post code + device_id + state + code_verifier to the existing
 *      /vk/verify, which trades the code for tokens on the server (the backend
 *      holds the app secret) and mints the session cookie.
 *
 * Because we pass our own `state` into Config, the value VK echoes back is the
 * same HMAC state our backend validates — no CSRF gap, and the whole tested
 * /vk/verify path is reused unchanged.
 */
interface VkIdWidgetProps {
  /** Called after the backend session is established (cookies set). */
  onSuccess: () => void;
  onError?: (message: string) => void;
}

function VkIdWidget({ onSuccess, onError }: VkIdWidgetProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    let disposed = false;
    let widget: OAuthList | null = null;

    (async () => {
      try {
        // 1. PKCE + signed state from the backend.
        const verifier = generateCodeVerifier();
        const challenge = await generateCodeChallenge(verifier);
        const resp = await authApi.vkStart(challenge);
        const { state, client_id: clientId, redirect_uri: redirectUri } = resp.data;

        if (disposed) return;

        // 2. Configure the SDK with our state + verifier so the backend
        //    exchange (which validates the state) still matches.
        //    NOTE `app` is the VK ID client_id passed VERBATIM: VK ID uses a
        //    hex id (e.g. "3772ca16...") which Number() would turn into NaN —
        //    and the SDK sends `client_id: app` straight into the authorize
        //    URL, validating it with !isNaN(parseInt(...)).
        Config.init({
          // The SDK's TS type says `app: number` (legacy — numeric VK app
          // ids), but the runtime validator accepts strings and the id is
          // forwarded verbatim as `client_id`. VK ID's hex id MUST stay a
          // string, so widen here.
          app: clientId as unknown as number,
          redirectUrl: redirectUri,
          responseMode: ConfigResponseMode.Callback,
          state,
          codeVerifier: verifier,
        });

        // 3. Render VK + OK + Mail as one OAuthList block.
        widget = new OAuthList();
        widget.render({
          container,
          oauthList: [OAuthName.VK, OAuthName.OK, OAuthName.MAIL],
        });

        widget.on(
          OAuthListInternalEvents.LOGIN_SUCCESS,
          async (payload: { code: string; device_id: string }) => {
            if (!payload?.code || !payload?.device_id) {
              const msg = 'Не удалось войти через VK';
              setError(msg);
              onError?.(msg);
              return;
            }
            try {
              // 4. Server-side exchange: tokens never reach the browser. The
              //    first successful exchange creates the account and stamps the
              //    152-FZ consent implicitly (registration = first social login).
              const resp = await authApi.vkVerify(
                payload.code,
                payload.device_id,
                state,
                verifier,
                true,
              );
              toast.success(
                resp.data.is_new_user
                  ? 'Добро пожаловать! Аккаунт создан.'
                  : 'Вход через VK выполнен!',
              );
              onSuccess();
            } catch (err: unknown) {
              const e = err as { response?: { data?: { detail?: string } } };
              const msg = e?.response?.data?.detail || 'Не удалось войти через VK';
              setError(msg);
              onError?.(msg);
            }
          },
        );
      } catch (err: unknown) {
        if (disposed) return;
        const e = err as { response?: { status?: number } } | undefined;
        // Inline widget mounts with the login form, so surface the error in
        // place (no toast) — a 503 while VK is unconfigured shouldn't nag on
        // every modal open.
        const msg =
          e?.response?.status === 503
            ? 'Вход через VK не настроен'
            : 'Не удалось загрузить виджет VK';
        setError(msg);
        onError?.(msg);
      }
    })();

    return () => {
      disposed = true;
      try {
        widget?.close();
      } catch {
        /* widget may not be mounted yet */
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="vkid-widget">
      {error && <p className="error-message">{error}</p>}
      <div ref={containerRef} data-testid="vkid-widget-container" />
    </div>
  );
}

export default VkIdWidget;
