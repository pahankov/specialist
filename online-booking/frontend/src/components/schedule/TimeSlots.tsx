import { useState } from 'react';
import type { Appointment } from '../../api/types';
import {
  getAppointmentsForSlot,
  getCoveringLive,
  getSlotStatus,
  appointmentSpanSlots,
  formatSlotTime,
  isSlotPast,
  isPast,
  STATUS_CONFIG,
  formatDate,
} from './helpers';
import { GranuleModeToggle } from './GranuleModeToggle';
import './ScheduleComponents.css';

interface TimeSlotsProps {
  selectedDate: Date | null;
  appointments: Appointment[];
  activeHours: Record<string, boolean>;
  onToggleHour: (dateStr: string, slot: number) => void;
  onOpenBooking: (date: Date, slot: number) => void;
  onCancelAppointment: (id: number) => Promise<void>;
  onConfirmAppointment?: (id: number) => Promise<void>;
  /** Slot size in minutes (60 / 30 / 15). */
  slotMinutes: 60 | 30 | 15;
  /** Applied work window: granules render for [windowStartSlot, windowEndSlot). */
  windowStartSlot?: number;
  windowEndSlot?: number;
  /** Stored range of the selected working day (in slots). */
  dayStartSlot?: number;
  dayEndSlot?: number;
  onChangeDaySlots?: (dateStr: string, startSlot: number, endSlot: number) => Promise<void> | void;
  /** Change the granule size for this day only (not the whole month). */
  onSlotMinutesChange?: (size: 60 | 30 | 15) => void;
}

const SLOTS_PER_DAY = (slotMinutes: number) => Math.ceil((24 * 60) / slotMinutes);

export function TimeSlots({
  selectedDate,
  appointments,
  activeHours,
  onToggleHour,
  onOpenBooking,
  onCancelAppointment,
  onConfirmAppointment,
  slotMinutes = 60,
  windowStartSlot,
  windowEndSlot,
  dayStartSlot,
  dayEndSlot,
  onChangeDaySlots,
  onSlotMinutesChange,
}: TimeSlotsProps) {
  const [adjusting, setAdjusting] = useState(false);
  if (!selectedDate) return null;

  const dateStr = formatDate(selectedDate);
  const maxSlot = SLOTS_PER_DAY(slotMinutes);
  const defaultStart = windowStartSlot ?? 0;
  const defaultEnd = windowEndSlot ?? maxSlot;
  // The day's own persisted range (when set) drives both the ± stepper and
  // the rendered list. The global window is only a fallback for days without
  // their own range — otherwise granules added and then removed with the ±
  // buttons would stay visible as inactive leftovers.
  const dayRange =
    dayStartSlot != null && dayEndSlot != null && dayEndSlot > dayStartSlot
      ? { start: dayStartSlot, end: dayEndSlot }
      : null;
  const baseRange = dayRange ?? { start: defaultStart, end: defaultEnd };
  // Never hide a live booking, even if it sits outside the stored day range
  // (legacy data or a range that was trimmed before this rule existed).
  const scheduledRange = getLiveAppointmentRange(appointments, selectedDate, slotMinutes);
  const daySchedule = scheduledRange
    ? {
        start: Math.min(baseRange.start, scheduledRange.start),
        end: Math.max(baseRange.end, scheduledRange.end),
      }
    : baseRange;
  const isDayPast = isPast(selectedDate);
  const allActive = checkAllActive(dateStr, daySchedule, activeHours);

  const applyDaySlots = async (start: number, end: number) => {
    if (!onChangeDaySlots) return;
    setAdjusting(true);
    try {
      await onChangeDaySlots(dateStr, start, end);
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
              toggleAllSlots(dateStr, daySchedule, e.target.checked, activeHours, onToggleHour)
            }
          />
          <span>Выбрать все гранулы</span>
        </label>

        {dayRange && !isDayPast && onChangeDaySlots && (
          <div className="time-slots-day-hours">
            <span className="time-slots-day-hours-label">Гранулы дня</span>
            <div className="day-hours-group">
              <button
                type="button"
                className="day-hours-btn"
                title="Добавить гранулу раньше"
                aria-label="Добавить гранулу раньше"
                disabled={adjusting || dayRange.start <= 0}
                onClick={() => applyDaySlots(dayRange.start - 1, dayRange.end)}
              >
                −
              </button>
              <span className="day-hours-value">{formatSlotTime(dayRange.start, slotMinutes)}</span>
              <button
                type="button"
                className="day-hours-btn"
                title="Убрать первую гранулу"
                aria-label="Убрать первую гранулу"
                disabled={adjusting || dayRange.start + 1 >= dayRange.end}
                onClick={() => applyDaySlots(dayRange.start + 1, dayRange.end)}
              >
                +
              </button>
            </div>
            <span className="day-hours-dash">—</span>
            <div className="day-hours-group">
              <button
                type="button"
                className="day-hours-btn"
                title="Убрать последнюю гранулу"
                aria-label="Убрать последнюю гранулу"
                disabled={adjusting || dayRange.end - 1 <= dayRange.start}
                onClick={() => applyDaySlots(dayRange.start, dayRange.end - 1)}
              >
                −
              </button>
              <span className="day-hours-value">{formatSlotTime(dayRange.end, slotMinutes)}</span>
              <button
                type="button"
                className="day-hours-btn"
                title="Добавить гранулу позже"
                aria-label="Добавить гранулу позже"
                disabled={adjusting || dayRange.end >= maxSlot}
                onClick={() => applyDaySlots(dayRange.start, dayRange.end + 1)}
              >
                +
              </button>
            </div>
            {onSlotMinutesChange && (
              <div className="time-slots-day-mode">
                <span className="time-slots-day-mode-label">Режим дня</span>
                <GranuleModeToggle
                  value={slotMinutes}
                  onChange={onSlotMinutesChange}
                  ariaLabel="Режим гранул на этот день"
                  compact
                />
              </div>
            )}
          </div>
        )}
      </div>

      <div className="time-slots-list">
        {generateSlots(
          selectedDate,
          daySchedule,
          appointments,
          activeHours,
          isDayPast,
          slotMinutes,
          onToggleHour,
          onOpenBooking,
          onCancelAppointment,
          onConfirmAppointment,
        )}
      </div>
    </div>
  );
}

