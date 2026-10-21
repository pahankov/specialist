import type { Appointment, Client, DaySchedule, BookingFormState } from '../../api/types';
import {
  formatDate,
  formatSlotTime,
} from './helpers';
import { adminApi } from '../../api/client';

export async function toggleDayWork(
  date: Date,
  schedule: Record<string, DaySchedule>,
  activeHours: Record<string, boolean>,
  appointments: Appointment[],
  setError: (msg: string) => void,
  masterId?: number | '',
  startSlot = 0,
  endSlot = 0,
  slotMinutes: 30 | 60 = 60,
): Promise<{
  newSchedule: Record<string, DaySchedule>;
  newActiveHours: Record<string, boolean>;
} | null> {
  const dateStr = formatDate(date);
  const isActive = !!schedule[dateStr];
  const masterParam = masterId !== '' && masterId != null ? masterId : undefined;

  if (isActive) {
    // Cancelled history doesn't block: only live bookings protect the day.
    const dayAppointments = appointments.filter(
      (a) => a.appointment_date?.split('T')[0] === dateStr && a.status !== 'cancelled',
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
    newSchedule[dateStr] = { start: startSlot, end: endSlot };
    for (let s = startSlot; s < endSlot; s++) {
      newActiveHours[`${dateStr}-${s}`] = true;
    }
  }

  // Sync with backend (scoped to the selected master for superadmins).
  // formatSlotTime renders "HH:MM" (e.g. "09:30") which SQL TIME accepts.
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
          start_time: formatSlotTime(startSlot, slotMinutes),
          end_time: formatSlotTime(endSlot, slotMinutes),
        });
      } else {
        await adminApi.createWorkingHour({
          master_id: masterParam,
          schedule_date: dateStr,
          start_time: formatSlotTime(startSlot, slotMinutes),
          end_time: formatSlotTime(endSlot, slotMinutes),
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
  slot: number,
  setActiveHours: (fn: (prev: Record<string, boolean>) => Record<string, boolean>) => void,
) {
  setActiveHours((prev) => ({ ...prev, [`${dateStr}-${slot}`]: !prev[`${dateStr}-${slot}`] }));
}

export function openBookingForm(
  date: Date,
  slot: number,
  setBookingForm: (fn: (prev: BookingFormState) => BookingFormState) => void,
) {
  setBookingForm((prev) => ({
    ...prev,
    open: true,
    date,
    hour: slot,
    clientId: null,
    serviceId: null,
    bundleId: null,
    status: 'confirmed',
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
    status: 'confirmed',
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
  slotMinutes: 30 | 60 = 60,
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
    const hhmm = formatSlotTime(bookingForm.hour, slotMinutes);
    const appointmentDate = `${y}-${m}-${d}T${hhmm}:00`;
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
