import { useCallback, useEffect, useRef, useState } from 'react';
import { useLocation, useNavigate, Link } from 'react-router-dom';
import { toast } from 'sonner';
import { adminApi, assetUrl, authApi } from '../../api/client';
import apiClient from '../../api/http';
import type { ClientContact, MasterDraftData, MasterDraftProfile } from '../../api/client';
import {
  AddressSelect,
  BackendImg,
  ConfirmDialog,
  EmptyState,
  Modal,
  Skeleton,
} from '../../components/common';
import type { CityOption } from '../../components/common/CitySelect';
import { hasHouseNumber } from '../../utils/address';
import { getApiErrorMessage } from '../../utils/apiError';
import { clearAuthCookies, decodeJwtPayload, getCookie } from '../../utils/cookies';
import { imageUploadError } from '../../utils/imageUpload';
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

/** Auth-channel flags shared by /admin/profile and the draft snapshot. */
interface ProfileAuthData {
  has_password?: boolean;
  vk_bound?: boolean;
  yandex_bound?: boolean;
  max_bound?: boolean;
  max_username?: string | null;
  contacts?: ProfileContact[];
}

/** Admin-profile endpoints for ContactsCard (super reuses the cabinet card). */
const ADMIN_CONTACTS_API: ContactsApi = {
  addContact: (data) => adminApi.addProfileContact(data),
  removeContact: (id) => adminApi.removeProfileContact(id),
  makeContactPrimary: (id) => adminApi.makeProfileContactPrimary(id),
  sendContactCode: (id) => adminApi.sendProfileContactCode(id),
  verifyContactCode: (id, code) => adminApi.verifyProfileContactCode(id, code),
};

interface ProfilePageProps {
  /** draft = client fills the same form before activating the master cabinet. */
  mode?: 'master' | 'draft';
}

