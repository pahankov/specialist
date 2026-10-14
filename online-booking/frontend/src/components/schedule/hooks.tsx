import type { Appointment, Client, DaySchedule, BookingFormState } from '../../api/types';
import { formatDate } from './helpers';
import { adminApi } from '../../api/client';

export async function toggleDayWork(
  date: Date,
  schedule: Record<string, DaySchedule>,
  activeHours: Record<string, boolean>,
  appointments: Appointment[],
  setError: (msg: string) => void,
  masterId?: number | '',
  dayStart = 8,
  dayEnd = 22,
): Promise<{
  newSchedule: Record<string, DaySchedule>;
  newActiveHours: Record<string, boolean>;
} | null> {
  const dateStr = formatDate(date);
  const isActive = !!schedule[dateStr];
  const masterParam = masterId !== '' && masterId != null ? masterId : undefined;

  if (isActive) {
    const dayAppointments = appointments.filter(
      (a) => a.appointment_date?.split('T')[0] === dateStr,
    );
    if (dayAppointments.length > 0) {
      setError(
        `Нельзя деактивировать день — в нём ${dayAppointments.length} запись(ей). Сначала удалите записи.`,
      );
      return null;
    }
  }

  const newSchedule = { ...schedule };
  const newActiveHours = { ...activeHours };

  if (isActive) {
    delete newSchedule[dateStr];
    for (const k of Object.keys(newActiveHours)) {
      if (k.startsWith(`${dateStr}-`)) delete newActiveHours[k];
    }
  } else {
    newSchedule[dateStr] = { start: dayStart, end: dayEnd };
    for (let h = dayStart; h < dayEnd; h++) {
      newActiveHours[`${dateStr}-${h}`] = true;
    }
  }

  const pad = (h: number) => `${String(h).padStart(2, '0')}:00`;
  // Sync with backend (scoped to the selected master for superadmins)
  try {
    if (isActive) {
      const resp = await adminApi.getWorkingHours(masterParam);
      const existing = resp.data.find((h: any) => h.schedule_date === dateStr);
      if (existing) await adminApi.deleteWorkingHour(existing.id);
    } else {
      const resp = await adminApi.getWorkingHours(masterParam);
      const existing = resp.data.find((h: any) => h.schedule_date === dateStr);
      if (existing) {
        await adminApi.updateWorkingHour(existing.id, {
          schedule_date: dateStr,
          start_time: pad(dayStart),
          end_time: pad(dayEnd),
        });
      } else {
        await adminApi.createWorkingHour({
          master_id: masterParam,
          schedule_date: dateStr,
          start_time: pad(dayStart),
          end_time: pad(dayEnd),
        });
      }
    }
  } catch (err) {
    console.error('Failed to sync working hours:', err);
  }

  return { newSchedule, newActiveHours };
}

export function toggleHour(
  dateStr: string,
  hour: number,
  setActiveHours: (fn: (prev: Record<string, boolean>) => Record<string, boolean>) => void,
) {
  setActiveHours((prev) => ({ ...prev, [`${dateStr}-${hour}`]: !prev[`${dateStr}-${hour}`] }));
}

export function openBookingForm(
  date: Date,
  hour: number,
  setBookingForm: (fn: (prev: BookingFormState) => BookingFormState) => void,
) {
  setBookingForm((prev) => ({
    ...prev,
    open: true,
    date,
    hour,
    clientId: null,
    serviceId: null,
    bundleId: null,
    status: 'pending',
    notes: '',
  }));
}

export function closeBookingForm(
  setBookingForm: (fn: (prev: BookingFormState) => BookingFormState) => void,
  setBookingClients: (clients: Client[]) => void,
) {
  setBookingForm(() => ({
    open: false,
    date: null,
    hour: null,
    clientId: null,
    serviceId: null,
    bundleId: null,
    status: 'pending',
    notes: '',
  }));
  setBookingClients([]);
}

export async function handleBookAppointment(
  bookingForm: BookingFormState,
  setBookingLoading: (loading: boolean) => void,
  setError: (msg: string) => void,
  api: typeof adminApi,
  onClose: () => void,
  masterId?: number | '',
): Promise<boolean> {
  if (
    !bookingForm.date ||
    bookingForm.hour === null ||
    !bookingForm.clientId ||
    (!bookingForm.serviceId && !bookingForm.bundleId) ||
    (bookingForm.serviceId && bookingForm.bundleId)
  )
    return false;

  setBookingLoading(true);
  try {
    const y = bookingForm.date.getFullYear();
    const m = String(bookingForm.date.getMonth() + 1).padStart(2, '0');
    const d = String(bookingForm.date.getDate()).padStart(2, '0');
    const hourStr = String(bookingForm.hour).padStart(2, '0');
    const appointmentDate = `${y}-${m}-${d}T${hourStr}:00:00`;
    await api.bookAppointment({
      master_id: masterId !== '' && masterId != null ? masterId : undefined,
      client_id: bookingForm.clientId,
      ...(bookingForm.bundleId
        ? { bundle_id: bookingForm.bundleId }
        : { service_id: bookingForm.serviceId! }),
      appointment_date: appointmentDate,
      status: bookingForm.status,
      notes: bookingForm.notes || undefined,
    });
    onClose();
    return true;
  } catch (err: any) {
    setError(err.response?.data?.detail || 'Произошла ошибка');
    return false;
  } finally {
    setBookingLoading(false);
  }
}
