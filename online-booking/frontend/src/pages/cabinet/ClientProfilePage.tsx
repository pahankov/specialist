import { useEffect, useState } from 'react';
import { toast } from 'sonner';
import { cabinetApi, type ClientMe } from '../../api/client';
import {
  AddressSelect,
  CitySelect,
  Skeleton,
} from '../../components/common';
import type { CityOption } from '../../components/common/CitySelect';
import { getApiErrorMessage } from '../../utils/apiError';
import { capitalizeWords, splitFullName } from '../../utils/names';
import './ClientProfilePage.css';

/** Client personal data: names, contacts (read-only ids), city, address. */
function ClientProfilePage() {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
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
    </div>
  );
}

export default ClientProfilePage;
