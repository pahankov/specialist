import { useEffect, useState, useCallback } from 'react'
import { adminApi } from '../../api/client'
import type { Appointment, Client, Service, DaySchedule, MonthlyStats, BookingFormState } from '../../api/types'
import { Calendar } from '../../components/schedule/Calendar'
import { TimeSlots } from '../../components/schedule/TimeSlots'
import { BookingModal } from '../../components/schedule/BookingModal'
import { MonthlyStatsComponent } from '../../components/schedule/MonthlyStats'
import {
  toggleDayWork,
  toggleHour,
  openBookingForm,
  closeBookingForm,
  handleBookAppointment,
} from '../../components/schedule/hooks'

function SchedulePage() {
  const [schedule, setSchedule] = useState<Record<string, DaySchedule>>({})
  const [currentMonth, setCurrentMonth] = useState(() => new Date())
  const [selectedDate, setSelectedDate] = useState<Date | null>(null)
  const [appointments, setAppointments] = useState<Appointment[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [bookingClients, setBookingClients] = useState<Client[]>([])
  const [bookingServices, setBookingServices] = useState<Service[]>([])
  const [bookingLoading, setBookingLoading] = useState(false)
  const [bookingForm, setBookingForm] = useState<BookingFormState>({
    open: false, date: null, hour: null,
    clientId: null, serviceId: null,
    status: 'pending', notes: '',
  })
  const [activeHours, setActiveHours] = useState<Record<string, boolean>>({})
  const [longPressTriggered, setLongPressTriggered] = useState(false)
  const [monthlyStats, setMonthlyStats] = useState<MonthlyStats | null>(null)

  useEffect(() => {
    let cancelled = false
    async function init() {
      try {
        const [scheduleResp, apptsResp, statsResp] = await Promise.all([
          adminApi.getWorkingHours(),
          adminApi.getAppointmentsByDate(
            `${currentMonth.getFullYear()}-01-01`,
            `${currentMonth.getFullYear()}-${String(currentMonth.getMonth() + 1).padStart(2, '0')}-28`
          ),
          adminApi.getMonthlyStats(currentMonth.getFullYear(), currentMonth.getMonth() + 1),
        ])
        if (cancelled) return

        const newSchedule: Record<string, DaySchedule> = {}
        const newActiveHours: Record<string, boolean> = {}
        for (const wh of scheduleResp.data) {
          const sh = wh.start_time.split(':').map(Number)
          const eh = wh.end_time.split(':').map(Number)
          newSchedule[wh.schedule_date] = { start: sh[0], end: eh[0] }
          for (let h = sh[0]; h < eh[0]; h++) {
            newActiveHours[`${wh.schedule_date}-${h}`] = true
          }
        }
        setSchedule(newSchedule)
        setActiveHours(newActiveHours)
        setAppointments(apptsResp.data || [])
        setMonthlyStats(statsResp.data || null)
      } catch (err: any) {
        console.error('[SchedulePage] Init error:', err)
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    init()
    return () => { cancelled = true }
  }, [currentMonth])

  useEffect(() => {
    if (!bookingForm.open) return
    let cancelled = false
    Promise.all([
      adminApi.getClients(),
      adminApi.getAllServices(),
    ]).then(([clientsResp, servicesResp]) => {
      if (cancelled) return
      setBookingClients(clientsResp.data || [])
      setBookingServices(servicesResp.data || [])
    }).catch(() => {
      if (!cancelled) {
        setBookingClients([])
        setBookingServices([])
      }
    })
    return () => { cancelled = true }
  }, [bookingForm.open])

  const handlePrevMonth = useCallback(() => {
    setCurrentMonth(d => new Date(d.getFullYear(), d.getMonth() - 1, 1))
  }, [])

  const handleNextMonth = useCallback(() => {
    setCurrentMonth(d => new Date(d.getFullYear(), d.getMonth() + 1, 1))
  }, [])

  const handleSelectDate = useCallback((date: Date) => {
    setSelectedDate(date)
  }, [])

  const handleToggleDay = useCallback(async (date: Date) => {
    const result = await toggleDayWork(date, schedule, activeHours, appointments, setError)
    if (result) {
      setSchedule(result.newSchedule)
      setActiveHours(result.newActiveHours)
    }
  }, [schedule, activeHours, appointments])

  const handleToggleHour = useCallback((dateStr: string, hour: number) => {
    toggleHour(dateStr, hour, setActiveHours)
  }, [])

  const handleOpenBooking = useCallback((date: Date, hour: number) => {
    openBookingForm(date, hour, setBookingForm)
  }, [])

  const handleBookingUpdate = useCallback((field: string, value: any) => {
    setBookingForm(prev => ({ ...prev, [field]: value }))
  }, [])

  const handleCloseBooking = useCallback(() => {
    closeBookingForm(setBookingForm, setBookingClients)
  }, [])

  const handleBook = useCallback(async () => {
    const success = await handleBookAppointment(
      bookingForm, setBookingLoading, setError,
      adminApi, handleCloseBooking
    )
    if (success) {
      const from = `${currentMonth.getFullYear()}-${String(currentMonth.getMonth()).padStart(2, '0')}-01`
      const lastDay = new Date(currentMonth.getFullYear(), currentMonth.getMonth() + 1, 0).getDate()
      const to = `${currentMonth.getFullYear()}-${String(currentMonth.getMonth() + 1).padStart(2, '0')}-${String(lastDay).padStart(2, '0')}`
      try {
        const resp = await adminApi.getAppointmentsByDate(from, to)
        setAppointments(resp.data || [])
      } catch { /* ignore */ }
    }
  }, [bookingForm, currentMonth, handleCloseBooking])

  if (loading) return <div style={{ padding: 60, textAlign: 'center', color: '#666' }}>Загрузка...</div>

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

      <Calendar
        currentMonth={currentMonth}
        schedule={schedule}
        appointments={appointments}
        selectedDate={selectedDate}
        onPrevMonth={handlePrevMonth}
        onNextMonth={handleNextMonth}
        onSelectDate={handleSelectDate}
        onToggleDay={handleToggleDay}
        longPressTriggered={longPressTriggered}
      />

      {selectedDate && (
        <TimeSlots
          selectedDate={selectedDate}
          schedule={schedule}
          appointments={appointments}
          activeHours={activeHours}
          onToggleHour={handleToggleHour}
          onOpenBooking={handleOpenBooking}
        />
      )}

      <MonthlyStatsComponent currentMonth={currentMonth} stats={monthlyStats} />

      {/* Error modal */}
      {error && (
        <div className="modal-overlay" onClick={() => setError('')}>
          <div className="modal" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 450 }}>
            <h3 style={{ color: '#c62828' }}>⚠️ Внимание</h3>
            <p style={{ color: '#333', fontSize: 14, marginBottom: 20 }}>{error}</p>
            <div className="modal-actions">
              <button className="btn btn-primary" onClick={() => setError('')}>OK</button>
            </div>
          </div>
        </div>
      )}

      <BookingModal
        open={bookingForm.open}
        date={bookingForm.date}
        hour={bookingForm.hour}
        clientId={bookingForm.clientId}
        serviceId={bookingForm.serviceId}
        status={bookingForm.status}
        notes={bookingForm.notes}
        clients={bookingClients}
        services={bookingServices}
        bookingLoading={bookingLoading}
        onClose={handleCloseBooking}
        onUpdate={handleBookingUpdate}
        onBook={handleBook}
      />
    </div>
  )
}

export default SchedulePage
