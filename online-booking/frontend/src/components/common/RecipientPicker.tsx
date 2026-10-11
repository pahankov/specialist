import { useMemo, useState } from 'react';
import './RecipientPicker.css';

export interface RecipientOption {
  id: number;
  name: string;
  sub?: string;
}

interface RecipientPickerProps {
  items: RecipientOption[];
  selected: Set<number>;
  onChange: (next: Set<number>) => void;
  loading?: boolean;
  placeholder?: string;
}

/** Recipient picker: name search + header checkbox + row checkboxes
 * (same standard as the admin tables). */
export default function RecipientPicker({
  items,
  selected,
  onChange,
  loading = false,
  placeholder = 'Введите имя для поиска...',
}: RecipientPickerProps) {
  const [query, setQuery] = useState('');

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return items;
    return items.filter(
      (i) => i.name.toLowerCase().includes(q) || (i.sub ?? '').toLowerCase().includes(q),
    );
  }, [items, query]);

  const allVisibleChecked = visible.length > 0 && visible.every((i) => selected.has(i.id));

  const toggleAllVisible = () => {
    const next = new Set(selected);
    if (allVisibleChecked) visible.forEach((i) => next.delete(i.id));
    else visible.forEach((i) => next.add(i.id));
    onChange(next);
  };

  const toggleOne = (id: number) => {
    const next = new Set(selected);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    onChange(next);
  };

  return (
    <div className="recipient-picker">
      <input
        type="text"
        className="filter-control recipient-search"
        placeholder={placeholder}
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        aria-label="Поиск получателей"
      />
      <div className="recipient-head">
        <label className="recipient-check-row">
          <input
            type="checkbox"
            checked={allVisibleChecked}
            onChange={toggleAllVisible}
            disabled={visible.length === 0}
            title="Выбрать всех видимых"
          />
          <span>
            {selected.size > 0 ? `Выбрано: ${selected.size}` : 'Выбрать всех видимых'}
          </span>
        </label>
        {selected.size > 0 && (
          <button type="button" className="btn btn-sm btn-ghost" onClick={() => onChange(new Set())}>
            ✕ Снять выбор
          </button>
        )}
      </div>
      <div className="recipient-list" role="listbox" aria-label="Получатели">
        {loading ? (
          <div className="recipient-empty">Загрузка…</div>
        ) : visible.length === 0 ? (
          <div className="recipient-empty">
            {items.length === 0 ? 'Нет получателей' : 'Ничего не найдено'}
          </div>
        ) : (
          visible.map((i) => (
            <label key={i.id} className="recipient-check-row recipient-row">
              <input
                type="checkbox"
                checked={selected.has(i.id)}
                onChange={() => toggleOne(i.id)}
              />
              <span className="recipient-name">{i.name}</span>
              {i.sub && <span className="recipient-sub">{i.sub}</span>}
            </label>
          ))
        )}
      </div>
    </div>
  );
}
