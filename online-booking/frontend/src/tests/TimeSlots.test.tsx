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
  it('renders only the day range, hiding granules outside it', () => {
    const { container } = renderTimeSlots();

    const slots = container.querySelectorAll('.time-slot');
    expect(slots).toHaveLength(1);
    expect(container.querySelector('.time-slot-time')?.textContent).toBe('10:00');
    // The ± stepper removed the earlier/later granules: they must not linger
    // as inactive rows from the global window.
    expect(container.querySelectorAll('.slot-inactive')).toHaveLength(0);
    expect(container.querySelectorAll('.slot-active')).toHaveLength(1);
  });

  it('falls back to the applied window for a day without a stored range', () => {
    const { container } = renderTimeSlots({
      activeHours: {},
      dayStartSlot: undefined,
      dayEndSlot: undefined,
    });

    expect(container.querySelectorAll('.time-slot')).toHaveLength(3);
    expect(container.querySelectorAll('.slot-inactive')).toHaveLength(3);
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

  it('keeps one card per hour and nests four quarter-hour subgranules inside', () => {
    const activeHours = Object.fromEntries(
      Array.from({ length: 16 }, (_, i) => [`2030-01-15-${48 + i}`, true]),
    );
    const { container } = renderTimeSlots({
      activeHours,
      slotMinutes: 15,
      windowStartSlot: 48,
      windowEndSlot: 64,
      dayStartSlot: 48,
      dayEndSlot: 64,
      onSlotMinutesChange: vi.fn(),
    });

    // 12:00–16:00 is four hourly cards, not sixteen top-level granules.
    const groups = container.querySelectorAll('.time-hour-group');
    expect(groups).toHaveLength(4);
    expect(container.querySelectorAll('.time-subslot')).toHaveLength(16);
    expect(container.querySelector('.time-hour-head')).toBeNull();
    expect(
      [...container.querySelectorAll('.time-subslot-time')].slice(0, 5).map((el) => el.textContent),
    ).toEqual(['12:00', '12:15', '12:30', '12:45', '13:00']);
    expect(container.querySelector('.day-hours-slot-size')).toBeNull();
    expect(screen.getByRole('button', { name: '15 мин' })).toHaveAttribute('aria-pressed', 'true');
    expect(container.querySelector('.day-hours-value')?.textContent).toBe('12:00');
  });

  it('keeps one card per hour with two half-hour subgranules in 30-minute mode', () => {
    const { container } = renderTimeSlots({
      activeHours: { '2030-01-15-20': true, '2030-01-15-21': true },
      slotMinutes: 30,
      windowStartSlot: 20,
      windowEndSlot: 22,
      dayStartSlot: 20,
      dayEndSlot: 22,
    });

    expect(container.querySelectorAll('.time-hour-group')).toHaveLength(1);
    expect(container.querySelectorAll('.time-subslot')).toHaveLength(2);
    expect(
      [...container.querySelectorAll('.time-subslot-time')].map((el) => el.textContent),
    ).toEqual(['10:00', '10:30']);
  });

  it('switches only the selected day mode from the day toolbar', () => {
    const onSlotMinutesChange = vi.fn();
    renderTimeSlots({
      activeHours: { '2030-01-15-10': true, '2030-01-15-11': true },
      windowStartSlot: 8,
      windowEndSlot: 22,
      dayStartSlot: 10,
      dayEndSlot: 12,
      onSlotMinutesChange,
    });

    fireEvent.click(screen.getByRole('button', { name: '15 мин' }));
    expect(onSlotMinutesChange).toHaveBeenCalledWith(15);
    expect(screen.getByRole('button', { name: '1 ч' })).toHaveAttribute('aria-pressed', 'true');
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
      fireEvent.click(screen.getByRole('button', { name: 'Добавить гранулу раньше' }));
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
