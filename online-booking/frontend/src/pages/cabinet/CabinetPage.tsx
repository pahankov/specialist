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
  const [notes, setNotes] = useState<
    {
      id: number;
      text: string;
      sender_name?: string | null;
      link?: string | null;
      is_read: boolean;
      created_at?: string | null;
    }[]
  >([]);
  const [notesUnread, setNotesUnread] = useState(0);
  // City was already given at registration — show it, edit only on demand.
  const [changingCity, setChangingCity] = useState(false);

  const fetchNotes = async () => {
    try {
      const { data } = await cabinetApi.notificationsInbox({ page: 1, page_size: 10 });
      setNotes(data.items);
      setNotesUnread(data.unread);
    } catch {
      /* inbox is optional — cabinet works without it */
    }
  };

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
    fetchNotes();
    // eslint-disable-next-line react-hooks/exhaustive-deps
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

      {notes.length > 0 && (
        <>
          <h2 className="cabinet-section">
            🔔 Уведомления{notesUnread > 0 ? ` (${notesUnread} новых)` : ''}
          </h2>
          <div className="cabinet-list">
            {notes.map((n) => (
              <div
                key={n.id}
                className="cabinet-card"
                onClick={() => {
                  if (n.link === 'appointments') navigate('/cabinet');
                }}
                style={n.link ? { cursor: 'pointer' } : undefined}
                title={n.link === 'appointments' ? 'Открыть мои записи →' : undefined}
              >
                <div className="cabinet-card-main">
                  <span style={{ whiteSpace: 'pre-wrap' }}>{n.text}</span>
                  <span className="cabinet-card-date">
                    {[n.sender_name ? `от ${n.sender_name}` : null, n.created_at ? new Date(n.created_at).toLocaleString('ru-RU') : null]
                      .filter(Boolean)
                      .join(' · ')}
                  </span>
                </div>
                <div className="cabinet-card-side">
                  {!n.is_read && (
                    <button
                      className="btn btn-sm btn-ghost"
                      onClick={async (e) => {
                        e.stopPropagation();
                        try {
                          await cabinetApi.readNotification(n.id);
                          setNotes((prev) =>
                            prev.map((x) => (x.id === n.id ? { ...x, is_read: true } : x)),
                          );
                          setNotesUnread((u) => Math.max(0, u - 1));
                        } catch {
                          /* ignore */
                        }
                      }}
                    >
                      ✓ Прочитано
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        </>
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
