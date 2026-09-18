import { useEffect, useState, useRef, useCallback } from 'react'
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
  const [successMsg, setSuccessMsg] = useState('')
  const [bookingClients, setBookingClients] = useState<any[]>([])
  const [bookingLoading, setBookingLoading] = useState(false)
  const [bookingForm, setBookingForm] = useState<{
    open: boolean
    date: Date | null
    hour: number | null
    clientId: number | null
    serviceId: number | null
    status: string
    notes: string
  }>({ open: false, date: null, hour: null, clientId: null, serviceId: null, status: 'pending', notes: '' })
  const [activeHours, setActiveHours] = useState<Record<string, boolean>>({})
  const [clientSearch, setClientSearch] = useState('')
  const [serviceSearch, setServiceSearch] = useState('')
  const [allServices, setAllServices] = useState<any[]>([])
  const [longPressTriggered, setLongPressTriggered] = useState(false)

  // Refs to avoid stale closures in event handlers
  const scheduleRef = useRef(schedule)
  scheduleRef.current = schedule

  // Long press state
  const pressTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const pressDateRef = useRef<Date | null>(null)
  const LONG_PRESS_MS = 500

  // Fetch function for backend refresh (defined first so toggleDayWork can reference it)
  const fetchScheduleFromBackend = useCallback(async () => {
    try {
      const resp = await adminApi.getWorkingHours()
      const map: Record<number, { start: number; end: number }> = {}
      resp.data.forEach((h: any) => {
        map[h.day_of_week] = { start: 8, end: 22 }
      })
      for (let dow = 0; dow < 7; dow++) {
        if (!map[dow]) {
          map[dow] = { start: 8, end: 22 }
        }
      }
      setSchedule(map)
    } catch (err) {
      console.error('Failed to refresh schedule:', err)
    }
  }, [])

  // toggleDayWork as stable callback that reads schedule from ref
  const toggleDayWork = useCallback(async (date: Date) => {
    const jsDow = date.getDay()
    const pyDow = (jsDow + 6) % 7
    const currentSchedule = scheduleRef.current
    const isActive = !!currentSchedule[pyDow]
    const dateStr = date.toISOString().split('T')[0]

    // Optimistic UI update
    setSchedule(prev => {
      const next = { ...prev }
      if (isActive) {
        delete next[pyDow]
      } else {
        next[pyDow] = { start: 8, end: 22 }
      }
      return next
    })
    setActiveHours(prev => {
      const next = { ...prev }
      if (isActive) {
        for (let h = 8; h < 22; h++) { delete next[`${dateStr}-${h}`] }
      } else {
        for (let h = 8; h < 22; h++) { next[`${dateStr}-${h}`] = true }
      }
      return next
    })

    // Sync with backend
    try {
      const resp = await adminApi.getWorkingHours()
      const existing = resp.data.find((h: any) => h.day_of_week === pyDow)
      if (isActive) {
        if (existing) {
          await adminApi.deleteWorkingHour(existing.id)
        }
      } else {
        if (existing) {
          await adminApi.updateWorkingHour(existing.id, {
            day_of_week: pyDow,
            start_time: '08:00',
            end_time: '22:00'
          })
        } else {
          await adminApi.createWorkingHour({
            day_of_week: pyDow,
            start_time: '08:00',
            end_time: '22:00'
          })
        }
      }
      // Refresh schedule from backend to confirm
      await fetchScheduleFromBackend()
    } catch (err) {
      console.error('Failed to sync working hours:', err)
    }
  }, [])

  useEffect(() => {
    const handlePointerDown = (e: PointerEvent) => {
      const tile = (e.target as HTMLElement).closest('.calendar-day')
      if (!tile) return
      const dateStr = tile.getAttribute('data-date')
      if (!dateStr) return
      const date = new Date(dateStr)
      if (isPast(date)) return

      pressDateRef.current = date
      if (pressTimerRef.current) {
        clearTimeout(pressTimerRef.current)
        pressTimerRef.current = null
      }
      const timer = setTimeout(() => {
        if (pressDateRef.current) {
          toggleDayWork(pressDateRef.current)
          setLongPressTriggered(true)
          setTimeout(() => setLongPressTriggered(false), 100)
          pressDateRef.current = null
        }
      }, LONG_PRESS_MS)
      pressTimerRef.current = timer
    }

    const handlePointerUp = () => {
      if (pressTimerRef.current) {
        clearTimeout(pressTimerRef.current)
        pressTimerRef.current = null
      }
      pressDateRef.current = null
    }

    window.addEventListener('pointerdown', handlePointerDown)
    window.addEventListener('pointerup', handlePointerUp)
    window.addEventListener('pointercancel', handlePointerUp)
    return () => {
      window.removeEventListener('pointerdown', handlePointerDown)
      window.removeEventListener('pointerup', handlePointerUp)
      window.removeEventListener('pointercancel', handlePointerUp)
      if (pressTimerRef.current) clearTimeout(pressTimerRef.current)
    }
  }, [toggleDayWork])

  useEffect(() => { fetchSchedule() }, [])

  const fetchSchedule = async () => {
    try {
      const resp = await adminApi.getWorkingHours()
      const map: Record<number, { start: number; end: number }> = {}
      resp.data.forEach((h: any) => {
        map[h.day_of_week] = { start: 8, end: 22 }
      })
      for (let dow = 0; dow < 7; dow++) {
        if (!map[dow]) {
          map[dow] = { start: 8, end: 22 }
        }
      }
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

  useEffect(() => { fetchAppointmentsForMonth() }, [])
  useEffect(() => {
    if (bookingForm.open) {
      adminApi.getClients()
        .then(r => setBookingClients(r.data))
        .catch(() => setBookingClients([]))
      adminApi.getAllServices()
        .then(r => setAllServices(r.data))
        .catch(() => setAllServices([]))
    }
  }, [bookingForm.open])

  const toggleAllHours = (checked: boolean) => {
    const dateStr = selectedDate?.toISOString().split('T')[0]
    if (!dateStr) return
    const newActive: Record<string, boolean> = {}
    const hours = getHoursForDay(selectedDate)
    for (let h = hours.start; h < hours.end; h++) {
      newActive[`${dateStr}-${h}`] = checked
    }
    setActiveHours(prev => ({ ...prev, ...newActive }))
  }

  const isAllHoursActive = () => {
    const dateStr = selectedDate?.toISOString().split('T')[0]
    if (!dateStr) return false
    const hours = getHoursForDay(selectedDate)
    for (let h = hours.start; h < hours.end; h++) {
      if (!activeHours[`${dateStr}-${h}`]) return false
    }
    return hours.end > hours.start
  }

  const filteredClients = clientSearch
    ? bookingClients.filter((c: any) =>
        c.name.toLowerCase().includes(clientSearch.toLowerCase()) ||
        c.phone.includes(clientSearch)
      )
    : bookingClients

  const filteredServices = serviceSearch
    ? allServices.filter((s: any) =>
        s.name.toLowerCase().includes(serviceSearch.toLowerCase())
      )
    : allServices

  const openBookingForm = (date: Date, hour: number) => {
    setBookingForm({ open: true, date, hour, clientId: null, serviceId: null, status: 'pending', notes: '' })
  }

  const closeBookingForm = () => {
    setBookingForm({ open: false, date: null, hour: null, clientId: null, serviceId: null, status: 'pending', notes: '' })
    setBookingClients([])
  }

  const handleBookAppointment = async () => {
    if (!bookingForm.date || bookingForm.hour === null || !bookingForm.clientId || !bookingForm.serviceId) return
    setBookingLoading(true)
    try {
      const dateStr = bookingForm.date.toISOString().split('T')[0]
      const hourStr = String(bookingForm.hour).padStart(2, '0')
      const appointmentDate = `${dateStr}T${hourStr}:00:00`
      await adminApi.bookAppointment({
        client_id: bookingForm.clientId,
        service_id: bookingForm.serviceId,
        appointment_date: appointmentDate,
        status: bookingForm.status,
        notes: bookingForm.notes || undefined
      })
      setSuccessMsg('Запись создана')
      closeBookingForm()
      fetchAppointmentsForMonth()
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Произошла ошибка')
    } finally {
      setBookingLoading(false)
    }
  }

  const toggleHour = (dateStr: string, hour: number) => {
    const key = `${dateStr}-${hour}`
    setActiveHours(prev => ({ ...prev, [key]: !prev[key] }))
  }

  const isHourActive = (date: Date, hour: number) => {
    const dateStr = date.toISOString().split('T')[0]
    return !!activeHours[`${dateStr}-${hour}`]
  }

  const isPast = (date: Date) => {
    const now = new Date()
    const d = new Date(date.getFullYear(), date.getMonth(), date.getDate())
    const n = new Date(now.getFullYear(), now.getMonth(), now.getDate())
    return d < n
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

  const getHoursForDay = (date: Date) => {
    const jsDow = date.getDay()
    const pyDow = (jsDow + 6) % 7
    return schedule[pyDow] || { start: 8, end: 22 } // all days default 8-22
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
                data-date={day.date.toISOString()}
                className={`calendar-day ${day.isCurrentMonth ? '' : 'other-month'} ${active ? 'active' : 'inactive'} ${today ? 'today' : ''} ${selected ? 'selected' : ''}`}
                onClick={() => day.isCurrentMonth && !past && !longPressTriggered && setSelectedDate(day.date)}
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
                  userSelect: 'none',
                  WebkitUserSelect: 'none',
                }}
                onMouseEnter={(e) => { if (day.isCurrentMonth && !past) e.currentTarget.style.transform = 'translateY(-2px)' }}
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
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {/* Global checkbox */}
              <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 8 }}>
                <input
                  type="checkbox"
                  checked={isAllHoursActive()}
                  onChange={(e) => toggleAllHours(e.target.checked)}
                  style={{ width: 18, height: 18, cursor: 'pointer', accentColor: '#667eea' }}
                />
                <span style={{ fontSize: 14, fontWeight: 600, color: '#333' }}>
                  Выбрать все часы
                </span>
              </div>
              {(() => {
                const hours = getHoursForDay(selectedDate)
                const slots: React.ReactNode[] = []
                for (let h = hours.start; h < hours.end; h++) {
                  const status = getSlotStatus(selectedDate, h)
                  const cfg = statusConfig[status]
                  const slotsForHour = getAppointmentsForSlot(selectedDate, h)
                  const past = isSlotPast(selectedDate, h)
                  const hourActive = isHourActive(selectedDate, h)

                  slots.push(
                    <div key={h} style={{ display: 'flex', alignItems: 'center', gap: 16, padding: '12px 16px', borderRadius: 8, border: `2px solid ${hourActive ? '#4caf50' : cfg.bg}`, background: past ? '#f5f5f5' : (hourActive ? '#e8f5e9' : cfg.bg), opacity: past ? 0.5 : 1, transition: 'all 0.2s ease' }}>
                      <input
                        type="checkbox"
                        checked={hourActive}
                        onChange={() => toggleHour(selectedDate!.toISOString().split('T')[0], h)}
                        disabled={past}
                        style={{ width: 18, height: 18, cursor: 'pointer', accentColor: '#4caf50', flexShrink: 0 }}
                      />
                      <div style={{ fontSize: 16, fontWeight: 700, color: past ? '#bbb' : (hourActive ? '#2e7d32' : '#333'), minWidth: 60, flexShrink: 0 }}>{formatHour(h)}</div>
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
                        <div style={{ flex: 1, display: 'flex', alignItems: 'center', gap: 12 }}>
                          <span style={{ color: past ? '#bbb' : (hourActive ? '#4caf50' : '#999'), fontSize: 13 }}>{past ? 'Прошёл' : (hourActive ? 'Свободно' : 'Неактивен')}</span>
                          {!past && hourActive && (
                            <button
                              onClick={() => openBookingForm(selectedDate!, h)}
                              style={{ background: '#4caf50', color: 'white', border: 'none', padding: '4px 12px', borderRadius: 6, cursor: 'pointer', fontSize: 12, fontWeight: 600 }}
                            >
                              + Записать
                            </button>
                          )}
                          {!past && !hourActive && (
                            <span style={{ color: '#999', fontSize: 12, fontStyle: 'italic' }}>Неактивен</span>
                          )}
                        </div>
                      )}
                    </div>
                  )
                }
                return slots
              })()}
          </div>
        </div>
      )}

      {/* Success/Error messages */}
      {successMsg && <div style={{ background: '#e8f5e9', color: '#2e7d32', padding: '12px 16px', borderRadius: 8, marginBottom: 20 }}>{successMsg}</div>}
      {error && <div style={{ background: '#fee2e2', color: '#991b1b', padding: '12px 16px', borderRadius: 8, marginBottom: 20 }}>{error}</div>}

      {/* Manual booking modal */}
      {bookingForm.open && (
        <div className="modal-overlay" onClick={closeBookingForm}>
          <div className="modal" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 450, maxHeight: '80vh', overflow: 'auto' }}>
            <h3>📅 Записать клиента</h3>
            <p style={{ color: '#666', fontSize: 14, marginBottom: 16 }}>
              {bookingForm.date?.toLocaleDateString('ru-RU', { weekday: 'long', day: 'numeric', month: 'long' })} в {formatHour(bookingForm.hour!)}
            </p>
            <div className="form-group">
              <label>Клиент</label>
              <input
                type="text"
                value={clientSearch}
                onChange={(e) => setClientSearch(e.target.value)}
                placeholder="Начните вводить имя или телефон..."
                style={{ width: '100%', padding: 10, border: '2px solid #e0e0e0', borderRadius: 8, fontSize: 14, marginBottom: 8 }}
              />
              <div style={{ maxHeight: 200, overflow: 'auto', border: '2px solid #e0e0e0', borderRadius: 8 }}>
                <select
                  value={bookingForm.clientId || ''}
                  onChange={(e) => setBookingForm({ ...bookingForm, clientId: +e.target.value })}
                  style={{ width: '100%', padding: 10, border: 'none', borderRadius: 0, fontSize: 14, background: 'white' }}
                >
                  <option value="">Выберите клиента</option>
                  {filteredClients.map((c: any) => (
                    <option key={c.id} value={c.id}>{c.name} ({c.phone})</option>
                  ))}
                </select>
              </div>
            </div>
            <div className="form-group">
              <label>Услуга</label>
              <input
                type="text"
                value={serviceSearch}
                onChange={(e) => setServiceSearch(e.target.value)}
                placeholder="Начните вводить название..."
                style={{ width: '100%', padding: 10, border: '2px solid #e0e0e0', borderRadius: 8, fontSize: 14, marginBottom: 8 }}
              />
              <div style={{ maxHeight: 200, overflow: 'auto', border: '2px solid #e0e0e0', borderRadius: 8 }}>
                <select
                  value={bookingForm.serviceId || ''}
                  onChange={(e) => setBookingForm({ ...bookingForm, serviceId: e.target.value ? parseInt(e.target.value) : null, notes: bookingForm.notes })}
                  style={{ width: '100%', padding: 10, border: 'none', borderRadius: 0, fontSize: 14, background: 'white' }}
                >
                  <option value="">Выберите услугу</option>
                  {filteredServices.map((s: any) => (
                    <option key={s.id} value={s.id}>{s.name} — {s.duration_minutes} мин, {Number(s.price).toLocaleString('ru-RU')} ₽</option>
                  ))}
                </select>
              </div>
            </div>
            <div className="form-group">
              <label>Статус</label>
              <select
                value={bookingForm.status}
                onChange={(e) => setBookingForm({ ...bookingForm, status: e.target.value })}
                style={{ width: '100%', padding: 10, border: '2px solid #e0e0e0', borderRadius: 8, fontSize: 14 }}
              >
                <option value="pending">⏳ Ожидает</option>
                <option value="confirmed">✅ Подтверждена</option>
              </select>
            </div>
            <div className="form-group">
              <label>Примечания</label>
              <textarea
                value={bookingForm.notes}
                onChange={(e) => setBookingForm({ ...bookingForm, notes: e.target.value })}
                placeholder="Доп. информация..."
                rows={2}
                style={{ width: '100%', padding: 10, border: '2px solid #e0e0e0', borderRadius: 8, fontSize: 14, resize: 'vertical' }}
              />
            </div>
            <div className="modal-actions">
              <button className="btn btn-ghost" onClick={closeBookingForm}>Отмена</button>
              <button
                className="btn btn-primary"
                onClick={handleBookAppointment}
                disabled={!bookingForm.clientId || !bookingForm.serviceId || bookingLoading}
              >
                {bookingLoading ? 'Запись...' : 'Записать'}
              </button>
            </div>
          </div>
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
