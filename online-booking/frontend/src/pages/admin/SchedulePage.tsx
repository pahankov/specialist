import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { toast } from 'sonner';
import { adminApi } from '../../api/client';
import type {
  Appointment,
  Client,
  Service,
  DaySchedule,
  MonthlyStats,
  BookingFormState,
  WorkingHour,
} from '../../api/types';
import type { Bundle } from '../../api/cabinet';
import { Calendar } from '../../components/schedule/Calendar';
import { TimeSlots } from '../../components/schedule/TimeSlots';
import { BookingModal } from '../../components/schedule/BookingModal';
import { SchedulePatternPanel } from '../../components/schedule/SchedulePatternPanel';
import {
  buildPatternPreview,
  createDefaultPattern,
  mondayOnOrBefore,
  type SchedulePattern,
} from '../../components/schedule/pattern';
import {
  ConfirmDialog,
  MasterSelect,
  AutoConfirmSwitch,
  AutoCompleteSwitch,
} from '../../components/common';
import { getApiErrorMessage, getApiErrorStatus } from '../../utils/apiError';
import { getCookie, decodeJwtPayload } from '../../utils/cookies';
import { MonthlyStatsComponent } from '../../components/schedule/MonthlyStats';
import {
  appointmentSpanSlots,
  getBlockingLive,
  hourToSlot,
  monthRangeISO,
  parseHourRangeToSlots,
  rescaleActiveHours,
  rescaleDayActiveHours,
  rescaleSchedule,
  rescaleSlotRange,
  formatDate,
  formatSlotTime,
  monthISO,
} from '../../components/schedule/helpers';
import { usePersistentState } from '../../utils/persistentState';
import {
  toggleDayWork,
  openBookingForm,
  closeBookingForm,
  handleBookAppointment,
} from '../../components/schedule/hooks';

/** Build calendar state from stored rows. Day ranges are stored as slot
 * indices (1 slot = slotMinutes minutes; slot == hour when slotMinutes=60).
 * Days with an individual mode are parsed on their own grid. */
function buildScheduleState(
  rows: WorkingHour[],
  slotMinutes: 60 | 30 | 15 = 60,
  daySlotMinutes: Record<string, 60 | 30 | 15> = {},
): {
  schedule: Record<string, DaySchedule>;
  activeHours: Record<string, boolean>;
} {
  const schedule: Record<string, DaySchedule> = {};
  const activeHours: Record<string, boolean> = {};
  for (const wh of rows) {
    const mode = normalizeSlotMinutes(daySlotMinutes[wh.schedule_date], slotMinutes);
    const range = parseHourRangeToSlots(wh.start_time, wh.end_time, mode);
    schedule[wh.schedule_date] = { start: range.startSlot, end: range.endSlot };
    for (let s = range.startSlot; s < range.endSlot; s++) {
      activeHours[`${wh.schedule_date}-${s}`] = true;
    }
  }
  return { schedule, activeHours };
}

type SlotMinutes = 60 | 30 | 15;

function normalizeSlotMinutes(value: unknown, fallback: SlotMinutes): SlotMinutes {
  return value === 60 || value === 30 || value === 15 ? value : fallback;
}

function labelOf(a: Appointment): string {
  const who = a.client_name || 'клиент';
  const what = a.service_name || 'запись';
  const when = String(a.appointment_date).slice(0, 16).replace('T', ' ');
  return `${who} — ${what} (${when})`;
}

