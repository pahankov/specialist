import { useEffect, useState } from 'react';
import { toast } from 'sonner';
import { adminApi } from '../../api/client';
import { ConfirmDialog, Skeleton } from '../../components/common';
import { getApiErrorMessage } from '../../utils/apiError';
import { useSectionPrefix, SUPER_PREFIX } from '../../utils/section';
import './NotificationsPage.css';

const SUPER_AUDIENCES = [
  { value: 'all', label: '🌍 Всем (мастера + клиенты)' },
  { value: 'masters', label: '👨‍💼 Всем мастерам' },
  { value: 'clients', label: '👥 Всем клиентам' },
  { value: 'selected', label: '🎯 Отдельным (ID через запятую)' },
];

const MASTER_AUDIENCES = [
  { value: 'my_clients', label: '👥 Моим клиентам' },
  { value: 'selected', label: '🎯 Отдельным клиентам (ID через запятую)' },
];

function NotificationsPage() {
  const section = useSectionPrefix();
  const isSuperSection = section === SUPER_PREFIX;
  const audiences = isSuperSection ? SUPER_AUDIENCES : MASTER_AUDIENCES;
  const [audience, setAudience] = useState(isSuperSection ? 'clients' : 'my_clients');
  const [idsInput, setIdsInput] = useState('');
  const [text, setText] = useState('');
  const [counts, setCounts] = useState<{
    total: number;
    with_max: number;
    without_max: number;
    skipped_not_allowed: number;
  } | null>(null);
  const [countsLoading, setCountsLoading] = useState(false);
  const [sending, setSending] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [lastResult, setLastResult] = useState<{
    total: number;
    sent: number;
    skipped_no_max: number;
    skipped_not_allowed: number;
  } | null>(null);

  const parsedIds = idsInput
    .split(/[,;\s]+/)
    .map((s) => Number(s.trim()))
    .filter((n) => Number.isInteger(n) && n > 0)
    .slice(0, 500);

  useEffect(() => {
    let cancelled = false;
    const t = setTimeout(async () => {
      if (audience === 'selected' && parsedIds.length === 0) {
        setCounts(null);
        return;
      }
      setCountsLoading(true);
      try {
        const { data } = await adminApi.getNotificationCounts(
          audience,
          audience === 'selected' ? parsedIds.join(',') : undefined,
        );
        if (!cancelled) setCounts(data);
      } catch {
        if (!cancelled) setCounts(null);
      } finally {
        if (!cancelled) setCountsLoading(false);
      }
    }, 400);
    return () => {
      cancelled = true;
      clearTimeout(t);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [audience, idsInput]);

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
      toast.success(`Отправлено: ${data.sent} из ${data.total}`);
      if (data.skipped_no_max > 0) {
        toast.warning(`Без привязанного MAX пропущено: ${data.skipped_no_max}`);
      }
    } catch (err: unknown) {
      toast.error(getApiErrorMessage(err, 'Не удалось отправить'));
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="notifications-page">
      <div className="page-header">
        <div>
          <h1>🔔 Уведомления</h1>
          <p>
            {isSuperSection
              ? 'Рассылка всем, мастерам, клиентам или точечно — через MAX-бота'
              : 'Рассылка своим клиентам — через MAX-бота'}
          </p>
        </div>
      </div>

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
            <label>ID получателей через запятую</label>
            <input
              value={idsInput}
              onChange={(e) => setIdsInput(e.target.value)}
              placeholder="Например: 12, 45, 78"
              inputMode="numeric"
            />
            {idsInput.trim() && parsedIds.length === 0 && (
              <span className="hint-error">Нет корректных ID — только числа через запятую</span>
            )}
          </div>
        )}

        <div className="form-group">
          <label>Текст сообщения ({text.length}/4000)</label>
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value.slice(0, 4000))}
            rows={5}
            placeholder="Например: Напоминаем о записи завтра в 14:00. Для переноса напишите нам."
            style={{ resize: 'vertical' }}
          />
        </div>

        <div className="counts-row">
          {countsLoading ? (
            <Skeleton width="240px" height="20px" />
          ) : counts ? (
            <span className="counts">
              Получателей: <strong>{counts.total}</strong> · с MAX:{' '}
              <strong>{counts.with_max}</strong> · без MAX (пропуск): {counts.without_max}
              {counts.skipped_not_allowed > 0 && (
                <> · без доступа: {counts.skipped_not_allowed}</>
              )}
            </span>
          ) : (
            <span className="counts-muted">
              {audience === 'selected'
                ? 'Укажите ID, чтобы увидеть охват'
                : 'Охват подгружается…'}
            </span>
          )}
        </div>

        <p className="hint">
          💡 Доставка только тем, кто привязал MAX (вход через MAX-бота). Остальные попадут в
          «пропуск» — попросите их привязать MAX при следующем визите.
        </p>

        <div className="form-actions">
          <button
            className="btn btn-primary"
            disabled={sending || !text.trim() || (audience === 'selected' && parsedIds.length === 0)}
            onClick={() => setConfirmOpen(true)}
          >
            {sending ? 'Отправка…' : '📤 Отправить'}
          </button>
        </div>

        {lastResult && (
          <div className="result-box">
            ✅ Последний результат: отправлено {lastResult.sent} из {lastResult.total}
            {lastResult.skipped_no_max > 0 && ` (без MAX: ${lastResult.skipped_no_max})`}
            {lastResult.skipped_not_allowed > 0 &&
              ` (без доступа: ${lastResult.skipped_not_allowed})`}
          </div>
        )}
      </div>

      <ConfirmDialog
        open={confirmOpen}
        onClose={() => setConfirmOpen(false)}
        title="📤 Отправить рассылку?"
        message={`Получателей: ${counts?.total ?? '?'}, с MAX: ${counts?.with_max ?? '?'}. Отмена невозможна — сообщения уйдут сразу.`}
        confirmLabel="Отправить"
        onConfirm={handleSend}
      />
    </div>
  );
}

export default NotificationsPage;
