import { useEffect, useState, useCallback } from 'react'
import { toast } from 'sonner'
import { adminApi } from '../../api/client'
import type { Appointment, Client, Service, DaySchedule, MonthlyStats, BookingFormState } from '../../api/types'
import { Calendar } from '../../components/schedule/Calendar'
import { TimeSlots } from '../../components/schedule/TimeSlots'
import { BookingModal } from '../../components/schedule/BookingModal'
import { ConfirmDialog, MasterSelect } from '../../components/common'
import { getApiErrorMessage } from '../../utils/apiError'
import { getCookie, decodeJwtPayload } from '../../utils/cookies'
import { MonthlyStatsComponent } from '../../components/schedule/MonthlyStats'
import {
  toggleDayWork,
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
  const [longPressTriggered] = useState(false)
  const [monthlyStats, setMonthlyStats] = useState<MonthlyStats | null>(null)
  const [selectedMasterId, setSelectedMasterId] = useState<number | ''>('')
  // Daily work window (whole hours): drives how many granules render.
  // Master sees own window; superadmin sees the selected master's.
  const [windowStart, setWindowStart] = useState(8)
  const [windowEnd, setWindowEnd] = useState(22)
  const [windowDraft, setWindowDraft] = useState({ start: '8', end: '22' })
  const [windowSaving, setWindowSaving] = useState(false)
  // Regular masters see only their own schedule; superadmin must pick one
  // (they have no profile of their own — empty view means "not chosen",
  // not "everyone is off").
  const [isSuperAdmin] = useState(
    () => decodeJwtPayload(getCookie('access_token') ?? '')?.is_admin === true,
  )

  useEffect(() => {
    let cancelled = false
    async function init() {
      try {
        const masterParam = selectedMasterId !== '' ? selectedMasterId : undefined
        const [scheduleResp, apptsResp, statsResp, windowResp] = await Promise.all([
          adminApi.getWorkingHours(masterParam),
          adminApi.getAppointmentsByDate(
            `${currentMonth.getFullYear()}-01-01`,
            `${currentMonth.getFullYear()}-${String(currentMonth.getMonth() + 1).padStart(2, '0')}-28`,
            masterParam
          ),
          adminApi.getMonthlyStats(
            currentMonth.getFullYear(), currentMonth.getMonth() + 1,
            masterParam,
          ),
          // No window without a master (superadmin must pick one first)
          (isSuperAdmin && selectedMasterId === '')
            ? Promise.resolve(null)
            : adminApi.getWorkWindow(masterParam).then(r => r.data).catch(() => null),
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
        if (windowResp) {
          setWindowStart(windowResp.start_hour)
          setWindowEnd(windowResp.end_hour)
          setWindowDraft({ start: String(windowResp.start_hour), end: String(windowResp.end_hour) })
        }
      } catch (err: any) {
        console.error('[SchedulePage] Init error:', err)
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    init()
    return () => { cancelled = true }
  }, [currentMonth, selectedMasterId])

  useEffect(() => {
    if (!bookingForm.open) return
    let cancelled = false
    Promise.all([
      adminApi.getClients(),
      adminApi.getAllServices(),
    ]).then(([clientsResp, servicesResp]) => {
      if (cancelled) return
      setBookingClients(clientsResp.data?.items || [])
      setBookingServices(servicesResp.data?.items || [])
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
    if (isSuperAdmin && selectedMasterId === '') {
      setError('Выберите мастера, чтобы менять расписание')
      return
    }
    const result = await toggleDayWork(date, schedule, activeHours, appointments, setError, selectedMasterId)
    if (result) {
      setSchedule(result.newSchedule)
      setActiveHours(result.newActiveHours)
    }
  }, [schedule, activeHours, appointments, selectedMasterId, isSuperAdmin])

  const handleAddSlot = useCallback(async (date: Date) => {
    const dateStr = date.toISOString().split('T')[0]
    // Check if already active
    if (schedule[dateStr]) return
    // Superadmin has no schedule of their own: a master must be chosen
    // (force-majeure adds go to the selected master).
    if (isSuperAdmin && selectedMasterId === '') {
      setError('Выберите мастера, чтобы добавить рабочий день')
      return
    }

    try {
      await adminApi.createWorkingHour({
        master_id: selectedMasterId === '' ? undefined : selectedMasterId,
        schedule_date: dateStr,
        start_time: '09:00',
        end_time: '18:00',
      })
      setSchedule(prev => ({
        ...prev,
        [dateStr]: { start: 9, end: 18 },
      }))
      const newActiveHours: Record<string, boolean> = {}
      for (let h = 9; h < 18; h++) {
        newActiveHours[`${dateStr}-${h}`] = true
      }
      setActiveHours(prev => ({ ...prev, ...newActiveHours }))
    } catch (err: unknown) {
      setError(getApiErrorMessage(err, 'Не удалось добавить рабочий день'))
    }
  }, [schedule, selectedMasterId, isSuperAdmin])

  // Toggling an hour persists to the server AND drives the day state:
  // turning any hour ON activates the whole day (it turns green),
  // turning the last hour OFF deactivates the day.
  const handleToggleHour = useCallback(async (dateStr: string, hour: number) => {
    const key = `${dateStr}-${hour}`
    const turningOn = !activeHours[key]
    if (isSuperAdmin && selectedMasterId === '') {
      setError('Выберите мастера, чтобы менять расписание')
      return
    }
    const masterParam = selectedMasterId !== '' ? selectedMasterId : undefined
    const pad = (h: number) => `${String(h).padStart(2, '0')}:00`

    if (turningOn) {
      setActiveHours(prev => ({ ...prev, [key]: true }))
      try {
        const resp = await adminApi.getWorkingHours(masterParam)
        const existing = resp.data.find((h: any) => h.schedule_date === dateStr)
        if (existing) {
          const curStart = Number(String(existing.start_time).split(':')[0])
          const curEnd = Number(String(existing.end_time).split(':')[0])
          const start = Math.min(curStart, hour)
          const end = Math.max(curEnd, hour + 1)
          await adminApi.updateWorkingHour(existing.id, {
            schedule_date: dateStr, start_time: pad(start), end_time: pad(end),
          })
          setSchedule(prev => ({ ...prev, [dateStr]: { start, end } }))
        } else {
          await adminApi.createWorkingHour({
            master_id: masterParam, schedule_date: dateStr,
            start_time: pad(hour), end_time: pad(hour + 1),
          })
          setSchedule(prev => ({ ...prev, [dateStr]: { start: hour, end: hour + 1 } }))
        }
      } catch (err: unknown) {
        setActiveHours(prev => ({ ...prev, [key]: false }))
        setError(getApiErrorMessage(err, 'Не удалось включить час'))
      }
      return
    }

    // Turning OFF
    const remaining = Object.keys(activeHours)
      .filter(k => k.startsWith(`${dateStr}-`) && k !== key && activeHours[k])
      .map(k => Number(k.split('-').pop()))
    setActiveHours(prev => ({ ...prev, [key]: false }))
    try {
      const resp = await adminApi.getWorkingHours(masterParam)
      const existing = resp.data.find((h: any) => h.schedule_date === dateStr)
      if (!existing) {
        if (remaining.length === 0) {
          setSchedule(prev => {
            const next = { ...prev }
            delete next[dateStr]
            return next
          })
        }
        return
      }
      if (remaining.length === 0) {
        await adminApi.deleteWorkingHour(existing.id)
        setSchedule(prev => {
          const next = { ...prev }
          delete next[dateStr]
          return next
        })
      } else {
        // Backend stores one range per day: shrink to the remaining edges
        // (a hole in the middle stays visually off but covered by the range)
        const start = Math.min(...remaining)
        const end = Math.max(...remaining) + 1
        await adminApi.updateWorkingHour(existing.id, {
          schedule_date: dateStr, start_time: pad(start), end_time: pad(end),
        })
        setSchedule(prev => ({ ...prev, [dateStr]: { start, end } }))
      }
    } catch (err: unknown) {
      setActiveHours(prev => ({ ...prev, [key]: true }))
      setError(getApiErrorMessage(err, 'Не удалось выключить час'))
    }
  }, [activeHours, selectedMasterId, isSuperAdmin])

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
        const resp = await adminApi.getAppointmentsByDate(
          from, to, selectedMasterId !== '' ? selectedMasterId : undefined)
        setAppointments(resp.data || [])
      } catch { /* ignore */ }
    }
  }, [bookingForm, currentMonth, handleCloseBooking, selectedMasterId])

  if (loading) return <div style={{ padding: 60, textAlign: 'center', color: '#666' }}>Загрузка...</div>

  return (
    <div style={{ padding: '0 20px', maxWidth: 1200, margin: '0 auto' }}>
      <div style={{ marginBottom: 8, textAlign: 'center' }}>
        <h1 style={{ fontSize: 24, margin: 0, color: '#1a1a2e' }}>📅 Рабочее расписание</h1>
        <p style={{ margin: '4px 0 0', color: '#666', fontSize: 14 }}>Нажмите на день чтобы увидеть бронирования</p>
      </div>

      {/* Master filter (superadmin only) */}
      {isSuperAdmin && (
        <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'center', gap: 12, alignItems: 'center' }}>
          <MasterSelect
            value={selectedMasterId}
            onChange={setSelectedMasterId}
            allowAll={false}
            label="Мастер (обязательно для добавления дней)"
          />
        </div>
      )}
      {isSuperAdmin && selectedMasterId === '' && (
        <div className="card" style={{ textAlign: 'center', marginBottom: 16 }}>
          <p style={{ margin: 0, color: '#666' }}>👆 Выберите мастера, чтобы увидеть его расписание. Добавлять дни себе нельзя — только мастерам.</p>
        </div>
      )}

      {/* No calendar without a master: nothing to display yet */}
      {!(isSuperAdmin && selectedMasterId === '') && (
      <>
      {/* Daily work window: how many hourly granules working days offer */}
      <div className="card" style={{ marginBottom: 16, padding: 12 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 10, flexWrap: 'wrap' }}>
          <span style={{ fontSize: 14, fontWeight: 600 }}>🕐 Рабочее время:</span>
          <span style={{ fontSize: 13, color: '#666' }}>с</span>
          <input
            type="number" min={0} max={23}
            value={windowDraft.start}
            onChange={(e) => setWindowDraft(d => ({ ...d, start: e.target.value }))}
            style={{ width: 64, padding: 6, border: '2px solid #e0e0e0', borderRadius: 8, fontSize: 14 }}
            aria-label="Начало рабочего времени"
          />
          <span style={{ fontSize: 13, color: '#666' }}>до</span>
          <input
            type="number" min={1} max={24}
            value={windowDraft.end}
            onChange={(e) => setWindowDraft(d => ({ ...d, end: e.target.value }))}
            style={{ width: 64, padding: 6, border: '2px solid #e0e0e0', borderRadius: 8, fontSize: 14 }}
            aria-label="Конец рабочего времени"
          />
          <button
            className="btn btn-sm btn-primary"
            disabled={windowSaving}
            onClick={async () => {
              const start = Number(windowDraft.start)
              const end = Number(windowDraft.end)
              if (!Number.isInteger(start) || !Number.isInteger(end) || start < 0 || end > 24 || start >= end) {
                setError('Укажите часы 0–24, начало раньше конца')
                return
              }
              setWindowSaving(true)
              try {
                const { data } = await adminApi.updateWorkWindow({
                  ...(selectedMasterId !== '' ? { master_id: selectedMasterId } : {}),
                  start_hour: start, end_hour: end,
                })
                setWindowStart(data.start_hour)
                setWindowEnd(data.end_hour)
                toast.success(`Рабочее время: ${data.start_hour}:00–${data.end_hour}:00`)
              } catch (err: unknown) {
                setError(getApiErrorMessage(err, 'Не удалось сохранить рабочее время'))
              } finally {
                setWindowSaving(false)
              }
            }}
          >
            Сохранить
          </button>
        </div>
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
        onAddSlot={handleAddSlot}
        longPressTriggered={longPressTriggered}
      />

      {selectedDate && (
        <TimeSlots
          selectedDate={selectedDate}
          appointments={appointments}
          activeHours={activeHours}
          onToggleHour={handleToggleHour}
          onOpenBooking={handleOpenBooking}
          windowStart={windowStart}
          windowEnd={windowEnd}
        />
      )}

      <MonthlyStatsComponent currentMonth={currentMonth} stats={monthlyStats} />
      </>
      )}

      {/* Error modal */}
      <ConfirmDialog
        open={error !== ''}
        onClose={() => setError('')}
        title="⚠️ Внимание"
        message={error}
        confirmLabel="OK"
        hideCancel
        onConfirm={() => setError('')}
      />

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
