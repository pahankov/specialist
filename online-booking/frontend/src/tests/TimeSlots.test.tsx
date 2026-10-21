import { describe, it, expect, vi } from 'vitest';
import { act, fireEvent, render, screen } from '@testing-library/react';
import { TimeSlots } from '../components/schedule/TimeSlots';

const selectedDate = new Date(2030, 0, 15);

describe('TimeSlots', () => {
  it('renders every granule of the global window, including inactive edges', () => {
    const { container } = render(
      <TimeSlots
        selectedDate={selectedDate}
        appointments={[]}
        activeHours={{ '2030-01-15-10': true }}
        onToggleHour={vi.fn()}
        onOpenBooking={vi.fn()}
        onCancelAppointment={vi.fn()}
        windowStart={8}
        windowEnd={11}
        dayStart={10}
        dayEnd={11}
      />,
    );

    const slots = container.querySelectorAll('.time-slot');
    expect(slots).toHaveLength(3);
    expect(screen.getByText('08:00')).toBeInTheDocument();
    expect(screen.getByText('09:00')).toBeInTheDocument();
    expect(screen.getByText('10:00')).toBeInTheDocument();
    // The two deactivated edge granules stay visible for reactivation.
    expect(container.querySelectorAll('.slot-inactive')).toHaveLength(2);
    expect(container.querySelectorAll('.slot-active')).toHaveLength(1);
  });

  it('sends earlier/later day-hour changes through the stepper controls', async () => {
    const onChangeDayHours = vi.fn();
    render(
      <TimeSlots
        selectedDate={selectedDate}
        appointments={[]}
        activeHours={{ '2030-01-15-10': true, '2030-01-15-11': true }}
        onToggleHour={vi.fn()}
        onOpenBooking={vi.fn()}
        onCancelAppointment={vi.fn()}
        windowStart={8}
        windowEnd={22}
        dayStart={10}
        dayEnd={12}
        onChangeDayHours={onChangeDayHours}
      />,
    );

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'Начать рабочий день на час раньше' }));
    });
    expect(onChangeDayHours).toHaveBeenLastCalledWith('2030-01-15', 9, 12);

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'Закончить рабочий день на час позже' }));
    });
    expect(onChangeDayHours).toHaveBeenLastCalledWith('2030-01-15', 10, 13);
  });
});
