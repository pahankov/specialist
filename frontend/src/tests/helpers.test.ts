import { describe, it, expect } from 'vitest'
import {
  formatDate,
  formatHour,
  getMonthDays,
  getHoursForDay,
  getAppointmentsForSlot,
  getSlotStatus,
  isPast,
  isToday,
  isSlotPast,
  getMonthName,
  getFilteredClients,
  getFilteredServices,
  formatPrice,
  buildMonthlyStats,
} from '../components/schedule/helpers'
import type { Appointment, DaySchedule } from '../api/types'

describe('helpers', () => {
  describe('formatDate', () => {
    it('formats date to YYYY-MM-DD', () => {
      const date = new Date(2026, 0, 15)
      const result = formatDate(date)
      expect(result).toMatch(/^\d{4}-\d{2}-\d{2}$/)
    })
  })

  describe('formatHour', () => {
    it('formats single digit hour', () => {
      expect(formatHour(9)).toBe('09:00')
    })

    it('formats double digit hour', () => {
      expect(formatHour(14)).toBe('14:00')
    })
  })

  describe('getMonthDays', () => {
    it('returns days for the given month', () => {
      const date = new Date(2026, 0, 15)
      const days = getMonthDays(date)
      expect(days.length).toBeGreaterThan(28)
      const currentMonthDays = days.filter(d => d.isCurrentMonth)
      expect(currentMonthDays.length).toBe(31)
    })

    it('includes previous month padding', () => {
      const date = new Date(2026, 0, 1)
      const days = getMonthDays(date)
      const prevMonthDays = days.filter(d => !d.isCurrentMonth)
      expect(prevMonthDays.length).toBeGreaterThan(0)
    })
  })

  describe('getHoursForDay', () => {
    it('returns default hours for missing date', () => {
      const schedule: Record<string, DaySchedule> = {}
      const date = new Date(2026, 0, 15)
      expect(getHoursForDay(schedule, date)).toEqual({ start: 8, end: 22 })
    })
  })

  describe('getAppointmentsForSlot', () => {
    const appointments: Appointment[] = [
      {
        id: 1, master_id: 1, service_id: 1, client_id: 1,
        appointment_date: '2026-01-15T09:00:00',
        status: 'confirmed', notes: '', created_at: '2026-01-10T00:00:00',
      },
      {
        id: 2, master_id: 1, service_id: 1, client_id: 2,
        appointment_date: '2026-01-15T10:00:00',
        status: 'pending', notes: '', created_at: '2026-01-10T00:00:00',
      },
    ]

    it('returns empty for no matching appointments', () => {
      const date = new Date(2026, 0, 15)
      const result = getAppointmentsForSlot(appointments, date, 15)
      expect(result).toHaveLength(0)
    })
  })

  describe('getSlotStatus', () => {
    it('returns free for empty array', () => {
      expect(getSlotStatus([])).toBe('free')
    })

    it('returns highest priority status', () => {
      const completedSlots: Appointment[] = [{
        id: 1, master_id: 1, service_id: 1, client_id: 1,
        appointment_date: '2026-01-15T09:00:00',
        status: 'completed', notes: '', created_at: '2026-01-10T00:00:00',
      }]
      const confirmedSlots: Appointment[] = [{
        id: 1, master_id: 1, service_id: 1, client_id: 1,
        appointment_date: '2026-01-15T09:00:00',
        status: 'confirmed', notes: '', created_at: '2026-01-10T00:00:00',
      }]
      const pendingSlots: Appointment[] = [{
        id: 1, master_id: 1, service_id: 1, client_id: 1,
        appointment_date: '2026-01-15T09:00:00',
        status: 'pending', notes: '', created_at: '2026-01-10T00:00:00',
      }]

      expect(getSlotStatus(completedSlots)).toBe('completed')
      expect(getSlotStatus(confirmedSlots)).toBe('confirmed')
      expect(getSlotStatus(pendingSlots)).toBe('pending')
    })
  })

  describe('isPast', () => {
    it('returns true for past date', () => {
      expect(isPast(new Date(2020, 0, 1))).toBe(true)
    })

    it('returns false for future date', () => {
      expect(isPast(new Date(2030, 0, 1))).toBe(false)
    })
  })

  describe('isToday', () => {
    it('returns true for today', () => {
      expect(isToday(new Date())).toBe(true)
    })

    it('returns false for non-today', () => {
      const yesterday = new Date()
      yesterday.setDate(yesterday.getDate() - 1)
      expect(isToday(yesterday)).toBe(false)
    })
  })

  describe('isSlotPast', () => {
    it('returns false for future slot', () => {
      const futureDate = new Date()
      futureDate.setFullYear(futureDate.getFullYear() + 1)
      futureDate.setHours(20, 0, 0, 0)
      expect(isSlotPast(futureDate, 20)).toBe(false)
    })
  })

  describe('getMonthName', () => {
    it('returns month name with year', () => {
      const date = new Date(2026, 0, 15)
      const name = getMonthName(date)
      expect(name).toContain('2026')
    })
  })

  describe('getFilteredClients', () => {
    const clients = [
      { id: 1, name: 'Иван Петров', phone: '+79001234567' },
      { id: 2, name: 'Мария Сидорова', phone: '+79009876543' },
      { id: 3, name: 'Алексей Козлов', phone: '+79005555555' },
    ]

    it('returns all clients when search is empty', () => {
      expect(getFilteredClients(clients, '')).toHaveLength(3)
    })

    it('filters by name', () => {
      const result = getFilteredClients(clients, 'Мария')
      expect(result).toHaveLength(1)
      expect(result[0].name).toBe('Мария Сидорова')
    })

    it('filters by phone', () => {
      const result = getFilteredClients(clients, '900123')
      expect(result).toHaveLength(1)
    })

    it('is case insensitive', () => {
      const result = getFilteredClients(clients, 'иван')
      expect(result).toHaveLength(1)
    })
  })

  describe('getFilteredServices', () => {
    const services = [
      { id: 1, name: 'Депиляция ног', duration_minutes: 30, price: 1500 },
      { id: 2, name: 'Депиляция рук', duration_minutes: 20, price: 1000 },
      { id: 3, name: 'Депиляция бикини', duration_minutes: 25, price: 2000 },
    ]

    it('returns all services when search is empty', () => {
      expect(getFilteredServices(services, '')).toHaveLength(3)
    })

    it('filters by name', () => {
      const result = getFilteredServices(services, 'ног')
      expect(result).toHaveLength(1)
      expect(result[0].name).toBe('Депиляция ног')
    })
  })

  describe('formatPrice', () => {
    it('formats number with locale', () => {
      const result = formatPrice(1500)
      expect(result.length).toBeGreaterThan(0)
    })

    it('formats string price', () => {
      const result = formatPrice('2500')
      expect(result.length).toBeGreaterThan(0)
    })
  })

  describe('buildMonthlyStats', () => {
    it('returns empty array for null stats', () => {
      expect(buildMonthlyStats(null)).toEqual([])
    })

    it('returns formatted stats', () => {
      const stats = {
        confirmed_appointments: 10,
        total_minutes: 600,
        total_hours: 10,
        revenue: 15000,
      }
      const result = buildMonthlyStats(stats)
      expect(result).toHaveLength(3)
      expect(result[0].value).toBe(10)
      expect(result[1].label).toBe('Часов (подт.)')
    })
  })
})
