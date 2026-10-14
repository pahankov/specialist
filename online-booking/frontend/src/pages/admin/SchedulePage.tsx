import { useEffect, useState, useCallback } from 'react';
import { toast } from 'sonner';
import { adminApi } from '../../api/client';
import type {
  Appointment,
  Client,
  Service,
  DaySchedule,
  MonthlyStats,
  BookingFormState,
} from '../../api/types';
import type { Bundle } from '../../api/cabinet';
import { Calendar } from '../../components/schedule/Calendar';
import { TimeSlots } from '../../components/schedule/TimeSlots';
import { BookingModal } from '../../components/schedule/BookingModal';
import { ConfirmDialog, MasterSelect } from '../../components/common';
import { getApiErrorMessage, getApiErrorStatus } from '../../utils/apiError';
import { getCookie, decodeJwtPayload } from '../../utils/cookies';
import { MonthlyStatsComponent } from '../../components/schedule/MonthlyStats';
import { getBlockingLive, monthRangeISO } from '../../components/schedule/helpers';
import { usePersistentState } from '../../utils/persistentState';
import {
  toggleDayWork,
  openBookingForm,
  closeBookingForm,
  handleBookAppointment,
} from '../../components/schedule/hooks';

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
    new Date().toISOString().slice(0, 7),
  );
  const currentMonth = new Date(`${currentMonthISO}-01T00:00:00`);
  const setCurrentMonth = (d: Date | ((p: Date) => Date)) => {
    setCurrentMonthISO(
      typeof d === 'function'
        ? d(currentMonth).toISOString().slice(0, 7)
        : d.toISOString().slice(0, 7),
    );
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
  // Daily work window (whole hours): drives how many granules render
  // AND the default hours for newly added working days.
  // Master sees own window; superadmin sees the selected master's.
  const [windowStart, setWindowStart] = useState(8);
  const [windowEnd, setWindowEnd] = useState(22);
  const [windowDraft, setWindowDraft] = useState({ start: '8', end: '22' });
  const [windowSaving, setWindowSaving] = useState(false);
  // Explicit opt-in per save (NOT persisted): bulk-applying silently on the
  // next save just because it was checked once is exactly the reported bug.
  const [applyToAllDays, setApplyToAllDays] = useState(false);
  // Regular masters see only their own schedule; superadmin must pick one
  // (they have no profile of their own — empty view means "not chosen",
  // not "everyone is off").
  const [isSuperAdmin] = useState(
    () => decodeJwtPayload(getCookie('access_token') ?? '')?.is_admin === true,
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

        const newSchedule: Record<string, DaySchedule> = {};
        const newActiveHours: Record<string, boolean> = {};
        for (const wh of scheduleResp.data) {
          const sh = wh.start_time.split(':').map(Number);
          const eh = wh.end_time.split(':').map(Number);
          newSchedule[wh.schedule_date] = { start: sh[0], end: eh[0] };
          for (let h = sh[0]; h < eh[0]; h++) {
            newActiveHours[`${wh.schedule_date}-${h}`] = true;
          }
        }
        setSchedule(newSchedule);
        setActiveHours(newActiveHours);
        setAppointments(apptsResp.data || []);
        setMonthlyStats(statsResp.data || null);
        if (windowResp) {
          setWindowStart(windowResp.start_hour);
          setWindowEnd(windowResp.end_hour);
          setWindowDraft({
            start: String(windowResp.start_hour),
            end: String(windowResp.end_hour),
          });
        }
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
    Promise.all([
      adminApi.getClients(),
      adminApi.getAllServices(
        selectedMasterId !== '' ? { master_id: selectedMasterId } : undefined,
      ),
      adminApi.getBundles(selectedMasterId !== '' ? selectedMasterId : undefined),
    ])
      .then(([clientsResp, servicesResp, bundlesResp]) => {
        if (cancelled) return;
        setBookingClients(clientsResp.data?.items || []);
        setBookingServices(servicesResp.data?.items || []);
        setBookingBundles(bundlesResp.data || []);
      })
      .catch(() => {
        if (!cancelled) {
          setBookingClients([]);
          setBookingServices([]);
          setBookingBundles([]);
        }
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
      const result = await toggleDayWork(
        date,
        schedule,
        activeHours,
        appointments,
        setError,
        selectedMasterId,
        windowStart,
        windowEnd,
      );
      if (result) {
        setSchedule(result.newSchedule);
        setActiveHours(result.newActiveHours);
      }
    },
    [schedule, activeHours, appointments, selectedMasterId, isSuperAdmin, windowStart, windowEnd],
  );

  // Toggling an hour persists to the server AND drives the day state:
  // turning any hour ON activates the whole day (it turns green),
  // turning the last hour OFF deactivates the day.
  const handleToggleHour = useCallback(
    async (dateStr: string, hour: number) => {
      const key = `${dateStr}-${hour}`;
      const turningOn = !activeHours[key];
      if (isSuperAdmin && selectedMasterId === '') {
        setError('Выберите мастера, чтобы менять расписание');
        return;
      }
      const masterParam = selectedMasterId !== '' ? selectedMasterId : undefined;
      const pad = (h: number) => `${String(h).padStart(2, '0')}:00`;

      if (turningOn) {
        setActiveHours((prev) => ({ ...prev, [key]: true }));
        try {
          const resp = await adminApi.getWorkingHours(masterParam);
          const existing = resp.data.find((h: any) => h.schedule_date === dateStr);
          if (existing) {
            const curStart = Number(String(existing.start_time).split(':')[0]);
            const curEnd = Number(String(existing.end_time).split(':')[0]);
            const start = Math.min(curStart, hour);
            const end = Math.max(curEnd, hour + 1);
            await adminApi.updateWorkingHour(existing.id, {
              schedule_date: dateStr,
              start_time: pad(start),
              end_time: pad(end),
            });
            setSchedule((prev) => ({ ...prev, [dateStr]: { start, end } }));
          } else {
            await adminApi.createWorkingHour({
              master_id: masterParam,
              schedule_date: dateStr,
              start_time: pad(hour),
              end_time: pad(hour + 1),
            });
            setSchedule((prev) => ({ ...prev, [dateStr]: { start: hour, end: hour + 1 } }));
          }
        } catch (err: unknown) {
          setActiveHours((prev) => ({ ...prev, [key]: false }));
          setError(getApiErrorMessage(err, 'Не удалось включить час'));
        }
        return;
      }

      // Turning OFF
      // A granule with a live booking cannot be unchecked: cancel the
      // booking first (mirrors the day toggle, which refuses days with rows).
      // Span continuations count too: a 90-мин service blocks two granules.
      const [y, m, d] = dateStr.split('-').map(Number);
      const liveHere = getBlockingLive(appointments, new Date(y, m - 1, d), hour);
      if (liveHere.length > 0) {
        const who = liveHere.map((a) => a.client_name || 'клиент').join(', ');
        setError(`Нельзя снять час — в нём бронь (${who}). Сначала отмените запись.`);
        return;
      }
      const remaining = Object.keys(activeHours)
        .filter((k) => k.startsWith(`${dateStr}-`) && k !== key && activeHours[k])
        .map((k) => Number(k.split('-').pop()));
      setActiveHours((prev) => ({ ...prev, [key]: false }));
      try {
        const resp = await adminApi.getWorkingHours(masterParam);
        const existing = resp.data.find((h: any) => h.schedule_date === dateStr);
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
            start_time: pad(start),
            end_time: pad(end),
          });
          setSchedule((prev) => ({ ...prev, [dateStr]: { start, end } }));
        }
      } catch (err: unknown) {
        setActiveHours((prev) => ({ ...prev, [key]: true }));
        setError(getApiErrorMessage(err, 'Не удалось выключить час'));
      }
    },
    [activeHours, appointments, selectedMasterId, isSuperAdmin],
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
    const success = await handleBookAppointment(
      bookingForm,
      setBookingLoading,
      setError,
      adminApi,
      handleCloseBooking,
      selectedMasterId,
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

  // Bulk-apply the saved window to every working day of the viewed month.
  // Days holding live bookings are skipped (shrinking hours under a booking
  // would strand it) and reported.
  const applyWindowToMonth = useCallback(
    async (start: number, end: number): Promise<{ updated: number; skipped: number }> => {
      const pad = (h: number) => `${String(h).padStart(2, '0')}:00`;
      const masterParam = selectedMasterId !== '' ? selectedMasterId : undefined;
      let rows: { id: number; schedule_date: string }[] = [];
      try {
        rows = (await adminApi.getWorkingHours(masterParam)).data.filter((h: any) =>
          String(h.schedule_date).startsWith(currentMonthISO),
        );
      } catch {
        return { updated: 0, skipped: 0 };
      }
      let updated = 0;
      let skipped = 0;
      const liveByDay = new Set(
        appointments
          .filter((a) => a.status !== 'cancelled')
          .map((a) => String(a.appointment_date).slice(0, 10)),
      );
      for (const row of rows) {
        if (liveByDay.has(row.schedule_date)) {
          skipped += 1;
          continue;
        }
        try {
          await adminApi.updateWorkingHour(row.id, {
            schedule_date: row.schedule_date,
            start_time: pad(start),
            end_time: pad(end),
          });
          updated += 1;
        } catch {
          skipped += 1;
        }
      }
      if (updated > 0) {
        setSchedule((prev) => {
          const next = { ...prev };
          for (const row of rows) {
            if (!liveByDay.has(row.schedule_date) && next[row.schedule_date]) {
              next[row.schedule_date] = { start, end };
            }
          }
          return next;
        });
        setActiveHours((prev) => {
          const next = { ...prev };
          for (const row of rows) {
            if (liveByDay.has(row.schedule_date)) continue;
            for (const k of Object.keys(next)) {
              if (k.startsWith(`${row.schedule_date}-`)) delete next[k];
            }
            for (let h = start; h < end; h++) next[`${row.schedule_date}-${h}`] = true;
          }
          return next;
        });
      }
      return { updated, skipped };
    },
    [appointments, currentMonthISO, selectedMasterId],
  );

  if (loading)
    return <div style={{ padding: 60, textAlign: 'center', color: '#666' }}>Загрузка...</div>;

  return (
    <div style={{ padding: '0 20px', maxWidth: 1200, margin: '0 auto' }}>
      <div style={{ marginBottom: 8, textAlign: 'center' }}>
        <h1 style={{ fontSize: 24, margin: 0, color: '#1a1a2e' }}>📅 Рабочее расписание</h1>
        <p style={{ margin: '4px 0 0', color: '#666', fontSize: 14 }}>
          Нажмите на день чтобы увидеть бронирования
        </p>
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
          {/* Daily work window: how many hourly granules working days offer */}
          <div className="card" style={{ marginBottom: 16, padding: 12 }}>
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: 10,
                flexWrap: 'wrap',
              }}
            >
              <span style={{ fontSize: 14, fontWeight: 600 }}>🕐 Рабочее время:</span>
              <span style={{ fontSize: 12, color: '#888' }}>
                (сохранено {windowStart}:00–{windowEnd}:00)
              </span>
              <span style={{ fontSize: 13, color: '#666' }}>с</span>
              <input
                type="number"
                min={0}
                max={23}
                value={windowDraft.start}
                onChange={(e) => setWindowDraft((d) => ({ ...d, start: e.target.value }))}
                style={{
                  width: 64,
                  padding: 6,
                  border: '2px solid #e0e0e0',
                  borderRadius: 8,
                  fontSize: 14,
                }}
                aria-label="Начало рабочего времени"
              />
              <span style={{ fontSize: 13, color: '#666' }}>до</span>
              <input
                type="number"
                min={1}
                max={24}
                value={windowDraft.end}
                onChange={(e) => setWindowDraft((d) => ({ ...d, end: e.target.value }))}
                style={{
                  width: 64,
                  padding: 6,
                  border: '2px solid #e0e0e0',
                  borderRadius: 8,
                  fontSize: 14,
                }}
                aria-label="Конец рабочего времени"
              />
              <button
                className="btn btn-sm btn-primary"
                disabled={windowSaving}
                onClick={async () => {
                  const start = Number(windowDraft.start);
                  const end = Number(windowDraft.end);
                  if (
                    !Number.isInteger(start) ||
                    !Number.isInteger(end) ||
                    start < 0 ||
                    end > 24 ||
                    start >= end
                  ) {
                    setError('Укажите часы 0–24, начало раньше конца');
                    return;
                  }
                  setWindowSaving(true);
                  const payload = {
                    ...(selectedMasterId !== '' ? { master_id: selectedMasterId } : {}),
                    start_hour: start,
                    end_hour: end,
                  };
                  const saveOnce = () => adminApi.updateWorkWindow(payload);
                  const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));
                  try {
                    let data: { start_hour: number; end_hour: number };
                    try {
                      ({ data } = await saveOnce());
                    } catch (firstErr: unknown) {
                      const status = getApiErrorStatus(firstErr);
                      if (status === undefined) {
                        // Transport-level blip (no response): one immediate retry.
                        ({ data } = await saveOnce());
                      } else if (status === 429) {
                        // Rate-limited: wait out the window, then one retry.
                        await sleep(1500);
                        ({ data } = await saveOnce());
                      } else {
                        throw firstErr;
                      }
                    }
                    setWindowStart(data.start_hour);
                    setWindowEnd(data.end_hour);
                    setWindowDraft({ start: String(data.start_hour), end: String(data.end_hour) });

                    let suffix = '';
                    if (applyToAllDays) {
                      const applied = await applyWindowToMonth(data.start_hour, data.end_hour);
                      suffix =
                        applied.updated > 0
                          ? ` Обновлено дней: ${applied.updated}` +
                            (applied.skipped > 0
                              ? ` (с бронями пропущено: ${applied.skipped})`
                              : '')
                          : applied.skipped > 0
                            ? ` Все дни с бронями — часы не тронуты (${applied.skipped})`
                            : ' Рабочих дней в месяце пока нет';
                    }
                    toast.success(
                      `Рабочее время сохранено: ${data.start_hour}:00–${data.end_hour}:00.${suffix}`,
                    );
                  } catch (err: unknown) {
                    const status = getApiErrorStatus(err);
                    setError(
                      status !== undefined
                        ? getApiErrorMessage(err, 'Не удалось сохранить рабочее время')
                        : 'Нет связи с сервером — проверьте соединение и нажмите «Сохранить» ещё раз',
                    );
                  } finally {
                    setWindowSaving(false);
                  }
                }}
              >
                Сохранить
              </button>
              <label
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 6,
                  cursor: 'pointer',
                  fontSize: 13,
                  color: '#555',
                }}
                title="Выставить это время всем рабочим дням текущего месяца (дни с записями пропускаются)"
              >
                <input
                  type="checkbox"
                  checked={applyToAllDays}
                  onChange={() => setApplyToAllDays((v) => !v)}
                  style={{ width: 16, height: 16, accentColor: '#e94560' }}
                />
                Применить ко всем дням месяца
              </label>
            </div>
          </div>
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
        bookingLoading={bookingLoading}
        onClose={handleCloseBooking}
        onUpdate={handleBookingUpdate}
        onBook={handleBook}
        servicesMasterId={selectedMasterId}
      />
    </div>
  );
}

export default SchedulePage;
