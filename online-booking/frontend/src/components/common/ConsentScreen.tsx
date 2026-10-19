import { useState } from 'react';
import { authApi } from '../../api/client';
import { toast } from 'sonner';
import './ConsentScreen.css';

interface ConsentScreenProps {
  /** The challenge token from the backend (phone/status or OAuth verify). */
  challenge: string;
  /** Called when consent is accepted and the session is established. */
  onSuccess: () => void;
  /** Called when consent is rejected or an error occurs. */
  onError: (message: string) => void;
}

/**
 * ConsentScreen — overlay shown after OAuth verify or phone/status returns
 * a challenge token for a new account without consent (152-FZ, 1.80.0).
 *
 * The user must explicitly accept the privacy policy and offer before the
 * account is committed. If rejected, the flow is aborted.
 *
 * Two paths:
 * 1. Phone register: /phone/status → challenge → /register-unified with challenge
 * 2. OAuth verify: /vk/verify (or /yandex/verify) → challenge → /consent/complete
 */
export default function ConsentScreen({ challenge, onSuccess, onError }: ConsentScreenProps) {
  const [loading, setLoading] = useState(false);

  const handleAccept = async () => {
    setLoading(true);
    try {
      // Try /auth/consent/complete first (OAuth verify path).
      // If it fails with 400 (user_id=0, orphan challenge), fall back to
      // /auth/register-unified with the challenge (phone/status path).
      try {
        await authApi.consentComplete(challenge, true);
        toast.success('Добро пожаловать! Аккаунт создан.');
        onSuccess();
      } catch (err: unknown) {
        const e = err as { response?: { status?: number } };
        // 400 = orphan challenge (phone/status path) → try register-unified.
        if (e?.response?.status === 400) {
          await authApi.registerUnified({
            phone: '',
            password: '',
            consent: true,
            challenge,
          });
          toast.success('Добро пожаловать! Аккаунт создан.');
          onSuccess();
        } else {
          throw err;
        }
      }
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
