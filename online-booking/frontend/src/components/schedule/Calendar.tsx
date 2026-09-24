import { useCallback, useRef } from 'react'
import type { Appointment, DaySchedule } from '../../api/types'
import { formatDate, getMonthDays, getAppointmentsForSlot, getSlotStatus, isPast, isToday, isSlotPast } from './helpers'
import './ScheduleComponents.css'

interface CalendarProps {
  currentMonth: Date
  schedule: Record<string, DaySchedule>
  appointments: Appointment[]
  selectedDate: Date | null
  onPrevMonth: () => void
  onNextMonth: () => void
  onSelectDate: (date: Date) => void
  onToggleDay: (date: Date) => void
  onAddSlot: (date: Date) => void
  longPressTriggered: boolean
}

const LONG_PRESS_MS = 500

export function Calendar({
  currentMonth,
  schedule,
  appointments,
  selectedDate,
  onPrevMonth,
  onNextMonth,
  onSelectDate,
  onToggleDay,
  onAddSlot,
  longPressTriggered,
}: CalendarProps) {
  const monthDays = getMonthDays(currentMonth)
  const monthName = currentMonth.toLocaleString('ru-RU', { month: 'long', year: 'numeric' })
  
  const pressTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const pressDateRef = useRef<Date | null>(null)

  const handlePointerDown = useCallback((e: React.PointerEvent<HTMLElement>, date: Date) => {
    const tile = (e.target as HTMLElement).closest('.calendar-day')
    if (!tile || isPast(date)) return

    pressDateRef.current = date
    if (pressTimerRef.current) {
      clearTimeout(pressTimerRef.current)
      pressTimerRef.current = null
    }
    pressTimerRef.current = setTimeout(() => {
      if (pressDateRef.current) {
        onToggleDay(pressDateRef.current)
        pressDateRef.current = null
      }
    }, LONG_PRESS_MS)
  }, [onToggleDay])

  const handlePointerUp = useCallback(() => {
    if (pressTimerRef.current) {
      clearTimeout(pressTimerRef.current)
      pressTimerRef.current = null
    }
    pressDateRef.current = null
  }, [])

  return (
    <div className="schedule-calendar">
      <div className="calendar-header">
        <button className="calendar-nav-btn" onClick={onPrevMonth}>←</button>
        <span className="calendar-month-name">{monthName}</span>
        <button className="calendar-nav-btn" onClick={onNextMonth}>→</button>
      </div>

      <div className="calendar-grid">
        {['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'].map((name, i) => (
          <div key={i} className={`calendar-day-header ${i >= 5 ? 'weekend' : ''}`}>
            {name}
          </div>
        ))}

        {monthDays.map((day, i) => {
          const dateStr = formatDate(day.date)
          const active = !!schedule[dateStr]
          const today = isToday(day.date)
          const past = isPast(day.date)
          const selected = selectedDate?.getDate() === day.date.getDate() &&
                          selectedDate?.getMonth() === day.date.getMonth()
          const hours = schedule[dateStr]
          
          let apptCount = 0
          if (active && day.isCurrentMonth && hours) {
            for (let h = hours.start; h < hours.end; h++) {
              const slots = getAppointmentsForSlot(appointments, day.date, h)
              const status = getSlotStatus(slots)
              if (status !== 'free' && isSlotPast(day.date, h)) apptCount++
            }
          }

          return (
            <div
              key={i}
              data-date={day.date.toISOString()}
              className={`calendar-day ${day.isCurrentMonth ? '' : 'other-month'} ${active ? 'active' : 'inactive'} ${today ? 'today' : ''} ${selected ? 'selected' : ''}`}
              onClick={() => day.isCurrentMonth && !past && !longPressTriggered && onSelectDate(day.date)}
              onPointerDown={(e) => handlePointerDown(e, day.date)}
              onPointerUp={handlePointerUp}
              onPointerCancel={handlePointerUp}
            >
              <div className="calendar-day-number">{day.date.getDate()}</div>
              <div className={`calendar-day-badge ${past ? 'badge-past' : active ? 'badge-active' : today ? 'badge-today' : 'badge-inactive'}`}>
                {past ? 'Прошёл' : active ? 'Рабочий' : today ? 'Сегодня' : 'Выходной'}
              </div>
              {active && !past && apptCount > 0 && (
                <div className="calendar-day-count">{apptCount} записей</div>
              )}
              {!active && !past && day.isCurrentMonth && (
                <button
                  className="calendar-add-slot-btn"
                  onClick={(e) => {
                    e.stopPropagation()
                    onAddSlot(day.date)
                  }}
                  title="Добавить рабочий день"
                >
                  +
                </button>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
