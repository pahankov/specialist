import { describe, it, expect, vi } from 'vitest';
import { act, fireEvent, render, screen } from '@testing-library/react';
import { TimeSlots } from '../components/schedule/TimeSlots';

const selectedDate = new Date(2030, 0, 15);

function renderTimeSlots(overrides: Record<string, unknown> = {}) {
  return render(
    <TimeSlots
      selectedDate={selectedDate}
      appointments={[]}
      activeHours={{ '2030-01-15-10': true }}
      onToggleHour={vi.fn()}
      onOpenBooking={vi.fn()}
      onCancelAppointment={vi.fn()}
      slotMinutes={60}
      windowStartSlot={8}
      windowEndSlot={11}
      dayStartSlot={10}
      dayEndSlot={11}
      onChangeDaySlots={vi.fn()}
      {...overrides}
    />,
  );
}

describe('TimeSlots', () => {
  it('renders every granule of the global window, including inactive edges', () => {
    const { container } = renderTimeSlots();

    const slots = container.querySelectorAll('.time-slot');
    expect(slots).toHaveLength(3);
    expect(container.querySelectorAll('.time-slot-time')[0]?.textContent).toBe('08:00');
    expect(container.querySelectorAll('.time-slot-time')[1]?.textContent).toBe('09:00');
    expect(container.querySelectorAll('.time-slot-time')[2]?.textContent).toBe('10:00');
    // The two deactivated edge granules stay visible for reactivation.
    expect(container.querySelectorAll('.slot-inactive')).toHaveLength(2);
    expect(container.querySelectorAll('.slot-active')).toHaveLength(1);
  });

  it('renders exactly the applied window when the day matches it', () => {
    const { container } = renderTimeSlots({
      activeHours: { '2030-01-15-10': true, '2030-01-15-11': true },
      windowStartSlot: 10,
      windowEndSlot: 12,
      dayStartSlot: 10,
      dayEndSlot: 12,
    });

    const slots = container.querySelectorAll('.time-slot');
    expect(slots).toHaveLength(2);
    expect(container.querySelectorAll('.time-slot-time')[0]?.textContent).toBe('10:00');
    expect(container.querySelectorAll('.time-slot-time')[1]?.textContent).toBe('11:00');
    expect(container.querySelectorAll('.time-slot-time').length).toBe(2);
  });

  it('keeps a preserved day visible even when its range exceeds the window', () => {
    const { container } = renderTimeSlots({
      activeHours: { '2030-01-15-8': true, '2030-01-15-19': true },
      windowStartSlot: 10,
      windowEndSlot: 18,
      dayStartSlot: 8,
      dayEndSlot: 20,
    });

    const slots = container.querySelectorAll('.time-slot');
    expect(slots).toHaveLength(12);
    expect(container.querySelectorAll('.time-slot-time')[0]?.textContent).toBe('08:00');
    expect(container.querySelectorAll('.time-slot-time')[11]?.textContent).toBe('19:00');
  });

  it('adds and removes edge granules through the stepper controls', async () => {
    const onChangeDaySlots = vi.fn();
    renderTimeSlots({
      activeHours: { '2030-01-15-10': true, '2030-01-15-11': true },
      windowStartSlot: 8,
      windowEndSlot: 22,
      dayStartSlot: 10,
      dayEndSlot: 12,
      onChangeDaySlots,
    });

    await act(async () => {
      fireEvent.click(
        screen.getByRole('button', { name: 'Добавить гранулу раньше' }),
      );
    });
    expect(onChangeDaySlots).toHaveBeenLastCalledWith('2030-01-15', 9, 12);

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'Добавить гранулу позже' }));
    });
    expect(onChangeDaySlots).toHaveBeenLastCalledWith('2030-01-15', 10, 13);

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'Убрать первую гранулу' }));
    });
    expect(onChangeDaySlots).toHaveBeenLastCalledWith('2030-01-15', 11, 12);

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'Убрать последнюю гранулу' }));
    });
    expect(onChangeDaySlots).toHaveBeenLastCalledWith('2030-01-15', 10, 11);
  });
});
