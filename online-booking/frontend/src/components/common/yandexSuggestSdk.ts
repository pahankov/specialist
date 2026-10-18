/** Integration layer for the official Yandex ID instant-auth SDK
 * (sdk-suggest.js, «мгновенная авторизация»).
 *
 * Kept apart from the React component: this module owns the per-page-load
 * caches (injected script, /yandex/start config, serialized inits); the
 * component only consumes it. See YandexSuggestButton for the flow docs.
 */
import { authApi } from '../../api/client';

export interface YandexSuggestTokenPayload {
  access_token?: string;
  expires_in?: number;
  /** client_id the token was issued to (informational). */
  cid?: string;
}

export interface YaAuthSuggestApi {
  init(
    oauthParams: {
      client_id: string;
      response_type: string;
      redirect_uri: string;
    },
    tokenPageOrigin: string,
    suggestParams?: Record<string, unknown>,
  ): Promise<{ handler: () => Promise<unknown> }>;
}

export interface YandexSuggestConfig {
  client_id: string;
  suggest_redirect_uri: string;
}

declare global {
  interface Window {
    YaAuthSuggest?: YaAuthSuggestApi;
  }
}

const SDK_SRC =
  'https://yastatic.net/s3/passport-sdk/autofill/v1/sdk-suggest-with-polyfills-latest.js';

// Per-page-load caches: the script is injected once, and client_id /
// suggest_redirect_uri are env config — one /yandex/start is enough.
let sdkPromise: Promise<YaAuthSuggestApi> | null = null;
let configPromise: Promise<YandexSuggestConfig> | null = null;
// The SDK rejects a concurrent init ({code:'in_progress'}), which React
// StrictMode would otherwise trigger by mounting effects twice — serialize
// inits so every mount gets its own fresh handler.
let lastInit: Promise<unknown> = Promise.resolve();

/** Test hook: drop the per-page caches between test cases. */
export function __resetYandexSuggestForTests() {
  sdkPromise = null;
  configPromise = null;
  lastInit = Promise.resolve();
}

export function loadSuggestSdk(): Promise<YaAuthSuggestApi> {
  // Already present (tests pre-install it; a second modal reuses it).
  if (window.YaAuthSuggest) return Promise.resolve(window.YaAuthSuggest);
  if (!sdkPromise) {
    sdkPromise = new Promise((resolve, reject) => {
      const script = document.createElement('script');
      script.src = SDK_SRC;
      script.async = true;
      script.onload = () => {
        if (window.YaAuthSuggest) resolve(window.YaAuthSuggest);
        else reject(new Error('YaAuthSuggest is missing after load'));
      };
      script.onerror = () => {
        sdkPromise = null; // allow a retry on the next mount
        reject(new Error('suggest SDK failed to load'));
      };
      document.head.appendChild(script);
    });
  }
  return sdkPromise;
}

export function loadSuggestConfig(): Promise<YandexSuggestConfig> {
  if (!configPromise) {
    configPromise = authApi
      .yandexStart()
      .then((resp) => ({
        client_id: resp.data.client_id,
        suggest_redirect_uri: resp.data.suggest_redirect_uri ?? '',
      }))
      .catch((err: unknown) => {
        configPromise = null; // transient failure — retry on the next mount
        throw err;
      });
  }
  return configPromise;
}

export async function initSuggest(
  sdk: YaAuthSuggestApi,
  cfg: YandexSuggestConfig,
  suggestParams: Record<string, unknown>,
) {
  await lastInit.catch(() => undefined);
  const pending = sdk.init(
    {
      client_id: cfg.client_id,
      response_type: 'token',
      redirect_uri: cfg.suggest_redirect_uri,
    },
    window.location.origin,
    suggestParams,
  );
  lastInit = pending;
  return pending;
}
