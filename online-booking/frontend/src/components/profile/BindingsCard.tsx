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
}: BindingsCardProps) {
  const [vkOpen, setVkOpen] = useState(false);
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

      <div className="bind-list">
        {/* ── VK (VK/OK/Mail widget, link mode) ── */}
        <div className="bind-row">
          <span className="bind-icon">
            <VkIcon size={20} />
          </span>
          <span className="bind-name">ВКонтакте</span>
          {vkBound ? (
            <span className="bind-done">✅ Привязан</span>
          ) : vkOpen ? null : (
            <button type="button" className="btn btn-ghost btn-sm" onClick={() => setVkOpen(true)}>
              Привязать
            </button>
          )}
        </div>
        {!vkBound && vkOpen && (
          <div className="bind-widget">
            <VkIdWidget
              link
              onSuccess={() => {
                setVkOpen(false);
                onChanged();
              }}
            />
          </div>
        )}

        {/* ── Yandex (redirect with a stashed return path) ── */}
        <div className="bind-row">
          <span className="bind-icon">
            <YandexIcon size={20} />
          </span>
          <span className="bind-name">Яндекс</span>
          {yandexBound ? (
            <span className="bind-done">✅ Привязан</span>
          ) : (
            <button
              type="button"
              className="btn btn-ghost btn-sm"
              disabled={yandexBusy}
              onClick={startYandexLink}
            >
              {yandexBusy ? 'Отправляем…' : 'Привязать'}
            </button>
          )}
        </div>

        {/* ── MAX (code login; the bot attaches by phone match) ── */}
        <div className="bind-row">
          <span className="bind-icon">
            <MaxIcon size={20} />
          </span>
          <span className="bind-name">
            MAX{maxBound && maxUsername ? ` (@${maxUsername})` : ''}
          </span>
          {maxBound ? (
            <span className="bind-done">✅ Привязан</span>
          ) : (
            <button type="button" className="btn btn-ghost btn-sm" onClick={onMaxLink}>
              Привязать
            </button>
          )}
        </div>
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
