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
  const verb = action === 'register' ? 'Регистрация через' : 'Войти через';
  return (
    <button
      type="button"
      className="social-auth-btn"
      style={{ '--brand-color': meta.color } as React.CSSProperties}
      onClick={onClick}
      disabled={disabled}
    >
      <span className="social-auth-icon">{meta.icon}</span>
      <span>
        {verb} {meta.label}
      </span>
    </button>
  );
}

export default SocialAuthButton;
