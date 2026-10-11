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

  const fetchData = async () => {
    try {
      const [meResp, apptsResp, statsResp] = await Promise.all([
        cabinetApi.me(),
        cabinetApi.myAppointments(),
        cabinetApi.stats(),
      ]);
      setMe(meResp.data);
      setAppointments(apptsResp.data);
      setStats(statsResp.data);
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleCityChange = async (city: CityOption | null) => {
    if (!city?.id) return;
    try {
      const resp = await cabinetApi.updateMe({ city_id: city.id });
      setMe(resp.data);
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
    .sort(
      (a, b) => new Date(b.appointment_date).getTime() - new Date(a.appointment_date).getTime(),
    );

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
        <CitySelect
          value={me?.city_id ?? null}
          valueName={me?.city_name ?? ''}
          onChange={handleCityChange}
        />
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
          onAction={() => navigate('/booking')}
        />
      ) : (
        <div className="cabinet-list">{upcoming.map(renderCard)}</div>
      )}

      <h2 className="cabinet-section">История</h2>
      {history.length === 0 ? (
        <EmptyState title="История пуста" />
      ) : (
        <div className="cabinet-list">{history.map(renderCard)}</div>
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
