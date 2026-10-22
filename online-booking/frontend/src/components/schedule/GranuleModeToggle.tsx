import './GranuleModeToggle.css';

export type GranuleSize = 60 | 30 | 15;

interface GranuleModeToggleProps {
  value: GranuleSize;
  onChange: (size: GranuleSize) => void;
  ariaLabel: string;
  /** Smaller variant for the selected-day toolbar. */
  compact?: boolean;
}

const MODES: {
  value: GranuleSize;
  label: string;
  title: string;
}[] = [
  { value: 60, label: '1 ч', title: 'Целые часы: 14:00, 15:00, 16:00' },
  { value: 30, label: '30 мин', title: 'Полчаса: 14:00, 14:30, 15:00' },
  { value: 15, label: '15 мин', title: 'Четверть часа: 14:00, 14:15, 14:30, 14:45' },
];

/** Segmented 1 ч / 30 мин / 15 мин switch shared by the month panel and a day. */
export function GranuleModeToggle({
  value,
  onChange,
  ariaLabel,
  compact = false,
}: GranuleModeToggleProps) {
  return (
    <div
      className={`granule-mode-toggle${compact ? ' granule-mode-toggle--compact' : ''}`}
      role="group"
      aria-label={ariaLabel}
    >
      {MODES.map((mode) => (
        <button
          key={mode.value}
          type="button"
          className={`granule-mode-btn ${value === mode.value ? 'active' : ''}`}
          onClick={() => onChange(mode.value)}
          aria-pressed={value === mode.value}
          title={mode.title}
        >
          {mode.label}
        </button>
      ))}
    </div>
  );
}
