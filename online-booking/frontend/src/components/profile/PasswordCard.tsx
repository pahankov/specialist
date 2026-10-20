import { useState } from 'react';
import { toast } from 'sonner';
import { authApi } from '../../api/client';
import { PASSWORD_PLACEHOLDER } from '../../constants';
import { passwordError } from '../../utils/password';
import { getApiErrorMessage } from '../../utils/apiError';
import './ProfileCards.css';

interface PasswordCardProps {
  /** False → the account logs in socially; no password to change. */
  hasPassword?: boolean;
  /** Whether the account has an email (the reset flow needs one). */
  hasEmail?: boolean;
}

/**
 * «Пароль»: change the password of the CURRENT account.
 *
 * Social accounts get a hint instead of a form — a password is never
 * imposed on them; one can be set consciously through «Забыли пароль?»
 * (the emailed code proves the address first).
 */
function PasswordCard({ hasPassword, hasEmail }: PasswordCardProps) {
  const [current, setCurrent] = useState('');
  const [next, setNext] = useState('');
  const [repeat, setRepeat] = useState('');
  const [showCurrent, setShowCurrent] = useState(false);
  const [showNext, setShowNext] = useState(false);
  const [showRepeat, setShowRepeat] = useState(false);
  const [saving, setSaving] = useState(false);

  const nextErr = next !== '' ? passwordError(next) : null;
  const mismatch = repeat !== '' && repeat !== next;

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!current) {
      toast.error('Введите текущий пароль');
      return;
    }
    const err = passwordError(next);
    if (err) {
      toast.error(err);
      return;
    }
    if (next !== repeat) {
      toast.error('Пароли не совпадают');
      return;
    }
    setSaving(true);
    try {
      await authApi.changePassword(current, next);
      toast.success('Пароль изменён');
      setCurrent('');
      setNext('');
      setRepeat('');
    } catch (err2: unknown) {
      toast.error(getApiErrorMessage(err2, 'Не удалось изменить пароль'));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="card" style={{ marginBottom: 16 }}>
      <h3>🔐 Пароль</h3>
      {!hasPassword ? (
        <p className="profile-card-hint" style={{ marginBottom: 0 }}>
          Пароля нет — вы входите через соцсеть или MAX, этого достаточно.
          {hasEmail
            ? ' Задать пароль можно через «Забыли пароль?» на экране входа: придёт код на почту.'
            : ' Чтобы задать пароль, сначала добавьте почту в контактах.'}
        </p>
      ) : (
        <form onSubmit={submit} className="password-form">
          {/* Owner layout (1.82.0): current password on its own row,
              new + repeat on the second row, standard-size button below. */}
          <div className="form-group">
            <label>Текущий пароль</label>
            <div className="password-input-wrap">
              <input
                type={showCurrent ? 'text' : 'password'}
                value={current}
                onChange={(e) => setCurrent(e.target.value)}
                autoComplete="current-password"
                required
              />
              <button
                type="button"
                className="password-eye"
                onClick={() => setShowCurrent(!showCurrent)}
                title={showCurrent ? 'Скрыть пароль' : 'Показать пароль'}
              >
                {showCurrent ? '🙈' : '👁️'}
              </button>
            </div>
          </div>
          <div className="form-row">
            <div className="form-group">
              <label>Новый пароль</label>
              <div className="password-input-wrap">
                <input
                  type={showNext ? 'text' : 'password'}
                  value={next}
                  onChange={(e) => setNext(e.target.value)}
                  placeholder={PASSWORD_PLACEHOLDER}
                  autoComplete="new-password"
                  required
                />
                <button
                  type="button"
                  className="password-eye"
                  onClick={() => setShowNext(!showNext)}
                  title={showNext ? 'Скрыть пароль' : 'Показать пароль'}
                >
                  {showNext ? '🙈' : '👁️'}
                </button>
              </div>
              {nextErr && <p className="error-message">{nextErr}</p>}
            </div>
            <div className="form-group">
              <label>Повторите новый пароль</label>
              <div className="password-input-wrap">
                <input
                  type={showRepeat ? 'text' : 'password'}
                  value={repeat}
                  onChange={(e) => setRepeat(e.target.value)}
                  autoComplete="new-password"
                  required
                />
                <button
                  type="button"
                  className="password-eye"
                  onClick={() => setShowRepeat(!showRepeat)}
                  title={showRepeat ? 'Скрыть пароль' : 'Показать пароль'}
                >
                  {showRepeat ? '🙈' : '👁️'}
                </button>
              </div>
              {mismatch && <p className="error-message">Пароли не совпадают</p>}
            </div>
          </div>
          <button type="submit" className="btn btn-primary password-submit" disabled={saving}>
            {saving ? 'Меняем…' : 'Сменить пароль'}
          </button>
        </form>
      )}
    </div>
  );
}

export default PasswordCard;
