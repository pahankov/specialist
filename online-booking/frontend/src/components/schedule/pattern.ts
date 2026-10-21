import { formatDate } from './helpers';

/** Repeating work/rest template used to fill a month in one action. */
export interface SchedulePattern {
  workDays: number;
  offDays: number;
  /** First work day of the cycle (YYYY-MM-DD, local date). */
  anchor: string;
  startHour: number;
  endHour: number;
  /** Remove working days that fall on rest days of the template. */
  replaceOffDays: boolean;
}

export interface PatternPreview {
  from: Date | null;
  to: Date | null;
  workDays: number;
  offDays: number;
  workDates: Set<string>;
  offDates: Set<string>;
  canApply: boolean;
}

export interface PatternPreset {
  label: string;
  workDays: number;
  offDays: number;
  hint: string;
}

export const PATTERN_PRESETS: PatternPreset[] = [
  { label: '5/2', workDays: 5, offDays: 2, hint: 'Будни' },
  { label: '2/2', workDays: 2, offDays: 2, hint: 'Смены' },
  { label: '3/3', workDays: 3, offDays: 3, hint: 'Смены' },
  { label: '1/3', workDays: 1, offDays: 3, hint: 'Сутки через три' },
  { label: '4/2', workDays: 4, offDays: 2, hint: 'Смены' },
  { label: '6/1', workDays: 6, offDays: 1, hint: 'Шестидневка' },
  { label: '7/0', workDays: 7, offDays: 0, hint: 'Без выходных' },
];

const DAY_MS = 24 * 60 * 60 * 1000;

/** Local midnight Monday of the week containing `date`. */
export function mondayOnOrBefore(date: Date): Date {
  const d = new Date(date.getFullYear(), date.getMonth(), date.getDate());
  const day = d.getDay() === 0 ? 7 : d.getDay(); // Mon=1..Sun=7
  d.setDate(d.getDate() - (day - 1));
  return d;
}

/** Default template: 5/2 aligned to Monday, hours 09:00–18:00. */
export function createDefaultPattern(today = new Date()): SchedulePattern {
  return {
    workDays: 5,
    offDays: 2,
    anchor: formatDate(mondayOnOrBefore(today)),
    startHour: 9,
    endHour: 18,
    replaceOffDays: true,
  };
}

function parseLocalDate(iso: string): Date | null {
  const parts = iso.split('-').map(Number);
  if (parts.length !== 3 || parts.some((n) => !Number.isFinite(n))) return null;
  return new Date(parts[0], parts[1] - 1, parts[2]);
}

function daySerial(date: Date): number {
  return Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()) / DAY_MS;
}

/**
 * Day 0 of the cycle (the anchor) is a work day; the next `workDays` days
 * work, then `offDays` rest. Negative offsets work too (month before anchor).
 */
export function isPatternWorkDay(
  date: Date,
  anchorISO: string,
  workDays: number,
  offDays: number,
): boolean {
  const cycle = Math.max(1, workDays + offDays);
  const anchor = parseLocalDate(anchorISO);
  if (!anchor) return true;
  const diff = Math.round(daySerial(date) - daySerial(anchor));
  const phase = ((diff % cycle) + cycle) % cycle;
  return phase < workDays;
}

/**
 * Work/rest days of `month` that the template would touch. Only today and
 * future dates are counted — the backend never edits past days.
 */
export function buildPatternPreview(
  month: Date,
  pattern: SchedulePattern,
  today = new Date(),
): PatternPreview {
  const monthStart = new Date(month.getFullYear(), month.getMonth(), 1);
  const monthEnd = new Date(month.getFullYear(), month.getMonth() + 1, 0);
  const todayStart = new Date(today.getFullYear(), today.getMonth(), today.getDate());
  const from = monthStart < todayStart ? todayStart : monthStart;
  const workDates = new Set<string>();
  const offDates = new Set<string>();
  let workDays = 0;
  let offDays = 0;

  if (from <= monthEnd) {
    for (let d = new Date(from); d <= monthEnd; d.setDate(d.getDate() + 1)) {
      const iso = formatDate(d);
      if (isPatternWorkDay(d, pattern.anchor, pattern.workDays, pattern.offDays)) {
        workDates.add(iso);
        workDays += 1;
      } else {
        offDates.add(iso);
        offDays += 1;
      }
    }
  }

  return {
    from: from <= monthEnd ? from : null,
    to: from <= monthEnd ? monthEnd : null,
    workDays,
    offDays,
    workDates,
    offDates,
    canApply:
      from <= monthEnd &&
      pattern.workDays >= 1 &&
      pattern.startHour >= 0 &&
      pattern.endHour > pattern.startHour &&
      pattern.endHour <= 24 &&
      parseLocalDate(pattern.anchor) !== null,
  };
}
