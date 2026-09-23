import type { Appointment, Client, DaySchedule, BookingFormState } from '../../api/types'
import { formatDate } from './helpers'
import { adminApi } from '../../api/client'

export async function toggleDayWork(
  date: Date,
  schedule: Record<string, DaySchedule>,
  activeHours: Record<string, boolean>,
  appointments: Appointment[],
  setError: (msg: string) => void
): Promise<{ newSchedule: Record<string, DaySchedule>; newActiveHours: Record<string, boolean> } | null> {
  const dateStr = formatDate(date)
  const isActive = !!schedule[dateStr]

  if (isActive) {
    const dayAppointments = appointments.filter(a => a.appointment_date?.split('T')[0] === dateStr)
    if (dayAppointments.length > 0) {
      setError(`Нельзя деактивировать день — в нём ${dayAppointments.length} запись(ей). Сначала удалите записи.`)
      return null
    }
  }

  const newSchedule = { ...schedule }
  const newActiveHours = { ...activeHours }

  if (isActive) {
    delete newSchedule[dateStr]
    for (let h = 8; h < 22; h++) { delete newActiveHours[`${dateStr}-${h}`] }
  } else {
    newSchedule[dateStr] = { start: 8, end: 22 }
    for (let h = 8; h < 22; h++) { newActiveHours[`${dateStr}-${h}`] = true }
  }

  // Sync with backend
  try {
    if (isActive) {
      const resp = await adminApi.getWorkingHours()
      const existing = resp.data.find((h: any) => h.schedule_date === dateStr)
      if (existing) await adminApi.deleteWorkingHour(existing.id)
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

  return { newSchedule, newActiveHours }
}

export function toggleHour(dateStr: string, hour: number, setActiveHours: (fn: (prev: Record<string, boolean>) => Record<string, boolean>) => void) {
  setActiveHours(prev => ({ ...prev, [`${dateStr}-${hour}`]: !prev[`${dateStr}-${hour}`] }))
}

export function openBookingForm(date: Date, hour: number, setBookingForm: (fn: (prev: BookingFormState) => BookingFormState) => void) {
  setBookingForm(prev => ({ ...prev, open: true, date, hour, clientId: null, serviceId: null, status: 'pending', notes: '' }))
}

export function closeBookingForm(
  setBookingForm: (fn: (prev: BookingFormState) => BookingFormState) => void,
  setBookingClients: (clients: Client[]) => void
) {
  setBookingForm(() => ({ open: false, date: null, hour: null, clientId: null, serviceId: null, status: 'pending', notes: '' }))
  setBookingClients([])
}

export async function handleBookAppointment(
  bookingForm: BookingFormState,
  setBookingLoading: (loading: boolean) => void,
  setError: (msg: string) => void,
  api: typeof adminApi,
  onClose: () => void
): Promise<boolean> {
  if (!bookingForm.date || bookingForm.hour === null || !bookingForm.clientId || !bookingForm.serviceId) return false

  setBookingLoading(true)
  try {
    const dateStr = bookingForm.date.toISOString().split('T')[0]
    const hourStr = String(bookingForm.hour).padStart(2, '0')
    const appointmentDate = `${dateStr}T${hourStr}:00:00`
    await api.bookAppointment({
      client_id: bookingForm.clientId,
      service_id: bookingForm.serviceId,
      appointment_date: appointmentDate,
      status: bookingForm.status,
      notes: bookingForm.notes || undefined
    })
    onClose()
    return true
  } catch (err: any) {
    setError(err.response?.data?.detail || 'Произошла ошибка')
    return false
  } finally {
    setBookingLoading(false)
  }
}

export async function fetchAppointmentsForMonth(
  currentMonth: Date,
  setAppointments: (appts: any[]) => void
) {
  const year = currentMonth.getFullYear()
  const month = currentMonth.getMonth()
  const from = `${year}-${String(month + 1).padStart(2, '0')}-01`
  const lastDay = new Date(year, month + 1, 0).getDate()
  const to = `${year}-${String(month + 1).padStart(2, '0')}-${String(lastDay).padStart(2, '0')}`
  try {
    const resp = await adminApi.getAppointmentsByDate(from, to)
    setAppointments(resp.data || [])
  } catch {
    setAppointments([])
  }
}
