import { describe, it, expect, vi, beforeEach } from 'vitest';

const { getWorkingHours, createWorkingHour, updateWorkingHour, deleteWorkingHour } = vi.hoisted(
  () => ({
    getWorkingHours: vi.fn(),
    createWorkingHour: vi.fn(),
    updateWorkingHour: vi.fn(),
    deleteWorkingHour: vi.fn(),
  }),
);

vi.mock('../api/client', () => ({
  adminApi: {
    getWorkingHours,
    createWorkingHour,
    updateWorkingHour,
    deleteWorkingHour,
  },
}));

import { toggleDayWork } from '../components/schedule/hooks';

const date = new Date(2026, 10, 3);

beforeEach(() => {
  getWorkingHours.mockReset();
  createWorkingHour.mockReset();
  updateWorkingHour.mockReset();
  deleteWorkingHour.mockReset();
});

describe('toggleDayWork', () => {
  it('does not apply an optimistic day when the server write fails', async () => {
    getWorkingHours.mockRejectedValue(new Error('network'));
    const setError = vi.fn();

    const result = await toggleDayWork(date, {}, {}, [], setError, undefined, 9, 18, 60);

    expect(result).toBeNull();
    expect(setError).toHaveBeenCalledWith(
      'Не удалось сохранить расписание. Изменения не применены.',
    );
  });

  it('returns the new schedule only after a successful write', async () => {
    getWorkingHours.mockResolvedValue({ data: [] });
    createWorkingHour.mockResolvedValue({ data: {} });
    const setError = vi.fn();

    const result = await toggleDayWork(date, {}, {}, [], setError, undefined, 9, 18, 60);

    expect(result?.newSchedule['2026-11-03']).toEqual({ start: 9, end: 18 });
    expect(createWorkingHour).toHaveBeenCalledWith(
      expect.objectContaining({
        schedule_date: '2026-11-03',
        start_time: '09:00',
        end_time: '18:00',
      }),
    );
    expect(setError).not.toHaveBeenCalled();
  });
});
