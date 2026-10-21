import { useCallback, useRef } from 'react';
import type { Appointment, DaySchedule } from '../../api/types';
import {
  formatDate,
  getMonthDays,
  getAppointmentsForSlot,
  isPast,
  isToday,
  pluralBookings,
  pluralHolds,
} from './helpers';
import './ScheduleComponents.css';

interface CalendarProps {
  currentMonth: Date;
  schedule: Record<string, DaySchedule>;
  appointments: Appointment[];
  selectedDate: Date | null;
  onPrevMonth: () => void;
  onNextMonth: () => void;
  onSelectDate: (date: Date) => void;
  onToggleDay: (date: Date) => void;
  /** Client booking view: no day toggling, click only selects a date. */
  interactive?: boolean;
  /** Master history: past days are selectable (read-only day view). */
  selectablePast?: boolean;
  /** Template preview: inactive days that will become working. */
  previewWorkDates?: Set<string>;
  /** Template preview: active days that will become rest days. */
  previewOffDates?: Set<string>;
  /** Granule size in minutes — shown as a half-filled dot on working days. */
  slotMinutes?: 60 | 30 | 15;
}

const LONG_PRESS_MS = 500;

export function Calendar({
  currentMonth,
  schedule,
  appointments,
  selectedDate,
  onPrevMonth,
  onNextMonth,
  onSelectDate,
  onToggleDay,
  interactive = true,
  selectablePast = false,
  slotMinutes = 60,
  previewWorkDates,
  previewOffDates,
}: CalendarProps) {
  const monthDays = getMonthDays(currentMonth);
  const monthName = currentMonth.toLocaleString('ru-RU', { month: 'long', year: 'numeric' });

  const pressTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pressDateRef = useRef<Date | null>(null);
  // Long-press also produces a click on release — swallow that click; the
  // long-press itself both toggles the day AND selects it (navigates to it).
  const longPressFiredRef = useRef(false);

  const handlePointerDown = useCallback(
    (e: React.PointerEvent<HTMLElement>, date: Date) => {
      if (!interactive) return;
      const tile = (e.target as HTMLElement).closest('.calendar-day');
      if (!tile || isPast(date)) return;

      longPressFiredRef.current = false;
      pressDateRef.current = date;
      if (pressTimerRef.current) {
        clearTimeout(pressTimerRef.current);
        pressTimerRef.current = null;
      }
      pressTimerRef.current = setTimeout(() => {
        if (pressDateRef.current) {
          longPressFiredRef.current = true;
          onToggleDay(pressDateRef.current);
          onSelectDate(pressDateRef.current);
          pressDateRef.current = null;
        }
      }, LONG_PRESS_MS);
    },
    [onToggleDay, onSelectDate, interactive],
  );

  const handlePointerUp = useCallback(() => {
    if (pressTimerRef.current) {
      clearTimeout(pressTimerRef.current);
      pressTimerRef.current = null;
    }
    pressDateRef.current = null;
  }, []);

  const handleDayClick = useCallback(
    (date: Date, isCurrentMonth: boolean, past: boolean) => {
      if (longPressFiredRef.current) {
        longPressFiredRef.current = false;
        return;
      }
      if (isCurrentMonth && (!past || selectablePast)) onSelectDate(date);
    },
    [onSelectDate, selectablePast],
  );

  // Desktop shortcut: double-click toggles the working day (long-press
  // stays for touch). Past days never toggle.
  const handleDayDoubleClick = useCallback(
    (date: Date, isCurrentMonth: boolean, past: boolean) => {
      if (!interactive || !isCurrentMonth || past) return;
      onToggleDay(date);
      onSelectDate(date);
    },
    [interactive, onToggleDay, onSelectDate],
  );

  return (
    <div className="schedule-calendar">
      <div className="calendar-header">
        <button className="calendar-nav-btn" onClick={onPrevMonth}>
          ←
        </button>
        <span className="calendar-month-name">{monthName}</span>
        <button className="calendar-nav-btn" onClick={onNextMonth}>
          →
        </button>
      </div>

      <div className="calendar-hint">
        {interactive
          ? '👆 День: клик — выбрать · даблклик — вкл/выкл рабочего дня (на телефоне — удерживайте)'
          : '👆 Нажмите на день, чтобы увидеть свободные часы'}
      </div>

      <div className="calendar-grid">
        {['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'].map((name, i) => (
          <div key={i} className={`calendar-day-header ${i >= 5 ? 'weekend' : ''}`}>
            {name}
          </div>
        ))}

        {monthDays.map((day, i) => {
          const dateStr = formatDate(day.date);
          const active = !!schedule[dateStr];
          const today = isToday(day.date);
          const past = isPast(day.date);
          const selected =
            selectedDate?.getDate() === day.date.getDate() &&
            selectedDate?.getMonth() === day.date.getMonth();
          const hours = schedule[dateStr];

          let apptCount = 0;
          let holdCount = 0;
          const liveIds = new Set<number>();
          const holdIds = new Set<number>();
          if (active && day.isCurrentMonth && hours) {
            for (let h = hours.start; h < hours.end; h++) {
              const slots = getAppointmentsForSlot(appointments, day.date, h, slotMinutes);
              for (const s of slots) {
                if (s.status === 'cancelled') continue;
                if (s.status === 'pending') holdIds.add(s.id);
                else liveIds.add(s.id);
              }
            }
            // One label per day: unique live bookings touching it
            // (long services span granules but count once).
            holdCount = holdIds.size;
            apptCount = liveIds.size;
          }
          const holdsOnly = holdIds.size > 0 && liveIds.size === 0;
          // Template preview is about actual changes only:
          // - inactive -> working (dashed green dot),
          // - active without live bookings -> rest day (dashed gray dot).
          const previewWork =
            day.isCurrentMonth && !past && !active && !!previewWorkDates?.has(dateStr);
          const previewOff =
            day.isCurrentMonth &&
            !past &&
            active &&
            liveIds.size === 0 &&
            holdIds.size === 0 &&
            !!previewOffDates?.has(dateStr);
          // Pending-only days glow amber (awaiting confirmation);
          // confirmed presence keeps the green booking tint.
          const dayLabel =
            holdCount > 0 && apptCount > 0
              ? `${pluralBookings(apptCount)} · ${pluralHolds(holdCount)}`
              : holdCount > 0
                ? pluralHolds(holdCount)
                : apptCount > 0
                  ? pluralBookings(apptCount)
                  : '';

          return (
            <div
              key={i}
              data-date={day.date.toISOString()}
              className={`calendar-day ${day.isCurrentMonth ? '' : 'other-month'} ${active ? 'active' : 'inactive'} ${today ? 'today' : ''} ${selected ? 'selected' : ''} ${past ? 'past' : ''} ${liveIds.size > 0 && !past ? 'has-bookings' : ''} ${holdsOnly && !past ? 'has-holds' : ''} ${previewWork ? 'preview-work' : ''} ${previewOff ? 'preview-off' : ''} ${(slotMinutes === 30 || slotMinutes === 15) && active ? 'slot30' : ''}`}
              title={
                previewWork
                  ? 'По графику будет рабочим после применения'
                  : previewOff
                    ? 'По графику станет выходным после применения'
                    : undefined
              }
              onClick={() => handleDayClick(day.date, day.isCurrentMonth, past)}
              onDoubleClick={() => handleDayDoubleClick(day.date, day.isCurrentMonth, past)}
              onPointerDown={(e) => handlePointerDown(e, day.date)}
              onPointerUp={handlePointerUp}
              onPointerCancel={handlePointerUp}
              onContextMenu={(e) => e.preventDefault()}
            >
              <div className="calendar-day-number">{day.date.getDate()}</div>
              <div
                className={`calendar-day-badge ${past ? 'badge-past' : active ? 'badge-active' : today ? 'badge-today' : 'badge-inactive'}`}
              >
                {past ? 'Прошёл' : active ? 'Рабочий' : today ? 'Сегодня' : 'Выходной'}
              </div>
              {active && !past && dayLabel !== '' && (
                <div className="calendar-day-count">{dayLabel}</div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
