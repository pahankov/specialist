import { useEffect, useRef, useState } from 'react';
import { toast } from 'sonner';
import Modal from '../common/Modal';
import { getApiErrorMessage } from '../../utils/apiError';
import './EmailVerifyModal.css';

interface EmailVerifyModalProps {
  open: boolean;
  /** The email being confirmed (null while nothing is being verified). */
  email: string | null;
  onClose: () => void;
  /** Sends a fresh code (caller picks the endpoint). */
  sendCode: () => Promise<unknown>;
  /** Verifies the code; resolves only when the contact is confirmed. */
  verifyCode: (code: string) => Promise<unknown>;
  /** Fired once the contact is verified (refresh the contacts list). */
  onVerified: () => void;
}

/**
 * «Подтвердить почту»: emailed six-digit code for an own email contact.
 * Shared by the client cabinet and the (super) admin profile — the caller
 * injects the two API calls, the modal owns the roundtrip UI.
 */
export default function EmailVerifyModal({
  open,
  email,
  onClose,
  sendCode,
  verifyCode,
  onVerified,
}: EmailVerifyModalProps) {
  const [code, setCode] = useState('');
  const [busy, setBusy] = useState<'send' | 'verify' | null>(null);

  // A fresh code goes out on every open; callbacks go through refs so a
  // parent re-render (new arrow functions) never re-triggers the send.
  const sendRef = useRef(sendCode);
  sendRef.current = sendCode;
  const verifyRef = useRef(verifyCode);
  verifyRef.current = verifyCode;

  useEffect(() => {
    if (!open) return;
    setCode('');
    let cancelled = false;
    (async () => {
      setBusy('send');
      try {
        await sendRef.current();
      } catch (err: unknown) {
        toast.error(getApiErrorMessage(err, 'Не удалось отправить письмо'));
      } finally {
        if (!cancelled) setBusy(null);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [open]);

  const resend = async () => {
    if (busy) return;
    setBusy('send');
    try {
      await sendRef.current();
      toast.success('Код отправлен ещё раз');
    } catch (err: unknown) {
      toast.error(getApiErrorMessage(err, 'Не удалось отправить письмо'));
    } finally {
      setBusy(null);
    }
  };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (busy || code.length < 6) return;
    setBusy('verify');
    try {
      await verifyRef.current(code);
      toast.success('Почта подтверждена');
      onVerified();
      onClose();
    } catch (err: unknown) {
      toast.error(getApiErrorMessage(err, 'Неверный код'));
    } finally {
      setBusy(null);
    }
  };

  return (
    <Modal open={open} onClose={onClose} title="Подтверждение почты" className="email-verify-modal">
      <p className="modal-message">
        {busy === 'send'
          ? `Отправляем код на ${email}…`
          : `Мы отправили код на ${email}. Введите 6 цифр из письма.`}
      </p>
      <form className="email-verify-form" onSubmit={submit}>
        <input
          className="email-verify-input"
          value={code}
          onChange={(e) => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
          inputMode="numeric"
          autoComplete="one-time-code"
          placeholder="000000"
          aria-label="Код из письма"
        />
        <button
          type="submit"
          className="btn btn-primary btn-submit"
          disabled={busy !== null || code.length < 6}
        >
          {busy === 'verify' ? 'Проверяем…' : 'Подтвердить'}
        </button>
      </form>
      <button
        type="button"
        className="email-verify-resend"
        onClick={resend}
        disabled={busy !== null}
      >
        {busy === 'send' ? 'Отправляем…' : 'Отправить код ещё раз'}
      </button>
    </Modal>
  );
}
