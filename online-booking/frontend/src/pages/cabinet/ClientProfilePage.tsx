import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { authApi, cabinetApi, type ClientMe } from '../../api/client';
import apiClient from '../../api/http';
import { AddressSelect, BackendImg, ConfirmDialog, Modal, Skeleton } from '../../components/common';
import LoginModal from '../../components/LoginModal';
import { BindingsCard, ContactsCard, PasswordCard } from '../../components/profile';
import type { CityOption } from '../../components/common/CitySelect';
import { getApiErrorMessage } from '../../utils/apiError';
import { clearAuthCookies } from '../../utils/cookies';
import { capitalizeWords, splitFullName } from '../../utils/names';
import './ClientProfilePage.css';

/** Client personal data: names, contacts (read-only ids), city, address. */
function ClientProfilePage() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [confirmDeleteStep2, setConfirmDeleteStep2] = useState(false);
  const [deleteWord, setDeleteWord] = useState('');
  const [me, setMe] = useState<ClientMe | null>(null);
  const [firstName, setFirstName] = useState('');
  const [lastName, setLastName] = useState('');
  const [city, setCity] = useState<CityOption | null>(null);
  const [address, setAddress] = useState('');
  const [addressCity, setAddressCity] = useState('');
  /** «Привязать MAX» opens the login modal in its MAX-code mode. */
  const [maxLinkOpen, setMaxLinkOpen] = useState(false);

  /** Re-read only the me payload (contacts/bindings) without touching the
      form drafts the person may be editing. */
  const refreshMe = async () => {
    try {
      const { data } = await cabinetApi.me();
      setMe(data);
    } catch {
      /* keep the previous payload — the next reload recovers */
    }
  };

  useEffect(() => {
    (async () => {
      try {
        const { data } = await cabinetApi.me();
        setMe(data);
        const [first, rest] = splitFullName(data.name || '');
        setFirstName(first);
        setLastName(data.last_name || rest);
        setCity(
          data.city_id != null
            ? { id: data.city_id, name: data.city_name || '', source: 'local' }
            : null,
        );
        setAddress(data.address || '');
        setAddressCity(data.city_name || '');
      } catch (err: unknown) {
        toast.error(getApiErrorMessage(err, 'Не удалось загрузить профиль'));
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  /** A DaData address pick carries its city: resolve the name to a local
      city_id (get-or-create server-side) so masters can still filter by
      city. A failed resolve keeps the previous city — the address saves. */
  const resolveAddressCity = async (name: string) => {
    setAddressCity(name);
    try {
      const { data } = await apiClient.post('/api/v1/cities/resolve', { name });
      setCity({ id: data.id, name: data.name_ru ?? name, source: 'dadata' });
    } catch {
      /* city stays as it was — search keeps the last known value */
    }
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!firstName.trim()) {
      toast.error('Введите имя');
      return;
    }
    setSaving(true);
    try {
      const { data } = await cabinetApi.updateMe({
        name: firstName.trim(),
        last_name: lastName.trim() || null,
        city_id: city?.id ?? me?.city_id ?? undefined,
        address: address.trim() || null,
      });
      setMe(data);
      toast.success('Профиль сохранён');
    } catch (err: unknown) {
      toast.error(getApiErrorMessage(err, 'Не удалось сохранить профиль'));
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    setDeleting(true);
    try {
      const { data } = await cabinetApi.deleteMe();
      if (data.cancelled_appointments > 0) {
        toast.info(`Отменено будущих записей: ${data.cancelled_appointments}`);
      }
      try {
        await authApi.logout();
      } catch {
        /* sessions already revoked server-side */
      }
      clearAuthCookies();
      toast.success('Аккаунт удалён');
      navigate('/', { replace: true });
    } catch (err: unknown) {
      toast.error(getApiErrorMessage(err, 'Не удалось удалить аккаунт'));
    } finally {
      setDeleting(false);
      setConfirmDelete(false);
    }
  };

  if (loading) {
    return (
      <div className="client-profile-page">
        <Skeleton rows={5} />
      </div>
    );
  }

  return (
    <div className="client-profile-page">
      <div className="page-header">
        <div>
          <h1>👤 Мой профиль</h1>
          <p>Имя, город и адрес для подбора мастеров</p>
        </div>
      </div>

      <form id="client-profile-form" onSubmit={handleSave}>
        <div className="card" style={{ marginBottom: 16 }}>
          {/* Social avatar: brought over by a VK/Yandex login. */}
          <div className="client-avatar-row">
            <BackendImg
              src={me?.avatar_url}
              alt={me?.name || 'Аватар'}
              className="client-avatar"
              fallbackEmoji="👤"
            />
            <span className="client-avatar-hint">
              {me?.avatar_url
                ? 'Фото из соцсети — обновится при следующем входе'
                : 'Фото появится после входа через VK или Яндекс'}
            </span>
          </div>
          <div className="form-row">
            <div className="form-group">
              <label>Имя *</label>
              <input
                value={firstName}
                onChange={(e) => setFirstName(capitalizeWords(e.target.value))}
                required
                placeholder="Анна"
              />
            </div>
            <div className="form-group">
              <label>Фамилия</label>
              <input
                value={lastName}
                onChange={(e) => setLastName(capitalizeWords(e.target.value))}
                placeholder="Иванова"
              />
            </div>
          </div>
        </div>

        <div className="card" style={{ marginBottom: 16 }}>
          <h3>📍 Где вас искать мастерам</h3>
          {/* One field (owner's ask): city + street in a single picker. The
              city is still stored as city_id for the masters search — a
              DaData pick carries its city, which we resolve to a local id. */}
          <AddressSelect
            value={address}
            onChange={(a, pickedCity, picked) => {
              setAddress(a);
              if (picked && pickedCity) void resolveAddressCity(pickedCity);
            }}
            label="Город, улица, дом"
            placeholder="Начните вводить город, улицу и дом..."
          />
          {(addressCity || city?.name) && (
            <span style={{ fontSize: 12, color: '#666' }}>
              Город для подбора: {addressCity || city?.name}
            </span>
          )}
        </div>
      </form>

      {/* Contact model (1.79.0): all phones/emails with verify flags. */}
      <ContactsCard contacts={me?.contacts ?? []} onChanged={refreshMe} />

      <BindingsCard
        vkBound={me?.vk_bound}
        yandexBound={me?.yandex_bound}
        maxBound={me?.max_bound}
        maxUsername={me?.max_username}
        onChanged={refreshMe}
        onMaxLink={() => setMaxLinkOpen(true)}
      />

      <PasswordCard
        hasPassword={me?.has_password}
        hasEmail={(me?.contacts ?? []).some((c) => c.contact_type === 'email')}
      />

      {/* Save sits at the bottom (owner's ask): outside the form element,
          wired to it through the HTML form= attribute. */}
      <div className="client-profile-actions">
        <button
          type="submit"
          form="client-profile-form"
          className="btn btn-primary"
          disabled={saving}
        >
          {saving ? 'Сохранение…' : 'Сохранить профиль'}
        </button>
      </div>

      {/* MAX link roundtrip: login code flow, then refresh in place. */}
      {maxLinkOpen && (
        <LoginModal
          isOpen
          initialMode="max"
          onClose={() => setMaxLinkOpen(false)}
          onAuthSuccess={refreshMe}
        />
      )}

      <div className="card account-danger-card" style={{ marginTop: 16, borderColor: '#e5484d' }}>
        <h3>🗑 Удаление аккаунта</h3>
        <p style={{ fontSize: 13, color: '#666' }}>
          Профиль деактивируется, контакты стираются, будущие записи отменяются. История хранится
          обезличенной 3 года согласно политике обработки данных.
        </p>
        <button
          type="button"
          className="btn btn-delete"
          disabled={deleting}
          onClick={() => setConfirmDelete(true)}
        >
          {deleting ? 'Удаление…' : 'Удалить мой аккаунт'}
        </button>
      </div>

      <ConfirmDialog
        open={confirmDelete}
        onClose={() => setConfirmDelete(false)}
        title="Удалить аккаунт?"
        message="Вход станет невозможен, будущие записи отменятся. Это действие нельзя отменить."
        confirmLabel="Продолжить"
        danger
        onConfirm={() => {
          setConfirmDelete(false);
          setDeleteWord('');
          setConfirmDeleteStep2(true);
        }}
      />
      <Modal
        open={confirmDeleteStep2}
        onClose={() => setConfirmDeleteStep2(false)}
        title="🗑 Точно удалить?"
      >
        <p style={{ fontSize: 14, color: '#555' }}>
          Последний шаг: введите слово <strong>УДАЛИТЬ</strong>, чтобы подтвердить удаление аккаунта
          и отмену будущих записей.
        </p>
        <div className="form-group" style={{ marginTop: 12 }}>
          <input
            value={deleteWord}
            onChange={(e) => setDeleteWord(e.target.value)}
            placeholder="УДАЛИТЬ"
            aria-label="Подтверждение удаления"
            style={{ textTransform: 'uppercase' }}
          />
        </div>
        <div className="modal-actions">
          <button
            type="button"
            className="btn btn-ghost"
            onClick={() => setConfirmDeleteStep2(false)}
          >
            Отмена
          </button>
          <button
            type="button"
            className="btn btn-delete"
            disabled={deleting || deleteWord.trim().toUpperCase() !== 'УДАЛИТЬ'}
            onClick={() => {
              setConfirmDeleteStep2(false);
              handleDelete();
            }}
          >
            {deleting ? 'Удаление…' : 'Удалить навсегда'}
          </button>
        </div>
      </Modal>
    </div>
  );
}

export default ClientProfilePage;
