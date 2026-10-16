import { useEffect, useMemo, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { toast } from 'sonner';
import { servicesApi, appointmentsApi, mastersApi, cabinetApi } from '../../api/client';
import type { Master, Service } from '../../api/types';
import { PHONE_PLACEHOLDER } from '../../constants';
import PhoneInput, { isCompletePhone } from '../../components/common/PhoneInput';
import CitySelect, { type CityOption } from '../../components/common/CitySelect';
import { EmptyState, Skeleton } from '../../components/common';
import { getCookie } from '../../utils/cookies';
import { getApiErrorMessage } from '../../utils/apiError';
import './BookingPage.css';

function formatRating(rating?: number | null): string {
  if (rating === null || rating === undefined) return '–';
  return `★ ${rating.toFixed(1)}`;
}

function groupByCategory(services: Service[]): [string, Service[]][] {
  const groups = new Map<string, Service[]>();
  for (const s of services) {
    const key = s.category?.trim() || 'Прочее';
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key)!.push(s);
  }
  const entries = [...groups.entries()];
  entries.sort((a, b) => {
    if (a[0] === 'Прочее') return 1;
    if (b[0] === 'Прочее') return -1;
    return a[0].localeCompare(b[0], 'ru');
  });
  return entries;
}

function BookingPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const defaultMasterId = searchParams.get('master_id')
    ? Number(searchParams.get('master_id'))
    : undefined;

  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [cityId, setCityId] = useState<number | null>(null);
  const [cityName, setCityName] = useState('');
  const [masters, setMasters] = useState<Master[]>([]);
  const [mastersLoading, setMastersLoading] = useState(true);
  const [selectedMaster, setSelectedMaster] = useState<Master | null>(null);
  const [services, setServices] = useState<Service[]>([]);
  const [servicesLoading, setServicesLoading] = useState(false);
  const [selectedService, setSelectedService] = useState<Service | null>(null);
  const [selectedDate, setSelectedDate] = useState<string>('');
  const [clientName, setClientName] = useState('');
  const [clientPhone, setClientPhone] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [success, setSuccess] = useState(false);

  // Logged-in clients: prefill contact + city, mark session for post-booking links.
  useEffect(() => {
    if (!getCookie('access_token')) return;
    setIsLoggedIn(true);
    cabinetApi
      .me()
      .then((resp) => {
        const me = resp.data;
        if (me.name) setClientName(me.name);
        if (me.phone) setClientPhone(me.phone);
        if (me.city_id) {
          setCityId(me.city_id);
          setCityName(me.city_name || '');
        }
      })
      .catch(() => {
        setIsLoggedIn(!!getCookie('access_token'));
      });
  }, []);

  // Masters for the chosen city (empty = all cities).
  useEffect(() => {
    const fetchMasters = async () => {
      setMastersLoading(true);
      setSelectedMaster(null);
      setServices([]);
      setSelectedService(null);
      try {
        const res = await mastersApi.getAll(cityId ?? undefined);
        setMasters(res.data);
        if (defaultMasterId) {
          const found = res.data.find((m) => m.id === defaultMasterId) || null;
          setSelectedMaster(found);
        }
      } catch (err) {
        console.error(err);
        toast.error(getApiErrorMessage(err, 'Не удалось загрузить мастеров'));
      } finally {
        setMastersLoading(false);
      }
    };

    fetchMasters();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cityId]);

  // Services of the chosen master, grouped by category on render.
  useEffect(() => {
    if (!selectedMaster) return;
    const fetchServices = async () => {
      setServicesLoading(true);
      setSelectedService(null);
      try {
        const res = await servicesApi.getAll(selectedMaster.id);
        const list = res.data;
        setServices(list);
        if (list.length > 0) setSelectedService(list[0]);
      } catch (err) {
        console.error(err);
        toast.error(getApiErrorMessage(err, 'Не удалось загрузить услуги'));
      } finally {
        setServicesLoading(false);
      }
    };

    fetchServices();
  }, [selectedMaster]);

  const groupedServices = useMemo(() => groupByCategory(services), [services]);

  const handleCityChange = (city: CityOption | null) => {
    setCityId(city?.id ?? null);
    setCityName(city?.name ?? '');
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!selectedService || !selectedDate || !clientName || !clientPhone) {
      toast.error('Заполните все поля');
      return;
    }
    if (!isCompletePhone(clientPhone)) {
      toast.error('Введите корректный номер телефона (11 цифр)');
      return;
    }

    try {
      setSubmitting(true);

      const appointmentData = {
        master_id: selectedService!.master_id,
        service_id: selectedService.id,
        client_name: clientName,
        client_phone: clientPhone,
        appointment_date: new Date(selectedDate).toISOString(),
      };

      await appointmentsApi.publicBooking(appointmentData);

      toast.success('Вы успешно записаны!');
      setSuccess(true);
      setSelectedDate('');
    } catch (err) {
      toast.error(getApiErrorMessage(err, 'Не удалось записаться'));
      console.error(err);
    } finally {
      setSubmitting(false);
    }
  };

  if (success) {
    return (
      <div className="booking-page">
        <div className="success-message card">
          <h2>✅ Спасибо за запись!</h2>
          <p>Ваша запись успешно создана.</p>
          <p>Мы свяжемся с вами в ближайшее время.</p>
          <button className="btn btn-primary" onClick={() => setSuccess(false)}>
            Новая запись
          </button>
          {isLoggedIn && (
            <button
              className="btn btn-ghost"
              style={{ marginLeft: 8 }}
              onClick={() => navigate('/cabinet')}
            >
              Мои записи
            </button>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="booking-page">
      <div className="container">
        <h1>Запись на процедуру</h1>

        <form onSubmit={handleSubmit} className="booking-form card">
          <fieldset>
            <legend>1. Ваш город</legend>
            <CitySelect value={cityId} valueName={cityName} onChange={handleCityChange} />
          </fieldset>

          <fieldset>
            <legend>2. Выберите мастера</legend>
            {mastersLoading ? (
              <Skeleton rows={3} />
            ) : masters.length === 0 ? (
              <EmptyState
                title={cityId ? 'В вашем городе мастеров нет' : 'Мастеров пока нет'}
                description={cityId ? 'Попробуйте другой город или все города' : 'Загляните позже'}
                actionLabel={cityId ? 'Показать все города' : undefined}
                onAction={cityId ? () => handleCityChange(null) : undefined}
              />
            ) : (
              <div className="masters-list">
                {masters.map((master) => (
                  <label
                    key={master.id}
                    className={`service-option${selectedMaster?.id === master.id ? ' selected' : ''}`}
                  >
                    <input
                      type="radio"
                      name="master"
                      checked={selectedMaster?.id === master.id}
                      onChange={() => setSelectedMaster(master)}
                    />
                    <span className="service-label">
                      <strong>{master.name}</strong>
                      <span className="service-details">
                        {[master.city_name, formatRating(master.avg_rating)]
                          .filter(Boolean)
                          .join(' • ')}
                      </span>
                      {master.description && (
                        <span className="service-details">{master.description}</span>
                      )}
                    </span>
                  </label>
                ))}
              </div>
            )}
          </fieldset>

          {selectedMaster && (
            <fieldset>
              <legend>3. Выберите услугу</legend>
              {servicesLoading ? (
                <Skeleton rows={3} />
              ) : groupedServices.length === 0 ? (
                <EmptyState title="У этого мастера пока нет услуг" />
              ) : (
                groupedServices.map(([category, items]) => (
                  <div key={category} className="service-category">
                    <h4 className="service-category-title">{category}</h4>
                    <div className="services-list">
                      {items.map((service) => (
                        <label key={service.id} className="service-option">
                          <input
                            type="radio"
                            value={service.id}
                            checked={selectedService?.id === service.id}
                            onChange={() => setSelectedService(service)}
                          />
                          <span className="service-label">
                            <strong>{service.name}</strong>
                            <span className="service-details">
                              {service.duration_minutes} мин • ₽{service.price}
                            </span>
                          </span>
                        </label>
                      ))}
                    </div>
                  </div>
                ))
              )}
            </fieldset>
          )}

          <fieldset>
            <legend>{selectedMaster ? '4' : '3'}. Дата и время</legend>
            <input
              type="datetime-local"
              value={selectedDate}
              onChange={(e) => setSelectedDate(e.target.value)}
              className="input"
              required
            />
          </fieldset>

          <fieldset>
            <legend>{selectedMaster ? '5' : '4'}. Ваши данные</legend>
            <input
              type="text"
              placeholder="Ваше имя"
              value={clientName}
              onChange={(e) => setClientName(e.target.value)}
              className="input"
              required
            />
            <PhoneInput
              placeholder={PHONE_PLACEHOLDER}
              value={clientPhone}
              onChange={setClientPhone}
              className="input"
              required
            />
          </fieldset>

          <button type="submit" className="btn btn-primary btn-submit" disabled={submitting}>
            {submitting ? 'Записываем...' : 'Записаться'}
          </button>
        </form>
      </div>
    </div>
  );
}

export default BookingPage;
