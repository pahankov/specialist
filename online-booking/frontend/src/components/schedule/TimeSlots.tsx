import type { Appointment } from '../../api/types'
import { getAppointmentsForSlot, getSlotStatus, formatHour, isSlotPast, STATUS_CONFIG, formatDate, isPast } from './helpers'
import './ScheduleComponents.css'

interface TimeSlotsProps {
  selectedDate: Date | null
  appointments: Appointment[]
  activeHours: Record<string, boolean>
  onToggleHour: (dateStr: string, hour: number) => void
  onOpenBooking: (date: Date, hour: number) => void
  onCancelAppointment: (id: number) => Promise<void>
  /** Daily work window: granules render for [windowStart, windowEnd) regardless
   * of the stored day range (the range is derived from active granules). */
  windowStart?: number
  windowEnd?: number
}

export function TimeSlots({
  selectedDate,
  appointments,
  activeHours,
  onToggleHour,
  onOpenBooking,
  onCancelAppointment,
  windowStart = 8,
  windowEnd = 22,
}: TimeSlotsProps) {
  if (!selectedDate) return null

  const dateStr = formatDate(selectedDate)
  // Granules come from the work window, not the stored range: activating one
  // hour must never hide the others.
  const daySchedule = { start: windowStart, end: windowEnd }
  const isDayPast = isPast(selectedDate)
  const allActive = checkAllActive(dateStr, daySchedule, activeHours)

  return (
    <div className="schedule-time-slots">
      <h3 className="time-slots-title">
        🕐 {selectedDate.toLocaleDateString('ru-RU', { weekday: 'long', day: 'numeric', month: 'long' })}
        {isDayPast && <span className="time-slots-past">— прошедший день</span>}
      </h3>

      <div className="time-slots-header">
        <label className="time-slots-checkbox">
          <input
            type="checkbox"
            checked={allActive}
            onChange={(e) => toggleAllHours(dateStr, daySchedule, e.target.checked, activeHours, onToggleHour)}
          />
          <span>Выбрать все часы</span>
        </label>
      </div>

      <div className="time-slots-list">
        {generateHourSlots(selectedDate, daySchedule, appointments, activeHours, isDayPast, onToggleHour, onOpenBooking, onCancelAppointment)}
      </div>
    </div>
  )
}

function checkAllActive(dateStr: string, hours: { start: number; end: number }, activeHours: Record<string, boolean>): boolean {
  for (let h = hours.start; h < hours.end; h++) {
    if (!activeHours[`${dateStr}-${h}`]) return false
  }
  return hours.end > hours.start
}

function toggleAllHours(
  dateStr: string,
  hours: { start: number; end: number },
  checked: boolean,
  activeHours: Record<string, boolean>,
  onToggle: (dateStr: string, hour: number) => void
) {
  for (let h = hours.start; h < hours.end; h++) {
    if (checked !== !!activeHours[`${dateStr}-${h}`]) {
      onToggle(dateStr, h)
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
  onCancelAppointment: (id: number) => Promise<void>
): React.ReactNode[] {
  const slots: React.ReactNode[] = []
  const dateStr = formatDate(date)

  for (let h = hours.start; h < hours.end; h++) {
    const slotsForHour = getAppointmentsForSlot(appointments, date, h)
    // One granule = one live booking. Cancelled history stays visible
    // below, but the granule color and buttons follow live bookings only:
    // after a cancel the granule is green and bookable again.
    const live = slotsForHour.filter(s => s.status !== 'cancelled')
    const status = getSlotStatus(live)
    const past = isSlotPast(date, h)
    const hourActive = !!activeHours[`${dateStr}-${h}`]
    const latestLive = live.length > 0 ? live.reduce((a, b) => (a.id > b.id ? a : b)) : null

    slots.push(
      <div
        key={h}
        className={`time-slot ${past ? 'slot-past' : hourActive ? 'slot-active' : 'slot-inactive'} ${status !== 'free' ? `slot-${status}` : ''}`}
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
            {slotsForHour.map(a => (
              <div key={a.id} className="time-slot-appt">
                <span className="appt-client">{a.client_name || 'Клиент'}</span>
                <span className="appt-service">{a.service_name}</span>
                <span className={`appt-status status-${a.status}`}>
                  {STATUS_CONFIG[a.status]?.label || a.status}
                </span>
              </div>
            ))}
          </div>
        ) : (
          <span className="time-slot-status">
            {past ? 'Прошёл' : hourActive ? 'Свободно' : 'Неактивен'}
          </span>
        )}

        {!past && hourActive && latestLive === null && (
          <button className="btn btn-sm btn-book" onClick={() => onOpenBooking(date, h)} title="Записать клиента">
            + Записать
          </button>
        )}
        {!past && latestLive !== null && (
          <button
            className="btn btn-sm btn-cancel"
            title={`Отменить запись: ${latestLive.client_name || 'клиент'}`}
            onClick={async (e) => {
              const btn = e.currentTarget
              btn.disabled = true
              try {
                await onCancelAppointment(latestLive.id)
              } finally {
                btn.disabled = false
              }
            }}
          >
            ✕ Отменить
          </button>
        )}
      </div>
    )
  }
  return slots
}
