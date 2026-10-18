import MaxIcon from './icons/MaxIcon';
import VkIcon from './icons/VkIcon';
import YandexIcon from './icons/YandexIcon';
import './SocialAuthButton.css';

/**
 * Social login/registration providers. MAX (chat-bot auth via
 * request_contact), VK (OAuth + PKCE redirect) and Yandex (OAuth redirect)
 * are wired; the list is the single place to add a new provider later
 * (WhatsApp, Telegram, Mail) — drop in an icon and a handler in LoginModal.
 */
export type SocialProvider = 'max' | 'vk' | 'yandex';

/**
 * Shared tile size for the social buttons. The VK OAuthList widget gets these
 * via `OAuthListStyles` (see VkIdWidget) and the Yandex/MAX icon tiles repeat
 * them — so both rows share one height and corner radius even though VK draws
 * its part inside an iframe we cannot style from CSS.
 */
export const SOCIAL_BTN_HEIGHT = 44;
export const SOCIAL_BTN_RADIUS = 10;

interface SocialProviderMeta {
  /** Button label shown to the user. */
  label: string;
  icon: React.ReactNode;
  /** Brand color for the icon accent (unused for layout). */
  color: string;
}

export const SOCIAL_PROVIDERS: Record<SocialProvider, SocialProviderMeta> = {
  max: {
    label: 'MAX',
    icon: <MaxIcon size={20} />,
    color: '#3D4EDB',
  },
  vk: {
    label: 'VK',
    icon: <VkIcon size={20} />,
    color: '#0077FF',
  },
  yandex: {
    label: 'Яндекс',
    icon: <YandexIcon size={20} />,
    color: '#FC3F1D',
  },
};

interface SocialAuthButtonProps {
  provider: SocialProvider;
  /** Same handler for login AND registration — MAX flow merges both. */
  onClick: () => void;
  disabled?: boolean;
  /** "Войти" (default) or "Регистрация" — MAX auth does both. */
  action?: 'login' | 'register';
}

/** One wording for text buttons, icon tiles, aria-labels and tests. */
export function socialAuthLabel(provider: SocialProvider, action: 'login' | 'register' = 'login') {
  const verb = action === 'register' ? 'Регистрация через' : 'Войти через';
  return `${verb} ${SOCIAL_PROVIDERS[provider].label}`;
}

/**
 * One-click social auth button in the style every messenger login uses:
 * brand icon + «Войти через MAX». The backend flow is identical for login
 * and registration (an account is created on the first verified code).
 */
function SocialAuthButton({
  provider,
  onClick,
  disabled = false,
  action = 'login',
}: SocialAuthButtonProps) {
  const meta = SOCIAL_PROVIDERS[provider];
  return (
    <button
      type="button"
      className="social-auth-btn"
      style={{ '--brand-color': meta.color } as React.CSSProperties}
      onClick={onClick}
      disabled={disabled}
    >
      <span className="social-auth-icon">{meta.icon}</span>
      <span>{socialAuthLabel(provider, action)}</span>
    </button>
  );
}

/**
 * Icon-only social tile (no caption) — used where the official VK OAuthList
 * widget already owns the row: Yandex and MAX continue it right below, at the
 * same height and corner radius, so the block reads as one set of providers.
 * VK draws its own three tiles inside an iframe, so they can never be merged
 * into a single row — this is the closest visual match available.
 *
 * The label moves into `aria-label`/`title`: the button is a bare icon on
 * screen, but assistive tech and tests still see «Регистрация через Яндекс».
 */
export function SocialAuthIconButton({
  provider,
  onClick,
  disabled = false,
  action = 'login',
}: SocialAuthButtonProps) {
  const meta = SOCIAL_PROVIDERS[provider];
  const label = socialAuthLabel(provider, action);
  return (
    <button
      type="button"
      className="social-icon-btn"
      style={
        {
          '--brand-color': meta.color,
          height: SOCIAL_BTN_HEIGHT,
          borderRadius: SOCIAL_BTN_RADIUS,
        } as React.CSSProperties
      }
      onClick={onClick}
      disabled={disabled}
      aria-label={label}
      title={label}
    >
      <span className="social-auth-icon">{meta.icon}</span>
    </button>
  );
}

export default SocialAuthButton;
