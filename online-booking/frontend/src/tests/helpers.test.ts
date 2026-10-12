import { describe, it, expect } from 'vitest';
import {
  formatDate,
  formatHour,
  getMonthDays,
  getHoursForDay,
  getAppointmentsForSlot,
  getCoveringLive,
  getBlockingLive,
  appointmentSpanHours,
  getSlotStatus,
  isPast,
  isToday,
  isSlotPast,
  getMonthName,
  getFilteredClients,
  getFilteredServices,
  formatPrice,
  buildMonthlyStats,
  pluralBookings,
  pluralHolds,
  monthRangeISO,
} from '../components/schedule/helpers';
import type { Appointment, DaySchedule } from '../api/types';

describe('helpers', () => {
  describe('pluralBookings', () => {
    it('declines запись correctly', () => {
      expect(pluralBookings(1)).toBe('1 запись');
      expect(pluralBookings(2)).toBe('2 записи');
      expect(pluralBookings(4)).toBe('4 записи');
      expect(pluralBookings(5)).toBe('5 записей');
      expect(pluralBookings(11)).toBe('11 записей');
      expect(pluralBookings(12)).toBe('12 записей');
      expect(pluralBookings(21)).toBe('21 запись');
      expect(pluralBookings(22)).toBe('22 записи');
      expect(pluralBookings(25)).toBe('25 записей');
    });
  });

  describe('pluralHolds', () => {
    it('declines бронь correctly', () => {
      expect(pluralHolds(1)).toBe('1 бронь');
      expect(pluralHolds(3)).toBe('3 брони');
      expect(pluralHolds(5)).toBe('5 броней');
      expect(pluralHolds(11)).toBe('11 броней');
      expect(pluralHolds(21)).toBe('21 бронь');
    });
  });

  describe('monthRangeISO', () => {
    it('covers the whole month incl. 29–31', () => {
      expect(monthRangeISO(new Date(2026, 9, 12))).toEqual({
        from: '2026-10-01',
        to: '2026-10-31',
      });
      expect(monthRangeISO(new Date(2026, 1, 5)).to).toBe('2026-02-28');
      expect(monthRangeISO(new Date(2024, 1, 5)).to).toBe('2024-02-29');
    });
  });

  describe('formatDate', () => {
    it('formats date to YYYY-MM-DD', () => {
      const date = new Date(2026, 0, 15);
      const result = formatDate(date);
      expect(result).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    });
  });

  describe('formatHour', () => {
    it('formats single digit hour', () => {
      expect(formatHour(9)).toBe('09:00');
    });

    it('formats double digit hour', () => {
      expect(formatHour(14)).toBe('14:00');
    });
  });

  describe('getMonthDays', () => {
    it('returns days for the given month', () => {
      const date = new Date(2026, 0, 15);
      const days = getMonthDays(date);
      expect(days.length).toBeGreaterThan(28);
      const currentMonthDays = days.filter((d) => d.isCurrentMonth);
      expect(currentMonthDays.length).toBe(31);
    });

    it('includes previous month padding', () => {
      const date = new Date(2026, 0, 1);
      const days = getMonthDays(date);
      const prevMonthDays = days.filter((d) => !d.isCurrentMonth);
      expect(prevMonthDays.length).toBeGreaterThan(0);
    });
  });

  describe('getHoursForDay', () => {
    it('returns default hours for missing date', () => {
      const schedule: Record<string, DaySchedule> = {};
      const date = new Date(2026, 0, 15);
      expect(getHoursForDay(schedule, date)).toEqual({ start: 8, end: 22 });
    });
  });

  describe('getAppointmentsForSlot', () => {
    const appointments: Appointment[] = [
      {
        id: 1,
        master_id: 1,
        service_id: 1,
        client_id: 1,
        appointment_date: '2026-01-15T09:00:00',
        status: 'confirmed',
        notes: '',
        created_at: '2026-01-10T00:00:00',
      },
      {
        id: 2,
        master_id: 1,
        service_id: 1,
        client_id: 2,
        appointment_date: '2026-01-15T10:00:00',
        status: 'pending',
        notes: '',
        created_at: '2026-01-10T00:00:00',
      },
    ];

    it('returns empty for no matching appointments', () => {
      const date = new Date(2026, 0, 15);
      const result = getAppointmentsForSlot(appointments, date, 15);
      expect(result).toHaveLength(0);
    });
  });

  describe('getSlotStatus', () => {
    it('returns free for empty array', () => {
      expect(getSlotStatus([])).toBe('free');
    });

    it('returns highest priority status', () => {
      const completedSlots: Appointment[] = [
        {
          id: 1,
          master_id: 1,
          service_id: 1,
          client_id: 1,
          appointment_date: '2026-01-15T09:00:00',
          status: 'completed',
          notes: '',
          created_at: '2026-01-10T00:00:00',
        },
      ];
      const confirmedSlots: Appointment[] = [
        {
          id: 1,
          master_id: 1,
          service_id: 1,
          client_id: 1,
          appointment_date: '2026-01-15T09:00:00',
          status: 'confirmed',
          notes: '',
          created_at: '2026-01-10T00:00:00',
        },
      ];
      const pendingSlots: Appointment[] = [
        {
          id: 1,
          master_id: 1,
          service_id: 1,
          client_id: 1,
          appointment_date: '2026-01-15T09:00:00',
          status: 'pending',
          notes: '',
          created_at: '2026-01-10T00:00:00',
        },
      ];

      expect(getSlotStatus(completedSlots)).toBe('completed');
      expect(getSlotStatus(confirmedSlots)).toBe('confirmed');
      expect(getSlotStatus(pendingSlots)).toBe('pending');
    });
  });

  describe('isPast', () => {
    it('returns true for past date', () => {
      expect(isPast(new Date(2020, 0, 1))).toBe(true);
    });

    it('returns false for future date', () => {
      expect(isPast(new Date(2030, 0, 1))).toBe(false);
    });
  });

  describe('isToday', () => {
    it('returns true for today', () => {
      expect(isToday(new Date())).toBe(true);
    });

    it('returns false for non-today', () => {
      const yesterday = new Date();
      yesterday.setDate(yesterday.getDate() - 1);
      expect(isToday(yesterday)).toBe(false);
    });
  });

  describe('isSlotPast', () => {
    it('returns false for future slot', () => {
      const futureDate = new Date();
      futureDate.setFullYear(futureDate.getFullYear() + 1);
      futureDate.setHours(20, 0, 0, 0);
      expect(isSlotPast(futureDate, 20)).toBe(false);
    });
  });

  describe('getMonthName', () => {
    it('returns month name with year', () => {
      const date = new Date(2026, 0, 15);
      const name = getMonthName(date);
      expect(name).toContain('2026');
    });
  });

  describe('getFilteredClients', () => {
    const clients = [
      { id: 1, name: 'Иван Петров', phone: '+79001234567' },
      { id: 2, name: 'Мария Сидорова', phone: '+79009876543' },
      { id: 3, name: 'Алексей Козлов', phone: '+79005555555' },
    ];

    it('returns all clients when search is empty', () => {
      expect(getFilteredClients(clients, '')).toHaveLength(3);
    });

    it('filters by name', () => {
      const result = getFilteredClients(clients, 'Мария');
      expect(result).toHaveLength(1);
      expect(result[0].name).toBe('Мария Сидорова');
    });

    it('filters by phone', () => {
      const result = getFilteredClients(clients, '900123');
      expect(result).toHaveLength(1);
    });

    it('is case insensitive', () => {
      const result = getFilteredClients(clients, 'иван');
      expect(result).toHaveLength(1);
    });
  });

  describe('getFilteredServices', () => {
    const services = [
      { id: 1, name: 'Депиляция ног', duration_minutes: 30, price: 1500 },
      { id: 2, name: 'Депиляция рук', duration_minutes: 20, price: 1000 },
      { id: 3, name: 'Депиляция бикини', duration_minutes: 25, price: 2000 },
    ];

    it('returns all services when search is empty', () => {
      expect(getFilteredServices(services, '')).toHaveLength(3);
    });

    it('filters by name', () => {
      const result = getFilteredServices(services, 'ног');
      expect(result).toHaveLength(1);
      expect(result[0].name).toBe('Депиляция ног');
    });
  });

  describe('formatPrice', () => {
    it('formats number with locale', () => {
      const result = formatPrice(1500);
      expect(result.length).toBeGreaterThan(0);
    });

    it('formats string price', () => {
      const result = formatPrice('2500');
      expect(result.length).toBeGreaterThan(0);
    });
  });

  describe('buildMonthlyStats', () => {
    it('returns empty array for null stats', () => {
      expect(buildMonthlyStats(null)).toEqual([]);
    });

    it('returns formatted stats', () => {
      const stats = {
        confirmed_appointments: 10,
        total_minutes: 600,
        total_hours: 10,
        revenue: 15000,
      };
      const result = buildMonthlyStats(stats);
      expect(result).toHaveLength(3);
      expect(result[0].value).toBe(10);
      expect(result[1].label).toBe('Часов (подт.)');
    });
  });

  describe('appointmentSpanHours', () => {
    it('rounds duration up to whole granules', () => {
      expect(appointmentSpanHours({ service_duration: 30 })).toBe(1);
      expect(appointmentSpanHours({ service_duration: 60 })).toBe(1);
      expect(appointmentSpanHours({ service_duration: 90 })).toBe(2);
      expect(appointmentSpanHours({ service_duration: 121 })).toBe(3);
    });

    it('defaults to one granule without duration', () => {
      expect(appointmentSpanHours({ service_duration: null })).toBe(1);
      expect(appointmentSpanHours({ service_duration: undefined })).toBe(1);
      expect(appointmentSpanHours({})).toBe(1);
    });
  });

  describe('getCoveringLive', () => {
    const day = new Date(2026, 9, 14);
    const mk = (id: number, hour: number, status: string, dur: number | null) =>
      ({
        id,
        appointment_date: `2026-10-14T${String(hour).padStart(2, '0')}:00:00`,
        status,
        service_duration: dur,
      }) as Appointment;

    it('finds a 90-min booking covering the next granule', () => {
      const appts = [mk(1, 14, 'confirmed', 90)];
      expect(getCoveringLive(appts, day, 15)?.id).toBe(1);
      expect(getCoveringLive(appts, day, 14)).toBeNull();
      expect(getCoveringLive(appts, day, 16)).toBeNull();
    });

    it('ignores cancelled bookings', () => {
      const appts = [mk(1, 14, 'cancelled', 120)];
      expect(getCoveringLive(appts, day, 15)).toBeNull();
    });

    it('getBlockingLive merges starters and continuations', () => {
      const appts = [
        mk(1, 14, 'confirmed', 90),
        mk(2, 15, 'pending', 30),
      ];
      const blocking = getBlockingLive(appts, day, 15);
      expect(blocking.map((a) => a.id).sort()).toEqual([1, 2]);
    });
  });
});
