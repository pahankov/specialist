import { useEffect, useState } from 'react'
import { adminApi } from '../api/adminClient'
import './SchedulePage.css'

const dayNames = ['Вс', 'Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб']
const dayNamesFull = ['Воскресенье', 'Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота']

const statusConfig = {
  pending: { label: 'Ожидает', color: '#ffc107', bg: '#fff8e1', text: '#f57f17' },
  confirmed: { label: 'Подтверждена', color: '#2196f3', bg: '#e3f2fd', text: '#1565c0' },
  completed: { label: 'Завершена', color: '#4caf50', bg: '#e8f5e9', text: '#2e7d32' },
  cancelled: { label: 'Отменена', color: '#9e9e9e', bg: '#f5f5f5', text: '#616161' },
}

function SchedulePage() {
  const [schedule, setSchedule] = useState<Record<number, { start: number; end: number }>>({})
  const [currentMonth, setCurrentMonth] = useState(new Date())
  const [selectedDate, setSelectedDate] = useState<Date | null>(null)
  const [appointments, setAppointments] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const fetchSchedule = async () => {
    try {
      const resp = await adminApi.getWorkingHours()
      const map: Record<number, { start: number; end: number }> = {}
      resp.data.forEach((h: any) => {
        const startHour = parseInt(h.start_time?.slice(0, 2) || '10')
        const endHour = parseInt(h.end_time?.slice(0, 2) || '18')
        map[h.day_of_week] = { start: startHour, end: endHour }
      })
      setSchedule(map)
    } catch (err: any) {
      if (err.response?.status === 401) {
        localStorage.removeItem('access_token')
        window.location.href = '/admin/login'
      } else {
        setError('Ошибка загрузки')
      }
    } finally {
      setLoading(false)
    }
  }

  const fetchAppointmentsForDate = async (date: Date) => {
    const dateStr = date.toISOString().split('T')[0]
    try {
      const resp = await adminApi.getAppointmentsByDate(dateStr, dateStr)
      setAppointments(resp.data)
    } catch {
      setAppointments([])
    }
  }

  useEffect(() => { fetchSchedule() }, [])

  useEffect(() => {
    if (selectedDate) {
      fetchAppointmentsForDate(selectedDate)
    }
  }, [selectedDate])

  const getMonthDays = (date: Date) => {
    const year = date.getFullYear()
    const month = date.getMonth()
    const firstDay = new Date(year, month, 1)
    const lastDay = new Date(year, month + 1, 0)
    const days: { date: Date; isCurrentMonth: boolean }[] = []

    const startDayOfWeek = firstDay.getDay()
    for (let i = 0; i < startDayOfWeek; i++) {
      const padDate = new Date(year, month, 1 - (startDayOfWeek - i))
      days.push({ date: padDate, isCurrentMonth: false })
    }

    for (let d = 1; d <= lastDay.getDate(); d++) {
      days.push({ date: new Date(year, month, d), isCurrentMonth: true })
    }

    return days
  }

  const isDayActive = (date: Date) => {
    const dow = date.getDay()
    return !!schedule[dow]
  }

  const getAppointmentsForSlot = (date: Date, hour: number) => {
    const dateStr = date.toISOString().split('T')[0]
    const hourStr = `${String(hour).padStart(2, '0')}:00`
    return appointments.filter(a => {
      const aDate = a.appointment_date.split('T')[0]
      const aHour = a.appointment_date.split('T')[1]?.slice(0, 5)
      return aDate === dateStr && aHour === hourStr
    })
  }

  const getSlotStatus = (date: Date, hour: number) => {
    const slots = getAppointmentsForSlot(date, hour)
    if (slots.length === 0) return 'free'
    
    // If multiple appointments (shouldn't happen), prioritize by status
    const statusOrder = ['completed', 'confirmed', 'pending', 'cancelled']
    for (const status of statusOrder) {
      if (slots.some(s => s.status === status)) return status
    }
    return 'pending'
  }

  const goToPrevMonth = () => {
    setCurrentMonth(new Date(currentMonth.getFullYear(), currentMonth.getMonth() - 1, 1))
  }

  const goToNextMonth = () => {
    setCurrentMonth(new Date(currentMonth.getFullYear(), currentMonth.getMonth() + 1, 1))
  }

  const isToday = (date: Date) => {
    const today = new Date()
    return date.getDate() === today.getDate() &&
      date.getMonth() === today.getMonth() &&
      date.getFullYear() === today.getFullYear()
  }

  const formatHour = (h: number) => String(h).padStart(2, '0') + ':00'

  if (loading) return <div className="admin-main"><div className="loading">Загрузка...</div></div>
  if (error) return <div className="admin-main"><div className="error-message">{error}</div></div>

  const monthDays = getMonthDays(currentMonth)
  const monthName = currentMonth.toLocaleString('ru-RU', { month: 'long', year: 'numeric' })

  return (
    <div className="admin-main">
      <div className="page-header">
        <h1>📅 Рабочее расписание</h1>
        <p>Нажмите на день чтобы увидеть бронирования</p>
      </div>

      {/* Legend */}
      <div className="legend card">
        <div className="legend-item">
          <span className="legend-dot free" />
          <span>Свободно</span>
        </div>
        <div className="legend-item">
          <span className="legend-dot pending" />
          <span>Ожидает</span>
        </div>
        <div className="legend-item">
          <span className="legend-dot confirmed" />
          <span>Подтверждена</span>
        </div>
        <div className="legend-item">
          <span className="legend-dot completed" />
          <span>Завершена</span>
        </div>
        <div className="legend-item">
          <span className="legend-dot cancelled" />
          <span>Отменена</span>
        </div>
      </div>

      {/* Calendar */}
      <div className="schedule-calendar">
        <div className="calendar-header">
          <button className="month-nav" onClick={goToPrevMonth}>←</button>
          <span className="month-title">{monthName}</span>
          <button className="month-nav" onClick={goToNextMonth}>→</button>
        </div>

        <div className="calendar-weekdays">
          {dayNames.map((name, i) => (
            <div key={i} className={`weekday ${i === 0 ? 'sunday' : ''} ${i === 6 ? 'saturday' : ''}`}>
              {name}
            </div>
          ))}
        </div>

        <div className="calendar-grid">
          {monthDays.map((day, i) => {
            const active = isDayActive(day.date)
            const today = isToday(day.date)
            const selected = selectedDate?.getDate() === day.date.getDate() &&
              selectedDate?.getMonth() === day.date.getMonth()

            return (
              <div
                key={i}
                className={`calendar-day ${day.isCurrentMonth ? '' : 'other-month'} ${active ? 'active' : 'inactive'} ${today ? 'today' : ''} ${selected ? 'selected' : ''}`}
                onClick={() => day.isCurrentMonth && setSelectedDate(day.date)}
              >
                <div className="day-number">{day.date.getDate()}</div>
                <div className="day-status">
                  {active ? (
                    <span className="status-badge active">Рабочий</span>
                  ) : (
                    <span className="status-badge inactive">Выходной</span>
                  )}
                </div>
                {active && day.isCurrentMonth && (
                  <div className="day-appointments-count">
                    {(() => {
                      const dow = day.date.getDay()
                      const hours = schedule[dow]
                      let count = 0
                      for (let h = hours.start; h < hours.end; h++) {
                        const status = getSlotStatus(day.date, h)
                        if (status !== 'free') count++
                      }
                      return count > 0 ? `${count} записей` : ''
                    })()}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      </div>

      {/* Time slots for selected date */}
      {selectedDate && (
        <div className="hours-section card">
          <h3>
            🕐 {selectedDate.toLocaleDateString('ru-RU', { weekday: 'long', day: 'numeric', month: 'long' })}
          </h3>
          {isDayActive(selectedDate) ? (
            <div className="hours-grid">
              {(() => {
                const dow = selectedDate.getDay()
                const hours = schedule[dow]
                const slots = []
                for (let h = hours.start; h < hours.end; h++) {
                  const status = getSlotStatus(selectedDate, h)
                  const config = statusConfig[status]
                  const slotsForHour = getAppointmentsForSlot(selectedDate, h)
                  
                  slots.push(
                    <div key={h} className={`hour-slot status-${status}`}>
                      <div className="hour-time">{formatHour(h)}</div>
                      {slotsForHour.map(a => (
                        <div key={a.id} className="appointment-info">
                          <div className="appt-client">{a.client_name}</div>
                          <div className="appt-service">{a.service_name}</div>
                          <div className={`appt-status status-${status}`}>
                            {config.label}
                          </div>
                        </div>
                      ))}
                    </div>
                  )
                }
                return slots
              })()}
            </div>
          ) : (
            <p className="empty-state">Этот день — выходной. Настройте расписание в настройках дней недели.</p>
          )}
        </div>
      )}

      {/* Summary */}
      <div className="schedule-summary card">
        <h3>📊 Статистика недели</h3>
        <div className="summary-stats">
          <div className="summary-item">
            <span className="summary-value">{Object.keys(schedule).length}</span>
            <span className="summary-label">Рабочих дней</span>
          </div>
          <div className="summary-item">
            <span className="summary-value">{7 - Object.keys(schedule).length}</span>
            <span className="summary-label">Выходных</span>
          </div>
          <div className="summary-item">
            <span className="summary-value">
              {Object.values(schedule).reduce((total, h) => total + (h.end - h.start), 0)}
            </span>
            <span className="summary-label">Часов в неделю</span>
          </div>
        </div>
      </div>
    </div>
  )
}

export default SchedulePage
