import { useState } from 'react';
import type { Appointment } from '../../api/types';
import {
  getAppointmentsForSlot,
  getCoveringLive,
  getSlotStatus,
  appointmentSpanHours,
  formatHour,
  isSlotPast,
  STATUS_CONFIG,
  formatDate,
  isPast,
} from './helpers';
import './ScheduleComponents.css';

interface TimeSlotsProps {
  selectedDate: Date | null;
  appointments: Appointment[];
  activeHours: Record<string, boolean>;
  onToggleHour: (dateStr: string, hour: number) => void;
  onOpenBooking: (date: Date, hour: number) => void;
  onCancelAppointment: (id: number) => Promise<void>;
  onConfirmAppointment?: (id: number) => Promise<void>;
  /** Applied work window: granules render for [windowStart, windowEnd). */
  windowStart?: number;
  windowEnd?: number;
  /** Stored range of the selected working day. It can be wider than the
   * applied window for preserved booked/past days, so it is unioned in. */
  dayStart?: number;
  dayEnd?: number;
  onChangeDayHours?: (dateStr: string, start: number, end: number) => Promise<void> | void;
}

export function TimeSlots({
  selectedDate,
  appointments,
  activeHours,
  onToggleHour,
  onOpenBooking,
  onCancelAppointment,
  onConfirmAppointment,
  windowStart = 8,
  windowEnd = 22,
  dayStart,
  dayEnd,
  onChangeDayHours,
}: TimeSlotsProps) {
  const [adjusting, setAdjusting] = useState(false);
  if (!selectedDate) return null;

  const dateStr = formatDate(selectedDate);
  // The applied window defines the default granule count, but a preserved day
  // may still hold bookings outside it. Union the selected day's range so
  // those granules (and their live bookings) never disappear.
  const daySchedule = {
    start: Math.min(windowStart, dayStart ?? windowStart),
    end: Math.max(windowEnd, dayEnd ?? windowEnd),
  };
  const isDayPast = isPast(selectedDate);
  const allActive = checkAllActive(dateStr, daySchedule, activeHours);
  const dayRange =
    dayStart != null && dayEnd != null && dayEnd > dayStart
      ? { start: dayStart, end: dayEnd }
      : null;
  const applyDayHours = async (start: number, end: number) => {
    if (!onChangeDayHours) return;
    setAdjusting(true);
    try {
      await onChangeDayHours(dateStr, start, end);
    } finally {
      setAdjusting(false);
    }
  };

  return (
    <div className="schedule-time-slots">
      <h3 className="time-slots-title">
        🕐{' '}
        {selectedDate.toLocaleDateString('ru-RU', {
          weekday: 'long',
          day: 'numeric',
          month: 'long',
        })}
        {isDayPast && <span className="time-slots-past">— прошедший день</span>}
      </h3>

      <div className="time-slots-header">
        <label className="time-slots-checkbox">
          <input
            type="checkbox"
            checked={allActive}
            onChange={(e) =>
              toggleAllHours(dateStr, daySchedule, e.target.checked, activeHours, onToggleHour)
            }
          />
          <span>Выбрать все часы</span>
        </label>

        {dayRange && !isDayPast && onChangeDayHours && (
          <div className="time-slots-day-hours">
            <span className="time-slots-day-hours-label">Гранулы дня</span>
            <div className="day-hours-group">
              <button
                type="button"
                className="day-hours-btn"
                title="Добавить час раньше"
                aria-label="Добавить гранулу раньше"
                disabled={adjusting || dayRange.start <= 0}
                onClick={() => applyDayHours(dayRange.start - 1, dayRange.end)}
              >
                −
              </button>
              <span className="day-hours-value">{formatHour(dayRange.start)}</span>
              <button
                type="button"
                className="day-hours-btn"
                title="Убрать первый час"
                aria-label="Убрать первую гранулу"
                disabled={adjusting || dayRange.start + 1 >= dayRange.end}
                onClick={() => applyDayHours(dayRange.start + 1, dayRange.end)}
              >
                +
              </button>
            </div>
            <span className="day-hours-dash">—</span>
            <div className="day-hours-group">
              <button
                type="button"
                className="day-hours-btn"
                title="Убрать последний час"
                aria-label="Убрать последнюю гранулу"
                disabled={adjusting || dayRange.end - 1 <= dayRange.start}
                onClick={() => applyDayHours(dayRange.start, dayRange.end - 1)}
              >
                −
              </button>
              <span className="day-hours-value">{formatHour(dayRange.end)}</span>
              <button
                type="button"
                className="day-hours-btn"
                title="Добавить час позже"
                aria-label="Добавить гранулу позже"
                disabled={adjusting || dayRange.end >= 24}
                onClick={() => applyDayHours(dayRange.start, dayRange.end + 1)}
              >
                +
              </button>
            </div>
          </div>
        )}
      </div>

      <div className="time-slots-list">
        {generateHourSlots(
          selectedDate,
          daySchedule,
          appointments,
          activeHours,
          isDayPast,
          onToggleHour,
          onOpenBooking,
          onCancelAppointment,
          onConfirmAppointment,
        )}
      </div>
    </div>
  );
}

function checkAllActive(
  dateStr: string,
  hours: { start: number; end: number },
  activeHours: Record<string, boolean>,
): boolean {
  for (let h = hours.start; h < hours.end; h++) {
    if (!activeHours[`${dateStr}-${h}`]) return false;
  }
  return hours.end > hours.start;
}

