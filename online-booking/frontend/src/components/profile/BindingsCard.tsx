import { useState } from 'react';
import { toast } from 'sonner';
import { authApi } from '../../api/client';
import { getApiErrorMessage } from '../../utils/apiError';
import { stashSocialLinkReturn } from '../../utils/socialLink';
import VkIdWidget from '../common/VkIdWidget';
import VkIcon from '../common/icons/VkIcon';
import YandexIcon from '../common/icons/YandexIcon';
import MaxIcon from '../common/icons/MaxIcon';
import './ProfileCards.css';

interface BindingsCardProps {
  vkBound?: boolean;
  yandexBound?: boolean;
  maxBound?: boolean;
  maxUsername?: string | null;
  /** Re-fetch the page data after a successful bind. */
  onChanged: () => void;
  /** Open the MAX code flow (LoginModal in max mode — owned by the page). */
  onMaxLink: () => void;
  /** Masters (and the draft) sign in only through socials — no password. */
  socialOnly?: boolean;
}

/**
 * «Вход и привязки»: attach VK / Yandex / MAX to the CURRENT account.
 *
 * All three use the signed-state link mode: VK — the official widget with
 * link=true (auth required server-side), Yandex — the redirect flow with a
 * stashed return path, MAX — the usual code login (the MAXUser is attached
 * by phone match, no separate consent needed).
 */
function BindingsCard({
  vkBound,
  yandexBound,
  maxBound,
  maxUsername,
  onChanged,
  onMaxLink,
  socialOnly = false,
}: BindingsCardProps) {
  const [yandexBusy, setYandexBusy] = useState(false);

  const startYandexLink = async () => {
    setYandexBusy(true);
    try {
      const resp = await authApi.yandexStart(true);
      try {
        sessionStorage.setItem('yandex_state', resp.data.state);
        sessionStorage.setItem('yandex_consent', '1');
      } catch {
        /* storage unavailable — the callback relies on the echoed state */
      }
      // Presence of the return path IS the link flag for the callback.
      stashSocialLinkReturn(window.location.pathname);
      window.location.href = resp.data.authorize_url;
    } catch (err: unknown) {
      setYandexBusy(false);
      toast.error(getApiErrorMessage(err, 'Не удалось начать привязку Яндекса'));
    }
  };

  return (
    <div className="card" style={{ marginBottom: 16 }}>
      <h3>🔑 Вход и привязки</h3>
      <p className="profile-card-hint">
        Привязанная соцсеть впускает в этот же аккаунт в один тап — пароль и код не нужны. Почта и
        телефон при этом не меняются.
      </p>
      {socialOnly && (
        <p className="profile-social-only">
          🔐 Вход в кабинет мастера — только через VK ID (ВКонтакте, Одноклассники, Mail), Яндекс
          или MAX. Пароль для мастера не используется.
        </p>
      )}

      <div className="bind-list">
        {/* ── VK ID: official VK / OK / Mail buttons, link mode ── */}
        {vkBound ? (
          <div className="bind-row">
            <span className="bind-icon">
              <VkIcon size={20} />
            </span>
            <span className="bind-name">ВКонтакте, Одноклассники, Mail</span>
            <span className="bind-done">✅ Привязан</span>
          </div>
        ) : (
          <div className="bind-official">
            <div className="bind-official-head">
              <VkIcon size={20} />
              <span>ВКонтакте, Одноклассники или Mail</span>
            </div>
            <VkIdWidget link onSuccess={onChanged} />
          </div>
        )}

        {/* ── Yandex (redirect with a stashed return path) ── */}
        {yandexBound ? (
          <div className="bind-row">
            <span className="bind-icon">
              <YandexIcon size={20} />
            </span>
            <span className="bind-name">Яндекс</span>
            <span className="bind-done">✅ Привязан</span>
          </div>
        ) : (
          <button
            type="button"
            className="social-auth-btn bind-brand-btn"
            disabled={yandexBusy}
            onClick={startYandexLink}
          >
            <span className="social-auth-icon">
              <YandexIcon size={20} />
            </span>
            <span>{yandexBusy ? 'Открываем Яндекс…' : 'Привязать Яндекс ID'}</span>
          </button>
        )}

        {/* ── MAX (code login; the bot attaches by phone match) ── */}
        {maxBound ? (
          <div className="bind-row">
            <span className="bind-icon">
              <MaxIcon size={20} />
            </span>
            <span className="bind-name">MAX{maxUsername ? ` (@${maxUsername})` : ''}</span>
            <span className="bind-done">✅ Привязан</span>
          </div>
        ) : (
          <button type="button" className="social-auth-btn bind-brand-btn" onClick={onMaxLink}>
            <span className="social-auth-icon">
              <MaxIcon size={20} />
            </span>
            <span>Привязать MAX</span>
          </button>
        )}
      </div>

      {!maxBound && (
        <p className="profile-card-hint" style={{ marginTop: 10, marginBottom: 0 }}>
          MAX привязывается по номеру: войдите в бота с телефоном, который есть в ваших контактах
          ниже.
        </p>
      )}
    </div>
  );
}

export default BindingsCard;
