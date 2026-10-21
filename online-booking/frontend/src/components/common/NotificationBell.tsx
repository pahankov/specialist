import { useCallback, useEffect, useRef, useState, type MouseEvent } from 'react';
import { createPortal } from 'react-dom';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { adminApi, cabinetApi } from '../../api/client';
import './NotificationBell.css';

interface BellItem {
  id: number;
  text: string;
  link?: string | null;
  kind?: string | null;
  appointment_id?: number | null;
  resolved_at?: string | null;
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

/** Exported for tests: every link shape must resolve to a real route. */
export function resolveTarget(bellLink: string, link: string | null | undefined): string {
  if (!link) return bellLink;
  // Links carry payloads ("appointments:42", "book:23") — never glue them
  // raw onto the URL ("/admin/appointments:42" matches no route and the
  // catch-all dumps the user on home). Parse every shape explicitly.
  const base = bellLink.endsWith('/notifications')
    ? bellLink.slice(0, -'/notifications'.length)
    : null;
  const inCabinet = bellLink.startsWith('/cabinet');
  if (link.startsWith('appointments')) {
    const id = link.split(':')[1];
    if (inCabinet || !base) return '/cabinet';
    return `${base}/appointments${id ? `?highlight=${id}` : ''}`;
  }
  if (link === 'reviews') {
    if (!inCabinet && base) return `${base}/profile#reviews`;
    return '/cabinet';
  }
  if (link === 'profile') {
    if (inCabinet) return '/cabinet/profile';
    return base ? `${base}/profile` : bellLink;
  }
  if (link === 'billing') {
    // Billing bells are master-bound; a dual-role master reading them in the
    // client cabinet still belongs on the master billing page.
    if (inCabinet) return '/admin/billing';
    return base ? `${base}/billing` : bellLink;
  }
  if (link.startsWith('book')) {
    const master = link.split(':')[1];
    return `/cabinet/book${master ? `?master_id=${master}` : ''}`;
  }
  if (link.startsWith('coupons')) {
    const id = link.split(':')[1];
    return `/cabinet/coupons${id ? `?highlight=${id}` : ''}`;
  }
  if (link.startsWith('review:')) {
    const id = link.split(':')[1];
    return `/cabinet${id ? `?review=${id}` : ''}`;
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
  const [visitBusy, setVisitBusy] = useState<number | null>(null);
  // Portal-anchored popover. The sidebar is a transformed, overflow:hidden
  // drawer on phones — even position:fixed children are clipped by it, which
  // cut the dropdown off at the 280px sidebar edge. Rendering into <body>
  // keeps it above the drawer and inside the real viewport.
  const btnRef = useRef<HTMLButtonElement>(null);
  const [pos, setPos] = useState({ top: 0, left: 0, width: 340, maxHeight: 440 });

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

  // The bell is an unread-only tray: read items live on the full page.
  const fetchRecent = useCallback(async () => {
    setLoading(true);
    setFailed(false);
    try {
      const { data } = await api.inbox({ page: 1, page_size: PAGE_SIZE, unread_only: true });
      setItems(data.items || []);
      setTotal(data.total || 0);
    } catch {
      setFailed(true);
    } finally {
      setLoading(false);
    }
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
      const margin = 8;
      const width = Math.max(200, Math.min(340, window.innerWidth - margin * 2));
      const top = Math.max(margin, Math.min(r.bottom + 8, window.innerHeight - 120));
      const left = Math.max(margin, Math.min(r.right - width, window.innerWidth - width - margin));
      setPos({
        top,
        left,
        width,
        maxHeight: Math.max(160, window.innerHeight - top - margin),
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
    // Read items leave the tray at once (full history is one click below).
    setItems((prev) => prev.filter((n) => n.id !== item.id));
    if (!item.is_read) {
      try {
        await api.read(item.id);
      } catch (err) {
        // Badge refresh below still converges.
        console.warn('[Bell] mark-read failed', item.id, err);
      }
      onRead?.();
    }
    if (!item.link) return;
    setOpen(false);
    // Cabinet review bells land straight in History (same as the inbox page).
    if (item.link === 'reviews' && bellLink.startsWith('/cabinet')) {
      navigate('/cabinet', { state: { scrollTo: 'history' } });
      return;
    }
    closeAndGo(resolveTarget(bellLink, item.link));
  };

  const handleReadAll = async () => {
    setItems([]);
    try {
      await api.readAll();
    } catch (err) {
      // Refresh below still converges.
      console.warn('[Bell] read-all failed', err);
    }
    onRead?.();
  };

  const handleVisitAnswer = async (
    item: BellItem,
    status: 'confirmed' | 'disputed',
    event: MouseEvent,
  ) => {
    event.stopPropagation();
    if (!item.appointment_id || visitBusy !== null) return;
    setVisitBusy(item.id);
    try {
      const { data } = await cabinetApi.confirmVisit(item.appointment_id, status);
      setItems((prev) => prev.filter((n) => n.id !== item.id));
      onRead?.();
      setOpen(false);
      if (status === 'confirmed') {
        navigate(data.review_url || `/cabinet?review=${item.appointment_id}`);
      } else {
        toast.success('Спасибо, запись отмечена как спорная');
      }
    } catch (err) {
      // Keep the prompt available — the client can retry.
      console.warn('[Bell] visit answer failed', item.id, err);
      toast.error('Не удалось сохранить ответ. Попробуйте ещё раз.');
    } finally {
      setVisitBusy(null);
    }
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

      {open &&
        createPortal(
          <>
            <div className="bell-backdrop" onClick={() => setOpen(false)} aria-hidden="true" />
            <div
              className="bell-pop"
              role="menu"
              aria-label="Уведомления"
              style={{
                top: pos.top,
                left: pos.left,
                width: pos.width,
                maxHeight: pos.maxHeight,
              }}
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
                    <div
                      key={n.id}
                      role={n.link ? 'button' : undefined}
                      tabIndex={n.link ? 0 : undefined}
                      className={`bell-item${n.is_read ? '' : ' unread'}${n.link ? ' linked' : ''}`}
                      onClick={() => handleItemClick(n)}
                      onKeyDown={(event) => {
                        if (n.link && (event.key === 'Enter' || event.key === ' ')) {
                          event.preventDefault();
                          handleItemClick(n);
                        }
                      }}
                      title={n.link ? 'Открыть' : undefined}
                    >
                      <span className="bell-item-dot" aria-hidden="true" />
                      <span className="bell-item-body">
                        <span className="bell-item-text">{n.text}</span>
                        <span className="bell-item-meta">
                          {n.sender_name ? `${n.sender_name} · ` : ''}
                          {n.created_at ? new Date(n.created_at).toLocaleString('ru-RU') : ''}
                        </span>
                        {scope === 'cabinet' && n.kind === 'visit_feedback' && n.appointment_id && (
                          <span className="bell-item-actions">
                            <button
                              type="button"
                              className="bell-action"
                              disabled={visitBusy !== null}
                              onClick={(event) => handleVisitAnswer(n, 'disputed', event)}
                            >
                              Не был
                            </button>
                            <button
                              type="button"
                              className="bell-action bell-action-primary"
                              disabled={visitBusy !== null}
                              onClick={(event) => handleVisitAnswer(n, 'confirmed', event)}
                            >
                              {visitBusy === n.id ? 'Сохраняем…' : 'Да, оценю'}
                            </button>
                          </span>
                        )}
                      </span>
                    </div>
                  ))
                )}
              </div>
              <div className="bell-pop-foot">
                <button type="button" className="bell-all" onClick={() => closeAndGo(bellLink)}>
                  Все уведомления{total > PAGE_SIZE ? ` (${total})` : ''} →
                </button>
              </div>
            </div>
          </>,
          document.body,
        )}
    </div>
  );
}

export default NotificationBell;