function toggleAllHours(
  dateStr: string,
  hours: { start: number; end: number },
  checked: boolean,
  activeHours: Record<string, boolean>,
  onToggle: (dateStr: string, hour: number) => void,
) {
  for (let h = hours.start; h < hours.end; h++) {
    if (checked !== !!activeHours[`${dateStr}-${h}`]) {
      onToggle(dateStr, h);
    }
  }
}

function generateHourSlots(
  date: Date,
  hours: { start: number; end: number },
  appointments: Appointment[],
  activeHours: Record<string, boolean>,
  _dayPast: boolean,
  onToggle: (dateStr: string, hour: number) => void,
  onOpenBooking: (date: Date, hour: number) => void,
  onCancelAppointment: (id: number) => Promise<void>,
  onConfirmAppointment?: (id: number) => Promise<void>,
): React.ReactNode[] {
  const slots: React.ReactNode[] = [];
  const dateStr = formatDate(date);

  for (let h = hours.start; h < hours.end; h++) {
    const slotsForHour = getAppointmentsForSlot(appointments, date, h);
    // One granule = one live booking. Cancelled history stays visible
    // below, but the granule color and buttons follow live bookings only:
    // after a cancel the granule is green and bookable again.
    const live = slotsForHour.filter((s) => s.status !== 'cancelled');
    // Span continuation: a long service (e.g. 90 мин) occupies the next
    // granules too — they render busy and cannot be booked separately.
    const coveredBy = live.length === 0 ? getCoveringLive(appointments, date, h) : null;
    const busy = coveredBy ?? null;
    const status = live.length > 0 ? getSlotStatus(live) : (busy?.status ?? 'free');
    const past = isSlotPast(date, h);
    const hourActive = !!activeHours[`${dateStr}-${h}`];
    const latestLive = live.length > 0 ? live.reduce((a, b) => (a.id > b.id ? a : b)) : null;
    const spanNote =
      latestLive !== null && appointmentSpanHours(latestLive) > 1
        ? ` · ${appointmentSpanHours(latestLive)} гр.`
        : '';

    slots.push(
      <div
        key={h}
        className={`time-slot ${past ? 'slot-past' : hourActive ? 'slot-active' : 'slot-inactive'} ${status !== 'free' ? `slot-${status}` : ''}${coveredBy ? ' slot-covered' : ''}`}
      >
        <label className="time-slot-checkbox">
          <input
            type="checkbox"
            checked={hourActive}
            onChange={() => onToggle(dateStr, h)}
            disabled={past}
          />
        </label>

        <span className="time-slot-time">{formatHour(h)}</span>

        {slotsForHour.length > 0 ? (
          <div className="time-slot-appointments">
            {slotsForHour.map((a) => (
              <div
                key={a.id}
                className="time-slot-appt"
                title={a.notes ? `💬 ${a.notes}` : undefined}
              >
                <span className="appt-client">{a.client_name || 'Клиент'}</span>
                <span className="appt-service">
                  {a.service_name}
                  {a.status !== 'cancelled' && appointmentSpanHours(a) > 1
                    ? ` · ${appointmentSpanHours(a)} гр.`
                    : ''}
                </span>
                <span className={`appt-status status-${a.status}`}>
                  {STATUS_CONFIG[a.status]?.label || a.status}
                </span>
                {a.discount_label ? (
                  <span className="appt-discount" title={`Скидка: ${a.discount_label}`}>
                    🏷 {a.discount_label}
                  </span>
                ) : null}
                {a.notes ? <span className="appt-notes">💬 {a.notes}</span> : null}
              </div>
            ))}
          </div>
        ) : busy ? (
          <div className="time-slot-appointments">
            <div className="time-slot-appt">
              <span className="appt-client">{busy.client_name || 'Клиент'}</span>
              <span className="appt-service">{busy.service_name} · продолжение</span>
              <span className={`appt-status status-${busy.status}`}>
                {STATUS_CONFIG[busy.status]?.label || busy.status}
              </span>
            </div>
          </div>
        ) : (
          <span className="time-slot-status">
            {past ? 'Прошёл' : hourActive ? 'Свободно' : 'Неактивен'}
          </span>
        )}

        {!past && hourActive && latestLive === null && coveredBy === null && (
          <button
            className="btn btn-sm btn-book"
            onClick={() => onOpenBooking(date, h)}
            title="Записать клиента"
          >
            + Записать
          </button>
        )}
        {!past && latestLive !== null && (
          <span className="slot-actions">
            {latestLive.status === 'pending' && onConfirmAppointment && (
              <button
                className="btn btn-sm btn-confirm"
                title={`Подтвердить запись: ${latestLive.client_name || 'клиент'}${spanNote}`}
                onClick={async (e) => {
                  const btn = e.currentTarget;
                  btn.disabled = true;
                  try {
                    await onConfirmAppointment(latestLive.id);
                  } finally {
                    btn.disabled = false;
                  }
                }}
              >
                ✓ Подтвердить
              </button>
            )}
            <button
              className="btn btn-sm btn-cancel"
              title={`Отменить запись: ${latestLive.client_name || 'клиент'}${spanNote}`}
              onClick={async (e) => {
                const btn = e.currentTarget;
                btn.disabled = true;
                try {
                  await onCancelAppointment(latestLive.id);
                } finally {
                  btn.disabled = false;
                }
              }}
            >
              ✕ Отменить
            </button>
          </span>
        )}
      </div>,
    );
  }
  return slots;
}
