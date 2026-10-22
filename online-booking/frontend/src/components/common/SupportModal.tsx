import { useEffect, useState } from 'react';
import { toast } from 'sonner';
import { supportApi } from '../../api/client';
import { getApiErrorMessage } from '../../utils/apiError';
import Modal from './Modal';
import './SupportModal.css';

interface SupportModalProps {
  open: boolean;
  onClose: () => void;
}

const MIN_LENGTH = 10;
const MAX_LENGTH = 2000;

/**
 * Sidebar support form for clients and masters. The backend forwards the
 * message to every active superadmin as a bell notification.
 */
function SupportModal({ open, onClose }: SupportModalProps) {
  const [message, setMessage] = useState('');
  const [sending, setSending] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (open) {
      setMessage('');
      setSending(false);
      setError('');
    }
  }, [open]);

  const trimmed = message.trim();
  const canSend = trimmed.length >= MIN_LENGTH && !sending;

  const handleSend = async () => {
    if (!canSend) return;
    setSending(true);
    setError('');
    try {
      await supportApi.send({
        message: trimmed,
        page: window.location.pathname,
      });
      toast.success('Сообщение отправлено в поддержку');
      onClose();
    } catch (err: unknown) {
      setError(getApiErrorMessage(err, 'Не удалось отправить сообщение'));
    } finally {
      setSending(false);
    }
  };

  return (
    <Modal open={open} onClose={onClose} title="💬 Связаться с поддержкой">
      <p className="support-modal-intro">
        Опишите вопрос или проблему. Сообщение придёт администратору — он увидит его в панели
        уведомлений.
      </p>

      <div className="form-group">
        <label htmlFor="support-message">Сообщение</label>
        <textarea
          id="support-message"
          className="form-input support-modal-textarea"
          value={message}
          onChange={(event) => setMessage(event.target.value.slice(0, MAX_LENGTH))}
          placeholder="Например: не получается изменить расписание на 15 минут..."
          rows={5}
          autoFocus
        />
        <div className="support-modal-meta">
          <span className={trimmed.length > 0 && trimmed.length < MIN_LENGTH ? 'is-short' : ''}>
            Минимум {MIN_LENGTH} символов
          </span>
          <span>
            {message.length}/{MAX_LENGTH}
          </span>
        </div>
      </div>

      {error && (
        <div className="support-modal-error" role="alert">
          {error}
        </div>
      )}

      <div className="modal-actions">
        <button type="button" className="btn btn-ghost" onClick={onClose} disabled={sending}>
          Отмена
        </button>
        <button type="button" className="btn btn-primary" onClick={handleSend} disabled={!canSend}>
          {sending ? 'Отправляем...' : 'Отправить'}
        </button>
      </div>
    </Modal>
  );
}

export default SupportModal;
