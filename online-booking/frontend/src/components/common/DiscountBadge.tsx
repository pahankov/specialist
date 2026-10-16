import { useEffect, useRef, useState } from 'react';
import { toast } from 'sonner';
import { formatDiscountTag } from '../schedule/helpers';
import { getApiErrorMessage } from '../../utils/apiError';

/** 🏷 Inline discount editor: click the badge, set % or ₽ + expiry in the row.
 * Closes on ✓, ✕, Escape or a click outside. */
export default function DiscountBadge({
  pct,
  fixed,
  until,
  onSave,
}: {
  pct?: number | null;
  fixed?: number | string | null;
  until?: string | null;
  onSave: (pct: number | null, fixed: number | null, until: string | null) => Promise<void> | void;
}) {
  const [open, setOpen] = useState(false);
  const [kind, setKind] = useState<'percent' | 'fixed'>('percent');
  const [v, setV] = useState('');
  const [u, setU] = useState('');
  const [saving, setSaving] = useState(false);
  const boxRef = useRef<HTMLSpanElement>(null);

  const reopen = () => {
    setKind(Number(fixed) > 0 ? 'fixed' : 'percent');
    setV(Number(fixed) > 0 ? String(fixed) : pct ? String(pct) : '');
    setU(until ? String(until).slice(0, 16) : '');
    setOpen(true);
  };

  const save = async () => {
    const num = v.trim() === '' ? null : Math.round(Number(v));
    if (num !== null && !(num >= 0)) {
      toast.error('Скидка не может быть отрицательной');
      return;
    }
    if (kind === 'percent' && num !== null && num > 90) {
      toast.error('Процент — максимум 90');
      return;
    }
    setSaving(true);
    try {
      await onSave(
        kind === 'percent' ? num : null,
        kind === 'fixed' ? num : null,
        u.trim() === '' ? null : new Date(u).toISOString(),
      );
      setOpen(false);
    } catch (err: unknown) {
      toast.error(getApiErrorMessage(err, 'Не удалось сохранить скидку'));
    } finally {
      setSaving(false);
    }
  };

  // Escape + outside click close the editor (inputs keep working inside).
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false);
    };
    const onDown = (e: PointerEvent) => {
      if (boxRef.current && !boxRef.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('keydown', onKey);
    document.addEventListener('pointerdown', onDown);
    return () => {
      document.removeEventListener('keydown', onKey);
      document.removeEventListener('pointerdown', onDown);
    };
  }, [open]);

  const tag = formatDiscountTag(pct, until, fixed);
  if (!open) {
    return (
      <button
        type="button"
        className="btn btn-sm btn-ghost"
        onClick={reopen}
        title={tag ? `Скидка ${tag} — нажать, чтобы изменить` : 'Назначить скидку'}
        aria-label="Скидка"
        style={tag ? { borderColor: '#e5484d', color: '#e5484d' } : undefined}
      >
        🏷️{tag ? ` ${tag}` : ''}
      </button>
    );
  }
  return (
    <span
      ref={boxRef}
      style={{ display: 'inline-flex', gap: 4, alignItems: 'center', flexWrap: 'wrap' }}
    >
      <span className="segmented" style={{ display: 'inline-flex' }}>
        <button
          type="button"
          className={`segmented-btn${kind === 'percent' ? ' active' : ''}`}
          onClick={() => setKind('percent')}
          title="Скидка в процентах"
          style={{ padding: '4px 10px', fontSize: 13 }}
        >
          %
        </button>
        <button
          type="button"
          className={`segmented-btn${kind === 'fixed' ? ' active' : ''}`}
          onClick={() => setKind('fixed')}
          title="Скидка в рублях"
          style={{ padding: '4px 10px', fontSize: 13 }}
        >
          ₽
        </button>
      </span>
      <input
        type="number"
        min={0}
        max={kind === 'percent' ? 90 : undefined}
        value={v}
        onChange={(e) => setV(e.target.value)}
        placeholder={kind === 'percent' ? '%' : '₽'}
        aria-label={kind === 'percent' ? 'Скидка, %' : 'Скидка, ₽'}
        style={{ width: 72 }}
      />
      <input
        type="datetime-local"
        value={u}
        onChange={(e) => setU(e.target.value)}
        aria-label="Скидка до"
        title="Скидка до (пусто = бессрочно)"
        style={{ width: 170 }}
      />
      <button
        type="button"
        className="btn btn-sm btn-primary"
        disabled={saving}
        onClick={save}
        title="Сохранить скидку"
      >
        ✓
      </button>
      <button
        type="button"
        className="btn btn-sm btn-ghost"
        onClick={() => setOpen(false)}
        title="Закрыть"
      >
        ✕
      </button>
    </span>
  );
}
