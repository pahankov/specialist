/** Schedule UI types (moved out of api/types — they describe view state, not API). */
import type { Appointment } from '../../api/types'

export interface MonthlyStats {
  confirmed_appointments: number
  total_minutes: number
  total_hours: number
  revenue: number
}

export interface CalendarDay {
  date: Date
  isCurrentMonth: boolean
}

export interface TimeSlot {
  hour: number
  status: 'free' | 'pending' | 'confirmed' | 'completed' | 'cancelled'
  appointments: Appointment[]
  isActive: boolean
}

export interface DaySchedule {
  start: number
  end: number
}

export interface BookingFormState {
  open: boolean
  date: Date | null
  hour: number | null
  clientId: number | null
  serviceId: number | null
  status: 'pending' | 'confirmed'
  notes: string
}
