import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { authApi, cabinetApi, type ClientMe } from '../../api/client';
import {
  AddressSelect,
  BackendImg,
  CitySelect,
  ConfirmDialog,
  Modal,
  Skeleton,
} from '../../components/common';
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

      <form onSubmit={handleSave}>
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
          <div className="form-row">
            <div className="form-group">
              <label>Телефон</label>
              <input value={me?.phone || ''} disabled className="input-disabled" />
            </div>
            <div className="form-group">
              <label>Email</label>
              <input value={me?.email || '—'} disabled className="input-disabled" />
            </div>
          </div>
          {me?.max_bound && (
            /* MAX chat-bot binding: quick login channel + @nickname for support. */
            <p style={{ fontSize: 13, color: '#666', margin: '4px 0 0' }}>
              ✅ Вход через MAX включён
              {me.max_username ? ` (@${me.max_username})` : ''}
            </p>
          )}
          {me?.vk_bound && (
            /* VK ID binding: login via the VK/OK/Mail widget. */
            <p style={{ fontSize: 13, color: '#666', margin: '4px 0 0' }}>
              ✅ Вход через VK включён
            </p>
          )}
          {me?.yandex_bound && (
            /* Yandex ID binding: login via the Yandex redirect. */
            <p style={{ fontSize: 13, color: '#666', margin: '4px 0 0' }}>
              ✅ Вход через Яндекс включён
            </p>
          )}
        </div>

        <div className="card" style={{ marginBottom: 16 }}>
          <h3>📍 Где вас искать мастерам</h3>
          <div className="form-row">
            <CitySelect
              value={city?.id ?? null}
              valueName={city?.name ?? ''}
              onChange={(c) => {
                setCity(c);
                if (c) setAddressCity(c.name);
              }}
            />
            <AddressSelect
              value={address}
              onChange={(a, pickedCity) => {
                setAddress(a);
                if (pickedCity) setAddressCity(pickedCity);
              }}
              label="Ваш адрес"
              placeholder="Город, улица, дом..."
            />
          </div>
          {(addressCity || city?.name) && (
            <span style={{ fontSize: 12, color: '#666' }}>
              Город для подбора: {addressCity || city?.name}
            </span>
          )}
        </div>

        <div className="form-actions">
          <button type="submit" className="btn btn-primary" disabled={saving}>
            {saving ? 'Сохранение…' : 'Сохранить профиль'}
          </button>
        </div>
      </form>

      <div className="card" style={{ marginTop: 16, borderColor: '#e5484d' }}>
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
