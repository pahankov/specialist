import type { Appointment, DaySchedule } from '../../api/types';

export const STATUS_CONFIG: Record<string, { label: string; bg: string; text: string }> = {
  free: { label: 'Свободно', bg: '#e0e0e0', text: '#666' },
  pending: { label: 'Ожидает', bg: '#fff8e1', text: '#f57f17' },
  confirmed: { label: 'Подтверждена', bg: '#e3f2fd', text: '#1565c0' },
  completed: { label: 'Завершена', bg: '#e8f5e9', text: '#2e7d32' },
  cancelled: { label: 'Отменена', bg: '#f5f5f5', text: '#616161' },
  'no-show': { label: 'Неявка', bg: '#fff3e0', text: '#e65100' },
};

/** Local YYYY-MM-DD (never toISOString: UTC shifts the day for +03:00). */
export function formatDate(date: Date): string {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, '0');
  const d = String(date.getDate()).padStart(2, '0');
  return `${y}-${m}-${d}`;
}

export function formatHour(h: number): string {
  return String(h).padStart(2, '0') + ':00';
}

/** Format a granule slot (index where 1 slot = slotMinutes minutes) as "HH:MM". */
export function formatSlotTime(slot: number, slotMinutes: number): string {
  const totalMinutes = slot * slotMinutes;
  const h = Math.floor(totalMinutes / 60);
  const m = totalMinutes % 60;
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`;
}

/** Backend stores SQL TIME (max 23:59), so 24:00 is sent as 23:59. */
export function hourToTime(hour: number): string {
  return hour >= 24 ? '23:59' : formatHour(hour);
}

/** Convert whole-hour time to a slot index (slotMinutes=60 → slot == hour). */
export function hourToSlot(hour: number, slotMinutes: number): number {
  return Math.round((hour * 60) / slotMinutes);
}

/** Parse a stored working-day range, rounding the end up to a full granule,
 * expressed in whole hours (backwards compatible). */
export function parseHourRange(startTime: string, endTime: string): DaySchedule {
  const [startHour] = startTime.split(':').map(Number);
  const [endHour, endMinute = 0, endSecond = 0] = endTime.split(':').map(Number);
  return {
    start: startHour,
    end: endHour + (endMinute > 0 || endSecond > 0 ? 1 : 0),
  };
}

/** Parse a stored working-day range into slot indices. */
export function parseHourRangeToSlots(
  startTime: string,
  endTime: string,
  slotMinutes: number,
): { startSlot: number; endSlot: number } {
  const [startHour, startMinute = 0] = startTime.split(':').map(Number);
  const [endHour, endMinute = 0, endSecond = 0] = endTime.split(':').map(Number);
  const startMinutes = startHour * 60 + startMinute;
  const endMinutes = endHour * 60 + endMinute + (endSecond > 0 ? 1 : 0);
  return {
    startSlot: Math.round(startMinutes / slotMinutes),
    endSlot: Math.round(endMinutes / slotMinutes),
  };
}

/** Total minutes of day for a slot index. */
export function slotToMinutes(slot: number, slotMinutes: number): number {
  return slot * slotMinutes;
}

/**
 * Re-index a day range for a different granule size. Splitting an hour into
 * halves/quarters is exact; when granules get coarser the range is rounded
 * outward so no working minutes are dropped.
 */
export function rescaleSlotRange(
  range: DaySchedule,
  fromMinutes: 60 | 30 | 15,
  toMinutes: 60 | 30 | 15,
): DaySchedule {
  if (fromMinutes === toMinutes) return { ...range };
  return {
    start: Math.floor((range.start * fromMinutes) / toMinutes),
    end: Math.ceil((range.end * fromMinutes) / toMinutes),
  };
}

/**
 * Rescale every enabled granule when the mode changes. One old granule maps
 * onto all new granules it covers: an active hour becomes two half-hour or
 * four quarter-hour granules, while disabled granules stay disabled. No new
 * working time appears outside the previous range.
 */
export function rescaleActiveHours(
  activeHours: Record<string, boolean>,
  fromMinutes: 60 | 30 | 15,
  toMinutes: 60 | 30 | 15,
): Record<string, boolean> {
  if (fromMinutes === toMinutes) return activeHours;
  const next: Record<string, boolean> = {};
  for (const [key, active] of Object.entries(activeHours)) {
    if (!active) continue;
    const dash = key.lastIndexOf('-');
    if (dash < 0) continue;
    const date = key.slice(0, dash);
    const slot = Number(key.slice(dash + 1));
    if (!Number.isInteger(slot)) continue;
    const start = Math.floor((slot * fromMinutes) / toMinutes);
    const end = Math.max(start + 1, Math.ceil(((slot + 1) * fromMinutes) / toMinutes));
    for (let s = start; s < end; s += 1) next[`${date}-${s}`] = true;
  }
  return next;
}

/** Rescale a whole month of day ranges for a new granule size. */
export function rescaleSchedule(
  schedule: Record<string, DaySchedule>,
  fromMinutes: 60 | 30 | 15,
  toMinutes: 60 | 30 | 15,
): Record<string, DaySchedule> {
  if (fromMinutes === toMinutes) return schedule;
  const next: Record<string, DaySchedule> = {};
  for (const [date, range] of Object.entries(schedule)) {
    const rescaled = rescaleSlotRange(range, fromMinutes, toMinutes);
    if (rescaled.end > rescaled.start) next[date] = rescaled;
  }
  return next;
}

export function getMonthDays(date: Date): { date: Date; isCurrentMonth: boolean }[] {
  const year = date.getFullYear();
  const month = date.getMonth();
  const firstDay = new Date(year, month, 1);
  const lastDay = new Date(year, month + 1, 0);
  const days: { date: Date; isCurrentMonth: boolean }[] = [];
  const startDayOfWeek = firstDay.getDay() === 0 ? 6 : firstDay.getDay() - 1;

  for (let i = 0; i < startDayOfWeek; i++) {
    days.push({ date: new Date(year, month, 1 - (startDayOfWeek - i)), isCurrentMonth: false });
  }
  for (let d = 1; d <= lastDay.getDate(); d++) {
    days.push({ date: new Date(year, month, d), isCurrentMonth: true });
  }
  return days;
}

export function getHoursForDay(
  schedule: Record<string, DaySchedule>,
  date: Date,
): { start: number; end: number } {
  const dateStr = formatDate(date);
  return schedule[dateStr] || { start: 8, end: 22 };
}

export function getAppointmentsForSlot(
  appointments: Appointment[],
  date: Date,
  slot: number,
  slotMinutes: 60 | 30 | 15 = 60,
): Appointment[] {
  // Compare via Date parts: backend strings may be naive or carry +03:00/Z,
  // string-splitting breaks across those shapes.
  const startMinute = slot * slotMinutes;
  return appointments.filter((a) => {
    const d = new Date(a.appointment_date);
    if (Number.isNaN(d.getTime())) return false;
    return (
      d.getFullYear() === date.getFullYear() &&
      d.getMonth() === date.getMonth() &&
      d.getDate() === date.getDate() &&
      d.getHours() * 60 + d.getMinutes() === startMinute
    );
  });
}

export function getSlotStatus(slots: Appointment[]): string {
  if (slots.length === 0) return 'free';
  const statusOrder = ['completed', 'confirmed', 'pending', 'cancelled'];
  for (const status of statusOrder) {
    if (slots.some((s) => s.status === status)) return status;
  }
  return 'pending';
}

/** How many granules a booking occupies (slotMinutes=30: 90 мин → 3, 30 мин → 1). */
export function appointmentSpanSlots(
  a: Pick<Appointment, 'service_duration'>,
  slotMinutes: 60 | 30 | 15 = 60,
): number {
  const dur = Number(a.service_duration);
  if (!Number.isFinite(dur) || dur <= 0) return 1;
  return Math.max(1, Math.ceil(dur / slotMinutes));
}

/** Backwards-compatible alias: granules are whole hours by default. */
export function appointmentSpanHours(a: Pick<Appointment, 'service_duration'>): number {
  return appointmentSpanSlots(a, 60);
}

/** Start slot of a booking on the given day (null when unparsable). */
function startSlotOnDay(a: Appointment, date: Date, slotMinutes: 60 | 30 | 15): number | null {
  const d = new Date(a.appointment_date);
  if (Number.isNaN(d.getTime())) return null;
  if (
    d.getFullYear() !== date.getFullYear() ||
    d.getMonth() !== date.getMonth() ||
    d.getDate() !== date.getDate()
  )
    return null;
  return Math.round((d.getHours() * 60 + d.getMinutes()) / slotMinutes);
}

/** Live booking that covers `slot` via an earlier start (span continuation).
 * Same-day part only (capped at 24:00); cancelled bookings never block. */
export function getCoveringLive(
  appointments: Appointment[],
  date: Date,
  slot: number,
  slotMinutes: 60 | 30 | 15 = 60,
): Appointment | null {
  const lastSlot = Math.ceil((24 * 60) / slotMinutes);
  for (const a of appointments) {
    if (a.status === 'cancelled') continue;
    const start = startSlotOnDay(a, date, slotMinutes);
    if (start === null || start >= slot) continue;
    if (slot < Math.min(lastSlot, start + appointmentSpanSlots(a, slotMinutes))) return a;
  }
  return null;
}

/** All live bookings blocking `slot`: starters + span continuations. */
export function getBlockingLive(
  appointments: Appointment[],
  date: Date,
  slot: number,
  slotMinutes: 60 | 30 | 15 = 60,
) {
  const starters = getAppointmentsForSlot(appointments, date, slot, slotMinutes).filter(
    (s) => s.status !== 'cancelled',
  );
  const covering = getCoveringLive(appointments, date, slot, slotMinutes);
  const out = [...starters];
  if (covering && !out.some((s) => s.id === covering.id)) out.push(covering);
  return out;
}

export function isPast(date: Date): boolean {
  const now = new Date();
  const d = new Date(date.getFullYear(), date.getMonth(), date.getDate());
  const n = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  return d < n;
}

export function isToday(date: Date): boolean {
  const today = new Date();
  return (
    date.getDate() === today.getDate() &&
    date.getMonth() === today.getMonth() &&
    date.getFullYear() === today.getFullYear()
  );
}

export function isSlotPast(date: Date, slot: number, slotMinutes: 60 | 30 | 15 = 60): boolean {
  const slotDate = new Date(date);
  const totalMinutes = slot * slotMinutes;
  slotDate.setHours(Math.floor(totalMinutes / 60), totalMinutes % 60, 0, 0);
  return slotDate < new Date();
}

export function getMonthName(date: Date): string {
  return date.toLocaleString('ru-RU', { month: 'long', year: 'numeric' });
}

export function getFilteredClients(
  clients: { id: number; name: string; phone: string }[],
  search: string,
): { id: number; name: string; phone: string }[] {
  if (!search) return clients;
  const lower = search.toLowerCase();
  return clients.filter((c) => c.name.toLowerCase().includes(lower) || c.phone.includes(search));
}

export function getFilteredServices(
  services: {
    id: number;
    name: string;
    duration_minutes: number;
    price: number | string;
    discount_percent?: number | null;
    effective_price?: number | string | null;
    discount_fixed?: number | string | null;
    discount_until?: string | null;
  }[],
  search: string,
): {
  id: number;
  name: string;
  duration_minutes: number;
  price: number | string;
  discount_percent?: number | null;
  effective_price?: number | string | null;
  discount_fixed?: number | string | null;
  discount_until?: string | null;
}[] {
  if (!search) return services;
  const lower = search.toLowerCase();
  return services.filter((s) => s.name.toLowerCase().includes(lower));
}

export function formatPrice(price: number | string): string {
  const num = typeof price === 'string' ? parseFloat(price) : price;
  return num.toLocaleString('ru-RU');
}

/** Local YYYY-MM (never toISOString().slice(): UTC midnight shifts the
 * month back in UTC+3 — forward navigation silently no-ops). */
export function monthISO(date: Date): string {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`;
}

