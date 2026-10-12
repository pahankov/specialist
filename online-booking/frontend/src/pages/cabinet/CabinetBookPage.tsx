import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { cabinetApi, mastersApi, servicesApi } from '../../api/client';
import type { Master, Service, Appointment } from '../../api/types';
import {
  ConfirmDialog,
  EmptyState,
  Modal,
  Skeleton,
} from '../../components/common';
import { Calendar } from '../../components/schedule/Calendar';
import CitySelect from '../../components/common/CitySelect';
import {
  appointmentSpanHours,
  formatDate,
  formatHour,
  getAppointmentsForSlot,
  getCoveringLive,
  isSlotPast,
} from '../../components/schedule/helpers';
import { getApiErrorMessage } from '../../utils/apiError';
import './CabinetBookPage.css';

function formatRating(rating?: number | null): string {
  if (rating === null || rating === undefined) return '';
  return `★ ${rating.toFixed(1)}`;
}

/** Read-only granules for clients: free ones open the booking modal. */
function ClientSlots({
  date,
  windowStart,
  windowEnd,
  activeHours,
  busy,
  onPick,
}: {
  date: Date;
  windowStart: number;
  windowEnd: number;
  activeHours: Record<string, boolean>;
  busy: Appointment[];
  onPick: (hour: number) => void;
}) {
  const dateStr = formatDate(date);
  const rows = [];
  for (let h = windowStart; h < windowEnd; h++) {
    const starters = getAppointmentsForSlot(busy, date, h).filter(
      (s) => s.status !== 'cancelled',
    );
    const coveredBy =
      starters.length === 0 ? getCoveringLive(busy, date, h) : null;
    const past = isSlotPast(date, h);
    const hourActive = !!activeHours[`${dateStr}-${h}`];
    const live = starters[0] ?? coveredBy;
    const free = !past && hourActive && !live;
    rows.push(
      <button
        key={h}
        type="button"
        disabled={!free}
        onClick={() => onPick(h)}
        className={`slot-row${live ? ` slot-${live.status}` : ''}${!hourActive ? ' slot-off' : ''}${past ? ' slot-past' : ''}`}
        title={
          live
            ? `Занято (${live.client_name || 'запись'})`
            : !hourActive
              ? 'Мастер не работает в этот час'
              : past
                ? 'Время прошло'
                : `Записаться на ${formatHour(h)}`
        }
      >
        <span className="slot-time">{formatHour(h)}</span>
        {live ? (
          <span className="slot-who">
            Занято
            {appointmentSpanHours(live) > 1 ? ` · ${appointmentSpanHours(live)} гр.` : ''}
          </span>
        ) : (
          <span className="slot-free">{past ? 'Прошёл' : hourActive ? '+ Записаться' : '—'}</span>
        )}
      </button>,
    );
  }
  return <div className="slot-list">{rows}</div>;
}

