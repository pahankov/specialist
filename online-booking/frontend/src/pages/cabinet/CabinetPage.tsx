import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { cabinetApi, type ClientMe, type ClientStats } from '../../api/client';
import type { Appointment } from '../../api/types';
import { ConfirmDialog, EmptyState, Skeleton, StatusBadge } from '../../components/common';
import CitySelect, { type CityOption } from '../../components/common/CitySelect';
import { getApiErrorMessage, getApiErrorStatus } from '../../utils/apiError';
import './CabinetPage.css';

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleString('ru-RU', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return iso;
  }
}

function CabinetPage() {
  const navigate = useNavigate();
  const [me, setMe] = useState<ClientMe | null>(null);
  const [appointments, setAppointments] = useState<Appointment[]>([]);
  const [stats, setStats] = useState<ClientStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [cancellingId, setCancellingId] = useState<number | null>(null);
  // City was already given at registration — show it, edit only on demand.
  const [changingCity, setChangingCity] = useState(false);
  // Own reviews: appointment_id → stars (to prompt only unrated visits).
  const [ratedByAppt, setRatedByAppt] = useState<Record<number, number>>({});
  const [reviewFor, setReviewFor] = useState<number | null>(null);
  const [stars, setStars] = useState(5);
  const [reviewText, setReviewText] = useState('');
  const [sendingReview, setSendingReview] = useState(false);
  // History filter chips, like the master panel.
  const [histFilter, setHistFilter] = useState('');

  const fetchData = async () => {
    try {
      // Reviews are optional: an older mock without myReviews must not
      // break the whole cabinet.
      const reviewsPromise =
        typeof cabinetApi.myReviews === 'function'
          ? cabinetApi
              .myReviews()
              .catch(() => ({ data: [] as { appointment_id: number; rating: number }[] }))
          : Promise.resolve({ data: [] as { appointment_id: number; rating: number }[] });
      const [meResp, apptsResp, statsResp, revResp] = await Promise.all([
        cabinetApi.me(),
        cabinetApi.myAppointments(),
        cabinetApi.stats(),
        reviewsPromise,
      ]);
      setMe(meResp.data);
      setAppointments(apptsResp.data);
      setStats(statsResp.data);
      setRatedByAppt(Object.fromEntries(revResp.data.map((r) => [r.appointment_id, r.rating])));
    } catch (err: unknown) {
      if (getApiErrorStatus(err) === 401) {
        navigate('/', { replace: true });
      } else {
        toast.error(getApiErrorMessage(err, 'Ошибка загрузки кабинета'));
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleCityChange = async (city: CityOption | null) => {
    if (!city?.id) return;
    try {
      const resp = await cabinetApi.updateMe({ city_id: city.id });
      setMe(resp.data);
      setChangingCity(false);
      toast.success(`Ваш город — ${resp.data.city_name || city.name}`);
    } catch (err: unknown) {
      toast.error(getApiErrorMessage(err, 'Не удалось сохранить город'));
    }
  };

  const handleCancel = async (id: number) => {
    try {
      await cabinetApi.cancelAppointment(id);
      toast.success('Запись отменена');
      fetchData();
    } catch (err: unknown) {
      toast.error(getApiErrorMessage(err, 'Не удалось отменить запись'));
    } finally {
      setCancellingId(null);
    }
  };

  if (loading) {
    return (
      <div className="cabinet-page">
        <Skeleton rows={6} />
      </div>
    );
  }

  const now = Date.now();
  const upcoming = appointments
    .filter(
      (a) =>
        (a.status === 'pending' || a.status === 'confirmed') &&
        new Date(a.appointment_date).getTime() >= now,
    )
    .sort(
      (a, b) => new Date(a.appointment_date).getTime() - new Date(b.appointment_date).getTime(),
    );
  const history = appointments
    .filter((a) => !upcoming.includes(a))
    .filter((a) => !histFilter || a.status === histFilter)
    .sort(
      (a, b) => new Date(b.appointment_date).getTime() - new Date(a.appointment_date).getTime(),
    );

  const submitReview = async (appointmentId: number) => {
    setSendingReview(true);
    try {
      const { data } = await cabinetApi.createReview({
        appointment_id: appointmentId,
        rating: stars,
        comment: reviewText.trim() || undefined,
      });
      setRatedByAppt((prev) => ({ ...prev, [appointmentId]: data.rating }));
      setReviewFor(null);
      setReviewText('');
      setStars(5);
      toast.success('Спасибо! Оценка учтена в рейтинге мастера ⭐');
    } catch (err: unknown) {
      toast.error(getApiErrorMessage(err, 'Не удалось отправить отзыв'));
    } finally {
      setSendingReview(false);
    }
  };

  const renderHistoryCard = (a: Appointment) => {
    const myStars = ratedByAppt[a.id];
    const canRate = a.status === 'completed' && myStars === undefined;
    return (
      <div key={a.id} className="cabinet-card">
        <div className="cabinet-card-main">
          <strong>{a.service_name || 'Услуга'}</strong>
          <span className="cabinet-card-master">{a.master_name || ''}</span>
          <span className="cabinet-card-date">{formatDate(a.appointment_date)}</span>
          {myStars !== undefined && (
            <span className="cabinet-card-master" title="Ваша оценка">
              Ваша оценка: {'★'.repeat(Math.round(myStars))}☆
            </span>
          )}
          {reviewFor === a.id && (
            <div style={{ marginTop: 8 }}>
              <div style={{ display: 'flex', gap: 4, fontSize: 24 }}>
                {[1, 2, 3, 4, 5].map((n) => (
                  <button
                    key={n}
                    type="button"
                    onClick={() => setStars(n)}
                    style={{
                      background: 'none',
                      border: 'none',
                      cursor: 'pointer',
                      color: n <= stars ? '#f5a623' : '#ddd',
                    }}
                    aria-label={`Оценка ${n}`}
                  >
                    ★
                  </button>
                ))}
              </div>
              <input
                value={reviewText}
                onChange={(e) => setReviewText(e.target.value)}
                placeholder="Пара слов о визите (необязательно)"
                maxLength={500}
                style={{ marginTop: 6, width: '100%' }}
              />
              <div style={{ display: 'flex', gap: 8, marginTop: 6 }}>
                <button
                  className="btn btn-sm btn-primary"
                  disabled={sendingReview}
                  onClick={() => submitReview(a.id)}
                >
                  {sendingReview ? 'Отправляем…' : 'Отправить отзыв'}
                </button>
                <button
                  className="btn btn-sm btn-ghost"
                  onClick={() => {
                    setReviewFor(null);
                    setReviewText('');
                  }}
                >
                  Позже
                </button>
              </div>
            </div>
          )}
        </div>
        <div className="cabinet-card-side">
          <StatusBadge status={a.status} />
          {canRate && reviewFor !== a.id && (
            <button
              className="btn btn-sm btn-ghost"
              onClick={() => {
                setReviewFor(a.id);
                setStars(5);
                setReviewText('');
              }}
            >
              ⭐ Оценить
            </button>
          )}
        </div>
      </div>
    );
  };

  const renderCard = (a: Appointment) => {
    const cancellable = a.status === 'pending' || a.status === 'confirmed';
    return (
      <div key={a.id} className="cabinet-card">
        <div className="cabinet-card-main">
          <strong>{a.service_name || 'Услуга'}</strong>
          <span className="cabinet-card-master">{a.master_name || ''}</span>
          <span className="cabinet-card-date">{formatDate(a.appointment_date)}</span>
        </div>
        <div className="cabinet-card-side">
          <StatusBadge status={a.status} />
          {cancellable && (
            <button className="btn btn-sm btn-delete" onClick={() => setCancellingId(a.id)}>
              Отменить
            </button>
          )}
        </div>
      </div>
    );
  };

  return (
    <div className="cabinet-page">
      <div className="page-header">
        <h1>Мои записи</h1>
        <p>{me ? `${me.name} · ${me.phone || ''}` : ''}</p>
      </div>

      <div className="cabinet-city-row">
        <span className="cabinet-city-label">Ваш город:</span>
        {me?.city_id && !changingCity ? (
          <>
            <strong>{me.city_name}</strong>
            <button className="btn btn-sm btn-ghost" onClick={() => setChangingCity(true)}>
              Изменить
            </button>
          </>
        ) : (
          <CitySelect
            value={me?.city_id ?? null}
            valueName={me?.city_name ?? ''}
            onChange={handleCityChange}
          />
        )}
      </div>

      {stats && (
        <div className="stat-strip">
          <div className="stat-mini">
            <span className="stat-mini-value">{stats.total_spent.toLocaleString('ru-RU')} ₽</span>
            <span className="stat-mini-label">потрачено</span>
          </div>
          <div className="stat-mini">
            <span className="stat-mini-value">{stats.completed_visits}</span>
            <span className="stat-mini-label">визитов</span>
          </div>
          <div className="stat-mini">
            <span className="stat-mini-value">{stats.upcoming_count}</span>
            <span className="stat-mini-label">предстоящих</span>
          </div>
          <div className="stat-mini">
            <span className="stat-mini-value">
              {stats.favorite_master ? stats.favorite_master.name : '—'}
            </span>
            <span className="stat-mini-label">любимый мастер</span>
          </div>
        </div>
      )}

      <h2 className="cabinet-section">Предстоящие</h2>
      {upcoming.length === 0 ? (
        <EmptyState
          title="Нет предстоящих записей"
          description="Выберите мастера и время — это займёт минуту"
          actionLabel="Записаться"
          onAction={() => navigate('/cabinet/book')}
        />
      ) : (
        <div className="cabinet-list">{upcoming.map(renderCard)}</div>
      )}

      <h2 className="cabinet-section">История</h2>
      <div className="filters-bar" style={{ marginBottom: 12 }}>
        {[
          { value: '', label: 'Все' },
          { value: 'confirmed', label: '✅ Подтверждена' },
          { value: 'completed', label: '🏁 Завершена' },
          { value: 'cancelled', label: '❌ Отменена' },
        ].map((f) => (
          <button
            key={f.value}
            type="button"
            className={`filter-btn ${histFilter === f.value ? 'active' : ''}`}
            onClick={() => setHistFilter(f.value)}
          >
            {f.label}
          </button>
        ))}
      </div>
      {history.length === 0 ? (
        <EmptyState title="История пуста" />
      ) : (
        <div className="cabinet-list">{history.map(renderHistoryCard)}</div>
      )}

      <ConfirmDialog
        open={cancellingId !== null}
        onClose={() => setCancellingId(null)}
        title="Отменить запись?"
        message="Мастер увидит отмену. Это действие нельзя отменить."
        confirmLabel="Отменить запись"
        danger
        onConfirm={() => cancellingId !== null && handleCancel(cancellingId)}
      />
    </div>
  );
}

export default CabinetPage;
