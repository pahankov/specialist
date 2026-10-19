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
  const [show, setShow] = useState(false);
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
        <form onSubmit={submit}>
          <div className="form-row">
            <div className="form-group">
              <label>Текущий пароль</label>
              <input
                type={show ? 'text' : 'password'}
                value={current}
                onChange={(e) => setCurrent(e.target.value)}
                autoComplete="current-password"
                required
              />
            </div>
            <div className="form-group">
              <label>Новый пароль</label>
              <input
                type={show ? 'text' : 'password'}
                value={next}
                onChange={(e) => setNext(e.target.value)}
                placeholder={PASSWORD_PLACEHOLDER}
                autoComplete="new-password"
                required
              />
              {nextErr && <p className="error-message">{nextErr}</p>}
            </div>
          </div>
          <div className="form-row">
            <div className="form-group">
              <label>Повторите новый пароль</label>
              <input
                type={show ? 'text' : 'password'}
                value={repeat}
                onChange={(e) => setRepeat(e.target.value)}
                autoComplete="new-password"
                required
              />
              {mismatch && <p className="error-message">Пароли не совпадают</p>}
            </div>
            <div className="form-group" style={{ justifyContent: 'flex-end' }}>
              <label className="checkbox-label" style={{ marginBottom: 10 }}>
                <input type="checkbox" checked={show} onChange={(e) => setShow(e.target.checked)} />
                <span>Показать пароли</span>
              </label>
              <button type="submit" className="btn btn-primary" disabled={saving}>
                {saving ? 'Меняем…' : 'Сменить пароль'}
              </button>
            </div>
          </div>
        </form>
      )}
    </div>
  );
}

export default PasswordCard;
