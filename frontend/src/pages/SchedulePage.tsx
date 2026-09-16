import { useEffect, useState } from 'react'
import { adminApi } from '../api/adminClient'

const statusConfig: Record<string, { label: string; bg: string; text: string }> = {
  free: { label: 'Свободно', bg: '#e0e0e0', text: '#666' },
  pending: { label: 'Ожидает', bg: '#fff8e1', text: '#f57f17' },
  confirmed: { label: 'Подтверждена', bg: '#e3f2fd', text: '#1565c0' },
  completed: { label: 'Завершена', bg: '#e8f5e9', text: '#2e7d32' },
  cancelled: { label: 'Отменена', bg: '#f5f5f5', text: '#616161' },
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

  const fetchAppointmentsForMonth = async () => {
    const now = new Date()
    const year = now.getFullYear()
    const month = now.getMonth()
    const from = `${year}-${String(month + 1).padStart(2, '0')}-01`
    const lastDay = new Date(year, month + 1, 0).getDate()
    const to = `${year}-${String(month + 1).padStart(2, '0')}-${String(lastDay).padStart(2, '0')}`
    try {
      const resp = await adminApi.getAppointmentsByDate(from, to)
      setAppointments(resp.data)
    } catch {
      setAppointments([])
    }
  }

  useEffect(() => { fetchSchedule() }, [])
  useEffect(() => { fetchAppointmentsForMonth() }, [])

  const getMonthDays = (date: Date) => {
    const year = date.getFullYear()
    const month = date.getMonth()
    const firstDay = new Date(year, month, 1)
    const lastDay = new Date(year, month + 1, 0)
    const days: { date: Date; isCurrentMonth: boolean }[] = []
    const startDayOfWeek = firstDay.getDay()
    for (let i = 0; i < startDayOfWeek; i++) {
      days.push({ date: new Date(year, month, 1 - (startDayOfWeek - i)), isCurrentMonth: false })
    }
    for (let d = 1; d <= lastDay.getDate(); d++) {
      days.push({ date: new Date(year, month, d), isCurrentMonth: true })
    }
    return days
  }

  const isDayActive = (date: Date) => {
    // JS getDay(): 0=Sun, 1=Mon, ..., 6=Sat
    // Backend day_of_week: 0=Mon, 1=Tue, ..., 6=Sun
    const jsDow = date.getDay()
    const pyDow = (jsDow + 6) % 7  // Convert Sun=0→6, Mon=1→0, Tue=2→1, ..., Sat=6→5
    return !!schedule[pyDow]
  }

  const getAppointmentsForSlot = (date: Date, hour: number) => {
    const dateStr = date.toISOString().split('T')[0]
    const hourStr = `${String(hour).padStart(2, '0')}`
    return appointments.filter(a => {
      const aDate = a.appointment_date.split('T')[0]
      const aHour = a.appointment_date.split('T')[1]?.slice(0, 2)
      return aDate === dateStr && aHour === hourStr
    })
  }

  const getSlotStatus = (date: Date, hour: number) => {
    const slots = getAppointmentsForSlot(date, hour)
    if (slots.length === 0) return 'free'
    const statusOrder = ['completed', 'confirmed', 'pending', 'cancelled']
    for (const status of statusOrder) {
      if (slots.some(s => s.status === status)) return status
    }
    return 'pending'
  }

  const goToPrevMonth = () => setCurrentMonth(new Date(currentMonth.getFullYear(), currentMonth.getMonth() - 1, 1))
  const goToNextMonth = () => setCurrentMonth(new Date(currentMonth.getFullYear(), currentMonth.getMonth() + 1, 1))
  const isToday = (date: Date) => {
    const today = new Date()
    return date.getDate() === today.getDate() && date.getMonth() === today.getMonth() && date.getFullYear() === today.getFullYear()
  }
  const isPast = (date: Date) => {
    const now = new Date()
    const d = new Date(date.getFullYear(), date.getMonth(), date.getDate())
    const n = new Date(now.getFullYear(), now.getMonth(), now.getDate())
    return d < n
  }
  const isSlotPast = (date: Date, hour: number) => {
    const slotDate = new Date(date)
    slotDate.setHours(hour, 0, 0, 0)
    return slotDate < new Date()
  }
  const formatHour = (h: number) => String(h).padStart(2, '0') + ':00'

  if (loading) return <div style={{ padding: 60, textAlign: 'center', color: '#666', fontSize: 16 }}>Загрузка...</div>
  if (error) return <div style={{ padding: 60, textAlign: 'center', color: '#f44336' }}>{error}</div>

  const monthDays = getMonthDays(currentMonth)
  const monthName = currentMonth.toLocaleString('ru-RU', { month: 'long', year: 'numeric' })

  return (
    <div style={{ padding: '0 20px', maxWidth: 1200, margin: '0 auto' }}>
      <div style={{ marginBottom: 8 }}>
        <h1 style={{ fontSize: 24, margin: 0, color: '#1a1a2e' }}>📅 Рабочее расписание</h1>
        <p style={{ margin: '4px 0 0', color: '#666', fontSize: 14 }}>Нажмите на день чтобы увидеть бронирования</p>
      </div>

      {/* Legend */}
      <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', marginBottom: 20, padding: 14, background: '#f9f9f9', borderRadius: 10 }}>
        {[
          { color: '#e0e0e0', label: 'Свободно' },
          { color: '#ffc107', label: 'Ожидает' },
          { color: '#2196f3', label: 'Подтверждена' },
          { color: '#4caf50', label: 'Завершена' },
          { color: '#9e9e9e', label: 'Отменена' },
        ].map(item => (
          <div key={item.label} style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, color: '#333' }}>
            <span style={{ width: 16, height: 16, borderRadius: 4, background: item.color, display: 'inline-block' }} />
            <span>{item.label}</span>
          </div>
        ))}
      </div>

      {/* Calendar */}
      <div style={{ marginBottom: 24 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
          <button onClick={goToPrevMonth} style={{ background: '#667eea', color: 'white', border: 'none', width: 40, height: 40, borderRadius: 8, fontSize: 20, cursor: 'pointer' }}>←</button>
          <span style={{ fontSize: 20, fontWeight: 600, color: '#1a1a2e', textTransform: 'capitalize' }}>{monthName}</span>
          <button onClick={goToNextMonth} style={{ background: '#667eea', color: 'white', border: 'none', width: 40, height: 40, borderRadius: 8, fontSize: 20, cursor: 'pointer' }}>→</button>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: 8, marginBottom: 8 }}>
          {['Вс', 'Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб'].map((name, i) => (
            <div key={i} style={{ textAlign: 'center', fontSize: 13, fontWeight: 600, color: i === 0 ? '#f44336' : i === 6 ? '#ff9800' : '#666', padding: '8px 0' }}>
              {name}
            </div>
          ))}
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: 8 }}>
          {monthDays.map((day, i) => {
            const active = isDayActive(day.date)
            const today = isToday(day.date)
            const past = isPast(day.date)
            const selected = selectedDate?.getDate() === day.date.getDate() && selectedDate?.getMonth() === day.date.getMonth()
            const jsDow = day.date.getDay()
            const pyDow = (jsDow + 6) % 7
            const hours = schedule[pyDow]
            let apptCount = 0
            if (active && day.isCurrentMonth && hours) {
              for (let h = hours.start; h < hours.end; h++) {
                if (!isSlotPast(day.date, h) && getSlotStatus(day.date, h) !== 'free') apptCount++
              }
            }

            return (
              <div
                key={i}
                onClick={() => day.isCurrentMonth && !past && setSelectedDate(day.date)}
                style={{
                  padding: '12px 8px',
                  borderRadius: 10,
                  textAlign: 'center',
                  cursor: (day.isCurrentMonth && !past) ? 'pointer' : 'default',
                  background: past ? '#f0f0f0' : active ? 'linear-gradient(135deg, #e8f5e9 0%, #c8e6c9 100%)' : '#f9f9f9',
                  border: `2px solid ${past ? '#e0e0e0' : active ? '#4caf50' : '#e0e0e0'}`,
                  minHeight: 80,
                  opacity: past ? 0.4 : day.isCurrentMonth ? 1 : 0.3,
                  transition: 'all 0.2s ease',
                  boxShadow: selected ? '0 0 0 3px rgba(255,152,0,0.3)' : today ? '0 0 0 2px rgba(102,126,234,0.3)' : 'none',
                }}
                onMouseEnter={(e) => { if (day.isCurrentMonth && !past) e.currentTarget.style.transform = 'translateY(-2px)' }}
                onMouseLeave={(e) => { if (day.isCurrentMonth && !past) e.currentTarget.style.transform = 'none' }}
              >
                <div style={{ fontSize: 18, fontWeight: 700, color: past ? '#bbb' : today ? '#667eea' : '#333', marginBottom: 6 }}>
                  {day.date.getDate()}
                </div>
                <div style={{ fontSize: 10, fontWeight: 600, background: past ? '#e0e0e0' : active ? '#c8e6c9' : '#f5f5f5', color: past ? '#999' : active ? '#2e7d32' : '#999', padding: '2px 8px', borderRadius: 10, display: 'inline-block' }}>
                  {past ? 'Прошёл' : active ? 'Рабочий' : 'Выходной'}
                </div>
                {active && !past && apptCount > 0 && (
                  <div style={{ marginTop: 4, fontSize: 11, color: '#1565c0', fontWeight: 500 }}>
                    {apptCount} записей
                  </div>
                )}
              </div>
            )
          })}
        </div>
      </div>

      {/* Time slots for selected date */}
      {selectedDate && (
        <div style={{ marginBottom: 24, padding: 20, background: 'white', borderRadius: 12, border: '1px solid #e0e0e0' }}>
          <h3 style={{ margin: '0 0 16px', fontSize: 18, color: '#1a1a2e', textTransform: 'capitalize' }}>
            🕐 {selectedDate.toLocaleDateString('ru-RU', { weekday: 'long', day: 'numeric', month: 'long' })}
            {isPast(selectedDate) && <span style={{ fontSize: 14, color: '#999', fontWeight: 400, marginLeft: 12 }}>— прошедший день</span>}
          </h3>
          {isDayActive(selectedDate) ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {(() => {
                const jsDow = selectedDate.getDay()
                const pyDow = (jsDow + 6) % 7
                const hours = schedule[pyDow]
                const slots: React.ReactNode[] = []
                for (let h = hours.start; h < hours.end; h++) {
                  const status = getSlotStatus(selectedDate, h)
                  const cfg = statusConfig[status]
                  const slotsForHour = getAppointmentsForSlot(selectedDate, h)
                  const past = isSlotPast(selectedDate, h)

                  slots.push(
                    <div key={h} style={{ display: 'flex', alignItems: 'center', gap: 16, padding: '12px 16px', borderRadius: 8, border: `2px solid ${cfg.bg}`, background: past ? '#f5f5f5' : cfg.bg, opacity: past ? 0.5 : 1 }}>
                      <div style={{ fontSize: 16, fontWeight: 700, color: past ? '#bbb' : '#333', minWidth: 60 }}>{formatHour(h)}</div>
                      {slotsForHour.length > 0 ? slotsForHour.map(a => {
                        const sc = statusConfig[a.status]
                        return (
                          <div key={a.id} style={{ flex: 1, display: 'flex', alignItems: 'center', gap: 12 }}>
                            <span style={{ fontWeight: 600, color: '#333', fontSize: 14 }}>{a.client_name}</span>
                            <span style={{ color: '#666', fontSize: 13 }}>{a.service_name}</span>
                            <span style={{ padding: '4px 10px', borderRadius: 12, fontSize: 12, fontWeight: 600, background: sc.bg, color: sc.text }}>
                              {sc.label}
                            </span>
                          </div>
                        )
                      }) : (
                        <span style={{ flex: 1, color: past ? '#bbb' : '#999', fontSize: 13 }}>{past ? 'Прошёл' : 'Свободно'}</span>
                      )}
                    </div>
                  )
                }
                return slots
              })()}
            </div>
          ) : (
            <p style={{ color: '#999', fontSize: 14, textAlign: 'center', padding: '20px 0' }}>Этот день — выходной</p>
          )}
        </div>
      )}

      {/* Summary */}
      <div style={{ padding: 20, background: 'white', borderRadius: 12, border: '1px solid #e0e0e0' }}>
        <h3 style={{ margin: '0 0 16px', fontSize: 18, color: '#1a1a2e' }}>📊 Статистика недели</h3>
        <div style={{ display: 'flex', gap: 24, flexWrap: 'wrap' }}>
          {[
            { value: Object.keys(schedule).length, label: 'Рабочих дней' },
            { value: 7 - Object.keys(schedule).length, label: 'Выходных' },
            { value: Object.values(schedule).reduce((t, h) => t + (h.end - h.start), 0), label: 'Часов в неделю' },
          ].map(item => (
            <div key={item.label} style={{ textAlign: 'center', flex: 1, minWidth: 120 }}>
              <span style={{ display: 'block', fontSize: 32, fontWeight: 700, color: '#667eea', marginBottom: 4 }}>{item.value}</span>
              <span style={{ fontSize: 13, color: '#666' }}>{item.label}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

export default SchedulePage
