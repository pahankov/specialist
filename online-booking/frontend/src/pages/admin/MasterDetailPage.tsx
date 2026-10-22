import { useEffect, useState } from 'react';
import { useParams, useNavigate, useSearchParams } from 'react-router-dom';
import { toast } from 'sonner';
import {
  billingApi,
  superAdminApi,
  type BillingInvoice,
  type BillingSummary,
} from '../../api/client';
import type { AuditLogEntry } from '../../api/types';
import { ConfirmDialog, Skeleton, EmptyState, Modal } from '../../components/common';
import { getApiErrorMessage } from '../../utils/apiError';
import { getCookie } from '../../utils/cookies';
import { startImpersonation } from '../../utils/impersonation';
import { useSectionPrefix, ADMIN_PREFIX } from '../../utils/section';
import './MasterDetailPage.css';
import { statusLabels } from '../../constants/statusLabels';

type TabType = 'overview' | 'reviews' | 'audit' | 'sessions' | 'billing';

function money(value: number | undefined | null): string {
  return `${Number(value ?? 0).toLocaleString('ru-RU', {
    minimumFractionDigits: Number.isInteger(Number(value ?? 0)) ? 0 : 2,
    maximumFractionDigits: 2,
  })} ₽`;
}

function shortDate(value?: string | null): string {
  if (!value) return '—';
  return new Date(value).toLocaleDateString('ru-RU');
}

interface MasterSession {
  id: number;
  created_at: string;
  expires_at: string;
}

interface MasterStats {
  total_appointments: number;
  status_counts: Record<string, number>;
  total_clients: number;
  total_services: number;
  total_revenue: number;
  avg_rating?: number | null;
  review_count: number;
}

interface MasterFull {
  id: number;
  user_id: number;
  name: string;
  email: string;
  phone?: string;
  telegram_username?: string;
  description?: string;
  avatar_url?: string;
  experience_years?: number;
  status: string;
  is_active: boolean;
  is_admin: boolean;
  tariff?: string;
  trial_ends_at?: string | null;
  created_at?: string;
  updated_at?: string;
  stats: MasterStats;
  recent_reviews: {
    id: number;
    client_name: string;
    client_phone: string;
    rating: number;
    comment?: string;
    is_published: boolean;
    created_at?: string;
  }[];
  recent_appointments: {
    id: number;
    client_name?: string;
    appointment_date?: string;
    status: string;
    service_name?: string;
    service_price: number;
  }[];
}

function MasterDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const section = useSectionPrefix();
  const [searchParams] = useSearchParams();
  const initialTab = searchParams.get('tab');

  const [master, setMaster] = useState<MasterFull | null>(null);
  const [auditLogs, setAuditLogs] = useState<AuditLogEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [auditLoading, setAuditLoading] = useState(false);
  const [activeTab, setActiveTab] = useState<TabType>(
    initialTab === 'billing' ||
      initialTab === 'reviews' ||
      initialTab === 'audit' ||
      initialTab === 'sessions'
      ? initialTab
      : 'overview',
  );
  const [sessions, setSessions] = useState<MasterSession[]>([]);
  const [sessionsLoading, setSessionsLoading] = useState(false);
  const [showPasswordModal, setShowPasswordModal] = useState(false);
  const [newPassword, setNewPassword] = useState('');
  const [actionBusy, setActionBusy] = useState(false);
  const [tariffDraft, setTariffDraft] = useState('');
  const [trialDraft, setTrialDraft] = useState('');
  const [billing, setBilling] = useState<BillingSummary | null>(null);
  const [billingLoading, setBillingLoading] = useState(false);
  const [creditAmount, setCreditAmount] = useState('');
  const [invoiceToPay, setInvoiceToPay] = useState<BillingInvoice | null>(null);
  // Placeholder for bulk selection (used in MastersPage, kept for future use)
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const [_selectedMasters, _setSelectedMasters] = useState<Set<number>>(new Set());

  const loadMaster = async () => {
    if (!id) return;
    setLoading(true);
    try {
      const { data } = await superAdminApi.getMasterFull(parseInt(id));
      setMaster(data);
    } catch (err: unknown) {
      const msg = getApiErrorMessage(err, 'Ошибка загрузки мастера');
      toast.error(msg);
    } finally {
      setLoading(false);
    }
  };

  const loadAuditLogs = async () => {
    if (!id) return;
    setAuditLoading(true);
    try {
      const auditResp = await superAdminApi.getMastersAudit(parseInt(id), 1, 50);
      setAuditLogs(auditResp.data.logs || []);
    } catch (err) {
      console.warn('[MasterDetail] audit log failed', err);
    } finally {
      setAuditLoading(false);
    }
  };

  useEffect(() => {
    loadMaster();
  }, [id]);
  useEffect(() => {
    if (activeTab === 'audit') loadAuditLogs();
  }, [activeTab, id]);
  useEffect(() => {
    if (activeTab === 'sessions') loadSessions();
  }, [activeTab, id]);
  useEffect(() => {
    if (activeTab === 'billing' && id) loadBilling();
  }, [activeTab, id]);

  const loadBilling = async () => {
    if (!id) return;
    setBillingLoading(true);
    try {
      const { data } = await billingApi.adminGet(parseInt(id));
      setBilling(data);
    } catch (err: unknown) {
      toast.error(getApiErrorMessage(err, 'Не удалось загрузить биллинг'));
    } finally {
      setBillingLoading(false);
    }
  };

  const handlePayInvoice = async () => {
    if (!invoiceToPay || actionBusy) return;
    setActionBusy(true);
    try {
      const { data } = await billingApi.payInvoice(invoiceToPay.id);
      setBilling(data.billing);
      setInvoiceToPay(null);
      toast.success('Платёж подтверждён, доступ обновлён');
    } catch (err: unknown) {
      toast.error(getApiErrorMessage(err, 'Не удалось подтвердить платёж'));
    } finally {
      setActionBusy(false);
    }
  };

  const handleAddCredit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!master || actionBusy) return;
    const amount = Number(creditAmount.replace(',', '.'));
    if (!Number.isFinite(amount) || amount <= 0) {
      toast.error('Введите сумму пополнения');
      return;
    }
    setActionBusy(true);
    try {
      const { data } = await billingApi.addCredit(master.id, {
        amount,
        note: 'Ручное начисление администратором',
      });
      setBilling(data.billing);
      setCreditAmount('');
      toast.success('Баланс пополнен');
    } catch (err: unknown) {
      toast.error(getApiErrorMessage(err, 'Не удалось пополнить баланс'));
    } finally {
      setActionBusy(false);
    }
  };

  const handleReviewAction = async (action: 'clear' | 'block') => {
    if (!master || actionBusy) return;
    setActionBusy(true);
    try {
      const { data } = await billingApi.reviewAction(master.id, action);
      setBilling(data.billing);
      toast.success(
        action === 'clear' ? 'Проверка снята, бонусы разблокированы' : 'Бонусы заблокированы',
      );
    } catch (err: unknown) {
      toast.error(getApiErrorMessage(err, 'Не удалось изменить статус проверки'));
    } finally {
      setActionBusy(false);
    }
  };

  const loadSessions = async () => {
    if (!id) return;
    setSessionsLoading(true);
    try {
      const { data } = await superAdminApi.getMasterSessions(parseInt(id));
      setSessions(data);
    } catch (err: unknown) {
      toast.error(getApiErrorMessage(err, 'Ошибка загрузки сессий'));
    } finally {
      setSessionsLoading(false);
    }
  };

  const handleImpersonate = async () => {
    if (!master || actionBusy) return;
    setActionBusy(true);
    try {
      const { data } = await superAdminApi.impersonateMaster(master.id);
      const adminToken = getCookie('access_token') ?? '';
      startImpersonation(adminToken, data.access_token, data.name);
      toast.success(`Вы вошли как ${data.name}`);
      navigate(`${ADMIN_PREFIX}/dashboard`);
      window.location.reload();
    } catch (err: unknown) {
      toast.error(getApiErrorMessage(err, 'Не удалось войти от имени мастера'));
    } finally {
      setActionBusy(false);
    }
  };

  const handlePasswordReset = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!master || actionBusy) return;
    setActionBusy(true);
    try {
      await superAdminApi.resetMasterPassword(master.id, newPassword);
      toast.success('Пароль обновлён, сессии отозваны');
      setShowPasswordModal(false);
      setNewPassword('');
    } catch (err: unknown) {
      toast.error(getApiErrorMessage(err, 'Не удалось сбросить пароль'));
    } finally {
      setActionBusy(false);
    }
  };

  const handleRevokeSessions = async () => {
    if (!master || actionBusy) return;
    setActionBusy(true);
    try {
      const { data } = await superAdminApi.revokeMasterSessions(master.id);
      toast.success(`Отозвано сессий: ${data.revoked ?? 0}`);
      loadSessions();
    } catch (err: unknown) {
      toast.error(getApiErrorMessage(err, 'Не удалось отозвать сессии'));
    } finally {
      setActionBusy(false);
    }
  };

  if (loading) {
    return (
      <div className="master-detail">
        <div className="detail-header">
          <button className="btn btn-ghost back-btn" onClick={() => navigate(`${section}/masters`)}>
            ← Назад к мастерам
          </button>
          <Skeleton width="300px" height="32px" />
        </div>
        <div className="detail-content">
          <Skeleton rows={3} height="60px" />
        </div>
      </div>
    );
  }

  if (!master) {
    return (
      <div className="master-detail">
        <button className="btn btn-ghost back-btn" onClick={() => navigate(`${section}/masters`)}>
          ← Назад
        </button>
        <EmptyState icon="👤" title="Мастер не найден" />
      </div>
    );
  }

  const ratingStars = master.stats.avg_rating
    ? '⭐'.repeat(Math.round(master.stats.avg_rating))
    : '—';

  return (
    <div className="master-detail">
      {/* Header */}
      <div className="detail-header">
        <button className="btn btn-ghost back-btn" onClick={() => navigate(`${section}/masters`)}>
          ← Назад к мастерам
        </button>
        <div className="detail-title">
          <h1>{master.name}</h1>
          <div className="detail-meta">
            <span
              className={`status-badge ${master.status === 'active' ? 'status-active' : 'status-inactive'}`}
            >
              {master.status === 'active'
                ? 'Активен'
                : master.status === 'suspended'
                  ? 'Заблокирован'
                  : 'Неактивен'}
            </span>
            {master.is_admin && <span className="role-badge role-admin">👑 Суперпользователь</span>}
            {master.telegram_username && (
              <span className="telegram-link">@{master.telegram_username}</span>
            )}
          </div>
        </div>
        <div className="detail-actions">
          <button
            className="btn btn-sm btn-success"
            onClick={() =>
              superAdminApi
                .toggleMasterActive(master.id)
                .then(() => loadMaster())
                .catch((err: unknown) =>
                  toast.error(getApiErrorMessage(err, 'Не удалось изменить статус')),
                )
            }
          >
            {master.is_active ? '🔒 Заблокировать' : '🔓 Разблокировать'}
          </button>
          <button
            className="btn btn-sm btn-warn"
            onClick={() =>
              superAdminApi
                .suspendMaster(master.id)
                .then(() => loadMaster())
                .catch((err: unknown) =>
                  toast.error(getApiErrorMessage(err, 'Не удалось заблокировать')),
                )
            }
          >
            ⏸ Заблокировать навсегда
          </button>
          <button
            className="btn btn-sm btn-secondary"
            onClick={handleImpersonate}
            disabled={actionBusy}
            title="Войти в панель глазами этого мастера (для поддержки)"
          >
            👁 Войти как
          </button>
          <button
            className="btn btn-sm btn-secondary"
            onClick={() => setShowPasswordModal(true)}
            title="Установить новый пароль (старые сессии будут отозваны)"
          >
            🔑 Сбросить пароль
          </button>
          <button
            className="btn btn-sm btn-primary"
            onClick={() => navigate(`${section}/masters/${master.id}/edit`)}
          >
            ✏️ Редактировать
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="detail-tabs">
        <button
          className={`tab-btn ${activeTab === 'overview' ? 'active' : ''}`}
          onClick={() => setActiveTab('overview')}
        >
          📊 Обзор
        </button>
        <button
          className={`tab-btn ${activeTab === 'reviews' ? 'active' : ''}`}
          onClick={() => setActiveTab('reviews')}
        >
          ⭐ Отзывы ({master.stats.review_count})
        </button>
        <button
          className={`tab-btn ${activeTab === 'audit' ? 'active' : ''}`}
          onClick={() => setActiveTab('audit')}
        >
          📋 Логи
        </button>
        <button
          className={`tab-btn ${activeTab === 'sessions' ? 'active' : ''}`}
          onClick={() => setActiveTab('sessions')}
        >
          🔐 Сессии
        </button>
        <button
          className={`tab-btn ${activeTab === 'billing' ? 'active' : ''}`}
          onClick={() => setActiveTab('billing')}
        >
          💳 Биллинг
        </button>
      </div>

      {/* Tab content */}
      <div className="detail-content">
        {activeTab === 'overview' && (
          <div className="overview-grid">
            {/* Stats cards */}
            <div className="stat-card card">
              <div className="stat-icon">📅</div>
              <div className="stat-value">{master.stats.total_appointments}</div>
              <div className="stat-label">Всего записей</div>
            </div>
            <div className="stat-card card">
              <div className="stat-icon">👥</div>
              <div className="stat-value">{master.stats.total_clients}</div>
              <div className="stat-label">Клиентов</div>
            </div>
            <div className="stat-card card">
              <div className="stat-icon">💰</div>
              <div className="stat-value">
                {master.stats.total_revenue.toLocaleString('ru-RU')} ₽
              </div>
              <div className="stat-label">Выручка</div>
            </div>
            <div className="stat-card card">
              <div className="stat-icon">⭐</div>
              <div className="stat-value">{master.stats.avg_rating || '—'}</div>
              <div className="stat-label">Рейтинг</div>
            </div>

            {/* Status breakdown */}
            <div className="card full-width">
              <h3>Статусы записей</h3>
              <div className="status-grid">
                {Object.entries(master.stats.status_counts).map(([status, count]) => (
                  <div key={status} className="status-item">
                    <span>{statusLabels[status] || status}</span>
                    <span className="status-count">{count}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Recent appointments */}
            <div className="card">
              <h3>Последние записи</h3>
              {master.recent_appointments.length === 0 ? (
                <EmptyState icon="📅" title="Нет записей" />
              ) : (
                <div className="appointment-list">
                  {master.recent_appointments.map((a) => (
                    <div key={a.id} className="appointment-row">
                      <div>
                        <div className="appt-client">{a.client_name || '—'}</div>
                        <div className="appt-service">{a.service_name || '—'}</div>
                      </div>
                      <div className="appt-date">
                        {a.appointment_date
                          ? new Date(a.appointment_date).toLocaleDateString('ru-RU')
                          : '—'}
                      </div>
                      <span className={`status-badge status-${a.status}`}>
                        {statusLabels[a.status] || a.status}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Info panel */}
            <div className="card">
              <h3>Информация</h3>
              <div className="info-list">
                <div className="info-row">
                  <span className="info-label">Email:</span>
                  <span className="info-value">{master.email}</span>
                </div>
                <div className="info-row">
                  <span className="info-label">Телефон:</span>
                  <span className="info-value">{master.phone || '—'}</span>
                </div>
                <div className="info-row">
                  <span className="info-label">Telegram:</span>
                  <span className="info-value">
                    {master.telegram_username ? `@${master.telegram_username}` : '—'}
                  </span>
                </div>
                <div className="info-row">
                  <span className="info-label">Тариф:</span>
                  <span className="info-value">
                    <select
                      value={tariffDraft || master.tariff || 'trial'}
                      onChange={(e) => setTariffDraft(e.target.value)}
                      style={{
                        padding: '4px 8px',
                        borderRadius: 6,
                        border: '2px solid #e0e0e0',
                        fontSize: 13,
                      }}
                      title="Сменить тариф"
                    >
                      <option value="trial">🆓 Триал</option>
                      <option value="basic">Базовый</option>
                      <option value="pro">Профи</option>
                      <option value="business">Бизнес</option>
                    </select>{' '}
                    <input
                      type="date"
                      value={
                        trialDraft ||
                        (master.trial_ends_at ? master.trial_ends_at.slice(0, 10) : '')
                      }
                      onChange={(e) => setTrialDraft(e.target.value)}
                      style={{
                        padding: '4px 8px',
                        borderRadius: 6,
                        border: '2px solid #e0e0e0',
                        fontSize: 13,
                      }}
                      title="Конец триала"
                    />
                    {(tariffDraft || trialDraft) && (
                      <button
                        className="btn btn-sm btn-primary"
                        style={{ marginLeft: 8 }}
                        disabled={actionBusy}
                        onClick={async () => {
                          setActionBusy(true);
                          try {
                            const patch: { tariff?: string; trial_ends_at?: string } = {};
                            if (tariffDraft) patch.tariff = tariffDraft;
                            if (trialDraft) patch.trial_ends_at = trialDraft;
                            await superAdminApi.updateMaster(master.id, patch);
                            toast.success('Тариф обновлён');
                            setTariffDraft('');
                            setTrialDraft('');
                            loadMaster();
                          } catch (err: unknown) {
                            toast.error(getApiErrorMessage(err, 'Не удалось обновить тариф'));
                          } finally {
                            setActionBusy(false);
                          }
                        }}
                      >
                        OK
                      </button>
                    )}
                  </span>
                </div>
                <div className="info-row">
                  <span className="info-label">Описание:</span>
                  <span className="info-value">{master.description || '—'}</span>
                </div>
                <div className="info-row">
                  <span className="info-label">Создан:</span>
                  <span className="info-value">
                    {master.created_at
                      ? new Date(master.created_at).toLocaleDateString('ru-RU')
                      : '—'}
                  </span>
                </div>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'reviews' && (
          <div>
            <div className="reviews-header">
              <h3>Отзывы клиента</h3>
              <div className="rating-summary">
                <span className="rating-big">{master.stats.avg_rating || '—'}</span>
                <span className="stars">{ratingStars}</span>
                <span className="review-count">{master.stats.review_count} отзывов</span>
              </div>
            </div>
            {master.recent_reviews.length === 0 ? (
              <EmptyState
                icon="⭐"
                title="Отзывов нет"
                description="Отзывы появятся после первых завершённых записей"
              />
            ) : (
              <div className="reviews-list">
                {master.recent_reviews.map((review) => (
                  <div key={review.id} className="review-card">
                    <div className="review-header">
                      <span className="review-client">{review.client_name}</span>
                      <span className="review-rating">
                        {'⭐'.repeat(Math.round(review.rating))}
                      </span>
                    </div>
                    {review.comment && <p className="review-comment">{review.comment}</p>}
                    <div className="review-meta">
                      <span>
                        {review.created_at
                          ? new Date(review.created_at).toLocaleDateString('ru-RU')
                          : ''}
                      </span>
                      {review.is_published ? (
                        <span className="published-badge">✓ Опубликован</span>
                      ) : (
                        <span className="unpublished-badge">⚠ Не опубликован</span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {activeTab === 'audit' && (
          <div>
            <h3>История действий</h3>
            {auditLoading ? (
              <Skeleton rows={3} height="48px" />
            ) : auditLogs.length === 0 ? (
              <EmptyState
                icon="📋"
                title="Логи пусты"
                description="Действия с мастером появятся в логах"
              />
            ) : (
              <div className="audit-list">
                {auditLogs.map((log) => (
                  <div key={log.id} className="audit-item">
                    <span className={`audit-level audit-${log.level}`}>{log.level}</span>
                    <div className="audit-content">
                      <div className="audit-action">
                        {log.action} — {log.entity_type} #{log.entity_id}
                      </div>
                      {log.details && <div className="audit-details">{log.details}</div>}
                    </div>
                    <span className="audit-time">
                      {log.created_at ? new Date(log.created_at).toLocaleString('ru-RU') : ''}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
        {activeTab === 'sessions' && (
          <div>
            <div className="reviews-header">
              <h3>Активные сессии</h3>
              <button
                className="btn btn-sm btn-delete"
                onClick={handleRevokeSessions}
                disabled={actionBusy || sessions.length === 0}
                title="Завершить все сессии мастера на всех устройствах"
              >
                Отозвать все
              </button>
            </div>
            {sessionsLoading ? (
              <Skeleton rows={2} height="48px" />
            ) : sessions.length === 0 ? (
              <EmptyState
                icon="🔐"
                title="Нет активных сессий"
                description="Мастер нигде не вошёл"
              />
            ) : (
              <div className="audit-list">
                {sessions.map((s) => (
                  <div key={s.id} className="audit-item">
                    <span className="audit-level audit-info">active</span>
                    <div className="audit-content">
                      <div className="audit-action">Сессия #{s.id}</div>
                      <div className="audit-details">
                        создана{' '}
                        {s.created_at ? new Date(s.created_at).toLocaleString('ru-RU') : '—'},
                        истекает{' '}
                        {s.expires_at ? new Date(s.expires_at).toLocaleString('ru-RU') : '—'}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
        {activeTab === 'billing' && (
          <div className="master-billing-tab">
            {billingLoading ? (
              <Skeleton rows={4} height="64px" />
            ) : !billing ? (
              <EmptyState icon="💳" title="Биллинг недоступен" />
            ) : (
              <>
                <div className="master-billing-top">
                  <div className="master-billing-stat">
                    <span>Доступ</span>
                    <strong className={`billing-admin-status status-${billing.access_status}`}>
                      {billing.access_status_label}
                    </strong>
                  </div>
                  <div className="master-billing-stat">
                    <span>К оплате</span>
                    <strong className={billing.balance.due > 0 ? 'text-danger' : ''}>
                      {money(billing.balance.due)}
                    </strong>
                  </div>
                  <div className="master-billing-stat">
                    <span>Баланс</span>
                    <strong className="text-success">{money(billing.balance.credit)}</strong>
                  </div>
                  <div className="master-billing-stat">
                    <span>Пробный период</span>
                    <strong>
                      {shortDate(billing.trial_started_at)} — {shortDate(billing.trial_ends_at)}
                    </strong>
                  </div>
                  <div className="master-billing-stat">
                    <span>Следующий счёт</span>
                    <strong>
                      {shortDate(billing.next_payment_at)} · {money(billing.next_payment_amount)}
                    </strong>
                  </div>
                </div>

                <div className="master-billing-actions">
                  <button className="btn btn-sm btn-secondary" onClick={loadBilling}>
                    ↻ Обновить
                  </button>
                  <button
                    className="btn btn-sm btn-secondary"
                    disabled={actionBusy}
                    onClick={async () => {
                      setActionBusy(true);
                      try {
                        const { data } = await billingApi.tick(master.id);
                        setBilling(data.billing);
                        toast.success('Биллинг пересчитан');
                      } catch (err: unknown) {
                        toast.error(getApiErrorMessage(err, 'Не удалось пересчитать'));
                      } finally {
                        setActionBusy(false);
                      }
                    }}
                  >
                    ⚙ Пересчитать
                  </button>
                  {billing.review_flag ? (
                    <button
                      className="btn btn-sm btn-success"
                      disabled={actionBusy}
                      onClick={() => handleReviewAction('clear')}
                    >
                      ✓ Снять проверку качества
                    </button>
                  ) : (
                    <button
                      className="btn btn-sm btn-warn"
                      disabled={actionBusy}
                      onClick={() => handleReviewAction('block')}
                    >
                      ⚠ Заблокировать бонусы
                    </button>
                  )}
                </div>

                {billing.review_flag && (
                  <div className="master-billing-alert">
                    Мастер на проверке качества: более 30% визитов не подтверждены. Бонус за текущий
                    месяц сохранён, будущие бонусы заблокированы.
                  </div>
                )}

                <section className="master-billing-section">
                  <h3>🧾 Счета</h3>
                  {billing.invoices.length === 0 ? (
                    <EmptyState icon="🧾" title="Счетов пока нет" />
                  ) : (
                    <div className="master-billing-table-wrap">
                      <table className="master-billing-table">
                        <thead>
                          <tr>
                            <th>Период</th>
                            <th>Сумма</th>
                            <th>Зачтено</th>
                            <th>Оплачено</th>
                            <th>К оплате</th>
                            <th>Срок</th>
                            <th>Статус</th>
                            <th />
                          </tr>
                        </thead>
                        <tbody>
                          {billing.invoices.map((invoice) => (
                            <tr key={invoice.id}>
                              <td>
                                {invoice.is_prepay
                                  ? `Предоплата · ${invoice.months ?? 1} мес.`
                                  : `Месяц ${invoice.period_index}`}
                              </td>
                              <td>
                                {money(invoice.amount)}
                                {invoice.is_prepay && invoice.base_amount ? (
                                  <span className="master-billing-subnote">
                                    зачислено {money(invoice.base_amount)}
                                  </span>
                                ) : null}
                              </td>
                              <td>{money(invoice.credits_applied)}</td>
                              <td>{money(invoice.paid_amount)}</td>
                              <td>
                                <strong>{money(invoice.due_amount)}</strong>
                              </td>
                              <td>{shortDate(invoice.due_at)}</td>
                              <td>
                                <span
                                  className={`billing-admin-pill ${
                                    invoice.status === 'paid'
                                      ? 'ok'
                                      : invoice.status === 'void'
                                        ? 'void'
                                        : 'warn'
                                  }`}
                                >
                                  {invoice.status_label}
                                </span>
                              </td>
                              <td>
                                {invoice.status !== 'paid' && invoice.due_amount > 0 && (
                                  <button
                                    className="btn btn-sm btn-success"
                                    onClick={() => setInvoiceToPay(invoice)}
                                  >
                                    Отметить оплату
                                  </button>
                                )}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                  <p className="master-billing-hint">
                    Оплата подтверждается вручную. После отметки счёт закрывается, доступ
                    восстанавливается в тот же день. Для предоплаты сумма зачисляется на баланс
                    мастера и закрывает будущие месячные счета.
                  </p>
                </section>

                <div className="master-billing-columns">
                  <section className="master-billing-section">
                    <h3>🎁 Бонус за клиентов</h3>
                    <div className="master-billing-kv">
                      <span>Подходящих клиентов</span>
                      <strong>
                        {billing.client_bonus.eligible_count} / {billing.client_bonus.max_count}
                      </strong>
                    </div>
                    <div className="master-billing-kv">
                      <span>Сумма</span>
                      <strong>{money(billing.client_bonus.amount)}</strong>
                    </div>
                    <div className="master-billing-kv">
                      <span>Статус</span>
                      <strong>{billing.client_bonus.status}</strong>
                    </div>
                    <div className="master-billing-kv">
                      <span>Проверка качества</span>
                      <strong>
                        {billing.client_bonus.unconfirmed_count} неподтв. из{' '}
                        {billing.client_bonus.prompted_count}
                      </strong>
                    </div>
                    <p className="master-billing-hint">
                      Оценка на 21-й день. Максимум 2 записи с клиента, 3 записи в день и 10
                      клиентов. Только записи, созданные клиентом из кабинета.
                    </p>
                  </section>

                  <section className="master-billing-section">
                    <h3>🤝 Рефералы</h3>
                    <div className="master-billing-kv">
                      <span>Код</span>
                      <code>{billing.referral_code}</code>
                    </div>
                    <div className="master-billing-kv">
                      <span>Зачтено</span>
                      <strong>
                        {billing.referral.qualified_count} / {billing.referral.max_count}
                      </strong>
                    </div>
                    <div className="master-billing-kv">
                      <span>Бонусы</span>
                      <strong>
                        {money(billing.referral.bonus_total)} / {money(billing.referral.max_amount)}
                      </strong>
                    </div>
                    {billing.referrals.length === 0 ? (
                      <p className="master-billing-hint">Приглашений пока нет.</p>
                    ) : (
                      <div className="master-billing-referrals">
                        {billing.referrals.map((referral) => (
                          <div key={referral.id} className="master-billing-referral">
                            <div>
                              <strong>{referral.referred_name}</strong>
                              <span>
                                {referral.qualified_count}/{referral.required_count} записей ·{' '}
                                {referral.status_label}
                              </span>
                            </div>
                            <span>{money(referral.amount)}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </section>
                </div>

                <section className="master-billing-section">
                  <h3>💎 Баланс и бонусы</h3>
                  <form className="master-billing-credit-form" onSubmit={handleAddCredit}>
                    <input
                      className="form-input"
                      inputMode="decimal"
                      value={creditAmount}
                      onChange={(event) => setCreditAmount(event.target.value)}
                      placeholder="Сумма, ₽"
                      aria-label="Сумма пополнения"
                    />
                    <button className="btn btn-primary" type="submit" disabled={actionBusy}>
                      Начислить на баланс
                    </button>
                  </form>
                  {billing.credits.length === 0 ? (
                    <p className="master-billing-hint">Начислений нет.</p>
                  ) : (
                    <div className="master-billing-credits">
                      {billing.credits.map((credit) => (
                        <div key={credit.id} className="master-billing-credit">
                          <div>
                            <strong>{credit.source_label}</strong>
                            <span>
                              {credit.note || 'Начисление'} · до {shortDate(credit.expires_at)}
                            </span>
                          </div>
                          <div>
                            <strong>{money(credit.remaining)}</strong>
                            <span>из {money(credit.amount)}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </section>
              </>
            )}
          </div>
        )}
      </div>

      <ConfirmDialog
        open={invoiceToPay !== null}
        onClose={() => setInvoiceToPay(null)}
        title="Подтвердить оплату"
        message={
          invoiceToPay
            ? invoiceToPay.is_prepay
              ? `Отметить счёт на предоплату (${invoiceToPay.months ?? 1} мес.) на ${money(
                  invoiceToPay.due_amount,
                )} оплаченным? Будет зачислено ${money(
                  invoiceToPay.base_amount ?? invoiceToPay.amount,
                )} на баланс для будущих счетов.`
              : `Отметить счёт за ${invoiceToPay.period_index}-й месяц на ${money(
                  invoiceToPay.due_amount,
                )} оплаченным?`
            : undefined
        }
        confirmLabel={actionBusy ? 'Сохраняем…' : 'Подтвердить оплату'}
        confirmDisabled={actionBusy}
        onConfirm={handlePayInvoice}
      />

      <Modal
        open={showPasswordModal}
        onClose={() => {
          setShowPasswordModal(false);
          setNewPassword('');
        }}
        title="🔑 Новый пароль мастера"
      >
        <form onSubmit={handlePasswordReset}>
          <div className="form-group">
            <label>Пароль (мин. 8 символов, Aa, цифра, спецсимвол)</label>
            <input
              type="text"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              placeholder="Сгенерируй и передай мастеру лично"
              required
              minLength={8}
              className="form-input"
            />
          </div>
          <div className="modal-actions">
            <button
              type="button"
              className="btn btn-ghost"
              onClick={() => setShowPasswordModal(false)}
            >
              Отмена
            </button>
            <button type="submit" className="btn btn-primary" disabled={actionBusy}>
              Установить
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
}

export default MasterDetailPage;