/** Slot range covered by live bookings on the selected day, if any. */
function getLiveAppointmentRange(
  appointments: Appointment[],
  date: Date,
  slotMinutes: 60 | 30 | 15,
): { start: number; end: number } | null {
  let start = Infinity;
  let end = -Infinity;
  for (const appointment of appointments) {
    if (appointment.status === 'cancelled') continue;
    const d = new Date(appointment.appointment_date);
    if (Number.isNaN(d.getTime())) continue;
    if (
      d.getFullYear() !== date.getFullYear() ||
      d.getMonth() !== date.getMonth() ||
      d.getDate() !== date.getDate()
    )
      continue;
    const slot = Math.round((d.getHours() * 60 + d.getMinutes()) / slotMinutes);
    start = Math.min(start, slot);
    end = Math.max(end, slot + appointmentSpanSlots(appointment, slotMinutes));
  }
  return Number.isFinite(start) && Number.isFinite(end) ? { start, end } : null;
}

function checkAllActive(
  dateStr: string,
  hours: { start: number; end: number },
  activeHours: Record<string, boolean>,
): boolean {
  for (let s = hours.start; s < hours.end; s++) {
    if (!activeHours[`${dateStr}-${s}`]) return false;
  }
  return hours.end > hours.start;
}

function toggleAllSlots(
  dateStr: string,
  hours: { start: number; end: number },
  checked: boolean,
  activeHours: Record<string, boolean>,
  onToggle: (dateStr: string, slot: number) => void,
) {
  for (let s = hours.start; s < hours.end; s++) {
    if (checked !== !!activeHours[`${dateStr}-${s}`]) {
      onToggle(dateStr, s);
    }
  }
}

interface GranuleProps {
  date: Date;
  dateStr: string;
  slot: number;
  slotMinutes: 60 | 30 | 15;
  appointments: Appointment[];
  activeHours: Record<string, boolean>;
  onToggle: (dateStr: string, slot: number) => void;
  onOpenBooking: (date: Date, slot: number) => void;
  onCancelAppointment: (id: number) => Promise<void>;
  onConfirmAppointment?: (id: number) => Promise<void>;
}

/** One bookable granule. Hour mode renders it as a top-level row; half- and
 * quarter-hour modes render the same row nested inside its hour card. */
