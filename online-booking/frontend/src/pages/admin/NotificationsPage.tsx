import { useEffect, useState } from 'react';
import { toast } from 'sonner';
import { adminApi, superAdminApi } from '../../api/client';
import {
  ConfirmDialog,
  EmptyState,
  RecipientPicker,
  Skeleton,
  type RecipientOption,
} from '../../components/common';
import { getApiErrorMessage } from '../../utils/apiError';
import { useSectionPrefix, SUPER_PREFIX } from '../../utils/section';
import './NotificationsPage.css';

const SUPER_AUDIENCES = [
  { value: 'all', label: '🌍 Всем (мастера + клиенты)' },
  { value: 'masters', label: '👨‍💼 Всем мастерам' },
  { value: 'clients', label: '👥 Всем клиентам' },
  { value: 'selected', label: '🎯 Отдельным получателям' },
];

const MASTER_AUDIENCES = [
  { value: 'my_clients', label: '👥 Моим клиентам' },
  { value: 'selected', label: '🎯 Отдельным клиентам' },
];

interface InboxItem {
  id: number;
  text: string;
  audience?: string | null;
  sender_name?: string | null;
  is_read: boolean;
  created_at?: string | null;
}

function NotificationsPage() {
  const section = useSectionPrefix();
  const isSuperSection = section === SUPER_PREFIX;
  const audiences = isSuperSection ? SUPER_AUDIENCES : MASTER_AUDIENCES;
  const [tab, setTab] = useState<'send' | 'inbox'>('send');
  const [audience, setAudience] = useState(isSuperSection ? 'clients' : 'my_clients');
  const [text, setText] = useState('');
  const [count, setCount] = useState<number | null>(null);
  const [countsLoading, setCountsLoading] = useState(false);
  const [sending, setSending] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [lastResult, setLastResult] = useState<{
    total: number;
    created: number;
    skipped_not_allowed: number;
  } | null>(null);

  // Recipient picker for audience=selected (checkboxes + name search).
  const [recipients, setRecipients] = useState<RecipientOption[]>([]);
  const [recipientsLoading, setRecipientsLoading] = useState(false);
  const [picked, setPicked] = useState<Set<number>>(new Set());
  const parsedIds = [...picked];

  const [inbox, setInbox] = useState<InboxItem[]>([]);
  const [unread, setUnread] = useState(0);
  const [inboxLoading, setInboxLoading] = useState(false);

  useEffect(() => {
    if (audience !== 'selected') return;
    let cancelled = false;
    (async () => {
      setRecipientsLoading(true);
      try {
        const clientsResp = await adminApi.getClients({ page: 1, page_size: 500 });
        const list: RecipientOption[] = (clientsResp.data.items || []).map((c) => ({
          id: c.id,
          name: c.name,
          sub: c.phone || undefined,
        }));
        if (isSuperSection) {
          try {
            const { data: masters } = await superAdminApi.getAllMasters();
            for (const m of masters as { id: number; user_id: number; name: string }[]) {
              list.push({ id: m.user_id, name: m.name, sub: 'мастер' });
            }
          } catch {
            /* clients alone are enough */
          }
        }
        if (!cancelled) {
          // Drop picks that vanished (e.g. section switch).
          const ids = new Set(list.map((r) => r.id));
          setPicked((prev) => new Set([...prev].filter((id) => ids.has(id))));
          setRecipients(list);
        }
      } catch {
        if (!cancelled) setRecipients([]);
      } finally {
        if (!cancelled) setRecipientsLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [audience]);

  useEffect(() => {
    let cancelled = false;
    const t = setTimeout(async () => {
      if (audience === 'selected' && parsedIds.length === 0) {
        setCount(null);
        return;
      }
      setCountsLoading(true);
      try {
        const { data } = await adminApi.getNotificationCounts(
          audience,
          audience === 'selected' ? parsedIds.join(',') : undefined,
        );
        if (!cancelled) setCount(data.total);
      } catch {
        if (!cancelled) setCount(null);
      } finally {
        if (!cancelled) setCountsLoading(false);
      }
    }, 400);
    return () => {
      cancelled = true;
      clearTimeout(t);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [audience, picked]);

  const fetchInbox = async () => {
    setInboxLoading(true);
    try {
      const { data } = await adminApi.getNotificationsInbox({ page: 1, page_size: 50 });
      setInbox(data.items);
      setUnread(data.unread);
    } catch (err: unknown) {
      toast.error(getApiErrorMessage(err, 'Не удалось загрузить входящие'));
    } finally {
      setInboxLoading(false);
    }
  };

  useEffect(() => {
    if (tab === 'inbox') fetchInbox();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab]);

  const handleSend = async () => {
    if (!text.trim()) {
      toast.error('Введите текст сообщения');
      return;
    }
    if (audience === 'selected' && parsedIds.length === 0) {
      toast.error('Укажите ID получателей');
      return;
    }
    setSending(true);
    try {
      const { data } = await adminApi.broadcastNotification({
        audience,
        ...(audience === 'selected' ? { user_ids: parsedIds } : {}),
        text: text.trim(),
      });
      setLastResult(data);
      setConfirmOpen(false);
      setText('');
      toast.success(`В колокольчики доставлено: ${data.created} из ${data.total}`);
    } catch (err: unknown) {
      toast.error(getApiErrorMessage(err, 'Не удалось отправить'));
    } finally {
      setSending(false);
    }
  };

  const handleRead = async (id: number) => {
    try {
      await adminApi.readNotification(id);
      setInbox((prev) => prev.map((n) => (n.id === id ? { ...n, is_read: true } : n)));
      setUnread((u) => Math.max(0, u - 1));
    } catch {
      /* ignore */
    }
  };

  const handleReadAll = async () => {
    try {
      await adminApi.readAllNotifications();
      setInbox((prev) => prev.map((n) => ({ ...n, is_read: true })));
      setUnread(0);
    } catch (err: unknown) {
      toast.error(getApiErrorMessage(err, 'Не удалось отметить прочитанным'));
    }
  };

  return (
    <div className="notifications-page">
      <div className="page-header">
        <div>
          <h1>🔔 Уведомления</h1>
          <p>
            {isSuperSection
              ? 'Внутренняя рассылка: всем, мастерам, клиентам или точечно'
              : 'Внутренняя рассылка своим клиентам + ваши входящие'}
          </p>
        </div>
        <div className="page-header-actions">
          <button
            className={`btn ${tab === 'send' ? 'btn-primary' : 'btn-ghost'}`}
            onClick={() => setTab('send')}
          >
            📤 Отправить
          </button>
          <button
            className={`btn ${tab === 'inbox' ? 'btn-primary' : 'btn-ghost'}`}
            onClick={() => setTab('inbox')}
          >
            📥 Входящие{unread > 0 ? ` (${unread})` : ''}
          </button>
        </div>
      </div>

      {tab === 'send' ? (
        <div className="card" style={{ marginBottom: 16 }}>
          <div className="form-group">
            <label>Кому отправить</label>
            <select value={audience} onChange={(e) => setAudience(e.target.value)}>
              {audiences.map((a) => (
                <option key={a.value} value={a.value}>
                  {a.label}
                </option>
              ))}
            </select>
          </div>

          {audience === 'selected' && (
            <div className="form-group">
              <label>Получатели</label>
              <RecipientPicker
                items={recipients}
                selected={picked}
                onChange={setPicked}
                loading={recipientsLoading}
                placeholder="Введите имя для поиска..."
              />
            </div>
          )}

          <div className="form-group">
            <label>Текст сообщения ({text.length}/4000)</label>
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value.slice(0, 4000))}
              rows={5}
              placeholder="Например: С 1 ноября новые часы работы — смотрите расписание."
              style={{ resize: 'vertical' }}
            />
          </div>

          <div className="counts-row">
            {countsLoading ? (
              <Skeleton width="200px" height="20px" />
            ) : count !== null ? (
              <span className="counts">
                Получателей: <strong>{count}</strong> — сообщение появится у них в колокольчике
              </span>
            ) : (
              <span className="counts-muted">
                {audience === 'selected'
                  ? 'Отметьте получателей выше, чтобы увидеть охват'
                  : 'Охват подгружается…'}
              </span>
            )}
          </div>

          <div className="form-actions">
            <button
              className="btn btn-primary"
              disabled={
                sending || !text.trim() || (audience === 'selected' && parsedIds.length === 0)
              }
              onClick={() => setConfirmOpen(true)}
            >
              {sending ? 'Отправка…' : '📤 Отправить'}
            </button>
          </div>

          {lastResult && (
            <div className="result-box">
              ✅ Доставлено в колокольчики: {lastResult.created} из {lastResult.total}
              {lastResult.skipped_not_allowed > 0 &&
                ` (без доступа: ${lastResult.skipped_not_allowed})`}
            </div>
          )}
        </div>
      ) : (
        <div className="card">
          <div className="card-header">
            <h3>
              Входящие {unread > 0 && <span className="client-count">({unread} новых)</span>}
            </h3>
            {unread > 0 && (
              <button className="btn btn-ghost" onClick={handleReadAll}>
                ✓ Прочитать все
              </button>
            )}
          </div>
          {inboxLoading ? (
            <Skeleton rows={4} />
          ) : inbox.length === 0 ? (
            <EmptyState title="Пока тихо" description="Входящих уведомлений нет" icon="🔕" />
          ) : (
            <div className="inbox-list">
              {inbox.map((n) => (
                <div key={n.id} className={`inbox-item${n.is_read ? '' : ' unread'}`}>
                  <div className="inbox-text">{n.text}</div>
                  <div className="inbox-meta">
                    {n.sender_name && <span>от {n.sender_name}</span>}
                    {n.created_at && (
                      <span>{new Date(n.created_at).toLocaleString('ru-RU')}</span>
                    )}
                    {!n.is_read && (
                      <button className="btn btn-sm btn-ghost" onClick={() => handleRead(n.id)}>
                        ✓ Прочитано
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      <ConfirmDialog
        open={confirmOpen}
        onClose={() => setConfirmOpen(false)}
        title="📤 Отправить рассылку?"
        message={`Получателей: ${count ?? '?'}. Сообщение появится в их колокольчике.`}
        confirmLabel="Отправить"
        onConfirm={handleSend}
      />
    </div>
  );
}

export default NotificationsPage;