function CabinetBookPage() {
  const navigate = useNavigate();
  const [cityId, setCityId] = useState<number | null>(null);
  const [cityName, setCityName] = useState('');
  const [masters, setMasters] = useState<Master[]>([]);
  const [mastersLoading, setMastersLoading] = useState(true);
  const [servicesByMaster, setServicesByMaster] = useState<Record<number, Service[]>>({});
  const [serviceFilter, setServiceFilter] = useState('');
  const [masterQuery, setMasterQuery] = useState('');
  const [selectedMaster, setSelectedMaster] = useState<Master | null>(null);

  const [monthISO, setMonthISO] = useState(() => new Date().toISOString().slice(0, 7));
  const currentMonth = useMemo(() => new Date(`${monthISO}-01T00:00:00`), [monthISO]);
  const [windowRange, setWindowRange] = useState({ start: 8, end: 22 });
  const [schedule, setSchedule] = useState<Record<string, { start: number; end: number }>>({});
  const [activeHours, setActiveHours] = useState<Record<string, boolean>>({});
  const [busy, setBusy] = useState<Appointment[]>([]);
  const [scheduleLoading, setScheduleLoading] = useState(false);

  const [selectedDate, setSelectedDate] = useState<Date | null>(null);
  const [slotHour, setSlotHour] = useState<number | null>(null);
  const [modalServiceId, setModalServiceId] = useState<number | ''>('');
  const [notes, setNotes] = useState('');
  const [bookingLoading, setBookingLoading] = useState(false);
  const [confirmCancel, setConfirmCancel] = useState(false);

  // Own city first (trip? pick another — masters reload).
  useEffect(() => {
    cabinetApi
      .me()
      .then((resp) => {
        if (resp.data.city_id) {
          setCityId(resp.data.city_id);
          setCityName(resp.data.city_name || '');
        }
      })
      .catch(() => {
        /* public flow without a city */
      });
  }, []);

  // Masters of the city + their services (for the service filter).
  useEffect(() => {
    let cancelled = false;
    (async () => {
      setMastersLoading(true);
      setSelectedMaster(null);
      try {
        const res = await mastersApi.getAll(cityId ?? undefined);
        if (cancelled) return;
        setMasters(res.data);
        const entries = await Promise.all(
          res.data.map(async (m) => {
            try {
              const s = await servicesApi.getAll(m.id);
              return [m.id, (s.data || []).filter((x) => x.is_active !== false)] as const;
            } catch {
              return [m.id, []] as const;
            }
          }),
        );
        if (!cancelled) setServicesByMaster(Object.fromEntries(entries));
      } catch {
        if (!cancelled) toast.error('Не удалось загрузить мастеров');
      } finally {
        if (!cancelled) setMastersLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [cityId]);

  const serviceNames = useMemo(() => {
    const set = new Set<string>();
    for (const list of Object.values(servicesByMaster)) {
      for (const s of list) set.add(s.name);
    }
    return [...set].sort((a, b) => a.localeCompare(b, 'ru'));
  }, [servicesByMaster]);

  const visibleMasters = useMemo(() => {
    const q = masterQuery.trim().toLowerCase();
    return masters.filter((m) => {
      if (q && !m.name.toLowerCase().includes(q)) return false;
      if (serviceFilter && !(servicesByMaster[m.id] || []).some((s) => s.name === serviceFilter))
        return false;
      return true;
    });
  }, [masters, masterQuery, serviceFilter, servicesByMaster]);

  // Active schedule of the chosen master.
  useEffect(() => {
    if (!selectedMaster) return;
    let cancelled = false;
    (async () => {
      setScheduleLoading(true);
      setSelectedDate(null);
      try {
        const { data } = await cabinetApi.getBookSchedule(selectedMaster.id, monthISO);
        if (cancelled) return;
        setWindowRange({ start: data.window.start_hour, end: data.window.end_hour });
        const hours: Record<string, boolean> = {};
        const sched: Record<string, { start: number; end: number }> = {};
        for (const w of data.working_hours) {
          const s = Number(String(w.start).slice(0, 2));
          const e = Number(String(w.end).slice(0, 2));
          sched[w.date] = { start: s, end: e };
          for (let h = s; h < e; h++) hours[`${w.date}-${h}`] = true;
        }
        setSchedule(sched);
        setActiveHours(hours);
        setBusy(
          (data.busy || []).map((b, i) => ({
            id: -(i + 1),
            master_id: data.master_id,
            service_id: 0,
            appointment_date: b.appointment_date,
            status: b.status as Appointment['status'],
            service_duration: b.service_duration,
          })) as Appointment[],
        );
      } catch (err: unknown) {
        if (!cancelled) toast.error(getApiErrorMessage(err, 'Не удалось загрузить расписание'));
      } finally {
        if (!cancelled) setScheduleLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedMaster?.id, monthISO]);

  const openSlot = (hour: number) => {
    const list = selectedMaster ? servicesByMaster[selectedMaster.id] || [] : [];
    setModalServiceId(list.length > 0 ? list[0].id : '');
    setNotes('');
    setSlotHour(hour);
  };

  const modalServices = selectedMaster ? servicesByMaster[selectedMaster.id] || [] : [];
  const modalService = modalServices.find((s) => s.id === modalServiceId) ?? null;

  const handleBook = async () => {
    if (!selectedMaster || !selectedDate || slotHour === null || modalServiceId === '') return;
    const y = selectedDate.getFullYear();
    const m = String(selectedDate.getMonth() + 1).padStart(2, '0');
    const d = String(selectedDate.getDate()).padStart(2, '0');
    setBookingLoading(true);
    try {
      await cabinetApi.bookAppointment({
        master_id: selectedMaster.id,
        service_id: Number(modalServiceId),
        appointment_date: `${y}-${m}-${d}T${String(slotHour).padStart(2, '0')}:00:00`,
        notes: notes.trim() || undefined,
      });
      toast.success('Вы записаны! Ждём вас 🎉');
      setSlotHour(null);
      navigate('/cabinet');
    } catch (err: unknown) {
      toast.error(getApiErrorMessage(err, 'Не удалось записаться'));
    } finally {
      setBookingLoading(false);
    }
  };

  return (
    <div className="cabinet-book-page">
      <div className="page-header">
        <div>
          <h1>💅 Записаться</h1>
          <p>Мастера вашего города → расписание → свободная гранула</p>
        </div>
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <div className="book-filters">
          <div className="filter-cell">
            <label className="filter-label">📍 Город {cityId ? '' : '(все города)'}</label>
            <CitySelect
              value={cityId}
              valueName={cityName}
              onChange={(c) => {
                setCityId(c?.id ?? null);
                setCityName(c?.name ?? '');
              }}
              label=""
            />
          </div>
          <div className="filter-cell">
            <label className="filter-label">💇 Услуга</label>
            <select
              className="filter-control"
              value={serviceFilter}
              onChange={(e) => setServiceFilter(e.target.value)}
            >
              <option value="">Все услуги</option>
              {serviceNames.map((n) => (
                <option key={n} value={n}>
                  {n}
                </option>
              ))}
            </select>
          </div>
          <div className="filter-cell">
            <label className="filter-label">🔍 Мастер</label>
            <input
              type="text"
              className="filter-control"
              placeholder="Имя мастера..."
              value={masterQuery}
              onChange={(e) => setMasterQuery(e.target.value)}
            />
          </div>
        </div>
      </div>

      {mastersLoading ? (
        <div className="card">
          <Skeleton rows={3} />
        </div>
      ) : visibleMasters.length === 0 ? (
        <EmptyState
          icon="👨‍💼"
          title={cityId ? 'В этом городе мастеров нет' : 'Мастеров пока нет'}
          description="Попробуйте другой город или сбросьте фильтры"
        />
      ) : (
        <div className="master-pick-list">
          {visibleMasters.map((m) => (
            <label
              key={m.id}
              className={`master-pick${selectedMaster?.id === m.id ? ' selected' : ''}`}
            >
              <input
                type="radio"
                name="cabinet-master"
                checked={selectedMaster?.id === m.id}
                onChange={() => setSelectedMaster(m)}
              />
              {m.avatar_url && <img src={m.avatar_url} alt={m.name} className="master-pick-avatar" />}
              <span className="master-pick-main">
                <strong>
                  {m.name} {formatRating(m.avg_rating)}
                </strong>
                {[m.cabinet_address, m.city_name].filter(Boolean).join(' • ') ||
                  'Адрес уточняйте'}
                {m.experience_years != null && <span> · опыт {m.experience_years} лет</span>}
                {m.description && <span className="master-pick-desc">{m.description}</span>}
              </span>
            </label>
          ))}
        </div>
      )}

      {selectedMaster && (
        <div className="card" style={{ marginTop: 16 }}>
          <div className="card-header">
            <h3>📅 {selectedMaster.name} — активное расписание</h3>
          </div>
          {scheduleLoading ? (
            <Skeleton rows={4} />
          ) : (
            <>
              <Calendar
                currentMonth={currentMonth}
                schedule={schedule}
                appointments={busy}
                selectedDate={selectedDate}
                onPrevMonth={() =>
                  setMonthISO((iso) => {
                    const [y, mo] = iso.split('-').map(Number);
                    const d = new Date(y, mo - 2, 1);
                    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
                  })
                }
                onNextMonth={() =>
                  setMonthISO((iso) => {
                    const [y, mo] = iso.split('-').map(Number);
                    const d = new Date(y, mo, 1);
                    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
                  })
                }
                onSelectDate={setSelectedDate}
                onToggleDay={() => {}}
                interactive={false}
              />
              {selectedDate &&
                (schedule[formatDate(selectedDate)] ? (
                  <ClientSlots
                    date={selectedDate}
                    windowStart={windowRange.start}
                    windowEnd={windowRange.end}
                    activeHours={activeHours}
                    busy={busy}
                    onPick={openSlot}
                  />
                ) : (
                  <EmptyState title="В этот день мастер не работает" icon="😴" />
                ))}
            </>
          )}
        </div>
      )}

      <Modal
        open={slotHour !== null}
        onClose={() => {
          // Don't lose a half-filled booking on an accidental X.
          if (slotHour !== null && modalServiceId !== '') setConfirmCancel(true);
          else setSlotHour(null);
        }}
        title="📅 Подтвердите запись"
      >
        {selectedMaster && selectedDate && slotHour !== null && (
          <div className="book-confirm">
            <p>
              <strong>{selectedMaster.name}</strong>
              <br />
              {selectedDate.toLocaleDateString('ru-RU', {
                weekday: 'long',
                day: 'numeric',
                month: 'long',
              })}{' '}
              в {formatHour(slotHour)}
            </p>
            <div className="form-group">
              <label>Услуга</label>
              <select
                value={modalServiceId}
                onChange={(e) =>
                  setModalServiceId(e.target.value === '' ? '' : Number(e.target.value))
                }
              >
                <option value="" disabled>
                  Выберите услугу…
                </option>
                {modalServices.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name} — {s.duration_minutes} мин, {s.price} ₽
                  </option>
                ))}
              </select>
              {modalService && (
                <span className="hint">
                  Займёт {formatHour(slotHour)}–
                  {(() => {
                    const dur = Number(modalService.duration_minutes) || 60;
                    const endH = slotHour + Math.floor(dur / 60);
                    const endM = dur % 60;
                    return `${String(endH).padStart(2, '0')}:${String(endM).padStart(2, '0')}`;
                  })()}
                </span>
              )}
            </div>
            <div className="form-group">
              <label>Комментарий (необязательно)</label>
              <input
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="Пожелания мастеру..."
                maxLength={500}
              />
            </div>
            <div className="modal-actions">
              <button
                type="button"
                className="btn btn-ghost"
                onClick={() => setSlotHour(null)}
              >
                Отмена
              </button>
              <button
                type="button"
                className="btn btn-primary"
                disabled={modalServiceId === '' || bookingLoading}
                onClick={handleBook}
              >
                {bookingLoading ? 'Записываем…' : 'Записаться'}
              </button>
            </div>
          </div>
        )}
      </Modal>

      <ConfirmDialog
        open={confirmCancel}
        onClose={() => setConfirmCancel(false)}
        title="Закрыть без записи?"
        message="Выбранные услуга и время не сохранятся."
        confirmLabel="Закрыть"
        onConfirm={() => {
          setConfirmCancel(false);
          setSlotHour(null);
        }}
      />
    </div>
  );
}

export default CabinetBookPage;