function Granule({
  date,
  dateStr,
  slot,
  slotMinutes,
  appointments,
  activeHours,
  onToggle,
  onOpenBooking,
  onCancelAppointment,
  onConfirmAppointment,
  nested,
}: GranuleProps & { nested: boolean }) {
  const slotAppointments = getAppointmentsForSlot(appointments, date, slot, slotMinutes);
  const live = slotAppointments.filter((a) => a.status !== 'cancelled');
  const coveredBy =
    live.length === 0 ? getCoveringLive(appointments, date, slot, slotMinutes) : null;
  const busy = coveredBy ?? null;
  const status = live.length > 0 ? getSlotStatus(live) : (busy?.status ?? 'free');
  const past = isSlotPast(date, slot, slotMinutes);
  const slotActive = !!activeHours[`${dateStr}-${slot}`];
  const latestLive = live.length > 0 ? live.reduce((a, b) => (a.id > b.id ? a : b)) : null;
  const span = latestLive ? appointmentSpanSlots(latestLive, slotMinutes) : 1;
  const spanNote = latestLive !== null && span > 1 ? ` · ${span} гр.` : '';

  return (
    <div
      data-testid="time-slot"
      className={`${nested ? 'time-subslot' : 'time-slot'} ${past ? 'slot-past' : slotActive ? 'slot-active' : 'slot-inactive'} ${status !== 'free' ? `slot-${status}` : ''}${coveredBy ? ' slot-covered' : ''}`}
    >
      <label className="time-slot-checkbox">
        <input
          type="checkbox"
          checked={slotActive}
          onChange={() => onToggle(dateStr, slot)}
          disabled={past}
        />
      </label>

      <span className={nested ? 'time-subslot-time' : 'time-slot-time'}>
        {formatSlotTime(slot, slotMinutes)}
      </span>

      {slotAppointments.length > 0 ? (
        <div className="time-slot-appointments">
          {slotAppointments.map((a) => (
            <div
              key={a.id}
              className="time-slot-appt"
              title={a.notes ? `💬 ${a.notes}` : undefined}
            >
              <span className="appt-client">{a.client_name || 'Клиент'}</span>
              <span className="appt-service">
                {a.service_name}
                {a.status !== 'cancelled' && appointmentSpanSlots(a, slotMinutes) > 1
                  ? ` · ${appointmentSpanSlots(a, slotMinutes)} гр.`
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
          {past ? 'Прошёл' : slotActive ? 'Свободно' : 'Неактивен'}
        </span>
      )}

      {!past && slotActive && latestLive === null && coveredBy === null && (
        <button
          className="btn btn-sm btn-book"
          onClick={() => onOpenBooking(date, slot)}
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
    </div>
  );
}

function generateSlots(
  date: Date,
  hours: { start: number; end: number },
  appointments: Appointment[],
  activeHours: Record<string, boolean>,
  _dayPast: boolean,
  slotMinutes: 60 | 30 | 15,
  onToggle: (dateStr: string, slot: number) => void,
  onOpenBooking: (date: Date, slot: number) => void,
  onCancelAppointment: (id: number) => Promise<void>,
  onConfirmAppointment?: (id: number) => Promise<void>,
): React.ReactNode[] {
  const dateStr = formatDate(date);
  const maxSlot = SLOTS_PER_DAY(slotMinutes);
  const end = Math.min(hours.end, maxSlot);
  const granuleProps = {
    date,
    dateStr,
    slotMinutes,
    appointments,
    activeHours,
    onToggle,
    onOpenBooking,
    onCancelAppointment,
    onConfirmAppointment,
  };

  // Hour mode: one row per granule, exactly as before.
  if (slotMinutes === 60) {
    const rows: React.ReactNode[] = [];
    for (let s = hours.start; s < end; s++) {
      rows.push(<Granule key={s} {...granuleProps} slot={s} nested={false} />);
    }
    return rows;
  }

  // Half/quarter-hour mode: keep the hourly card, split its hour into
  // subgranules inside. The number of top-level cards therefore stays equal
  // to the number of hours while each hour becomes finer-grained.
  const perHour = 60 / slotMinutes;
  const firstHour = Math.floor(hours.start / perHour);
  const lastHour = Math.ceil(end / perHour);
  const groups: React.ReactNode[] = [];

  for (let hour = firstHour; hour < lastHour; hour++) {
    const groupStart = Math.max(hours.start, hour * perHour);
    const groupEnd = Math.min(end, (hour + 1) * perHour);
    if (groupEnd <= groupStart) continue;

    const subslots: React.ReactNode[] = [];
    let hasActive = false;
    for (let s = groupStart; s < groupEnd; s++) {
      if (activeHours[`${dateStr}-${s}`]) hasActive = true;
      subslots.push(<Granule key={s} {...granuleProps} slot={s} nested />);
    }

    groups.push(
      <div
        key={`hour-${hour}`}
        className={`time-hour-group${hasActive ? ' has-active' : ''}`}
        data-testid="time-hour-group"
      >
        <div className="time-hour-body">{subslots}</div>
      </div>,
    );
  }
  return groups;
}
