import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { superAdminApi } from '../../api/client';
import type { AuditLogEntry } from '../../api/types';
import { Skeleton, EmptyState, Modal } from '../../components/common';
import { getApiErrorMessage } from '../../utils/apiError';
import { getCookie } from '../../utils/cookies';
import { startImpersonation } from '../../utils/impersonation';
import { useSectionPrefix, ADMIN_PREFIX } from '../../utils/section';
import './MasterDetailPage.css';
import { statusLabels } from '../../constants/statusLabels';

type TabType = 'overview' | 'reviews' | 'audit' | 'sessions';

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

  const [master, setMaster] = useState<MasterFull | null>(null);
  const [auditLogs, setAuditLogs] = useState<AuditLogEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [auditLoading, setAuditLoading] = useState(false);
  const [activeTab, setActiveTab] = useState<TabType>('overview');
  const [sessions, setSessions] = useState<MasterSession[]>([]);
  const [sessionsLoading, setSessionsLoading] = useState(false);
  const [showPasswordModal, setShowPasswordModal] = useState(false);
  const [newPassword, setNewPassword] = useState('');
  const [actionBusy, setActionBusy] = useState(false);
  const [tariffDraft, setTariffDraft] = useState('');
  const [trialDraft, setTrialDraft] = useState('');
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
    } catch {
      // Ignore audit errors
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
                .catch(() => toast.error('Ошибка'))
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
                .catch(() => toast.error('Ошибка'))
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
      </div>

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
