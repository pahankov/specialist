interface PagerProps {
  /** Zero-based current page */
  page: number;
  /** Total pages (>= 1) */
  totalPages: number;
  onChange: (page: number) => void;
  /** Optional label override, e.g. with total counts */
  label?: string;
}

/** Shared pagination: first / prev / label / next / last. */
export default function Pager({ page, totalPages, onChange, label }: PagerProps) {
  const total = Math.max(1, totalPages);
  const go = (p: number) => onChange(Math.min(Math.max(0, p), total - 1));
  const btn = (disabled: boolean): React.CSSProperties => ({ opacity: disabled ? 0.5 : 1 });

  return (
    <div
      style={{
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        gap: 8,
        marginTop: 20,
      }}
    >
      <button
        className="btn btn-ghost"
        onClick={() => go(0)}
        disabled={page === 0}
        style={btn(page === 0)}
        title="В начало"
      >
        ⇤ В начало
      </button>
      <button
        className="btn btn-ghost"
        onClick={() => go(page - 1)}
        disabled={page === 0}
        style={btn(page === 0)}
        title="Назад"
      >
        ← Назад
      </button>
      <span style={{ fontSize: 14, color: '#666', minWidth: 120, textAlign: 'center' }}>
        {label ?? `Страница ${page + 1} из ${total}`}
      </span>
      <button
        className="btn btn-ghost"
        onClick={() => go(page + 1)}
        disabled={page + 1 >= total}
        style={btn(page + 1 >= total)}
        title="Вперёд"
      >
        Вперёд →
      </button>
      <button
        className="btn btn-ghost"
        onClick={() => go(total - 1)}
        disabled={page + 1 >= total}
        style={btn(page + 1 >= total)}
        title="В конец"
      >
        В конец ⇥
      </button>
    </div>
  );
}
