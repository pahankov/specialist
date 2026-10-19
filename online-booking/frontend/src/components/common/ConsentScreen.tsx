import { useState } from 'react';
import { authApi } from '../../api/client';
import { toast } from 'sonner';
import './ConsentScreen.css';

interface ConsentScreenProps {
  /** The challenge token from OAuth verify (VK/Yandex/MAX). */
  challenge: string;
  /** Called when consent is accepted and the session is established. */
  onSuccess: () => void;
  /** Called when consent is rejected or an error occurs. */
  onError: (message: string) => void;
}

/**
 * ConsentScreen — overlay shown when OAuth verify returns a challenge
 * token for a new/pending account without consent (152-FZ, 1.80.0).
 *
 * The user must explicitly accept the privacy policy and offer before the
 * account session is issued. If rejected, the flow is aborted.
 *
 * OAuth verify: /vk/verify (or /yandex/verify, /max/verify) → challenge
 * → /auth/consent/complete. Phone registration asks consent on the
 * register form itself and goes through /auth/register-unified.
 */
export default function ConsentScreen({ challenge, onSuccess, onError }: ConsentScreenProps) {
  const [loading, setLoading] = useState(false);

  const handleAccept = async () => {
    setLoading(true);
    try {
      // Completes the 2-step flow: the backend stamps consent, creates the
      // cabinet profile, writes the welcome note and returns a session.
      await authApi.consentComplete(challenge, true);
      toast.success('Добро пожаловать! Аккаунт создан.');
      onSuccess();
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } };
      const msg = e?.response?.data?.detail || 'Ошибка подтверждения согласия';
      toast.error(msg);
      onError(msg);
    } finally {
      setLoading(false);
    }
  };

  const handleReject = () => {
    toast.info('Для продолжения необходимо дать согласие.');
    onError('Согласие отклонено');
  };

  return (
    <div className="consent-screen-overlay">
      <div className="consent-screen-card">
        <h2 className="consent-screen-title">Подтверждение согласия</h2>
        <p className="consent-screen-text">
          Для создания аккаунта необходимо принять{' '}
          <a href="/privacy" target="_blank" rel="noopener noreferrer">
            политику обработки персональных данных
          </a>{' '}
          и{' '}
          <a href="/offer" target="_blank" rel="noopener noreferrer">
            публичную оферту
          </a>
          .
        </p>
        <div className="consent-screen-actions">
          <button
            className="consent-screen-btn consent-screen-btn--accept"
            onClick={handleAccept}
            disabled={loading}
          >
            {loading ? 'Подтверждение...' : 'Принимаю'}
          </button>
          <button
            className="consent-screen-btn consent-screen-btn--reject"
            onClick={handleReject}
            disabled={loading}
          >
            Отмена
          </button>
        </div>
      </div>
    </div>
  );
}