/** Short discount tag: "−20%", "−500 ₽", "−20% до 20.10". Empty when none. */
export function formatDiscountTag(
  discountPercent?: number | null,
  discountUntil?: string | null,
  discountFixed?: number | string | null,
): string {
  const parts: string[] = [];
  if (discountPercent) parts.push(`−${discountPercent}%`);
  const fixed = Number(discountFixed) || 0;
  if (fixed > 0) parts.push(`−${fixed} ₽`);
  if (parts.length === 0) return '';
  let tag = parts.join(' ');
  if (discountUntil) {
    try {
      const d = new Date(discountUntil);
      tag += ` до ${d.toLocaleDateString('ru-RU', { day: 'numeric', month: 'numeric' })}`;
    } catch {
      /* date stays hidden */
    }
  }
  return tag;
}

/** Generic Russian plural: pluralize(1,'запись','записи','записей'). */
export function pluralize(n: number, one: string, few: string, many: string): string {
  const m10 = n % 10;
  const m100 = n % 100;
  const word =
    m10 === 1 && m100 !== 11 ? one : m10 >= 2 && m10 <= 4 && (m100 < 12 || m100 > 14) ? few : many;
  return `${n} ${word}`;
}

/** Russian plural for pending holds: "1 бронь", "3 брони", "5 броней". */
export function pluralHolds(n: number): string {
  return pluralize(n, 'бронь', 'брони', 'броней');
}

/** Exact viewed-month range for by-date fetches (init once cut at the 28th). */
export function monthRangeISO(d: Date): { from: string; to: string } {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const last = new Date(y, d.getMonth() + 1, 0).getDate();
  return { from: `${y}-${m}-01`, to: `${y}-${m}-${String(last).padStart(2, '0')}` };
}
/** Russian plural for bookings: "1 запись", "3 записи", "5 записей". */
export function pluralBookings(n: number): string {
  return pluralize(n, 'запись', 'записи', 'записей');
}

export function buildMonthlyStats(
  stats: {
    confirmed_appointments: number;
    total_minutes: number;
    total_hours: number;
    revenue: number;
    cancelled_appointments?: number;
  } | null,
): { value: string | number; label: string }[] {
  if (!stats) return [];
  return [
    { value: stats.confirmed_appointments, label: 'Подтверждено записей' },
    { value: stats.cancelled_appointments ?? 0, label: 'Отменено записей' },
    { value: stats.total_hours, label: 'Часов (всего)' },
    { value: `${formatPrice(stats.revenue)} ₽`, label: 'Доход (заверш.)' },
  ];
}
