import { useEffect, useRef, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { adminApi, assetUrl, authApi } from '../../api/client';
import type { ClientContact } from '../../api/cabinet';
import {
  AddressSelect,
  BackendImg,
  CitySelect,
  ConfirmDialog,
  EmptyState,
  Modal,
  Skeleton,
} from '../../components/common';
import type { CityOption } from '../../components/common/CitySelect';
import { getApiErrorMessage } from '../../utils/apiError';
import { clearAuthCookies, decodeJwtPayload, getCookie } from '../../utils/cookies';
import { capitalizeWords, splitFullName } from '../../utils/names';
import { MasterReviews } from '../../components/reviews';
import { BindingsCard, PasswordCard, ContactsCard } from '../../components/profile';
import type { ContactsApi } from '../../components/profile/ContactsCard';
import LoginModal from '../../components/LoginModal';
import './ProfilePage.css';

interface Cert {
  name: string;
  url?: string;
}

/** Built-in avatars (mirror of backend AVATAR_PRESETS): photo or preset. */
const AVATAR_PRESETS = [
  '🐱',
  '🐶',
  '🐥',
  '🦅',
  '🦊',
  '🐼',
  '🐸',
  '🦁',
  '🐯',
  '🐰',
  '🐷',
  '🐮',
  '🐵',
  '🐔',
  '🦄',
  '🐙',
];

/** Contact row of GET /admin/profile — the cabinet contact shape. */
type ProfileContact = ClientContact;

/** Admin-profile endpoints for ContactsCard (super reuses the cabinet card). */
const ADMIN_CONTACTS_API: ContactsApi = {
  addContact: (data) => adminApi.addProfileContact(data),
  removeContact: (id) => adminApi.removeProfileContact(id),
  makeContactPrimary: (id) => adminApi.makeProfileContactPrimary(id),
  sendContactCode: (id) => adminApi.sendProfileContactCode(id),
  verifyContactCode: (id, code) => adminApi.verifyProfileContactCode(id, code),
};

/** Master personal data: photo, names, contacts, city, cabinet, certificates. */
function ProfilePage() {
  const navigate = useNavigate();
  const location = useLocation();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [confirmDeleteStep2, setConfirmDeleteStep2] = useState(false);
  const [deleteWord, setDeleteWord] = useState('');
  const [uploading, setUploading] = useState(false);
  const [firstName, setFirstName] = useState('');
  const [lastName, setLastName] = useState('');
  const [telegram, setTelegram] = useState('');
  const [description, setDescription] = useState('');
  const [experience, setExperience] = useState('');
  const [city, setCity] = useState<CityOption | null>(null);
  const [address, setAddress] = useState('');
  const [avatar, setAvatar] = useState<string | null>(null);
  const [preset, setPreset] = useState<string | null>(null);
  const [certs, setCerts] = useState<Cert[]>([]);
  const [profileId, setProfileId] = useState<number | null>(null);
  const [hasPassword, setHasPassword] = useState(false);
  const [hasEmail, setHasEmail] = useState(false);
  const [vkBound, setVkBound] = useState(false);
  const [yandexBound, setYandexBound] = useState(false);
  const [maxBound, setMaxBound] = useState(false);
  const [maxUsername, setMaxUsername] = useState<string | null>(null);
  /** «Привязать MAX» opens the login modal in its MAX-code mode. */
  const [maxLinkOpen, setMaxLinkOpen] = useState(false);
  const [newCertName, setNewCertName] = useState('');
  const [newCertUrl, setNewCertUrl] = useState<string | undefined>(undefined);
  const [uploadingCert, setUploadingCert] = useState(false);
  const avatarInput = useRef<HTMLInputElement>(null);
  const certInput = useRef<HTMLInputElement>(null);
  const [contacts, setContacts] = useState<ProfileContact[]>([]);
  /** Super profile: «Имя и фамилия» save (sidebar refresh follows). */
  const [savingNames, setSavingNames] = useState(false);

  /** Superadmin gets a slim profile: auth channels + password + contacts —
      the master-only blocks (photo/certs/reviews/delete) do not apply. */
  const isSuper = (() => {
    try {
      return decodeJwtPayload(getCookie('access_token') ?? '')?.is_admin === true;
    } catch {
      return false;
    }
  })();

  const applyAuthFlags = (data: {
    has_password?: boolean;
    vk_bound?: boolean;
    yandex_bound?: boolean;
    max_bound?: boolean;
    max_username?: string | null;
    contacts?: ProfileContact[];
  }) => {
    setHasPassword(Boolean(data.has_password));
    setVkBound(Boolean(data.vk_bound));
    setYandexBound(Boolean(data.yandex_bound));
    setMaxBound(Boolean(data.max_bound));
    setMaxUsername(data.max_username ?? null);
    const list = data.contacts ?? [];
    setContacts(list);
    setHasEmail(list.some((c) => c.contact_type === 'email'));
  };

  useEffect(() => {
    (async () => {
      try {
        const { data } = await adminApi.getProfile();
        const [first, rest] = splitFullName(data.name || '');
        setFirstName(first);
        setLastName(data.last_name || rest);
        setTelegram(data.telegram_username || '');
        setDescription(data.description || '');
        setExperience(data.experience_years != null ? String(data.experience_years) : '');
        setCity(
          data.city_id != null
            ? { id: data.city_id, name: data.city_name || '', source: 'local' }
            : null,
        );
        setAddress(data.cabinet_address || '');
        setAvatar(data.avatar_url || null);
        setPreset(data.avatar_preset || null);
        setCerts(data.certificates || []);
        setProfileId(data.profile_id ?? null);
        applyAuthFlags(data);
      } catch (err: unknown) {
        toast.error(getApiErrorMessage(err, 'Не удалось загрузить профиль'));
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  /** Light reload for the bind cards (keeps the form drafts untouched). */
  const refreshAuthFlags = async () => {
    try {
      const { data } = await adminApi.getProfile();
      applyAuthFlags(data);
    } catch {
      /* ignore — the next full reload recovers */
    }
  };

  /** Super profile: save «Имя и фамилия»; the fresh token updates the
      sidebar in place (BaseLayout listens for auth:user-updated). */
  const saveNames = async (e: React.FormEvent) => {
    e.preventDefault();
    const first = capitalizeWords(firstName).trim();
    if (!first) {
      toast.error('Введите имя');
      return;
    }
    setSavingNames(true);
    try {
      await adminApi.updateProfile({ name: first, last_name: lastName.trim() });
      try {
        await authApi.refreshSession();
      } catch {
        /* старый токен остаётся валидным — имя появится после следующего входа */
      }
      window.dispatchEvent(new Event('auth:user-updated'));
      setFirstName(first);
      toast.success('Имя сохранено');
    } catch (err: unknown) {
      toast.error(getApiErrorMessage(err, 'Не удалось сохранить имя'));
    } finally {
      setSavingNames(false);
    }
  };

  // Sidebar rating badge jumps here (#reviews).
  useEffect(() => {
    if (location.hash === '#reviews') {
      const t = setTimeout(() => {
        document.getElementById('reviews')?.scrollIntoView({ behavior: 'smooth' });
      }, 300);
      return () => clearTimeout(t);
    }
  }, [location.hash, loading]);

  const uploadFile = async (file: File, kind: 'avatar' | 'cert'): Promise<string | null> => {
    if (!/^image\/(jpeg|png|webp)$/.test(file.type)) {
      toast.error('Только JPEG, PNG или WebP');
      return null;
    }
    if (file.size > 5 * 1024 * 1024) {
      toast.error('Файл больше 5 МБ');
      return null;
    }
    const { data } = await adminApi.uploadAvatar(file, kind);
    return data.avatar_url;
  };

  const handleAvatarPick = async (file: File | undefined) => {
    if (!file) return;
    setUploading(true);
    try {
      const url = await uploadFile(file, 'avatar');
      if (url) {
        setAvatar(url);
        setPreset(null);
        toast.success('Фото обновлено');
      }
    } catch (err: unknown) {
      toast.error(getApiErrorMessage(err, 'Не удалось загрузить фото'));
    } finally {
      setUploading(false);
    }
  };

  const pickPreset = (emoji: string) => {
    // Preset replaces the uploaded photo (backend enforces the same).
    setPreset(emoji);
    setAvatar(null);
  };

  const handleCertPhoto = async (file: File | undefined) => {
    if (!file) return;
    setUploadingCert(true);
    try {
      // kind=cert: standalone file, never touches the profile photo.
      const url = await uploadFile(file, 'cert');
      if (url) setNewCertUrl(url);
    } catch (err: unknown) {
      toast.error(getApiErrorMessage(err, 'Не удалось загрузить фото'));
    } finally {
      setUploadingCert(false);
    }
  };

  const addCert = () => {
    const name = newCertName.trim();
    if (!name) {
      toast.error('Введите название сертификата');
      return;
    }
    setCerts((prev) => [...prev, newCertUrl ? { name, url: newCertUrl } : { name }]);
    setNewCertName('');
    setNewCertUrl(undefined);
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!firstName.trim()) {
      toast.error('Введите имя');
      return;
    }
    // A typed-but-unadded draft (name + optional photo, "+ Добавить" not
    // pressed) goes in automatically — otherwise it silently vanishes.
    let list = certs;
    const draft = newCertName.trim();
    if (draft && !certs.some((c) => c.name === draft)) {
      list = [...certs, newCertUrl ? { name: draft, url: newCertUrl } : { name: draft }];
    }
    setSaving(true);
    try {
      const { data } = await adminApi.updateProfile({
        name: firstName.trim(),
        last_name: lastName.trim() || null,
        telegram_username: telegram.trim() || null,
        description: description.trim() || null,
        experience_years: experience.trim() === '' ? null : Number(experience),
        city_id: city?.id ?? null,
        cabinet_address: address.trim() || null,
        certificates: list,
        avatar_preset: preset,
      });
      // Converge with the server (it echoes the saved profile).
      setCerts(data?.certificates || list);
      setNewCertName('');
      setNewCertUrl(undefined);
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
      const { data } = await adminApi.deleteMyProfile();
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
      <div className="profile-page">
        <Skeleton rows={6} />
      </div>
    );
  }

  if (isSuper) {
    return (
      <div className="profile-page">
        <div className="page-header">
          <div>
            <h1>👤 Мой профиль</h1>
            <p>Способы входа, пароль и контакты суперпользователя</p>
          </div>
        </div>

        <div className="card" style={{ marginBottom: 16 }}>
          <h3>👤 Имя и фамилия</h3>
          <p className="profile-card-hint">
            Показывается в сайдбаре и журнале действий. После сохранения сайдбар обновится сразу.
          </p>
          <form onSubmit={saveNames}>
            <div className="form-row">
              <div className="form-group">
                <label>Имя *</label>
                <input
                  value={firstName}
                  onChange={(e) => setFirstName(capitalizeWords(e.target.value))}
                  placeholder="Иван"
                  required
                />
              </div>
              <div className="form-group">
                <label>Фамилия</label>
                <input
                  value={lastName}
                  onChange={(e) => setLastName(capitalizeWords(e.target.value))}
                  placeholder="Петров"
                />
              </div>
            </div>
            <button type="submit" className="btn btn-primary" disabled={savingNames}>
              {savingNames ? 'Сохраняем…' : 'Сохранить'}
            </button>
          </form>
        </div>

        <BindingsCard
          vkBound={vkBound}
          yandexBound={yandexBound}
          maxBound={maxBound}
          maxUsername={maxUsername}
          onChanged={refreshAuthFlags}
          onMaxLink={() => setMaxLinkOpen(true)}
        />

        <PasswordCard hasPassword={hasPassword} hasEmail={hasEmail} />

        <ContactsCard contacts={contacts} onChanged={refreshAuthFlags} api={ADMIN_CONTACTS_API} />

        {/* MAX link roundtrip: login code flow, then refresh in place. */}
        {maxLinkOpen && (
          <LoginModal
            isOpen
            initialMode="max"
            onClose={() => setMaxLinkOpen(false)}
            onAuthSuccess={refreshAuthFlags}
          />
        )}
      </div>
    );
  }

  return (
    <div className="profile-page">
      <div className="page-header">
        <div>
          <h1>👤 Мой профиль</h1>
          <p>Личные данные, фото, адрес кабинета и сертификаты</p>
        </div>
      </div>

      <form onSubmit={handleSave}>
        <div className="card" style={{ marginBottom: 16 }}>
          <h3>Фото и имя</h3>
          <div className="profile-photo-row">
            {preset ? (
              <div className="profile-photo profile-photo-emoji" role="img" aria-label="Аватар">
                {preset}
              </div>
            ) : avatar ? (
              <BackendImg
                src={assetUrl(avatar)}
                alt="Фото мастера"
                className="profile-photo"
                fallbackEmoji="📷"
              />
            ) : (
              <div className="profile-photo profile-photo-empty">📷</div>
            )}
            <div>
              <input
                ref={avatarInput}
                type="file"
                accept="image/jpeg,image/png,image/webp"
                style={{ display: 'none' }}
                onChange={(e) => {
                  handleAvatarPick(e.target.files?.[0]);
                  e.target.value = '';
                }}
              />
              <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 8 }}>
                <button
                  type="button"
                  className="btn btn-ghost"
                  disabled={uploading}
                  onClick={() => avatarInput.current?.click()}
                >
                  {uploading ? 'Загрузка…' : avatar ? 'Сменить фото' : 'Добавить фото'}
                </button>
                {(avatar || preset) && (
                  <button
                    type="button"
                    className="btn btn-ghost btn-sm"
                    onClick={() => {
                      setAvatar(null);
                      setPreset(null);
                    }}
                    title="Убрать фото и пресет"
                  >
                    ✕
                  </button>
                )}
              </div>
              <div className="hint">JPEG, PNG или WebP до 5 МБ — или выберите зверя ниже</div>
              <div className="preset-grid" role="group" aria-label="Стандартные аватары">
                {AVATAR_PRESETS.map((emoji) => (
                  <button
                    key={emoji}
                    type="button"
                    className={`preset-btn${preset === emoji ? ' picked' : ''}`}
                    onClick={() => pickPreset(emoji)}
                    title="Выбрать этот аватар"
                  >
                    {emoji}
                  </button>
                ))}
              </div>
            </div>
          </div>
          <div className="form-row">
            <div className="form-group">
              <label>Имя *</label>
              <input
                value={firstName}
                onChange={(e) => setFirstName(capitalizeWords(e.target.value))}
                required
                placeholder="Иван"
              />
            </div>
            <div className="form-group">
              <label>Фамилия</label>
              <input
                value={lastName}
                onChange={(e) => setLastName(capitalizeWords(e.target.value))}
                placeholder="Петров"
              />
            </div>
          </div>
          <div className="form-row">
            <div className="form-group">
              <label>Telegram</label>
              <input
                value={telegram}
                onChange={(e) => setTelegram(e.target.value)}
                placeholder="@username"
              />
            </div>
            <div className="form-group">
              <label>Опыт (лет)</label>
              <input
                type="number"
                min={0}
                max={80}
                value={experience}
                onChange={(e) => setExperience(e.target.value)}
                placeholder="5"
              />
            </div>
          </div>
          <div className="form-group">
            <label>О себе</label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
              placeholder="Специализация, подход к работе..."
            />
          </div>
        </div>

        <div className="card" style={{ marginBottom: 16 }}>
          <h3>Город и кабинет</h3>
          <div className="form-row">
            <CitySelect value={city?.id ?? null} valueName={city?.name ?? ''} onChange={setCity} />
            <AddressSelect value={address} onChange={setAddress} />
          </div>
        </div>

        <div className="card" style={{ marginBottom: 16 }}>
          <h3>Дипломы и сертификаты</h3>
          {certs.length === 0 ? (
            <EmptyState title="Пока нет сертификатов" icon="🎓" />
          ) : (
            <div className="cert-list">
              {certs.map((c, i) => (
                <div key={`${c.name}-${i}`} className="cert-item">
                  {c.url && (
                    <a
                      href={assetUrl(c.url) || ''}
                      target="_blank"
                      rel="noreferrer"
                      title="Открыть фото"
                    >
                      <BackendImg src={assetUrl(c.url)} alt={c.name} className="cert-thumb" />
                    </a>
                  )}
                  <span className="cert-name">{c.name}</span>
                  <button
                    type="button"
                    className="btn btn-sm btn-delete"
                    onClick={() => setCerts((prev) => prev.filter((_, j) => j !== i))}
                    title="Убрать сертификат"
                  >
                    ✖
                  </button>
                </div>
              ))}
            </div>
          )}
          {newCertUrl ? (
            <div className="cert-draft">
              <BackendImg
                src={assetUrl(newCertUrl)}
                alt="Новое фото сертификата"
                className="cert-thumb"
              />
              <span className="cert-name">
                {newCertName.trim() || 'Без названия'} — добавится при сохранении
              </span>
            </div>
          ) : null}
          <div className="cert-add">
            <input
              value={newCertName}
              onChange={(e) => setNewCertName(e.target.value)}
              placeholder="Название сертификата"
            />
            <input
              ref={certInput}
              type="file"
              accept="image/jpeg,image/png,image/webp"
              style={{ display: 'none' }}
              onChange={(e) => {
                handleCertPhoto(e.target.files?.[0]);
                e.target.value = '';
              }}
            />
            <button
              type="button"
              className="btn btn-ghost btn-sm"
              disabled={uploadingCert}
              onClick={() => certInput.current?.click()}
              title="Фото диплома (необязательно)"
            >
              {uploadingCert ? '…' : newCertUrl ? '✓ Фото есть' : '📷 Фото'}
            </button>
            <button type="button" className="btn btn-secondary btn-sm" onClick={addCert}>
              + Добавить
            </button>
          </div>
        </div>

        <div className="form-actions">
          <button type="submit" className="btn btn-primary" disabled={saving}>
            {saving ? 'Сохранение…' : 'Сохранить профиль'}
          </button>
        </div>
      </form>

      {/* Auth channels (1.79.0): bind socials, change password. */}
      <BindingsCard
        vkBound={vkBound}
        yandexBound={yandexBound}
        maxBound={maxBound}
        maxUsername={maxUsername}
        onChanged={refreshAuthFlags}
        onMaxLink={() => setMaxLinkOpen(true)}
      />

      <PasswordCard hasPassword={hasPassword} hasEmail={hasEmail} />

      <div className="card" id="reviews" style={{ marginTop: 16, scrollMarginTop: 12 }}>
        <h3>⭐ Мои отзывы и оценки</h3>
        <p style={{ fontSize: 13, color: '#666' }}>
          Средний рейтинг виден клиентам при записи. Отзыв появляется здесь сразу после оценки
          визита.
        </p>
        <MasterReviews profileId={profileId} />
      </div>

      <div className="card" style={{ marginTop: 16, borderColor: '#e5484d' }}>
        <h3>🗑 Удаление аккаунта</h3>{' '}
        <p style={{ fontSize: 13, color: '#666' }}>
          Профиль снимется с публикации, контакты сотрутся, будущие записи клиентов отменятся.
          История хранится обезличенной 3 года согласно политике обработки данных.
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

      {/* MAX link roundtrip: login code flow, then refresh in place. */}
      {maxLinkOpen && (
        <LoginModal
          isOpen
          initialMode="max"
          onClose={() => setMaxLinkOpen(false)}
          onAuthSuccess={refreshAuthFlags}
        />
      )}

      <ConfirmDialog
        open={confirmDelete}
        onClose={() => setConfirmDelete(false)}
        title="Удалить аккаунт?"
        message="Профиль исчезнет из каталога, вход станет невозможен. Это действие нельзя отменить."
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
          и отмену будущих записей клиентов.
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

export default ProfilePage;
