import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import {
  assetUrl,
  authApi,
  cabinetApi,
  type ClientMe,
  type MasterApplicationData,
} from '../../api/client';
import apiClient from '../../api/http';
import { AddressSelect, BackendImg, Skeleton } from '../../components/common';
import { ContactsCard } from '../../components/profile';
import type { CityOption } from '../../components/common/CitySelect';
import { getApiErrorMessage } from '../../utils/apiError';
import { capitalizeWords, splitFullName } from '../../utils/names';
import '../admin/ProfilePage.css';
import './BecomeMasterPage.css';

const EMPTY_APP: MasterApplicationData | null = null;

/**
 * Master application (owner review 1.82.0): the full master profile is
 * filled in before applying — names, verified contacts, cabinet address,
 * optionally a photo and certificates. The profile is created INACTIVE and
 * opens the panel only after a superadmin approves it.
 *
 * Requirements mirror the backend: at least one phone AND one email on the
 * account, one of them verified (social login / emailed code), and a
 * password or a social binding as the login channel.
 */
function BecomeMasterPage() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [status, setStatus] = useState<'none' | 'pending' | 'active'>('none');
  const [application, setApplication] = useState<MasterApplicationData | null>(EMPTY_APP);
  const [me, setMe] = useState<ClientMe | null>(null);

  const [firstName, setFirstName] = useState('');
  const [lastName, setLastName] = useState('');
  const [address, setAddress] = useState('');
  const [city, setCity] = useState<CityOption | null>(null);
  const [description, setDescription] = useState('');
  const [experience, setExperience] = useState('');
  const [telegram, setTelegram] = useState('');
  const [avatar, setAvatar] = useState<string | null>(null);
  const [uploadingAvatar, setUploadingAvatar] = useState(false);
  const [preferMaster, setPreferMaster] = useState(true);
  const [sending, setSending] = useState(false);

  const [certs, setCerts] = useState<{ name: string; url?: string }[]>([]);
  const [newCertName, setNewCertName] = useState('');
  const [newCertUrl, setNewCertUrl] = useState<string | undefined>();
  const [uploadingCert, setUploadingCert] = useState(false);

  const avatarInput = useRef<HTMLInputElement>(null);
  const certInput = useRef<HTMLInputElement>(null);

  const refreshMe = async () => {
    try {
      const { data } = await cabinetApi.me();
      setMe(data);
    } catch {
      /* keep the previous contacts — the form stays usable */
    }
  };

  useEffect(() => {
    (async () => {
      try {
        const [{ data: meData }, appResult] = await Promise.all([
          cabinetApi.me(),
          authApi.masterApplication().catch(() => null),
        ]);
        setMe(meData);
        const [first, rest] = splitFullName(meData.name || '');
        setFirstName(first);
        setLastName(meData.last_name || rest);
        setCity(
          meData.city_id != null
            ? { id: meData.city_id, name: meData.city_name || '', source: 'local' }
            : null,
        );
        setAddress(meData.address || '');
        setAvatar(meData.avatar_url || null);

        const app = appResult?.data;
        if (app && app.status !== 'none' && app.application) {
          setStatus(app.status);
          setApplication(app.application);
          const [aFirst, aRest] = splitFullName(app.application.name || '');
          setFirstName(aFirst);
          setLastName(app.application.last_name || aRest);
          setAddress(app.application.cabinet_address || '');
          setDescription(app.application.description || '');
          setExperience(
            app.application.experience_years != null
              ? String(app.application.experience_years)
              : '',
          );
          setTelegram(app.application.telegram_username || '');
          setAvatar(app.application.avatar_url || meData.avatar_url || null);
          setCerts(app.application.certificates || []);
          setPreferMaster(app.application.prefer_master_cabinet !== false);
        }
      } catch (err: unknown) {
        toast.error(getApiErrorMessage(err, 'Не удалось загрузить профиль'));
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  /** DaData pick carries the city: resolve it to a local id, like the
      client profile does, so masters can be filtered by city. */
  const resolveCity = async (name: string) => {
    try {
      const { data } = await apiClient.post('/api/v1/cities/resolve', { name });
      setCity({ id: data.id, name: data.name_ru ?? name, source: 'dadata' });
    } catch {
      /* keep the previous city — the address still saves */
    }
  };

  const uploadImage = async (file: File, kind: 'avatar' | 'cert'): Promise<string | null> => {
    if (!/^image\/(jpeg|png|webp)$/.test(file.type)) {
      toast.error('Только JPEG, PNG или WebP');
      return null;
    }
    if (file.size > 5 * 1024 * 1024) {
      toast.error('Файл больше 5 МБ');
      return null;
    }
    const { data } = await authApi.uploadMasterPhoto(file, kind);
    return data.avatar_url;
  };

  const handleAvatarPick = async (file: File | undefined) => {
    if (!file) return;
    setUploadingAvatar(true);
    try {
      const url = await uploadImage(file, 'avatar');
      if (url) {
        setAvatar(url);
        toast.success('Фото загружено');
      }
    } catch (err: unknown) {
      toast.error(getApiErrorMessage(err, 'Не удалось загрузить фото'));
    } finally {
      setUploadingAvatar(false);
    }
  };

  const handleCertPhoto = async (file: File | undefined) => {
    if (!file) return;
    setUploadingCert(true);
    try {
      const url = await uploadImage(file, 'cert');
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

  const contacts = me?.contacts ?? [];
  const phones = contacts.filter((c) => c.contact_type === 'phone');
  const emails = contacts.filter((c) => c.contact_type === 'email');
  // Legacy accounts may still carry the phone/email only in the old
  // columns; the backend accepts those too, so the checklist must match.
  const hasPhone = phones.length > 0 || Boolean(me?.phone);
  const hasEmail = emails.length > 0 || Boolean(me?.email);
  const hasVerifiedContact =
    contacts.some((c) => c.is_verified) || Boolean(me?.is_verified && hasEmail);
  const canLogin = Boolean(me?.has_password || me?.vk_bound || me?.yandex_bound || me?.max_bound);

  const checklist = [
    {
      ok: firstName.trim() !== '' && lastName.trim() !== '',
      label: 'Имя и фамилия',
    },
    { ok: address.trim() !== '', label: 'Адрес кабинета' },
    { ok: hasPhone, label: 'Телефон в контактах' },
    { ok: hasEmail, label: 'Почта в контактах' },
    {
      ok: hasVerifiedContact,
      label: 'Один контакт подтверждён (соцсеть или код)',
    },
    { ok: canLogin, label: 'Вход по паролю или через соцсеть' },
  ];
  const ready = checklist.every((item) => item.ok);
  const parsedExperience = experience.trim() === '' ? null : Number(experience);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!firstName.trim()) {
      toast.error('Введите имя');
      return;
    }
    if (!lastName.trim()) {
      toast.error('Введите фамилию');
      return;
    }
    if (!address.trim()) {
      toast.error('Укажите адрес кабинета');
      return;
    }
    if (
      parsedExperience !== null &&
      (!Number.isInteger(parsedExperience) || parsedExperience < 0 || parsedExperience > 80)
    ) {
      toast.error('Опыт укажите целым числом от 0 до 80 лет');
      return;
    }
    if (!ready) {
      toast.error('Выполните обязательные пункты чек-листа');
      return;
    }
    setSending(true);
    try {
      await authApi.becomeMaster({
        name: firstName.trim(),
        last_name: lastName.trim(),
        cabinet_address: address.trim(),
        city_id: city?.id ?? me?.city_id ?? null,
        description: description.trim() || null,
        experience_years: parsedExperience,
        telegram_username: telegram.trim() || null,
        avatar_url: avatar,
        certificates: certs,
        prefer_master_cabinet: preferMaster,
      });
      setStatus('pending');
      setApplication({
        name: `${firstName.trim()} ${lastName.trim()}`.trim(),
        last_name: lastName.trim(),
        cabinet_address: address.trim(),
        city_id: city?.id ?? null,
        description: description.trim() || null,
        experience_years: parsedExperience,
        telegram_username: telegram.trim() || null,
        avatar_url: avatar,
        certificates: certs,
        prefer_master_cabinet: preferMaster,
      });
      toast.success('Заявка отправлена! Профиль появится после проверки.');
      window.scrollTo({ top: 0, behavior: 'smooth' });
    } catch (err: unknown) {
      toast.error(getApiErrorMessage(err, 'Не удалось отправить заявку'));
    } finally {
      setSending(false);
    }
  };

  if (loading) {
    return (
      <div className="profile-page become-master-page">
        <Skeleton rows={6} />
      </div>
    );
  }

  if (status === 'active') {
    return (
      <div className="profile-page become-master-page">
        <div className="page-header">
          <div>
            <h1>✨ Профиль мастера</h1>
            <p>Ваш профиль мастера уже активен</p>
          </div>
        </div>
        <div className="card">
          <h3>✅ Вы мастер</h3>
          <p style={{ fontSize: 14, color: '#555' }}>
            Панель мастера доступна в меню. Профиль можно редактировать в разделе «Мой профиль».
          </p>
          <button className="btn btn-primary" onClick={() => navigate('/admin/dashboard')}>
            Перейти в панель мастера
          </button>
        </div>
      </div>
    );
  }

  if (status === 'pending') {
    const app = application;
    return (
      <div className="profile-page become-master-page">
        <div className="page-header">
          <div>
            <h1>✨ Профиль мастера</h1>
            <p>Заявка отправлена — её проверит администратор</p>
          </div>
        </div>
        <div className="card">
          <h3>⏳ Заявка на проверке</h3>
          <p style={{ fontSize: 14, color: '#555' }}>
            Мы проверяем заявки вручную. Как только администратор одобрит профиль, в меню появится
            «Панель мастера». Пока можно пользоваться кабинетом клиента.
          </p>
          {app && (
            <div className="become-summary">
              <div>
                <strong>Имя:</strong> {app.name || '—'}
              </div>
              <div>
                <strong>Адрес кабинета:</strong> {app.cabinet_address || '—'}
              </div>
              {app.experience_years != null && (
                <div>
                  <strong>Опыт:</strong> {app.experience_years} лет
                </div>
              )}
              <div>
                <strong>Вход после одобрения:</strong>{' '}
                {app.prefer_master_cabinet === false
                  ? 'в кабинет клиента'
                  : 'сразу в панель мастера'}
              </div>
            </div>
          )}
          <button className="btn btn-primary" onClick={() => navigate('/cabinet')}>
            В кабинет
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="profile-page become-master-page">
      <div className="page-header">
        <div>
          <h1>✨ Профиль мастера</h1>
          <p>
            Заполните профиль для заявки. Панель мастера откроется после проверки администратором.
          </p>
        </div>
      </div>

      <div>
        <div className="card" style={{ marginBottom: 16 }}>
          <h3>Фото и имя</h3>
          <div className="profile-photo-row">
            {avatar ? (
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
                  disabled={uploadingAvatar}
                  onClick={() => avatarInput.current?.click()}
                >
                  {uploadingAvatar ? 'Загрузка…' : avatar ? 'Сменить фото' : 'Добавить фото'}
                </button>
                {avatar && (
                  <button
                    type="button"
                    className="btn btn-ghost btn-sm"
                    onClick={() => setAvatar(null)}
                    title="Убрать фото"
                  >
                    ✕
                  </button>
                )}
              </div>
              <div className="hint">
                Необязательно. JPEG, PNG или WebP до 5 МБ — можно взять фото из соцсети.
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
                placeholder="Анна"
              />
            </div>
            <div className="form-group">
              <label>Фамилия *</label>
              <input
                value={lastName}
                onChange={(e) => setLastName(capitalizeWords(e.target.value))}
                required
                placeholder="Иванова"
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
          <AddressSelect
            value={address}
            onChange={(a, pickedCity, picked) => {
              setAddress(a);
              if (picked && pickedCity) void resolveCity(pickedCity);
            }}
            label="Адрес кабинета *"
            placeholder="Начните вводить город, улицу и дом..."
          />
          <div className="hint">
            Адрес увидят клиенты. Город для поиска: {city?.name || 'определится по адресу'}.
          </div>
        </div>
      </div>

      {/* ContactsCard is its own card and has its own form — keep it outside
          the application form so the two never nest. The checklist below
          reflects its data. */}
      <p className="profile-card-hint" style={{ margin: '0 0 8px' }}>
        Для заявки нужны хотя бы один телефон и одна почта; один из контактов должен быть
        подтверждён соцсетью или кодом из письма.
      </p>
      <ContactsCard contacts={contacts} onChanged={refreshMe} />

      <form onSubmit={handleSubmit}>
        <div className="card" style={{ marginBottom: 16 }}>
          <h3>Дипломы и сертификаты</h3>
          <p className="profile-card-hint">Необязательно — можно добавить позже.</p>
          {certs.length > 0 && (
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
                {newCertName.trim() || 'Без названия'} — добавится в список
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

        <div className="card" style={{ marginBottom: 16 }}>
          <h3>Проверка заявки</h3>
          <div className="become-checklist">
            {checklist.map((item) => (
              <div key={item.label} className={`req${item.ok ? ' ok' : ''}`}>
                <span className="mark">{item.ok ? '✓' : '○'}</span> {item.label}
              </div>
            ))}
          </div>
          <label className="checkbox-label landing-check">
            <input
              type="checkbox"
              checked={preferMaster}
              onChange={(e) => setPreferMaster(e.target.checked)}
            />
            <span>После одобрения входить сразу в кабинет мастера, а не как клиент</span>
          </label>
        </div>

        <div className="form-actions">
          <button type="submit" className="btn btn-primary" disabled={sending || !ready}>
            {sending ? 'Отправка…' : 'Отправить заявку'}
          </button>
        </div>
      </form>
    </div>
  );
}

export default BecomeMasterPage;
