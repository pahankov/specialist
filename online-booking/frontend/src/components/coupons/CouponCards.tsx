export interface CouponCardRow {
  id: number;
  code: string;
  kind: string;
  value: number;
  max_uses: number | null;
  used_count: number;
  audience: string;
  user_ids: number[];
  recipient_names?: string[];
  valid_until: string | null;
  is_active: boolean;
}

/** Spent out, expired or switched off — lives in the archive. */
export function isCouponArchived(c: CouponCardRow, now: number): boolean {
  if (!c.is_active) return true;
  if (c.max_uses != null && (c.used_count || 0) >= c.max_uses) return true;
  if (c.valid_until && new Date(c.valid_until).getTime() <= now) return true;
  return false;
}

function archiveReason(c: CouponCardRow, now: number): string {
  if (!c.is_active) return 'выкл';
  if (c.max_uses != null && (c.used_count || 0) >= c.max_uses) return 'исчерпан';
  if (c.valid_until && new Date(c.valid_until).getTime() <= now) return 'истёк';
  return '';
}

function recipientsLabel(c: CouponCardRow): string {
  if (c.audience !== 'selected') return '👥 всем своим';
  const names = (c.recipient_names || []).filter(Boolean);
  if (names.length > 0) return `👥 ${names.join(', ')}`;
  return `👥 ${c.user_ids.length} получател.`;
}

function CouponCard({
  c,
  archived,
  reason,
  onDelete,
}: {
  c: CouponCardRow;
  archived: boolean;
  reason: string;
  onDelete: (id: number) => void;
}) {
  return (
    <div key={c.id} className={`bundle-card${c.is_active && !archived ? '' : ' bundle-off'}`}>
      <div className="bundle-head">
        <strong>🎟 {c.code}</strong>
        <span className="bundle-chip">
          {c.kind === 'percent' ? `−${c.value}%` : `−${c.value} ₽`}
        </span>
        {archived && <span className="bundle-badge">{reason}</span>}
      </div>
      <div className="bundle-comp">
        <span className="bundle-chip" title={recipientsLabel(c)}>
          {recipientsLabel(c)}
        </span>
        <span className="bundle-chip">
          Использовано: {c.used_count}
          {c.max_uses ? ` из ${c.max_uses}` : ''}
        </span>
        {c.valid_until && (
          <span className="bundle-chip">до {new Date(c.valid_until).toLocaleString('ru-RU')}</span>
        )}
      </div>
      {!archived && (
        <div className="bundle-actions">
          {c.is_active && (
            <button
              className="btn btn-sm btn-delete"
              onClick={() => onDelete(c.id)}
              title="Выключить купон"
            >
              ✖
            </button>
          )}
        </div>
      )}
    </div>
  );
}

export default function CouponCards({
  coupons,
  showArchive,
  onToggleArchive,
  onDelete,
}: {
  coupons: CouponCardRow[];
  showArchive: boolean;
  onToggleArchive: () => void;
  onDelete: (id: number) => void;
}) {
  const now = Date.now();
  const live = coupons.filter((c) => !isCouponArchived(c, now));
  const archived = coupons.filter((c) => isCouponArchived(c, now));
  return (
    <div>
      <div className="bundle-list">
        {live.map((c) => (
          <CouponCard key={c.id} c={c} archived={false} reason="" onDelete={onDelete} />
        ))}
      </div>
      {archived.length > 0 && (
        <div style={{ marginTop: 12 }}>
          <button type="button" className="btn btn-ghost btn-sm" onClick={onToggleArchive}>
            {showArchive ? '▲ Скрыть архив' : `📦 Архив (${archived.length})`}
          </button>
          {showArchive && (
            <div className="bundle-list" style={{ marginTop: 8 }}>
              {archived.map((c) => (
                <CouponCard
                  key={c.id}
                  c={c}
                  archived
                  reason={archiveReason(c, now)}
                  onDelete={onDelete}
                />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
