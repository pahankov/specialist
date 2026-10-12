import { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { adminApi, cabinetApi } from '../../api/client';
import './NotificationBell.css';

interface BellItem {
  id: number;
  text: string;
  link?: string | null;
  sender_name?: string | null;
  is_read: boolean;
  created_at?: string | null;
}

interface NotificationBellProps {
  unread: number;
  /** Full inbox page (e.g. /admin/notifications) or section root (/cabinet). */
  bellLink: string;
  /** Which API family to use for inbox/reads. */
  scope: 'panel' | 'cabinet';
  /** Refresh the header badge after reads. */
  onRead?: () => void;
}

const PAGE_SIZE = 10;

function resolveTarget(bellLink: string, link: string | null | undefined): string {
  if (!link) return bellLink;
  // Panel inboxes live at <base>/notifications → linked rows jump to the
  // sibling page (e.g. <base>/appointments). Cabinet root has no sibling.
  if (bellLink.endsWith('/notifications')) {
    return `${bellLink.slice(0, -'/notifications'.length)}/${link}`;
  }
  return bellLink;
}

/**
 * Header bell with a dropdown of recent notifications (standard popover:
 * opens on click, closes on outside click / Escape / navigation).
 */
function NotificationBell({ unread, bellLink, scope, onRead }: NotificationBellProps) {
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<BellItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [failed, setFailed] = useState(false);
  // Fixed-anchored popover (the sidebar has overflow:hidden, which would
  // clip an absolutely-positioned child — incl. the collapsed 64px rail).
  const btnRef = useRef<HTMLButtonElement>(null);
  const [pos, setPos] = useState({ top: 0, left: 0 });

  const api =
    scope === 'cabinet'
      ? {
          inbox: cabinetApi.notificationsInbox,
          read: cabinetApi.readNotification,
          readAll: cabinetApi.readAllNotifications,
        }
      : {
          inbox: adminApi.getNotificationsInbox,
          read: adminApi.readNotification,
          readAll: adminApi.readAllNotifications,
        };

  const fetchRecent = useCallback(async () => {
    setLoading(true);
    setFailed(false);
    try {
      const { data } = await api.inbox({ page: 1, page_size: PAGE_SIZE });
      setItems(data.items || []);
      setTotal(data.total || 0);
    } catch {
      setFailed(true);
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scope]);

  useEffect(() => {
    if (open) fetchRecent();
  }, [open, fetchRecent]);

  // Anchor the fixed popover under the bell, clamped to the viewport.
  useEffect(() => {
    if (!open) return;
    const place = () => {
      const r = btnRef.current?.getBoundingClientRect();
      if (!r) return;
      const w = 340;
      setPos({
        top: r.bottom + 8,
        left: Math.max(8, Math.min(r.right - w, window.innerWidth - w - 8)),
      });
    };
    place();
    window.addEventListener('resize', place);
    return () => window.removeEventListener('resize', place);
  }, [open]);

  // Close on Escape.
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open]);

  const closeAndGo = (to: string) => {
    setOpen(false);
    navigate(to);
  };

  const handleItemClick = async (item: BellItem) => {
    if (!item.is_read) {
      setItems((prev) => prev.map((n) => (n.id === item.id ? { ...n, is_read: true } : n)));
      try {
        await api.read(item.id);
      } catch (err) {
        // Badge refresh below still converges.
        console.warn('[Bell] mark-read failed', item.id, err);
      }
      onRead?.();
    }
    if (item.link) closeAndGo(resolveTarget(bellLink, item.link));
  };

  const handleReadAll = async () => {
    try {
      await api.readAll();
    } catch (err) {
      // Refresh below still converges.
      console.warn('[Bell] read-all failed', err);
    }
    setItems((prev) => prev.map((n) => ({ ...n, is_read: true })));
    onRead?.();
  };

  return (
    <div className="bell-wrap">
      <button
        type="button"
        ref={btnRef}
        className="bell-btn"
        title={unread > 0 ? `Уведомления (${unread} новых)` : 'Уведомления'}
        aria-label="Уведомления"
        aria-expanded={open}
        aria-haspopup="true"
        onClick={() => setOpen((v) => !v)}
      >
        🔔
        {unread > 0 && <span className="bell-badge">{unread > 99 ? '99+' : unread}</span>}
      </button>

      {open && (
        <>
          <div className="bell-backdrop" onClick={() => setOpen(false)} aria-hidden="true" />
          <div
            className="bell-pop"
            role="menu"
            aria-label="Уведомления"
            style={{ top: pos.top, left: pos.left }}
          >
            <div className="bell-pop-head">
              <span>Уведомления{unread > 0 ? ` · ${unread} новых` : ''}</span>
              {unread > 0 && (
                <button type="button" className="bell-read-all" onClick={handleReadAll}>
                  Прочитать все
                </button>
              )}
            </div>
            <div className="bell-pop-list">
              {loading ? (
                <div className="bell-empty">Загрузка…</div>
              ) : failed ? (
                <div className="bell-empty">
                  Нет связи с сервером — он перезапускается или недоступен.
                  <button type="button" className="bell-retry" onClick={fetchRecent}>
                    Повторить
                  </button>
                </div>
              ) : items.length === 0 ? (
                <div className="bell-empty">🔕 Пока тихо</div>
              ) : (
                items.map((n) => (
                  <button
                    key={n.id}
                    type="button"
                    className={`bell-item${n.is_read ? '' : ' unread'}${n.link ? ' linked' : ''}`}
                    onClick={() => handleItemClick(n)}
                    title={n.link ? 'Открыть' : undefined}
                  >
                    <span className="bell-item-dot" aria-hidden="true" />
                    <span className="bell-item-body">
                      <span className="bell-item-text">{n.text}</span>
                      <span className="bell-item-meta">
                        {n.sender_name ? `${n.sender_name} · ` : ''}
                        {n.created_at ? new Date(n.created_at).toLocaleString('ru-RU') : ''}
                      </span>
                    </span>
                  </button>
                ))
              )}
            </div>
            <div className="bell-pop-foot">
              <button type="button" className="bell-all" onClick={() => closeAndGo(bellLink)}>
                Все уведомления{total > PAGE_SIZE ? ` (${total})` : ''} →
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

export default NotificationBell;
