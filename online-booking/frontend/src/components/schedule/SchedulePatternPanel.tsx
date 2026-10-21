import type { PatternPreview, SchedulePattern } from './pattern';
import { PATTERN_PRESETS } from './pattern';
import { formatHour } from './helpers';
import './SchedulePatternPanel.css';

type GranuleSize = 60 | 30 | 15;

interface SchedulePatternPanelProps {
  monthLabel: string;
  value: SchedulePattern;
  preview: PatternPreview;
  applying: boolean;
  onChange: (patch: Partial<SchedulePattern>) => void;
  onPreset: (workDays: number, offDays: number) => void;
  onApply: () => void;
  /** Current granule size in minutes (60 / 30 / 15). */
  slotMinutes: GranuleSize;
  onSlotMinutesChange: (size: GranuleSize) => void;
  onResetMonth: () => void;
}

function pluralDays(n: number): string {
  const mod10 = n % 10;
  const mod100 = n % 100;
  if (mod10 === 1 && mod100 !== 11) return `${n} день`;
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return `${n} дня`;
  return `${n} дней`;
}

interface StepperProps {
  label?: string;
  value: number;
  min: number;
  max: number;
  format?: (value: number) => string;
  suffix?: string;
  decreaseLabel: string;
  increaseLabel: string;
  onChange: (value: number) => void;
  className?: string;
}

function Stepper({
  label,
  value,
  min,
  max,
  format = String,
  suffix,
  decreaseLabel,
  increaseLabel,
  onChange,
  className,
}: StepperProps) {
  return (
    <div className="pattern-field">
      {label && <span className="pattern-field-label">{label}</span>}
      <div className={`pattern-stepper ${className ?? ''}`} role="group" aria-label={label}>
        <button
          type="button"
          className="pattern-stepper-btn"
          onClick={() => onChange(value - 1)}
          disabled={value <= min}
          aria-label={decreaseLabel}
        >
          −
        </button>
        <span className="pattern-stepper-value">
          {format(value)}
          {suffix ? <small>{suffix}</small> : null}
        </span>
        <button
          type="button"
          className="pattern-stepper-btn"
          onClick={() => onChange(value + 1)}
          disabled={value >= max}
          aria-label={increaseLabel}
        >
          +
        </button>
      </div>
    </div>
  );
}

/**
 * "Сначала график, потом часы, потом применить": a template builder for a
 * whole month. Presets cover common cycles; the two counters cover any N/M
 * pattern (including 7/0 without days off). Applying always resets work days
 * to the cycle and drops days that fall on rest days — the per-day ± controls
 * are the only manual fine-tuning needed.
 */
