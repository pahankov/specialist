import type { Appointment, DaySchedule } from '../../api/types'

export const STATUS_CONFIG: Record<string, { label: string; bg: string; text: string }> = {
  free: { label: 'Свободно', bg: '#e0e0e0', text: '#666' },
  pending: { label: 'Ожидает', bg: '#fff8e1', text: '#f57f17' },
  confirmed: { label: 'Подтверждена', bg: '#e3f2fd', text: '#1565c0' },
  completed: { label: 'Завершена', bg: '#e8f5e9', text: '#2e7d32' },
  cancelled: { label: 'Отменена', bg: '#f5f5f5', text: '#616161' },
}

export function formatDate(date: Date): string {
  return date.toISOString().split('T')[0]
}

export function formatHour(h: number): string {
  return String(h).padStart(2, '0') + ':00'
}

export function getMonthDays(date: Date): { date: Date; isCurrentMonth: boolean }[] {
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

export function getHoursForDay(schedule: Record<string, DaySchedule>, date: Date): { start: number; end: number } {
  const dateStr = formatDate(date)
  return schedule[dateStr] || { start: 8, end: 22 }
}

export function getAppointmentsForSlot(
  appointments: Appointment[],
  date: Date,
  hour: number
): Appointment[] {
  const dateStr = formatDate(date)
  const hourStr = String(hour).padStart(2, '0')
  return appointments.filter(a => {
    const aDate = a.appointment_date.split('T')[0]
    const aHour = a.appointment_date.split('T')[1]?.slice(0, 2)
    return aDate === dateStr && aHour === hourStr
  })
}

export function getSlotStatus(slots: Appointment[]): string {
  if (slots.length === 0) return 'free'
  const statusOrder = ['completed', 'confirmed', 'pending', 'cancelled']
  for (const status of statusOrder) {
    if (slots.some(s => s.status === status)) return status
  }
  return 'pending'
}

export function isPast(date: Date): boolean {
  const now = new Date()
  const d = new Date(date.getFullYear(), date.getMonth(), date.getDate())
  const n = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  return d < n
}

export function isToday(date: Date): boolean {
  const today = new Date()
  return date.getDate() === today.getDate() &&
         date.getMonth() === today.getMonth() &&
         date.getFullYear() === today.getFullYear()
}

export function isSlotPast(date: Date, hour: number): boolean {
  const slotDate = new Date(date)
  slotDate.setHours(hour, 0, 0, 0)
  return slotDate < new Date()
}

export function getMonthName(date: Date): string {
  return date.toLocaleString('ru-RU', { month: 'long', year: 'numeric' })
}

export function getFilteredClients(
  clients: Array<{ id: number; name: string; phone: string }>,
  search: string
): Array<{ id: number; name: string; phone: string }> {
  if (!search) return clients
  const lower = search.toLowerCase()
  return clients.filter(c =>
    c.name.toLowerCase().includes(lower) || c.phone.includes(search)
  )
}

export function getFilteredServices(
  services: Array<{ id: number; name: string; duration_minutes: number; price: number | string }>,
  search: string
): Array<{ id: number; name: string; duration_minutes: number; price: number | string }> {
  if (!search) return services
  const lower = search.toLowerCase()
  return services.filter(s => s.name.toLowerCase().includes(lower))
}

export function formatPrice(price: number | string): string {
  const num = typeof price === 'string' ? parseFloat(price) : price
  return num.toLocaleString('ru-RU')
}

export function buildMonthlyStats(stats: { confirmed_appointments: number; total_minutes: number; total_hours: number; revenue: number } | null): Array<{ value: string | number; label: string }> {
  if (!stats) return []
  return [
    { value: stats.confirmed_appointments, label: 'Подтверждено записей' },
    { value: stats.total_hours, label: 'Часов (подт.)' },
    { value: `${formatPrice(stats.revenue)} ₽`, label: 'Доход (заверш.)' },
  ]
}