/** Master personal data: photo, names, contacts, cabinet address, certificates. */
function ProfilePage({ mode = 'master' }: ProfilePageProps) {
  const navigate = useNavigate();
  const location = useLocation();
  const isDraft = mode === 'draft';
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [activating, setActivating] = useState(false);
  const [acceptMasterTerms, setAcceptMasterTerms] = useState(false);
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
  /** City parsed from the address picker, shown as a catalogue hint. */
  const [addressCity, setAddressCity] = useState('');
  const [resolvingCity, setResolvingCity] = useState(false);
  const cityResolveSeq = useRef(0);
  const [avatar, setAvatar] = useState<string | null>(null);
  const [preset, setPreset] = useState<string | null>(null);
  const [certs, setCerts] = useState<Cert[]>([]);
  const [profileId, setProfileId] = useState<number | null>(null);
  const [hasPassword, setHasPassword] = useState(false);
  const [hasEmail, setHasEmail] = useState(false);
  /** Legacy users.phone fallback for the activation checklist. */
  const [profilePhone, setProfilePhone] = useState<string | null>(null);
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
  /** Login landing: open the master panel instead of the client cabinet. */
  const [preferMaster, setPreferMaster] = useState(true);
  /** Super profile: «Имя и фамилия» save (sidebar refresh follows). */
  const [savingNames, setSavingNames] = useState(false);

  /** Superadmin gets a slim profile: auth channels + password + contacts —
      the master-only blocks (photo/certs/reviews/delete) do not apply. */
  const isSuper =
    !isDraft &&
    (() => {
      try {
        return decodeJwtPayload(getCookie('access_token') ?? '')?.is_admin === true;
      } catch {
        return false;
      }
    })();

  const applyAuthFlags = useCallback((data: ProfileAuthData) => {
    setHasPassword(Boolean(data.has_password));
    setVkBound(Boolean(data.vk_bound));
    setYandexBound(Boolean(data.yandex_bound));
    setMaxBound(Boolean(data.max_bound));
    setMaxUsername(data.max_username ?? null);
    const list = data.contacts ?? [];
    setContacts(list);
    setHasEmail(list.some((c) => c.contact_type === 'email'));
  }, []);

  /** Fill the reused form from either the master profile or the draft. */
  const applyProfileData = useCallback(
    (data: MasterDraftProfile) => {
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
      setAddressCity(data.city_name || '');
      setAvatar(data.avatar_url || null);
      setPreset(data.avatar_preset || null);
      setCerts(data.certificates || []);
      setProfileId(data.profile_id ?? null);
      setProfilePhone(data.phone ?? null);
      setPreferMaster(data.prefer_master_cabinet !== false);
      applyAuthFlags(data);
    },
    [applyAuthFlags],
  );

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        if (isDraft) {
          const { data } = await authApi.masterDraft();
          if (cancelled) return;
          if (data.status === 'active') {
            navigate('/admin/profile', { replace: true });
            return;
          }
          applyProfileData(data.profile);
        } else {
          const { data } = await adminApi.getProfile();
          if (cancelled) return;
          applyProfileData(data);
        }
      } catch (err: unknown) {
        toast.error(getApiErrorMessage(err, 'Не удалось загрузить профиль'));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [isDraft, navigate, applyProfileData]);

  /** Light reload for the bind cards (keeps the form drafts untouched). */
  const refreshAuthFlags = async () => {
    try {
      if (isDraft) {
        const { data } = await authApi.masterDraft();
        applyAuthFlags(data.profile);
      } else {
        const { data } = await adminApi.getProfile();
        applyAuthFlags(data);
      }
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
    const fileError = imageUploadError(file);
    if (fileError) {
      toast.error(fileError);
      return null;
    }
    const { data } = isDraft
      ? await authApi.uploadMasterPhoto(file, kind)
      : await adminApi.uploadAvatar(file, kind);
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
      toast.error('Введите название диплома или фото');
      return;
    }
    setCerts((prev) => [...prev, newCertUrl ? { name, url: newCertUrl } : { name }]);
    setNewCertName('');
    setNewCertUrl(undefined);
  };

  /** A typed-but-unadded certificate goes in automatically on save. */
  const collectCerts = (): Cert[] => {
    const draft = newCertName.trim();
    if (draft && !certs.some((c) => c.name === draft)) {
      return [...certs, newCertUrl ? { name: draft, url: newCertUrl } : { name: draft }];
    }
    return certs;
  };

  /** One address field still stores a real city for catalogue filters.
      A DaData pick carries its city; resolve it to a local id (get-or-create
      on the server). Sequence guard keeps the last pick if answers race. */
  const resolveAddressCity = async (name: string) => {
    const seq = ++cityResolveSeq.current;
    setAddressCity(name);
    setResolvingCity(true);
    try {
      const { data } = await apiClient.post('/api/v1/cities/resolve', { name });
      if (seq !== cityResolveSeq.current) return;
      setCity({ id: data.id, name: data.name_ru ?? name, source: 'dadata' });
    } catch {
      if (seq === cityResolveSeq.current) {
        // Keep a city that was already valid for this name; a different one
        // must not stay tied to the new address.
        if (city?.name.trim().toLowerCase() !== name.trim().toLowerCase()) {
          setCity(null);
          setAddressCity('');
        }
        toast.error('Не удалось определить город. Выберите адрес из подсказки ещё раз.');
      }
    } finally {
      if (seq === cityResolveSeq.current) setResolvingCity(false);
    }
  };

  const basePayload = (list: Cert[]): MasterDraftData => ({
    // Empty names are allowed in a draft; the activation gate enforces both.
    name: firstName.trim() || undefined,
    last_name: lastName.trim() || null,
    telegram_username: telegram.trim() || null,
    description: description.trim() || null,
    experience_years: experience.trim() === '' ? null : Number(experience),
    city_id: city?.id ?? undefined,
    cabinet_address: address.trim() || null,
    certificates: list,
    prefer_master_cabinet: preferMaster,
  });

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!isDraft && !firstName.trim()) {
      toast.error('Введите имя');
      return;
    }
    if (resolvingCity) {
      toast.error('Определяем город по адресу — подождите пару секунд');
      return;
    }
    const list = collectCerts();
    setSaving(true);
    try {
      if (isDraft) {
        const { data } = await authApi.saveMasterDraft({
          ...basePayload(list),
          avatar_url: preset ? null : avatar,
          avatar_preset: preset,
        });
        applyProfileData(data.profile);
        toast.success('Черновик сохранён');
      } else {
        const { data } = await adminApi.updateProfile({
          ...basePayload(list),
          avatar_preset: preset,
        });
        // Converge with the server (it echoes the saved profile).
        setCerts(data?.certificates || list);
        toast.success('Профиль сохранён');
      }
      setCerts(list);
      setNewCertName('');
      setNewCertUrl(undefined);
    } catch (err: unknown) {
      toast.error(
        getApiErrorMessage(
          err,
          isDraft ? 'Не удалось сохранить черновик' : 'Не удалось сохранить профиль',
        ),
      );
    } finally {
      setSaving(false);
    }
  };

  const handleActivate = async () => {
    if (!isDraft || activating) return;
    if (!acceptMasterTerms) {
      toast.error('Подтвердите принятие условий для мастеров');
      return;
    }
    if (resolvingCity) {
      toast.error('Определяем город по адресу — подождите пару секунд');
      return;
    }
    if (!hasHouseNumber(address)) {
      toast.error('Укажите адрес кабинета с номером дома');
      return;
    }
    const list = collectCerts();
    setActivating(true);
    try {
      await authApi.activateMaster({
        ...basePayload(list),
        avatar_url: preset ? null : avatar,
        avatar_preset: preset,
        accept_master_terms: true,
      });
      toast.success('Кабинет мастера активирован');
      // Hard navigation: the activation response already set the MASTER
      // access cookie; the admin layout then loads with the new role.
      window.location.assign('/admin/profile');
    } catch (err: unknown) {
      toast.error(getApiErrorMessage(err, 'Не удалось активировать кабинет мастера'));
    } finally {
      setActivating(false);
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

  // The same five conditions the backend checks at activation. The email
  // item is green only for a VERIFIED contact — merely having a row is not
  // enough (owner review 1.83.0).
  const draftChecklist = [
    {
      key: 'names',
      label: 'Имя и фамилия',
      done: Boolean(firstName.trim() && lastName.trim()),
    },
    {
      key: 'cabinet_address',
      label: 'Адрес кабинета с номером дома',
      done: hasHouseNumber(address),
    },
    {
      key: 'phone',
      label: 'Телефон добавлен',
      done: contacts.some((c) => c.contact_type === 'phone') || Boolean(profilePhone),
    },
    {
      key: 'verified_email',
      label: 'Почта подтверждена',
      done: contacts.some((c) => c.contact_type === 'email' && c.is_verified),
    },
    {
      key: 'social',
      label: 'Привязана соцсеть (VK ID, Яндекс или MAX)',
      done: vkBound || yandexBound || maxBound,
    },
  ];
  const canActivate = draftChecklist.every((item) => item.done);

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
          <h1>{isDraft ? '🎨 Профиль мастера' : '👤 Мой профиль'}</h1>
          <p>
            {isDraft
              ? 'Кабинет мастера неактивен. Заполните профиль — он активируется сразу, как только будут выполнены все условия.'
              : 'Личные данные, фото, адрес кабинета, дипломы и рабочее место'}
          </p>
        </div>
      </div>

      {isDraft && (
        <div className={`card profile-activation-card${canActivate ? ' ready' : ''}`}>
          <div className="profile-activation-head">
            <div>
              <h3>Активация кабинета мастера</h3>
              <p className="profile-card-hint">
                Кабинет пока неактивен, поэтому вы остаётесь клиентом. Проверьте условия и нажмите
                кнопку — одобрение администратора не требуется.
              </p>
            </div>
            <span className={`profile-activation-badge${canActivate ? ' ready' : ''}`}>
              {canActivate ? 'Всё готово' : 'Неактивен'}
            </span>
          </div>
          <ul className="profile-activation-list">
            {draftChecklist.map((item) => (
              <li key={item.key} className={item.done ? 'done' : 'pending'}>
                <span className="profile-check" aria-hidden="true">
                  {item.done ? '✓' : '○'}
                </span>
                <span>{item.label}</span>
              </li>
            ))}
          </ul>
          <label className="profile-terms-check">
            <input
              type="checkbox"
              checked={acceptMasterTerms}
              onChange={(event) => setAcceptMasterTerms(event.target.checked)}
            />
            <span>
              Я принимаю{' '}
              <Link to="/offer#master-terms" target="_blank" rel="noreferrer">
                условия для мастеров
              </Link>{' '}
              и{' '}
              <Link to="/offer" target="_blank" rel="noreferrer">
                публичную оферту
              </Link>
              . Версия документа и дата принятия сохраняются.
            </span>
          </label>
          <button
            type="button"
            className="btn btn-primary"
            disabled={!canActivate || !acceptMasterTerms || activating || resolvingCity}
            onClick={handleActivate}
          >
            {activating
              ? 'Активируем…'
              : resolvingCity
                ? 'Определяем город…'
                : 'Активировать кабинет'}
          </button>
          {!canActivate && (
            <p className="profile-card-hint" style={{ marginBottom: 0 }}>
              Кнопка станет активной, когда все пункты будут отмечены.
            </p>
          )}
          {canActivate && !acceptMasterTerms && (
            <p className="profile-card-hint" style={{ marginBottom: 0 }}>
              Отметьте принятие условий для мастеров, чтобы активировать кабинет.
            </p>
          )}
        </div>
      )}

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
                accept="image/*,.heic,.heif"
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
              <div className="hint">
                JPEG, PNG, WebP или HEIC до 15 МБ — или выберите зверя ниже
              </div>
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
              <label>Имя{isDraft ? '' : ' *'}</label>
              <input
                value={firstName}
                onChange={(e) => setFirstName(capitalizeWords(e.target.value))}
                required={!isDraft}
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
          <h3>📍 Адрес кабинета</h3>
          <AddressSelect
            value={address}
            onChange={(nextAddress, pickedCity, picked) => {
              setAddress(nextAddress);
              if (picked && pickedCity) {
                void resolveAddressCity(pickedCity);
              } else if (!nextAddress.trim()) {
                cityResolveSeq.current += 1;
                setCity(null);
                setAddressCity('');
                setResolvingCity(false);
              }
            }}
            label="Город, улица и дом"
            placeholder="Начните вводить город, улицу и дом..."
            style={{ width: '100%' }}
          />
          <p className="profile-card-hint" style={{ margin: '8px 0 0' }}>
            Город определится автоматически из выбранного адреса и сохранится для каталога.
          </p>
          {addressCity && (
            <p className="profile-card-hint" style={{ margin: '4px 0 0' }}>
              Определён город: <strong>{addressCity}</strong>
              {resolvingCity ? ' — привязываем…' : ' — сохранится для каталога.'}
            </p>
          )}
          {address.trim() && !hasHouseNumber(address) && (
            <p className="profile-card-hint" style={{ margin: '6px 0 0', color: '#b45309' }}>
              Добавьте номер дома — без него адрес кабинета не засчитается для активации.
            </p>
          )}
          <label className="profile-prefer-master">
            <input
              type="checkbox"
              checked={preferMaster}
              onChange={(e) => setPreferMaster(e.target.checked)}
            />
            <span>После входа открывать панель мастера, а не кабинет клиента</span>
          </label>
        </div>

        <div className="card" style={{ marginBottom: 16 }}>
          <h3>Дипломы, сертификаты и рабочее место</h3>
          <p className="profile-card-hint">
            Добавьте дипломы, сертификаты или фото кабинета — это необязательно, можно вернуться к
            этому позже.
          </p>
          {certs.length === 0 ? (
            <EmptyState title="Пока нет дипломов и фото" icon="🎓" />
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
                    title="Убрать диплом или фото"
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
                alt="Новое фото диплома или рабочего места"
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
              placeholder="Диплом, сертификат или фото кабинета"
            />
            <input
              ref={certInput}
              type="file"
              accept="image/*,.heic,.heif"
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
              title="Фото диплома или рабочего места (необязательно)"
            >
              {uploadingCert ? '…' : newCertUrl ? '✓ Фото есть' : '📷 Фото'}
            </button>
            <button type="button" className="btn btn-secondary btn-sm" onClick={addCert}>
              + Добавить
            </button>
          </div>
        </div>

        <div className="form-actions">
          <button type="submit" className="btn btn-primary" disabled={saving || resolvingCity}>
            {saving
              ? 'Сохранение…'
              : resolvingCity
                ? 'Определяем город…'
                : isDraft
                  ? 'Сохранить черновик'
                  : 'Сохранить профиль'}
          </button>
        </div>
      </form>

      {/* Master login is social-only: bind VK/Yandex/MAX; no password card. */}
      <BindingsCard
        socialOnly
        vkBound={vkBound}
        yandexBound={yandexBound}
        maxBound={maxBound}
        maxUsername={maxUsername}
        onChanged={refreshAuthFlags}
        onMaxLink={() => setMaxLinkOpen(true)}
      />

      {/* Contacts stay editable after activation: the draft uses the client
          cabinet API, an active master the admin-profile API. */}
      <ContactsCard
        contacts={contacts}
        onChanged={refreshAuthFlags}
        api={isDraft ? undefined : ADMIN_CONTACTS_API}
      />

      {!isDraft && (
        <>
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
        </>
      )}

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