export function SchedulePatternPanel({
  monthLabel,
  value,
  preview,
  applying,
  onChange,
  onPreset,
  onApply,
  slotMinutes,
  onSlotMinutesChange,
  onResetMonth,
}: SchedulePatternPanelProps) {
  const fromLabel = preview.from
    ? preview.from.toLocaleDateString('ru-RU', { day: 'numeric', month: 'long' })
    : '';

  return (
    <div className="card schedule-pattern-card">
      <div className="schedule-pattern-head">
        <div>
          <h2>Основной график</h2>
          <p>Выберите цикл, рабочие часы и примените его к месяцу.</p>
        </div>
      </div>

      <section className="schedule-pattern-section" aria-labelledby="pattern-cycle-title">
        <div className="schedule-pattern-step">1</div>
        <div className="schedule-pattern-body">
          <h3 id="pattern-cycle-title">Цикл работы и отдыха</h3>
          <div className="pattern-presets" role="group" aria-label="Готовые графики">
            {PATTERN_PRESETS.map((preset) => {
              const active = value.workDays === preset.workDays && value.offDays === preset.offDays;
              return (
                <button
                  key={preset.label}
                  type="button"
                  className={`pattern-preset ${active ? 'active' : ''}`}
                  onClick={() => onPreset(preset.workDays, preset.offDays)}
                  title={preset.hint}
                >
                  {preset.label}
                </button>
              );
            })}
          </div>

          <div className="pattern-row pattern-controls-unified">
            <div className="pattern-field pattern-field-unified">
              <Stepper
                label="Работать"
                value={value.workDays}
                min={1}
                max={31}
                suffix=" дн."
                decreaseLabel="Уменьшить число рабочих дней"
                increaseLabel="Увеличить число рабочих дней"
                onChange={(workDays) => onChange({ workDays })}
                className="pattern-stepper-full"
              />
            </div>
            <div className="pattern-field pattern-field-unified">
              <Stepper
                label="Отдыхать"
                value={value.offDays}
                min={0}
                max={31}
                suffix=" дн."
                decreaseLabel="Уменьшить число выходных дней"
                increaseLabel="Увеличить число выходных дней"
                onChange={(offDays) => onChange({ offDays })}
                className="pattern-stepper-full"
              />
            </div>
            <div className="pattern-field pattern-field-unified">
              <span className="pattern-field-label">Первый рабочий день цикла</span>
              <input
                className="pattern-date-input pattern-date-full"
                type="date"
                value={value.anchor}
                onChange={(event) => onChange({ anchor: event.target.value })}
              />
            </div>
            <div className="pattern-field pattern-field-unified pattern-slot-field">
              <span className="pattern-field-label">Режим</span>
              <div
                className="pattern-slot-toggle-group"
                role="group"
                aria-label="Режим расписания"
              >
                <button
                  type="button"
                  className={`pattern-slot-btn ${slotMinutes === 60 ? 'active' : ''}`}
                  onClick={() => onSlotMinutesChange(60)}
                  aria-pressed={slotMinutes === 60}
                >
                  Час
                </button>
                <button
                  type="button"
                  className={`pattern-slot-btn ${slotMinutes === 30 ? 'active' : ''}`}
                  onClick={() => onSlotMinutesChange(30)}
                  aria-pressed={slotMinutes === 30}
                >
                  Полчаса
                </button>
                <button
                  type="button"
                  className={`pattern-slot-btn ${slotMinutes === 15 ? 'active' : ''}`}
                  onClick={() => onSlotMinutesChange(15)}
                  aria-pressed={slotMinutes === 15}
                >
                  Четверть
                </button>
              </div>
            </div>
          </div>

          <p className="schedule-pattern-hint">
            {value.offDays === 0
              ? `Цикл ${value.workDays}/${value.offDays}: работаем каждый день, без выходных.`
              : `Цикл ${value.workDays}/${value.offDays}: ${pluralDays(value.workDays)} работы, затем ${pluralDays(value.offDays)} отдыха.`}
          </p>
        </div>
      </section>

      <section className="schedule-pattern-section" aria-labelledby="pattern-hours-title">
        <div className="schedule-pattern-step">2</div>
        <div className="schedule-pattern-body">
          <h3 id="pattern-hours-title">Рабочие часы</h3>
          <div className="pattern-row pattern-controls">
            <Stepper
              label="Начало"
              value={value.startHour}
              min={0}
              max={Math.min(23, value.endHour - 1)}
              format={formatHour}
              decreaseLabel="Начать рабочий день на час раньше"
              increaseLabel="Начать рабочий день на час позже"
              onChange={(startHour) => onChange({ startHour })}
            />
            <span className="pattern-time-dash" aria-hidden="true">
              —
            </span>
            <Stepper
              label="Конец"
              value={value.endHour}
              min={Math.max(1, value.startHour + 1)}
              max={24}
              format={formatHour}
              decreaseLabel="Закончить рабочий день на час раньше"
              increaseLabel="Закончить рабочий день на час позже"
              onChange={(endHour) => onChange({ endHour })}
            />
          </div>
          <p className="schedule-pattern-hint">
            {value.endHour - value.startHour} ч в день. Кнопками «−» и «+» можно добавить время
            раньше или позже.
          </p>
        </div>
      </section>

      <section className="schedule-pattern-section" aria-labelledby="pattern-apply-title">
        <div className="schedule-pattern-step">3</div>
        <div className="schedule-pattern-body">
          <h3 id="pattern-apply-title">Применить</h3>
          <div className="schedule-pattern-apply">
            <div className="schedule-pattern-summary">
              {preview.canApply ? (
                <>
                  <strong>
                    {fromLabel ? `С ${fromLabel}: ` : ''}
                    {pluralDays(preview.workDays)} работы и {pluralDays(preview.offDays)} отдыха
                  </strong>
                  <span>Прошедшие дни и дни с записями не изменяются.</span>
                </>
              ) : (
                <span>В этом месяце уже нет будущих дней для применения.</span>
              )}
            </div>
            <div className="schedule-pattern-actions">
              <button
                type="button"
                className="btn btn-outline pattern-reset-btn"
                disabled={applying || !preview.canApply}
                onClick={onResetMonth}
              >
                Сбросить месяц
              </button>
              <button
                type="button"
                className="btn btn-primary pattern-apply-btn"
                disabled={applying || !preview.canApply}
                onClick={onApply}
              >
                {applying ? 'Применяем…' : `Применить: ${monthLabel}`}
              </button>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
