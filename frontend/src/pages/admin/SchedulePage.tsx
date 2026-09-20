import { useEffect, useState, useRef, useCallback } from 'react'
import { adminApi } from '../../api/client'

const statusConfig: Record<string, { label: string; bg: string; text: string }> = {
  free: { label: 'Свободно', bg: '#e0e0e0', text: '#666' },
  pending: { label: 'Ожидает', bg: '#fff8e1', text: '#f57f17' },
  confirmed: { label: 'Подтверждена', bg: '#e3f2fd', text: '#1565c0' },
  completed: { label: 'Завершена', bg: '#e8f5e9', text: '#2e7d32' },
  cancelled: { label: 'Отменена', bg: '#f5f5f5', text: '#616161' },
}

function SchedulePage() {
  const [schedule, setSchedule] = useState<Record<string, { start: number; end: number }>>({})
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
  const [showClientDropdown, setShowClientDropdown] = useState(false)
  const [showServiceDropdown, setShowServiceDropdown] = useState(false)
  const [allServices, setAllServices] = useState<any[]>([])
  const [longPressTriggered, setLongPressTriggered] = useState(false)
  const [monthlyStats, setMonthlyStats] = useState<{
    confirmed_appointments: number
    total_minutes: number
    total_hours: number
    revenue: number
  } | null>(null)

  // Refs to avoid stale closures in event handlers
  const scheduleRef = useRef(schedule)
  scheduleRef.current = schedule

  const activeHoursRef = useRef(activeHours)
  activeHoursRef.current = activeHours

  // Long press state
  const pressTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const pressDateRef = useRef<Date | null>(null)
  const LONG_PRESS_MS = 500

  const toggleDayWork = useCallback(async (date: Date) => {
    const dateStr = date.toISOString().split('T')[0]
    const currentSchedule = scheduleRef.current
    const isActive = !!currentSchedule[dateStr]
    const currentActive = activeHoursRef.current

    // Optimistic UI update — update BOTH schedule AND activeHours atomically
    const newSchedule: Record<string, { start: number; end: number }> = { ...currentSchedule }
    const newActiveHours: Record<string, boolean> = { ...currentActive }

    if (isActive) {
      delete newSchedule[dateStr]
      for (let h = 8; h < 22; h++) { delete newActiveHours[`${dateStr}-${h}`] }
    } else {
      newSchedule[dateStr] = { start: 8, end: 22 }
      for (let h = 8; h < 22; h++) { newActiveHours[`${dateStr}-${h}`] = true }
    }

    setSchedule(newSchedule)
    setActiveHours(newActiveHours)

    // Sync with backend — save by schedule_date
    try {
      if (isActive) {
        const resp = await adminApi.getWorkingHours()
        const existing = resp.data.find((h: any) => h.schedule_date === dateStr)
        if (existing) {
          await adminApi.deleteWorkingHour(existing.id)
        }
      } else {
        const resp = await adminApi.getWorkingHours()
        const existing = resp.data.find((h: any) => h.schedule_date === dateStr)
        if (existing) {
          await adminApi.updateWorkingHour(existing.id, {
            schedule_date: dateStr,
            start_time: '08:00',
            end_time: '22:00'
          })
        } else {
          await adminApi.createWorkingHour({
            schedule_date: dateStr,
            start_time: '08:00',
            end_time: '22:00'
          })
        }
      }
    } catch (err) {
      console.error('Failed to sync working hours:', err)
    }
  }, [])

  const isPast = (date: Date) => {
    const now = new Date()
    const d = new Date(date.getFullYear(), date.getMonth(), date.getDate())
    const n = new Date(now.getFullYear(), now.getMonth(), now.getDate())
    return d < n
  }

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

  // Close dropdowns on outside click
  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      const target = e.target as HTMLElement
      if (!target.closest('.client-dropdown') && showClientDropdown) setShowClientDropdown(false)
      if (!target.closest('.service-dropdown') && showServiceDropdown) setShowServiceDropdown(false)
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [showClientDropdown, showServiceDropdown])

  const fetchSchedule = async () => {
    try {
      const resp = await adminApi.getWorkingHours()
      const newSchedule: Record<string, { start: number; end: number }> = {}
      const newActiveHours: Record<string, boolean> = {}
      for (const wh of resp.data) {
        const startTime = wh.start_time.split(':').map(Number)
        const endTime = wh.end_time.split(':').map(Number)
        newSchedule[wh.schedule_date] = {
          start: startTime[0],
          end: endTime[0]
        }
        for (let h = startTime[0]; h < endTime[0]; h++) {
          newActiveHours[`${wh.schedule_date}-${h}`] = true
        }
      }
      setSchedule(newSchedule)
      setActiveHours(newActiveHours)
    } catch (err: any) {
      console.error('[fetchSchedule] ERROR:', err.message)
      console.error('[fetchSchedule] Response:', err.response?.data)
    } finally {
      setLoading(false)
    }
  }


  const loadMonthlyStats = useCallback(() => {
    const year = currentMonth.getFullYear()
    const month = currentMonth.getMonth() + 1
    adminApi.getMonthlyStats(year, month)
      .then(r => {
        console.log('[SchedulePage] Monthly stats loaded:', r.data)
        setMonthlyStats(r.data)
      })
      .catch((err) => {
        console.error('[SchedulePage] Failed to load monthly stats:', err)
        console.error('[SchedulePage] Error details:', err.response?.data)
        setMonthlyStats(null)
      })
  }, [currentMonth])

  useEffect(() => { loadMonthlyStats() }, [loadMonthlyStats])
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
    const hours = getHoursForDay(selectedDate)
    const newActive: Record<string, boolean> = {}
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

  const fetchAppointmentsForMonth = useCallback(async () => {
    const year = currentMonth.getFullYear()
    const month = currentMonth.getMonth()
    const from = `${year}-${String(month + 1).padStart(2, '0')}-01`
    const lastDay = new Date(year, month + 1, 0).getDate()
    const to = `${year}-${String(month + 1).padStart(2, '0')}-${String(lastDay).padStart(2, '0')}`
    try {
      const resp = await adminApi.getAppointmentsByDate(from, to)
      setAppointments(resp.data)
    } catch {
      setAppointments([])
    }
  }, [currentMonth])

  useEffect(() => { fetchAppointmentsForMonth() }, [fetchAppointmentsForMonth])

  const getMonthDays = (date: Date) => {
    const year = date.getFullYear()
    const month = date.getMonth()
    const firstDay = new Date(year, month, 1)
    const lastDay = new Date(year, month + 1, 0)
    const days: { date: Date; isCurrentMonth: boolean }[] = []
    const startDayOfWeek = firstDay.getDay() === 0 ? 6 : firstDay.getDay() - 1
    for (let i = 0; i < startDayOfWeek; i++) {
      days.push({ date: new Date(year, month, 1 - (startDayOfWeek - i)), isCurrentMonth: false })
    }
    for (let d = 1; d <= lastDay.getDate(); d++) {
      days.push({ date: new Date(year, month, d), isCurrentMonth: true })
    }
    return days
  }

  const isDayActive = (date: Date) => {
    const dateStr = date.toISOString().split('T')[0]
    return !!schedule[dateStr]
  }

  const getHoursForDay = (date: Date) => {
    const dateStr = date.toISOString().split('T')[0]
    if (schedule[dateStr]) return schedule[dateStr]
    return { start: 8, end: 22 } // default for inactive days
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
      <div style={{ marginBottom: 8, textAlign: 'center' }}>
        <h1 style={{ fontSize: 24, margin: 0, color: '#1a1a2e' }}>📅 Рабочее расписание</h1>
        <p style={{ margin: '4px 0 0', color: '#666', fontSize: 14 }}>Нажмите на день чтобы увидеть бронирования</p>
      </div>

      {/* Legend */}
      <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', marginBottom: 20, padding: 14, background: '#f9f9f9', borderRadius: 10, justifyContent: 'center' }}>
        {[
          { color: '#4caf50', bg: '#e8f5e9', label: 'Рабочий день' },
          { color: '#e0e0e0', bg: '#f5f5f5', label: 'Выходной' },
          { color: '#667eea', bg: '#e8eaf6', label: 'Сегодня' },
          { color: '#9e9e9e', bg: '#f5f5f5', label: 'Прошедший' },
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
          {['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'].map((name, i) => (
            <div key={i} style={{ textAlign: 'center', fontSize: 13, fontWeight: 600, color: i === 5 ? '#ff9800' : i === 6 ? '#f44336' : '#666', padding: '8px 0' }}>
              {name}
            </div>
          ))}
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: 8 }}>
          {monthDays.map((day, i) => {
            const dateStr = day.date.toISOString().split('T')[0]
            const active = isDayActive(day.date)
            const today = isToday(day.date)
            const past = isPast(day.date)
            const selected = selectedDate?.getDate() === day.date.getDate() && selectedDate?.getMonth() === day.date.getMonth()
            const hours = schedule[dateStr]
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
                  background: past ? '#f5f5f5' : active ? 'linear-gradient(135deg, #e8f5e9 0%, #c8e6c9 100%)' : today ? '#fff8e1' : '#f9f9f9',
                  border: `2px solid ${past ? '#e0e0e0' : active ? '#4caf50' : today ? '#ff9800' : '#e0e0e0'}`,
                  minHeight: 80,
                  opacity: past ? 0.6 : 1,
                  transition: 'all 0.2s ease',
                  boxShadow: today ? '0 0 0 2px rgba(255,152,0,0.2)' : selected ? '0 0 0 3px rgba(255,152,0,0.3)' : 'none',
                  userSelect: 'none',
                  WebkitUserSelect: 'none',
                }}
                onMouseEnter={(e) => { if (day.isCurrentMonth && !past) e.currentTarget.style.transform = 'translateY(-2px)' }}
              >
                <div style={{ fontSize: 18, fontWeight: 700, color: past ? '#bbb' : today ? '#ff9800' : '#333', marginBottom: 6 }}>
                  {day.date.getDate()}
                </div>
                <div style={{ fontSize: 10, fontWeight: 600, background: past ? '#e0e0e0' : active ? '#c8e6c9' : today ? '#ffe0b2' : '#f5f5f5', color: past ? '#999' : active ? '#2e7d32' : today ? '#e65100' : '#999', padding: '2px 8px', borderRadius: 10, display: 'inline-block' }}>
                  {past ? 'Прошёл' : active ? 'Рабочий' : today ? 'Сегодня' : 'Выходной'}
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
              <div style={{ position: 'relative' }}>
                <input
                  type="text"
                  value={bookingForm.clientId ? (bookingClients.find((c: any) => c.id === bookingForm.clientId)?.name || '') : clientSearch}
                  onChange={(e) => { setClientSearch(e.target.value); setShowClientDropdown(true) }}
                  onFocus={() => { if (!bookingForm.clientId) setShowClientDropdown(true) }}
                  placeholder="Начните вводить имя или телефон..."
                  style={{ width: '100%', padding: 10, border: '2px solid #e0e0e0', borderRadius: 8, fontSize: 14 }}
                />
                {showClientDropdown && (
                  <div className="client-dropdown" style={{
                    position: 'absolute', top: '100%', left: 0, right: 0, maxHeight: 200, overflow: 'auto',
                    border: '2px solid #e0e0e0', borderRadius: 8, marginTop: 4, background: 'white', zIndex: 1000
                  }}>
                    {filteredClients.length === 0 ? (
                      <div style={{ padding: 12, color: '#999', fontSize: 13 }}>Ничего не найдено</div>
                    ) : (
                      filteredClients.map((c: any) => (
                        <div
                          key={c.id}
                          onClick={() => { setBookingForm({ ...bookingForm, clientId: c.id }); setShowClientDropdown(false); setClientSearch('') }}
                          style={{ padding: '10px 12px', cursor: 'pointer', fontSize: 14, borderBottom: '1px solid #f0f0f0',
                            background: bookingForm.clientId === c.id ? '#e8f5e9' : 'white' }}
                          onMouseEnter={(e) => e.currentTarget.style.background = '#f5f5f5'}
                          onMouseLeave={(e) => e.currentTarget.style.background = bookingForm.clientId === c.id ? '#e8f5e9' : 'white'}
                        >
                          <strong>{c.name}</strong> — {c.phone}
                        </div>
                      ))
                    )}
                  </div>
                )}
              </div>
            </div>
            <div className="form-group">
              <label>Услуга</label>
              <div style={{ position: 'relative' }}>
                <input
                  type="text"
                  value={bookingForm.serviceId ? (allServices.find((s: any) => s.id === bookingForm.serviceId)?.name || '') : serviceSearch}
                  onChange={(e) => { setServiceSearch(e.target.value); setShowServiceDropdown(true) }}
                  onFocus={() => { if (!bookingForm.serviceId) setShowServiceDropdown(true) }}
                  placeholder="Начните вводить название..."
                  style={{ width: '100%', padding: 10, border: '2px solid #e0e0e0', borderRadius: 8, fontSize: 14 }}
                />
                {showServiceDropdown && (
                  <div className="service-dropdown" style={{
                    position: 'absolute', top: '100%', left: 0, right: 0, maxHeight: 200, overflow: 'auto',
                    border: '2px solid #e0e0e0', borderRadius: 8, marginTop: 4, background: 'white', zIndex: 1000
                  }}>
                    {filteredServices.length === 0 ? (
                      <div style={{ padding: 12, color: '#999', fontSize: 13 }}>Ничего не найдено</div>
                    ) : (
                      filteredServices.map((s: any) => (
                        <div
                          key={s.id}
                          onClick={() => { setBookingForm({ ...bookingForm, serviceId: s.id }); setShowServiceDropdown(false); setServiceSearch('') }}
                          style={{ padding: '10px 12px', cursor: 'pointer', fontSize: 14, borderBottom: '1px solid #f0f0f0',
                            background: bookingForm.serviceId === s.id ? '#e8f5e9' : 'white' }}
                          onMouseEnter={(e) => e.currentTarget.style.background = '#f5f5f5'}
                          onMouseLeave={(e) => e.currentTarget.style.background = bookingForm.serviceId === s.id ? '#e8f5e9' : 'white'}
                        >
                          <strong>{s.name}</strong> — {s.duration_minutes} мин, {Number(s.price).toLocaleString('ru-RU')} ₽
                        </div>
                      ))
                    )}
                  </div>
                )}
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

      {/* Monthly Summary */}
      <div style={{ padding: 20, background: 'white', borderRadius: 12, border: '1px solid #e0e0e0' }}>
        <h3 style={{ margin: '0 0 16px', fontSize: 18, color: '#1a1a2e' }}>📊 Статистика за {monthName}</h3>
        <div style={{ display: 'flex', gap: 24, flexWrap: 'wrap' }}>
          {monthlyStats ? (() => [
            { value: monthlyStats.confirmed_appointments, label: 'Подтверждено записей' },
            { value: monthlyStats.total_hours, label: 'Часов (подт.)' },
            { value: `${monthlyStats.revenue.toLocaleString('ru-RU')} ₽`, label: 'Доход (заверш.)' },
          ])().map(item => (
            <div key={item.label} style={{ textAlign: 'center', flex: 1, minWidth: 120 }}>
              <span style={{ display: 'block', fontSize: 32, fontWeight: 700, color: '#667eea', marginBottom: 4 }}>{item.value}</span>
              <span style={{ fontSize: 13, color: '#666' }}>{item.label}</span>
            </div>
          )) : (
            <div style={{ color: '#999', fontSize: 14 }}>Загрузка...</div>
          )}
        </div>
      </div>
    </div>
  )
}

export default SchedulePage