function SchedulePage() {
  const [schedule, setSchedule] = useState<Record<string, DaySchedule>>({});
  const [currentMonthISO, setCurrentMonthISO] = usePersistentState(
    'schedule.month',
    monthISO(new Date()),
  );
  const currentMonth = new Date(`${currentMonthISO}-01T00:00:00`);

  // Self-heal a corrupt persisted month (e.g. ancient sessionStorage value):
  // outside [-12, +36] months from now it can only be garbage.
  useEffect(() => {
    const m = new Date(`${currentMonthISO}-01T00:00:00`);
    if (Number.isNaN(m.getTime())) {
      setCurrentMonthISO(monthISO(new Date()));
      return;
    }
    const diff =
      (m.getFullYear() - new Date().getFullYear()) * 12 + (m.getMonth() - new Date().getMonth());
    if (diff < -12 || diff > 36) setCurrentMonthISO(monthISO(new Date()));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  // Functional update from the FRESH state: handlers are useCallback([]) and
  // must never compute from a stale render closure (that froze month flips).
  const setCurrentMonth = (d: Date | ((p: Date) => Date)) => {
    setCurrentMonthISO((prevISO) => {
      const prev = new Date(`${prevISO}-01T00:00:00`);
      const next = typeof d === 'function' ? d(prev) : d;
      return monthISO(next);
    });
  };
  const [selectedDate, setSelectedDate] = useState<Date | null>(null);
  const [appointments, setAppointments] = useState<Appointment[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  // Month bookings failed to load (backend down/flapping): stale days must
  // say so instead of silently showing an empty month.
  const [monthError, setMonthError] = useState('');
  // Slot cancel asks for a reason (no silent one-click cancels).
  const [cancelTarget, setCancelTarget] = useState<{
    id: number;
    label: string;
    notes?: string | null;
  } | null>(null);
  const [cancelReason, setCancelReason] = useState('');
  const [bookingClients, setBookingClients] = useState<Client[]>([]);
  const [bookingServices, setBookingServices] = useState<Service[]>([]);
  const [bookingBundles, setBookingBundles] = useState<Bundle[]>([]);
  // The modal dropdowns filter locally — they need the FULL lists, not the
  // first API page (clients past #20 were unfindable). Loaded flag gates the
  // "no services" hint so it never flashes on a not-yet-loaded list.
  const [bookingListsLoaded, setBookingListsLoaded] = useState(false);
  const [bookingLoading, setBookingLoading] = useState(false);
  const [bookingForm, setBookingForm] = useState<BookingFormState>({
    open: false,
    date: null,
    hour: null,
    clientId: null,
    serviceId: null,
    bundleId: null,
    status: 'pending',
    notes: '',
  });
  const [activeHours, setActiveHours] = useState<Record<string, boolean>>({});
  const [monthlyStats, setMonthlyStats] = useState<MonthlyStats | null>(null);
  const [selectedMasterId, setSelectedMasterId] = usePersistentState<number | ''>(
    'schedule.master',
    '',
  );
  // Daily work window (whole hours): drives how many granules render.
  // Applying a template resets it to the template's hours; the per-day ±
  // controls grow it when an earlier/later granule is added by click.
  // Master sees own window; superadmin sees the selected master's.
  const [windowStart, setWindowStart] = useState(8);
  const [windowEnd, setWindowEnd] = useState(22);
  // Granule size: 60 = whole hours (default), 30 = half-hour, 15 = quarter-hour.
  const [slotMinutes, setSlotMinutes] = usePersistentState<60 | 30 | 15>(
    'schedule.slotMinutes',
    60,
  );
  // Per-day overrides: the month mode above is the default, but a single day
  // can switch to its own grid. Its stored range/active keys live on that
  // day's grid, so both modes must be rescaled together.
  const [daySlotMinutes, setDaySlotMinutes] = usePersistentState<Record<string, 60 | 30 | 15>>(
    'schedule.daySlotMinutes',
    {},
  );
  const daySlotMinutesRef = useRef(daySlotMinutes);
  daySlotMinutesRef.current = daySlotMinutes;
  // Remember the previous granule size so that stored day ranges (slot
  // indices) can be remapped to the new grid when the user switches modes.
  const prevSlotMinutesRef = useRef(slotMinutes);
  // Async loaders must build the grid with the latest mode, even when they
  // were started before the user touched the toggle.
  const slotMinutesRef = useRef(slotMinutes);
  slotMinutesRef.current = slotMinutes;

  const modeForDate = useCallback(
    (dateStr: string) => normalizeSlotMinutes(daySlotMinutes[dateStr], slotMinutes),
    [daySlotMinutes, slotMinutes],
  );
  const selectedDateStr = selectedDate ? formatDate(selectedDate) : null;
  const selectedDayMinutes = selectedDateStr ? modeForDate(selectedDateStr) : slotMinutes;

  // Split/merge existing granules when the month mode changes. Days with
  // their own mode are left untouched (their grid did not change). The layout
  // effect runs before paint, so the old grid is never shown with new labels.
  useLayoutEffect(() => {
    const prev = prevSlotMinutesRef.current;
    if (prev === slotMinutes) return;
    prevSlotMinutesRef.current = slotMinutes;
    const overrides = daySlotMinutesRef.current;
    setSchedule((current) => {
      const rescaledInput: Record<string, DaySchedule> = {};
      const kept: Record<string, DaySchedule> = {};
      for (const [date, range] of Object.entries(current)) {
        if (overrides[date]) kept[date] = range;
        else rescaledInput[date] = range;
      }
      return { ...rescaleSchedule(rescaledInput, prev, slotMinutes), ...kept };
    });
    setActiveHours((current) => {
      const rescaledInput: Record<string, boolean> = {};
      const kept: Record<string, boolean> = {};
      for (const [key, active] of Object.entries(current)) {
        if (!active) continue;
        const date = key.slice(0, key.lastIndexOf('-'));
        if (overrides[date]) kept[key] = true;
        else rescaledInput[key] = true;
      }
      return { ...rescaleActiveHours(rescaledInput, prev, slotMinutes), ...kept };
    });
    // An override equal to the new month mode is now redundant; dropping it
    // keeps future month switches applying to this day as expected.
    setDaySlotMinutes((current) => {
      let changed = false;
      const next = { ...current };
      for (const [date, mode] of Object.entries(current)) {
        if (mode === slotMinutes) {
          delete next[date];
          changed = true;
        }
      }
      return changed ? next : current;
    });
  }, [slotMinutes, setDaySlotMinutes]);
  // The base repeating template. It is a builder, not saved schedule data;
  // server rows are written only by the explicit "Применить" action.
  const [pattern, setPattern] = usePersistentState<SchedulePattern>(
    'schedule.pattern',
    createDefaultPattern(),
  );
  const [applyingPattern, setApplyingPattern] = useState(false);
  // Regular masters see only their own schedule; superadmin must pick one
  // (they have no profile of their own — empty view means "not chosen",
  // not "everyone is off").
  const [isSuperAdmin] = useState(
    () => decodeJwtPayload(getCookie('access_token') ?? '')?.is_admin === true,
  );

  // Preview is scoped to the viewed month and clipped to today, matching the
  // backend's "past days are never touched" rule.
  const patternPreview = useMemo(
    () => buildPatternPreview(new Date(`${currentMonthISO}-01T00:00:00`), pattern),
    [currentMonthISO, pattern],
  );

  useEffect(() => {
    let cancelled = false;
    async function init() {
      try {
        const masterParam = selectedMasterId !== '' ? selectedMasterId : undefined;
        const { from, to } = monthRangeISO(currentMonth);
        const [scheduleResp, apptsResp, statsResp, windowResp] = await Promise.all([
          adminApi.getWorkingHours(masterParam),
          adminApi.getAppointmentsByDate(from, to, masterParam),
          adminApi.getMonthlyStats(
            currentMonth.getFullYear(),
            currentMonth.getMonth() + 1,
            masterParam,
          ),
          // No window without a master (superadmin must pick one first)
          isSuperAdmin && selectedMasterId === ''
            ? Promise.resolve(null)
            : adminApi
                .getWorkWindow(masterParam)
                .then((r) => r.data)
                .catch(() => null),
        ]);
        if (cancelled) return;

        const built = buildScheduleState(
          scheduleResp.data,
          slotMinutesRef.current,
          daySlotMinutesRef.current,
        );
        setSchedule(built.schedule);
        setActiveHours(built.activeHours);
        setAppointments(apptsResp.data || []);
        setMonthlyStats(statsResp.data || null);
        // Exactly the saved window: granules must match the applied schedule.
        // A selected day with older saved hours still renders its own range.
        setWindowStart(windowResp?.start_hour ?? 8);
        setWindowEnd(windowResp?.end_hour ?? 22);
      } catch (err: any) {
        console.error('[SchedulePage] Init error:', err);
        if (!cancelled) {
          setMonthError(
            getApiErrorStatus(err) === undefined
              ? 'Нет связи с сервером — записи месяца не загружены'
              : getApiErrorMessage(err, 'Не удалось загрузить записи месяца'),
          );
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    init();
    return () => {
      cancelled = true;
    };
    // NOTE: currentMonth is a fresh Date every render — depend on the stable
    // ISO string, otherwise the fetch loops forever and trips rate limits.
  }, [currentMonthISO, selectedMasterId]);

  useEffect(() => {
    if (!bookingForm.open) return;
    let cancelled = false;
    setBookingListsLoaded(false);
    // Independent fetches: one failing must not blank the other two.
    Promise.allSettled([
      adminApi.getClients({ page: 1, page_size: 500 }),
      adminApi.getAllServices({
        page: 1,
        page_size: 200,
        ...(selectedMasterId !== '' ? { master_id: selectedMasterId } : {}),
      }),
      adminApi.getBundles(selectedMasterId !== '' ? selectedMasterId : undefined),
    ]).then((results) => {
      if (cancelled) return;
      const [clientsRes, servicesRes, bundlesRes] = results;
      setBookingClients(
        clientsRes.status === 'fulfilled' ? clientsRes.value.data?.items || [] : [],
      );
      setBookingServices(
        servicesRes.status === 'fulfilled' ? servicesRes.value.data?.items || [] : [],
      );
      setBookingBundles(bundlesRes.status === 'fulfilled' ? bundlesRes.value.data || [] : []);
      setBookingListsLoaded(true);
    });
    return () => {
      cancelled = true;
    };
  }, [bookingForm.open, selectedMasterId]);

  const handlePrevMonth = useCallback(() => {
    setCurrentMonth((d) => new Date(d.getFullYear(), d.getMonth() - 1, 1));
  }, []);

  const handleNextMonth = useCallback(() => {
    setCurrentMonth((d) => new Date(d.getFullYear(), d.getMonth() + 1, 1));
  }, []);

  const handleSelectDate = useCallback((date: Date) => {
    setSelectedDate(date);
  }, []);

  const handleToggleDay = useCallback(
    async (date: Date) => {
      if (isSuperAdmin && selectedMasterId === '') {
        setError('Выберите мастера, чтобы менять расписание');
        return;
      }
      const dateMode = modeForDate(formatDate(date));
      const result = await toggleDayWork(
        date,
        schedule,
        activeHours,
        appointments,
        setError,
        selectedMasterId,
        hourToSlot(windowStart, dateMode),
        hourToSlot(windowEnd, dateMode),
        dateMode,
      );
      if (result) {
        setSchedule(result.newSchedule);
        setActiveHours(result.newActiveHours);
      }
    },
    [
      schedule,
      activeHours,
      appointments,
      selectedMasterId,
      isSuperAdmin,
      windowStart,
      windowEnd,
      modeForDate,
    ],
  );

  // Toggling a slot persists to the server AND drives the day state:
  // turning any slot ON activates the whole day (it turns green),
  // turning the last slot OFF deactivates the day.
  const handleToggleHour = useCallback(
    async (dateStr: string, slot: number) => {
      const key = `${dateStr}-${slot}`;
      const turningOn = !activeHours[key];
      if (isSuperAdmin && selectedMasterId === '') {
        setError('Выберите мастера, чтобы менять расписание');
        return;
      }
      const masterParam = selectedMasterId !== '' ? selectedMasterId : undefined;
      const dateMode = modeForDate(dateStr);

      if (turningOn) {
        setActiveHours((prev) => ({ ...prev, [key]: true }));
        try {
          const resp = await adminApi.getWorkingHours(masterParam);
          const existing = resp.data.find((h: WorkingHour) => h.schedule_date === dateStr);
          if (existing) {
            const current = parseHourRangeToSlots(existing.start_time, existing.end_time, dateMode);
            const start = Math.min(current.startSlot, slot);
            const end = Math.max(current.endSlot, slot + 1);
            await adminApi.updateWorkingHour(existing.id, {
              schedule_date: dateStr,
              start_time: formatSlotTime(start, dateMode),
              end_time: formatSlotTime(end, dateMode),
            });
            setSchedule((prev) => ({ ...prev, [dateStr]: { start, end } }));
          } else {
            await adminApi.createWorkingHour({
              master_id: masterParam,
              schedule_date: dateStr,
              start_time: formatSlotTime(slot, dateMode),
              end_time: formatSlotTime(slot + 1, dateMode),
            });
            setSchedule((prev) => ({ ...prev, [dateStr]: { start: slot, end: slot + 1 } }));
          }
        } catch (err: unknown) {
          setActiveHours((prev) => ({ ...prev, [key]: false }));
          setError(getApiErrorMessage(err, 'Не удалось включить гранулу'));
        }
        return;
      }

      // Turning OFF
      // A slot with a live booking cannot be unchecked: cancel the
      // booking first (mirrors the day toggle, which refuses days with rows).
      // Span continuations count too: a 90-мин service blocks multiple slots.
      const [y, m, d] = dateStr.split('-').map(Number);
      const liveHere = getBlockingLive(appointments, new Date(y, m - 1, d), slot, dateMode);
      if (liveHere.length > 0) {
        const who = liveHere.map((a) => a.client_name || 'клиент').join(', ');
        setError(`Нельзя снять гранулу — в ней бронь (${who}). Сначала отмените запись.`);
        return;
      }
      const remaining = Object.keys(activeHours)
        .filter((k) => k.startsWith(`${dateStr}-`) && k !== key && activeHours[k])
        .map((k) => Number(k.split('-').pop()));
      setActiveHours((prev) => ({ ...prev, [key]: false }));
      try {
        const resp = await adminApi.getWorkingHours(masterParam);
        const existing = resp.data.find((h: WorkingHour) => h.schedule_date === dateStr);
        if (!existing) {
          if (remaining.length === 0) {
            setSchedule((prev) => {
              const next = { ...prev };
              delete next[dateStr];
              return next;
            });
          }
          return;
        }
        if (remaining.length === 0) {
          await adminApi.deleteWorkingHour(existing.id);
          setSchedule((prev) => {
            const next = { ...prev };
            delete next[dateStr];
            return next;
          });
        } else {
          // Backend stores one range per day: shrink to the remaining edges
          // (a hole in the middle stays visually off but covered by the range)
          const start = Math.min(...remaining);
          const end = Math.max(...remaining) + 1;
          await adminApi.updateWorkingHour(existing.id, {
            schedule_date: dateStr,
            start_time: formatSlotTime(start, dateMode),
            end_time: formatSlotTime(end, dateMode),
          });
          setSchedule((prev) => ({ ...prev, [dateStr]: { start, end } }));
        }
      } catch (err: unknown) {
        setActiveHours((prev) => ({ ...prev, [key]: true }));
        setError(getApiErrorMessage(err, 'Не удалось выключить гранулу'));
      }
    },
    [activeHours, appointments, selectedMasterId, isSuperAdmin, modeForDate],
  );

  const handleOpenBooking = useCallback((date: Date, hour: number) => {
    openBookingForm(date, hour, setBookingForm);
  }, []);

  const handleBookingUpdate = useCallback((field: string, value: any) => {
    setBookingForm((prev) => ({ ...prev, [field]: value }));
  }, []);

  const handleCloseBooking = useCallback(() => {
    closeBookingForm(setBookingForm, setBookingClients);
  }, []);

  const refreshMonthAppointments = useCallback(async () => {
    const { from, to } = monthRangeISO(currentMonth);
    try {
      const resp = await adminApi.getAppointmentsByDate(
        from,
        to,
        selectedMasterId !== '' ? selectedMasterId : undefined,
      );
      setAppointments(resp.data || []);
      setMonthError('');
    } catch (err: unknown) {
      setMonthError(
        getApiErrorStatus(err) === undefined
          ? 'Нет связи с сервером — записи месяца не загружены'
          : getApiErrorMessage(err, 'Не удалось загрузить записи месяца'),
      );
    }
  }, [currentMonthISO, selectedMasterId]);

  const handleBook = useCallback(async () => {
    const bookingDateStr = bookingForm.date ? formatDate(bookingForm.date) : null;
    const bookingMode = bookingDateStr ? modeForDate(bookingDateStr) : slotMinutes;
    const success = await handleBookAppointment(
      bookingForm,
      setBookingLoading,
      setError,
      adminApi,
      handleCloseBooking,
      selectedMasterId,
      bookingMode,
    );
    if (success) {
      await refreshMonthAppointments();
    }
  }, [
    bookingForm,
    currentMonthISO,
    handleCloseBooking,
    selectedMasterId,
    refreshMonthAppointments,
    modeForDate,
    slotMinutes,
  ]);

  const handleCancelSlotAppointment = useCallback(
    async (id: number) => {
      // Never one-click: master must confirm + give a reason (the client
      // gets it in the bell), and sees the client's comment for context.
      const found = appointments.find((a) => a.id === id) || null;
      setCancelTarget(
        found
          ? { id, label: labelOf(found), notes: found.notes }
          : { id, label: '', notes: undefined },
      );
      setCancelReason('');
    },
    [appointments],
  );

  const handleConfirmSlotCancel = useCallback(async () => {
    if (!cancelTarget || !cancelReason.trim()) return;
    try {
      await adminApi.cancelAppointment(cancelTarget.id, cancelReason.trim());
      toast.success('Запись отменена');
      setCancelTarget(null);
      setCancelReason('');
      await refreshMonthAppointments();
    } catch (err: unknown) {
      setError(getApiErrorMessage(err, 'Не удалось отменить запись'));
    }
  }, [cancelTarget, cancelReason, refreshMonthAppointments]);

  const handleConfirmSlotAppointment = useCallback(
    async (id: number) => {
      try {
        await adminApi.confirmAppointment(id);
        toast.success('Запись подтверждена');
        await refreshMonthAppointments();
      } catch (err: unknown) {
        setError(getApiErrorMessage(err, 'Не удалось подтвердить запись'));
      }
    },
    [refreshMonthAppointments],
  );

  const handlePatternChange = useCallback(
    (patch: Partial<SchedulePattern>) => {
      setPattern((prev) => ({ ...prev, ...patch }));
    },
    [setPattern],
  );

  // Presets are a starting point only; choosing one also puts the phase on
  // today (or on the first day of a future month), so the preview is
  // immediately meaningful. 5/2 additionally snaps to Monday.
  const handlePatternPreset = useCallback(
    (workDays: number, offDays: number) => {
      const monthStart = new Date(`${currentMonthISO}-01T00:00:00`);
      const now = new Date();
      const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
      const base = monthStart > today ? monthStart : today;
      const anchor = workDays === 5 && offDays === 2 ? mondayOnOrBefore(base) : base;
      setPattern((prev) => ({
        ...prev,
        workDays,
        offDays,
        anchor: formatDate(anchor),
      }));
    },
    [currentMonthISO, setPattern],
  );

  // One atomic request instead of a per-day loop: the backend decides which
  // days are past or protected by live bookings and reports the counts.
  const handleApplyPattern = useCallback(async () => {
    if (isSuperAdmin && selectedMasterId === '') {
      setError('Выберите мастера, чтобы применять график');
      return;
    }
    if (!patternPreview.canApply) return;

    const base = new Date(`${currentMonthISO}-01T00:00:00`);
    const { from, to } = monthRangeISO(base);
    const masterParam = selectedMasterId !== '' ? selectedMasterId : undefined;
    setError('');
    setApplyingPattern(true);
    try {
      const { data } = await adminApi.applySchedule({
        ...(masterParam ? { master_id: masterParam } : {}),
        range_start: from,
        range_end: to,
        cycle_work_days: pattern.workDays,
        cycle_off_days: pattern.offDays,
        cycle_anchor: pattern.anchor,
        start_time: formatSlotTime(
          hourToSlot(pattern.startHour, slotMinutesRef.current),
          slotMinutesRef.current,
        ),
        end_time: formatSlotTime(
          hourToSlot(pattern.endHour, slotMinutesRef.current),
          slotMinutesRef.current,
        ),
        replace_off_days: true,
      });

      const scheduleResp = await adminApi.getWorkingHours(masterParam);
      const built = buildScheduleState(
        scheduleResp.data,
        slotMinutesRef.current,
        daySlotMinutesRef.current,
      );
      setWindowStart(data.window_start_hour);
      setWindowEnd(data.window_end_hour);
      setSchedule(built.schedule);
      setActiveHours(built.activeHours);
      await refreshMonthAppointments();

      const skipped =
        data.skipped_booked > 0 ? ` Дней с записями сохранено: ${data.skipped_booked}.` : '';
      toast.success(
        `График применён: ${data.work_days} раб. / ${data.off_days} вых. ` +
          `Создано ${data.created}, обновлено ${data.updated}, удалено ${data.removed}.${skipped}`,
      );
    } catch (err: unknown) {
      setError(getApiErrorMessage(err, 'Не удалось применить график'));
    } finally {
      setApplyingPattern(false);
    }
  }, [
    currentMonthISO,
    isSuperAdmin,
    pattern,
    patternPreview,
    refreshMonthAppointments,
    selectedMasterId,
  ]);

  // Wipe every working hour in the viewed month except days holding live
  // appointments.
  const handleResetMonth = useCallback(async () => {
    if (isSuperAdmin && selectedMasterId === '') {
      setError('Выберите мастера, чтобы сбрасывать расписание');
      return;
    }
    const base = new Date(`${currentMonthISO}-01T00:00:00`);
    const { from, to } = monthRangeISO(base);
    const masterParam = selectedMasterId !== '' ? selectedMasterId : undefined;
    setApplyingPattern(true);
    setError('');
    try {
      const { data } = await adminApi.resetMonth({
        ...(masterParam ? { master_id: masterParam } : {}),
        range_start: from,
        range_end: to,
      });
      const scheduleResp = await adminApi.getWorkingHours(masterParam);
      const built = buildScheduleState(
        scheduleResp.data,
        slotMinutesRef.current,
        daySlotMinutesRef.current,
      );
      setSchedule(built.schedule);
      setActiveHours(built.activeHours);
      const skipped =
        data.skipped_booked > 0 ? ` Дней с записями сохранено: ${data.skipped_booked}.` : '';
      toast.success(`График месяца сброшен: удалено ${data.removed} дн.${skipped}`);
    } catch (err: unknown) {
      setError(getApiErrorMessage(err, 'Не удалось сбросить график месяца'));
    } finally {
      setApplyingPattern(false);
    }
  }, [currentMonthISO, isSuperAdmin, selectedMasterId]);

  // ± on a selected working day. Expanding the range may grow the global
  // window; shrinking below a live booking is refused (the backend performs
  // the same protection for bulk apply). `start`/`end` are slot indices.
  const handleChangeDayHours = useCallback(
    async (dateStr: string, startSlot: number, endSlot: number) => {
      if (isSuperAdmin && selectedMasterId === '') {
        setError('Выберите мастера, чтобы менять расписание');
        return;
      }
      const dateMode = modeForDate(dateStr);
      const maxSlot = Math.ceil((24 * 60) / dateMode);
      if (
        !Number.isInteger(startSlot) ||
        !Number.isInteger(endSlot) ||
        startSlot < 0 ||
        endSlot > maxSlot ||
        startSlot >= endSlot
      ) {
        setError('Начало рабочего дня должно быть раньше конца');
        return;
      }

      const [y, m, d] = dateStr.split('-').map(Number);
      const dayDate = new Date(y, m - 1, d);
      const live = appointments.filter(
        (a) => a.status !== 'cancelled' && String(a.appointment_date).slice(0, 10) === dateStr,
      );
      if (live.length > 0) {
        const starts = live.map((a) =>
          hourToSlot(new Date(a.appointment_date).getHours(), dateMode),
        );
        const ends = live.map((a) => {
          const h = new Date(a.appointment_date).getHours();
          const min = new Date(a.appointment_date).getMinutes();
          const startSlotAppt = hourToSlot(h, dateMode) + Math.round(min / dateMode);
          return startSlotAppt + appointmentSpanSlots(a, dateMode);
        });
        const earliest = Math.min(...starts);
        const latest = Math.max(...ends);
        if (startSlot > earliest || endSlot < latest) {
          setError(
            `Нельзя сократить день — в нём есть записи (${dayDate.toLocaleDateString('ru-RU')}). ` +
              'Сначала перенесите или отмените их.',
          );
          return;
        }
      }

      const masterParam = selectedMasterId !== '' ? selectedMasterId : undefined;
      setError('');
      try {
        // Work window is stored as whole hours on the backend; round the
        // applied slot range out to full hours so new granules stay visible.
        const nextWindowStart = Math.min(windowStart, Math.floor((startSlot * dateMode) / 60));
        const nextWindowEnd = Math.max(windowEnd, Math.ceil((endSlot * dateMode) / 60));
        if (nextWindowStart !== windowStart || nextWindowEnd !== windowEnd) {
          const { data } = await adminApi.updateWorkWindow({
            ...(masterParam ? { master_id: masterParam } : {}),
            start_hour: nextWindowStart,
            end_hour: nextWindowEnd,
          });
          setWindowStart(data.start_hour);
          setWindowEnd(data.end_hour);
        }

        const resp = await adminApi.getWorkingHours(masterParam);
        const existing = resp.data.find((h: WorkingHour) => h.schedule_date === dateStr);
        if (existing) {
          await adminApi.updateWorkingHour(existing.id, {
            schedule_date: dateStr,
            start_time: formatSlotTime(startSlot, dateMode),
            end_time: formatSlotTime(endSlot, dateMode),
          });
        } else {
          await adminApi.createWorkingHour({
            master_id: masterParam,
            schedule_date: dateStr,
            start_time: formatSlotTime(startSlot, dateMode),
            end_time: formatSlotTime(endSlot, dateMode),
          });
        }

        setSchedule((prev) => ({ ...prev, [dateStr]: { start: startSlot, end: endSlot } }));
        setActiveHours((prev) => {
          const next = { ...prev };
          for (const k of Object.keys(next)) {
            if (k.startsWith(`${dateStr}-`)) delete next[k];
          }
          for (let s = startSlot; s < endSlot; s++) next[`${dateStr}-${s}`] = true;
          return next;
        });
      } catch (err: unknown) {
        setError(getApiErrorMessage(err, 'Не удалось изменить гранулы дня'));
      }
    },
    [appointments, isSuperAdmin, selectedMasterId, windowEnd, windowStart, modeForDate],
  );

  // Per-day mode switch: rescale ONLY this day's range and enabled granules.
  // The month toggle and every other day stay untouched.
  const handleDaySlotMinutesChange = useCallback(
    (dateStr: string, nextMode: SlotMinutes) => {
      const currentGlobal = slotMinutesRef.current;
      const prevMode = normalizeSlotMinutes(daySlotMinutesRef.current[dateStr], currentGlobal);
      if (prevMode === nextMode) return;

      setSchedule((current) => {
        const range = current[dateStr];
        if (!range) return current;
        return {
          ...current,
          [dateStr]: rescaleSlotRange(range, prevMode, nextMode),
        };
      });
      setActiveHours((current) => rescaleDayActiveHours(current, dateStr, prevMode, nextMode));
      setDaySlotMinutes((current) => {
        const next = { ...current };
        if (nextMode === slotMinutesRef.current) delete next[dateStr];
        else next[dateStr] = nextMode;
        return next;
      });
    },
    [setDaySlotMinutes],
  );

  if (loading)
    return <div style={{ padding: 60, textAlign: 'center', color: '#666' }}>Загрузка...</div>;

  return (
    <div className="schedule-page">
      <div style={{ marginBottom: 8, textAlign: 'center' }}>
        <h1 style={{ fontSize: 24, margin: 0, color: '#1a1a2e' }}>📅 Рабочее расписание</h1>
        <p style={{ margin: '4px 0 0', color: '#666', fontSize: 14 }}>
          Нажмите на день чтобы увидеть бронирования
        </p>
        {!isSuperAdmin && (
          <div
            style={{
              marginTop: 8,
              display: 'flex',
              justifyContent: 'center',
              gap: 8,
              flexWrap: 'wrap',
            }}
          >
            <AutoConfirmSwitch />
            <AutoCompleteSwitch />
          </div>
        )}
      </div>

      {/* Master filter (superadmin only) */}
      {isSuperAdmin && (
        <div
          style={{
            marginBottom: 16,
            display: 'flex',
            justifyContent: 'center',
            gap: 12,
            alignItems: 'center',
          }}
        >
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
          <p style={{ margin: 0, color: '#666' }}>
            👆 Выберите мастера, чтобы увидеть его расписание. Добавлять дни себе нельзя — только
            мастерам.
          </p>
        </div>
      )}

      {/* No calendar without a master: nothing to display yet */}
      {!(isSuperAdmin && selectedMasterId === '') && (
        <>
          <SchedulePatternPanel
            monthLabel={`${currentMonth.toLocaleString('ru-RU', { month: 'long' })} ${currentMonth.getFullYear()}`}
            value={pattern}
            preview={patternPreview}
            applying={applyingPattern}
            onChange={handlePatternChange}
            onPreset={handlePatternPreset}
            onApply={handleApplyPattern}
            slotMinutes={slotMinutes}
            onSlotMinutesChange={setSlotMinutes}
            onResetMonth={handleResetMonth}
          />
          {/* Legend */}
          <div
            style={{
              display: 'flex',
              gap: 16,
              flexWrap: 'wrap',
              marginBottom: 20,
              padding: 14,
              background: '#f9f9f9',
              borderRadius: 10,
              justifyContent: 'center',
            }}
          >
            {[
              { color: '#4caf50', bg: '#e8f5e9', label: 'Рабочий день' },
              { color: '#e0e0e0', bg: '#f5f5f5', label: 'Выходной' },
              { color: '#667eea', bg: '#e8eaf6', label: 'Сегодня' },
              { color: '#9e9e9e', bg: '#f5f5f5', label: 'Прошедший' },
            ].map((item) => (
              <div
                key={item.label}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  fontSize: 13,
                  color: '#333',
                }}
              >
                <span
                  style={{
                    width: 16,
                    height: 16,
                    borderRadius: 4,
                    background: item.color,
                    display: 'inline-block',
                  }}
                />
                <span>{item.label}</span>
              </div>
            ))}
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                fontSize: 13,
                color: '#333',
              }}
            >
              <span
                style={{
                  width: 16,
                  height: 16,
                  borderRadius: 4,
                  border: '2px dashed #4caf50',
                  display: 'inline-block',
                }}
              />
              <span>Пунктир — после применения</span>
            </div>
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
            selectablePast
            slotMinutes={slotMinutes}
            slotMinutesByDate={daySlotMinutes}
            previewWorkDates={patternPreview.workDates}
            previewOffDates={patternPreview.offDates}
          />

          {monthError && (
            <div className="schedule-load-error" role="alert">
              <span>⚠️ {monthError}</span>
              <button
                type="button"
                className="btn btn-sm btn-secondary"
                onClick={refreshMonthAppointments}
              >
                Повторить
              </button>
            </div>
          )}

          {selectedDate && (
            <TimeSlots
              selectedDate={selectedDate}
              appointments={appointments}
              activeHours={activeHours}
              onToggleHour={handleToggleHour}
              onOpenBooking={handleOpenBooking}
              onCancelAppointment={handleCancelSlotAppointment}
              onConfirmAppointment={handleConfirmSlotAppointment}
              slotMinutes={selectedDayMinutes}
              windowStartSlot={hourToSlot(windowStart, selectedDayMinutes)}
              windowEndSlot={hourToSlot(windowEnd, selectedDayMinutes)}
              dayStartSlot={schedule[formatDate(selectedDate)]?.start}
              dayEndSlot={schedule[formatDate(selectedDate)]?.end}
              onChangeDaySlots={handleChangeDayHours}
              onSlotMinutesChange={(mode) =>
                selectedDateStr && handleDaySlotMinutesChange(selectedDateStr, mode)
              }
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

      {/* Slot cancel: confirm + mandatory reason, client comment visible */}
      <ConfirmDialog
        open={cancelTarget !== null}
        onClose={() => setCancelTarget(null)}
        title="❌ Отменить запись?"
        message={cancelTarget?.label}
        confirmLabel="Отменить запись"
        danger
        confirmDisabled={!cancelReason.trim()}
        onConfirm={handleConfirmSlotCancel}
      >
        {cancelTarget?.notes ? (
          <p className="modal-message">💬 Комментарий клиента: {cancelTarget.notes}</p>
        ) : null}
        <div className="form-group">
          <label>Причина отмены (клиент увидит её в уведомлении)</label>
          <textarea
            value={cancelReason}
            onChange={(e) => setCancelReason(e.target.value)}
            placeholder="Укажите причину..."
            rows={3}
            style={{
              width: '100%',
              padding: 10,
              border: '2px solid #e0e0e0',
              borderRadius: 8,
              fontSize: 14,
              resize: 'vertical',
            }}
          />
        </div>
      </ConfirmDialog>

      <BookingModal
        open={bookingForm.open}
        date={bookingForm.date}
        hour={bookingForm.hour}
        clientId={bookingForm.clientId}
        serviceId={bookingForm.serviceId}
        bundleId={bookingForm.bundleId}
        status={bookingForm.status}
        notes={bookingForm.notes}
        clients={bookingClients}
        services={bookingServices}
        bundles={bookingBundles}
        listsLoaded={bookingListsLoaded}
        bookingLoading={bookingLoading}
        slotMinutes={selectedDayMinutes}
        onClose={handleCloseBooking}
        onUpdate={handleBookingUpdate}
        onBook={handleBook}
        servicesMasterId={selectedMasterId}
      />
    </div>
  );
}

export default SchedulePage;
