import { describe, it, expect } from 'vitest';
import {
  PATTERN_PRESETS,
  buildPatternPreview,
  createDefaultPattern,
  isPatternWorkDay,
  mondayOnOrBefore,
} from '../components/schedule/pattern';

describe('mondayOnOrBefore', () => {
  it('returns the same Monday', () => {
    expect(mondayOnOrBefore(new Date(2026, 9, 5))).toEqual(new Date(2026, 9, 5));
  });

  it('returns the previous Monday for Sunday', () => {
    expect(mondayOnOrBefore(new Date(2026, 9, 11))).toEqual(new Date(2026, 9, 5));
  });

  it('keeps local midnight', () => {
    const result = mondayOnOrBefore(new Date(2026, 9, 7, 18, 45));
    expect(result.getHours()).toBe(0);
    expect(result.getMinutes()).toBe(0);
  });
});

describe('createDefaultPattern', () => {
  it('defaults to 5/2 from Monday 09:00–18:00', () => {
    const pattern = createDefaultPattern(new Date(2026, 9, 14));
    expect(pattern.workDays).toBe(5);
    expect(pattern.offDays).toBe(2);
    expect(pattern.anchor).toBe('2026-10-12');
    expect(pattern.startHour).toBe(9);
    expect(pattern.endHour).toBe(18);
    expect(pattern.replaceOffDays).toBe(true);
  });
});

describe('isPatternWorkDay', () => {
  it('handles a 5/2 week', () => {
    const anchor = '2026-10-05'; // Monday
    expect(isPatternWorkDay(new Date(2026, 9, 5), anchor, 5, 2)).toBe(true);
    expect(isPatternWorkDay(new Date(2026, 9, 9), anchor, 5, 2)).toBe(true);
    expect(isPatternWorkDay(new Date(2026, 9, 10), anchor, 5, 2)).toBe(false);
    expect(isPatternWorkDay(new Date(2026, 9, 11), anchor, 5, 2)).toBe(false);
    expect(isPatternWorkDay(new Date(2026, 9, 12), anchor, 5, 2)).toBe(true);
  });

  it('handles 2/2 across month boundaries', () => {
    const anchor = '2026-10-01';
    expect(isPatternWorkDay(new Date(2026, 9, 1), anchor, 2, 2)).toBe(true);
    expect(isPatternWorkDay(new Date(2026, 9, 2), anchor, 2, 2)).toBe(true);
    expect(isPatternWorkDay(new Date(2026, 9, 3), anchor, 2, 2)).toBe(false);
    expect(isPatternWorkDay(new Date(2026, 9, 5), anchor, 2, 2)).toBe(true);
    // Negative offsets (before the anchor) use the same cycle.
    expect(isPatternWorkDay(new Date(2026, 8, 30), anchor, 2, 2)).toBe(false);
    expect(isPatternWorkDay(new Date(2026, 8, 28), anchor, 2, 2)).toBe(true);
    expect(isPatternWorkDay(new Date(2026, 9, 4), anchor, 2, 2)).toBe(false);
  });

  it('handles 1/3 and 7/0', () => {
    const anchor = '2026-10-01';
    expect(isPatternWorkDay(new Date(2026, 9, 1), anchor, 1, 3)).toBe(true);
    expect(isPatternWorkDay(new Date(2026, 9, 2), anchor, 1, 3)).toBe(false);
    expect(isPatternWorkDay(new Date(2026, 9, 5), anchor, 1, 3)).toBe(true);
    expect(isPatternWorkDay(new Date(2030, 0, 1), anchor, 7, 0)).toBe(true);
  });

  it('treats an invalid anchor as a work day', () => {
    expect(isPatternWorkDay(new Date(2026, 9, 1), 'nope', 2, 2)).toBe(true);
  });
});

describe('buildPatternPreview', () => {
  const pattern = createDefaultPattern(new Date(2026, 9, 5));

  it('clips the month to today and counts only future days', () => {
    const preview = buildPatternPreview(new Date(2026, 9, 1), pattern, new Date(2026, 9, 14));
    expect(preview.from).toEqual(new Date(2026, 9, 14));
    expect(preview.to).toEqual(new Date(2026, 9, 31));
    // Oct 14–31 with Mon–Fri work: 13 work, 5 rest.
    expect(preview.workDays).toBe(13);
    expect(preview.offDays).toBe(5);
    expect(preview.workDates.has('2026-10-14')).toBe(true);
    expect(preview.offDates.has('2026-10-17')).toBe(true);
    expect(preview.canApply).toBe(true);
  });

  it('does not allow applying to a fully past month', () => {
    const preview = buildPatternPreview(new Date(2026, 8, 1), pattern, new Date(2026, 9, 14));
    expect(preview.from).toBeNull();
    expect(preview.to).toBeNull();
    expect(preview.workDays).toBe(0);
    expect(preview.offDays).toBe(0);
    expect(preview.canApply).toBe(false);
  });

  it('previews a future month from its first day', () => {
    const preview = buildPatternPreview(new Date(2026, 10, 1), pattern, new Date(2026, 9, 14));
    expect(preview.from).toEqual(new Date(2026, 10, 1));
    expect(preview.workDays + preview.offDays).toBe(30);
    expect(preview.canApply).toBe(true);
  });

  it('rejects invalid hour ranges and anchors', () => {
    const invalidHours = buildPatternPreview(
      new Date(2026, 9, 1),
      { ...pattern, startHour: 19, endHour: 18 },
      new Date(2026, 9, 14),
    );
    expect(invalidHours.canApply).toBe(false);

    const invalidAnchor = buildPatternPreview(
      new Date(2026, 9, 1),
      { ...pattern, anchor: 'not-a-date' },
      new Date(2026, 9, 14),
    );
    expect(invalidAnchor.canApply).toBe(false);
  });

  it('offers only the four compact presets, keeping 7/0 for custom counters', () => {
    const labels = PATTERN_PRESETS.map((preset) => preset.label);
    expect(labels).toEqual(['5/2', '2/2', '3/3', '1/3']);
  });
});
