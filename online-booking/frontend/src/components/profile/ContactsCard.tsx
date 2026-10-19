import { useState } from 'react';
import { toast } from 'sonner';
import { cabinetApi, type ClientContact } from '../../api/client';
import PhoneInput, { isCompletePhone } from '../common/PhoneInput';
import { getApiErrorMessage } from '../../utils/apiError';
import './ProfileCards.css';

interface ContactsCardProps {
  contacts: ClientContact[];
  /** Re-fetch the page data after any change. */
  onChanged: () => void;
}

function verifyLabel(contact: ClientContact): string {
  if (contact.verified_via === 'social') return 'подтверждён соцсетью';
  if (contact.verified_via === 'code') return 'подтверждён кодом';
  return 'не подтверждён';
}

/**
 * «Контакты»: all phones/emails of the account (1.79.0 contact model).
 *
 * The client can add, remove and re-promote contacts — but a self-typed
 * value lands UNVERIFIED: verification comes from social logins or emailed
 * codes. Removing the last contact of a password account is blocked by the
 * backend (it would lock the person out).
 */
function ContactsCard({ contacts, onChanged }: ContactsCardProps) {
  const [newType, setNewType] = useState<'phone' | 'email'>('phone');
  const [newValue, setNewValue] = useState('');
  const [busy, setBusy] = useState<number | 'add' | null>(null);

  const phones = contacts.filter((c) => c.contact_type === 'phone');
  const emails = contacts.filter((c) => c.contact_type === 'email');

  const add = async (e: React.FormEvent) => {
    e.preventDefault();
    const value = newValue.trim();
    if (newType === 'phone' && !isCompletePhone(value)) {
      toast.error('Введите телефон полностью');
      return;
    }
    if (newType === 'email' && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)) {
      toast.error('Введите корректный email');
      return;
    }
    setBusy('add');
    try {
      await cabinetApi.addContact({ contact_type: newType, value });
      toast.success('Контакт добавлен');
      setNewValue('');
      onChanged();
    } catch (err: unknown) {
      toast.error(getApiErrorMessage(err, 'Не удалось добавить контакт'));
    } finally {
      setBusy(null);
    }
  };

  const remove = async (contact: ClientContact) => {
    setBusy(contact.id);
    try {
      await cabinetApi.removeContact(contact.id);
      toast.success('Контакт удалён');
      onChanged();
    } catch (err: unknown) {
      toast.error(getApiErrorMessage(err, 'Не удалось удалить контакт'));
    } finally {
      setBusy(null);
    }
  };

  const makePrimary = async (contact: ClientContact) => {
    setBusy(contact.id);
    try {
      await cabinetApi.makeContactPrimary(contact.id);
      toast.success('Основной контакт обновлён');
      onChanged();
    } catch (err: unknown) {
      toast.error(getApiErrorMessage(err, 'Не удалось обновить контакт'));
    } finally {
      setBusy(null);
    }
  };

  const renderList = (list: ClientContact[], title: string) =>
    list.length > 0 && (
      <div className="contact-group">
        <div className="contact-group-title">{title}</div>
        {list.map((c) => (
          <div key={c.id} className="contact-row">
            <div className="contact-main">
              <span className="contact-value">{c.value}</span>
              <span className="contact-badges">
                {c.is_primary && <span className="badge badge-primary">основной</span>}
                <span className={`badge ${c.is_verified ? 'badge-verified' : 'badge-unverified'}`}>
                  {verifyLabel(c)}
                </span>
              </span>
            </div>
            <div className="contact-actions">
              {!c.is_primary && (
                <button
                  type="button"
                  className="btn btn-ghost btn-sm"
                  disabled={busy === c.id}
                  onClick={() => makePrimary(c)}
                  title="Входить по этому номеру/почте"
                >
                  Сделать основным
                </button>
              )}
              <button
                type="button"
                className="btn btn-sm btn-delete"
                disabled={busy === c.id}
                onClick={() => remove(c)}
                title="Удалить контакт"
              >
                ✖
              </button>
            </div>
          </div>
        ))}
      </div>
    );

  return (
    <div className="card" style={{ marginBottom: 16 }}>
      <h3>📱 Контакты</h3>
      <p className="profile-card-hint">
        Основной телефон — вход по паролю; основной email — письма и восстановление пароля.
        «Подтверждён» появляется после входа через соцсеть или кода из письма.
      </p>

      {renderList(phones, 'Телефоны')}
      {renderList(emails, 'Почты')}
      {contacts.length === 0 && (
        <p className="profile-card-hint">Пока пусто — добавьте телефон или почту.</p>
      )}

      <form className="contact-add" onSubmit={add}>
        <select
          value={newType}
          onChange={(e) => {
            setNewType(e.target.value as 'phone' | 'email');
            setNewValue('');
          }}
          aria-label="Тип контакта"
        >
          <option value="phone">Телефон</option>
          <option value="email">Email</option>
        </select>
        {newType === 'phone' ? (
          <PhoneInput value={newValue} onChange={setNewValue} placeholder="+7 (999) 123-45-67" />
        ) : (
          <input
            type="email"
            value={newValue}
            onChange={(e) => setNewValue(e.target.value)}
            placeholder="email@example.com"
          />
        )}
        <button type="submit" className="btn btn-primary" disabled={busy === 'add'}>
          {busy === 'add' ? 'Добавляем…' : 'Добавить'}
        </button>
      </form>
    </div>
  );
}

export default ContactsCard;
