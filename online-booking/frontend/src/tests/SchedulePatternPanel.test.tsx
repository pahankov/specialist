import { describe, it, expect, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { SchedulePatternPanel } from '../components/schedule/SchedulePatternPanel';
import { buildPatternPreview, createDefaultPattern } from '../components/schedule/pattern';

const month = new Date(2026, 10, 1);
const pattern = createDefaultPattern(month);
const preview = buildPatternPreview(month, pattern);

function renderPanel(overrides: Record<string, unknown> = {}) {
  return render(
    <SchedulePatternPanel
      monthLabel="ноябрь 2026"
      value={pattern}
      preview={preview}
      applying={false}
      onChange={vi.fn()}
      onPreset={vi.fn()}
      onApply={vi.fn()}
      slotMinutes={60}
      onSlotMinutesChange={vi.fn()}
      onResetMonth={vi.fn()}
      {...overrides}
    />,
  );
}

describe('SchedulePatternPanel', () => {
  it('renders each cycle preset exactly once', () => {
    renderPanel();

    for (const label of ['5/2', '2/2', '3/3', '1/3']) {
      expect(screen.getAllByRole('button', { name: label })).toHaveLength(1);
    }
  });

  it('keeps the mode switch beside the cycle presets and reports 15 minutes', () => {
    const onSlotMinutesChange = vi.fn();
    const { container } = renderPanel({ onSlotMinutesChange });

    const cycleRow = container.querySelector('.pattern-controls-unified');
    expect(cycleRow?.querySelector('.pattern-presets')).not.toBeNull();
    expect(cycleRow?.querySelector('.granule-mode-toggle')).not.toBeNull();

    fireEvent.click(screen.getByRole('button', { name: '15 мин' }));
    expect(onSlotMinutesChange).toHaveBeenCalledWith(15);
  });
});
