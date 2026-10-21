import { useEffect, useState, type MouseEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { cabinetApi } from '../../api/client';
import { ConfirmDialog, EmptyState, Skeleton } from '../../components/common';
import { getApiErrorMessage } from '../../utils/apiError';
import './CabinetPage.css';

interface Note {
  id: number;
  text: string;
  audience?: string | null;
  link?: string | null;
  kind?: string | null;
  appointment_id?: number | null;
  resolved_at?: string | null;
  sender_name?: string | null;
  is_read: boolean;
  created_at?: string | null;
}

/** Client bells live here — never inside "Мои записи". */
function CabinetNotificationsPage() {
  const navigate = useNavigate();
  const [notes, setNotes] = useState<Note[]>([]);
  const [unread, setUnread] = useState(0);
  const [loading, setLoading] = useState(true);
  const [confirmClear, setConfirmClear] = useState(false);
  const [visitBusy, setVisitBusy] = useState<number | null>(null);

  const fetchNotes = async () => {
    try {
      const { data } = await cabinetApi.notificationsInbox({ page: 1, page_size: 20 });
      setNotes(data.items);
      setUnread(data.unread);
    } catch (err: unknown) {
      toast.error(getApiErrorMessage(err, 'Не удалось загрузить уведомления'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchNotes();
  }, []);

  const markRead = async (id: number) => {
    try {
      await cabinetApi.readNotification(id);
      setNotes((prev) => prev.map((x) => (x.id === id ? { ...x, is_read: true } : x)));
      setUnread((u) => Math.max(0, u - 1));
    } catch {
      /* badge heals on next poll */
    }
  };

  const readAll = async () => {
    try {
      await cabinetApi.readAllNotifications();
      setNotes((prev) => prev.map((x) => ({ ...x, is_read: true })));
      setUnread(0);
      toast.success('Все уведомления прочитаны');
    } catch (err: unknown) {
      toast.error(getApiErrorMessage(err, 'Не удалось отметить уведомления'));
    }
  };

  const clearAll = async () => {
    try {
      await cabinetApi.clearNotifications();
      setNotes([]);
      setUnread(0);
      toast.success('Уведомления очищены');
    } catch (err: unknown) {
      toast.error(getApiErrorMessage(err, 'Не удалось очистить уведомления'));
    } finally {
      setConfirmClear(false);
    }
  };

  const answerVisit = async (note: Note, status: 'confirmed' | 'disputed', event: MouseEvent) => {
    event.stopPropagation();
    if (!note.appointment_id || visitBusy !== null) return;
    setVisitBusy(note.id);
    try {
      const { data } = await cabinetApi.confirmVisit(note.appointment_id, status);
      if (status === 'confirmed') {
        navigate(data.review_url || `/cabinet?review=${note.appointment_id}`);
      } else {
        setNotes((prev) =>
          prev.map((item) =>
            item.id === note.id
              ? { ...item, is_read: true, resolved_at: new Date().toISOString() }
              : item,
          ),
        );
        setUnread((value) => Math.max(0, value - (note.is_read ? 0 : 1)));
        toast.success('Спасибо, запись отмечена как спорная');
      }
    } catch (err: unknown) {
      toast.error(getApiErrorMessage(err, 'Не удалось сохранить ответ'));
    } finally {
      setVisitBusy(null);
    }
  };

  if (loading) {
    return (
      <div className="cabinet-page">
        <Skeleton rows={5} />
      </div>
    );
  }

  return (
    <div className="cabinet-page">
      <div className="page-header">
        <h1>🔔 Уведомления{unread > 0 ? ` (${unread} новых)` : ''}</h1>
      </div>
      {(unread > 0 || notes.length > 0) && (
        <div
          style={{
            display: 'flex',
            gap: 8,
            marginBottom: 16,
            alignItems: 'center',
            justifyContent: 'flex-start',
          }}
        >
          {unread > 0 && (
            <button
              className="btn btn-sm btn-ghost"
              style={{ flex: '0 0 auto', width: 'auto' }}
              onClick={readAll}
            >
              ✓ Прочитать все
            </button>
          )}
          {notes.length > 0 && (
            <button
              className="btn btn-sm btn-ghost"
              style={{ flex: '0 0 auto', width: 'auto' }}
              onClick={() => setConfirmClear(true)}
            >
              🗑 Очистить
            </button>
          )}
        </div>
      )}
      {notes.length === 0 ? (
        <EmptyState title="Пока тихо" description="Подтверждения и отмены записей появятся здесь" />
      ) : (
        <div className="cabinet-list">
          {notes.map((n) => (
            <div
              key={n.id}
              className="cabinet-card"
              onClick={() => {
                if (n.link === 'reviews') navigate('/cabinet', { state: { scrollTo: 'history' } });
                else if (n.link && n.link.startsWith('review:')) {
                  navigate(`/cabinet?review=${n.link.split(':')[1]}`);
                } else if (n.link && n.link.startsWith('coupons')) {
                  const id = n.link.split(':')[1];
                  navigate(`/cabinet/coupons${id ? `?highlight=${id}` : ''}`);
                } else if (n.link && n.link.startsWith('book:'))
                  navigate(`/cabinet/book?master_id=${n.link.split(':')[1]}`);
                else if (n.link === 'book') navigate('/cabinet/book');
                else if (n.link === 'billing') navigate('/admin/billing');
                else if (n.link && n.link.startsWith('appointments')) navigate('/cabinet');
              }}
              style={n.link ? { cursor: 'pointer' } : undefined}
              title={
                n.link === 'reviews'
                  ? 'Открыть историю и оценить →'
                  : n.link && n.link.startsWith('coupons')
                    ? 'Открыть мои купоны →'
                    : n.link && n.link.startsWith('book')
                      ? 'Перейти к записи →'
                      : n.link && n.link.startsWith('appointments')
                        ? 'Открыть мои записи →'
                        : undefined
              }
            >
              <div className="cabinet-card-main">
                <span style={{ whiteSpace: 'pre-wrap' }}>{n.text}</span>
                <span className="cabinet-card-date">
                  {[
                    n.sender_name ? `от ${n.sender_name}` : null,
                    n.created_at ? new Date(n.created_at).toLocaleString('ru-RU') : null,
                  ]
                    .filter(Boolean)
                    .join(' · ')}
                </span>
              </div>
              <div className="cabinet-card-side">
                {n.kind === 'visit_feedback' && n.appointment_id && !n.resolved_at && (
                  <>
                    <button
                      className="btn btn-sm btn-ghost"
                      disabled={visitBusy !== null}
                      onClick={(event) => answerVisit(n, 'disputed', event)}
                    >
                      Не был
                    </button>
                    <button
                      className="btn btn-sm btn-primary"
                      disabled={visitBusy !== null}
                      onClick={(event) => answerVisit(n, 'confirmed', event)}
                    >
                      {visitBusy === n.id ? 'Сохраняем…' : 'Да, оценю'}
                    </button>
                  </>
                )}
                {!n.is_read && (
                  <button
                    className="btn btn-sm btn-ghost"
                    onClick={(e) => {
                      e.stopPropagation();
                      markRead(n.id);
                    }}
                  >
                    ✓ Прочитано
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      <ConfirmDialog
        open={confirmClear}
        onClose={() => setConfirmClear(false)}
        title="🗑 Очистить уведомления?"
        message="Все уведомления будут удалены без возможности восстановления."
        confirmLabel="Очистить"
        danger
        onConfirm={clearAll}
      />
    </div>
  );
}

export default CabinetNotificationsPage;
