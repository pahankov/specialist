import { useEffect, useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { adminApi } from '../../api/client'
import type { DashboardStats, AdminStats } from '../../api/types'
import { Skeleton, EmptyState } from '../../components/common'
import './DashboardPage.css'

function DashboardPage() {
  const navigate = useNavigate()
  const [stats, setStats] = useState<DashboardStats | AdminStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    setLoading(true)
    adminApi.getDashboard()
      .then(r => {
        setStats(r.data)
      })
      .catch((err: any) => {
        console.error('Dashboard error:', err)
        if (err.response?.status === 401) {
          localStorage.removeItem('access_token')
          window.location.href = '/admin/login'
        } else {
          const detail = err.response?.data?.detail || err.message || 'Неизвестная ошибка'
          setError(`Ошибка загрузки: ${detail}`)
        }
      })
      .finally(() => setLoading(false))
  }, [])

  if (error) return <div><div className="error-message">{error}</div></div>
  if (!stats) return null

  const statusLabels: Record<string, string> = { pending: '⏳ Ожидает', confirmed: '✅ Подтверждена', cancelled: '❌ Отменена', completed: '🏁 Завершена' }

  // Check if this is global stats (superadmin)
  const isGlobal = 'total_masters' in stats
  const g = stats as AdminStats

  const handleCardClick = (path: string) => {
    navigate(path)
  }

  const statusCounts = stats.status_counts || {}
  const pendingCount = statusCounts['pending'] || 0
  const confirmedCount = statusCounts['confirmed'] || 0
  const cancelledCount = statusCounts['cancelled'] || 0
  const completedCount = statusCounts['completed'] || 0

  const avgRevenuePerAppointment = completedCount > 0 ? (g.total_revenue || 0) / completedCount : 0

  return (
    <div className="dashboard-page">
      <div className="page-header">
        <h1>{isGlobal ? '🍬 Глобальный дашборд' : 'Дашборд'}</h1>
        <p>{isGlobal ? 'Общая статистика по всей системе' : 'Обзор вашей записи и статистики'}</p>
      </div>

      {loading ? (
        <div className="stats-grid">
          <Skeleton width="100%" height="120px" />
          <Skeleton width="100%" height="120px" />
          <Skeleton width="100%" height="120px" />
          <Skeleton width="100%" height="120px" />
          {isGlobal && <Skeleton width="100%" height="120px" />}
        </div>
      ) : (
        <>
          {/* ─── Main stat cards — clickable ─── */}
          <div className="stats-grid">
            {isGlobal && (
              <div className="stat-card clickable" onClick={() => handleCardClick('/admin/masters')}>
                <div className="stat-icon">👨‍💼</div>
                <div className="stat-value">{g.total_masters || 0}</div>
                <div className="stat-label">
                  Всего мастеров
                  {g.active_masters != null && (
                    <span className="stat-sub">
                      {' '}
                      <span className="stat-active">{g.active_masters}</span> активных
                    </span>
                  )}
                </div>
                <div className="card-hint">Нажмите для перехода →</div>
              </div>
            )}
            <div className="stat-card clickable" onClick={() => handleCardClick('/admin/appointments')}>
              <div className="stat-icon">📅</div>
              <div className="stat-value">{stats.total_appointments}</div>
              <div className="stat-label">Всего записей</div>
              <div className="card-hint">Нажмите для перехода →</div>
            </div>
            <div className="stat-card clickable" onClick={() => handleCardClick('/admin/clients')}>
              <div className="stat-icon">👥</div>
              <div className="stat-value">{stats.total_clients}</div>
              <div className="stat-label">Клиентов</div>
              <div className="card-hint">Нажмите для перехода →</div>
            </div>
            <div className="stat-card clickable" onClick={() => handleCardClick('/admin/services')}>
              <div className="stat-icon">💇</div>
              <div className="stat-value">{stats.total_services}</div>
              <div className="stat-label">Услуг</div>
              <div className="card-hint">Нажмите для перехода →</div>
            </div>
            <div className="stat-card clickable" onClick={() => handleCardClick('/admin/revenue')}>
              <div className="stat-icon">💰</div>
              <div className="stat-value">{stats.total_revenue.toLocaleString('ru-RU')} ₽</div>
              <div className="stat-label">Доход</div>
              <div className="card-hint">Нажмите для перехода →</div>
            </div>
          </div>

          {/* ─── Revenue breakdown section ─── */}
          <div className="revenue-section">
            <div className="section-title">
              <h2>💰 Весь доход</h2>
              <span className="section-subtitle">Детализация по статусам и метрикам</span>
            </div>

            <div className="revenue-grid">
              {/* Completed revenue */}
              <div className="revenue-card card">
                <div className="revenue-card-header">
                  <span className="revenue-card-icon">🏁</span>
                  <span className="revenue-card-title">Завершённые</span>
                </div>
                <div className="revenue-card-value">{completedCount}</div>
                <div className="revenue-card-amount">{(completedCount > 0 ? (g.total_revenue || 0) : 0).toLocaleString('ru-RU')} ₽</div>
                <div className="revenue-card-detail">
                  Ср. чек: {avgRevenuePerAppointment > 0 ? avgRevenuePerAppointment.toLocaleString('ru-RU', { maximumFractionDigits: 0 }) : '—'} ₽
                </div>
              </div>

              {/* Pending */}
              <div className="revenue-card card">
                <div className="revenue-card-header">
                  <span className="revenue-card-icon">⏳</span>
                  <span className="revenue-card-title">Ожидают</span>
                </div>
                <div className="revenue-card-value">{pendingCount}</div>
                <div className="revenue-card-detail">Ожидают подтверждения</div>
              </div>

              {/* Confirmed */}
              <div className="revenue-card card">
                <div className="revenue-card-header">
                  <span className="revenue-card-icon">✅</span>
                  <span className="revenue-card-title">Подтверждены</span>
                </div>
                <div className="revenue-card-value">{confirmedCount}</div>
                <div className="revenue-card-detail">Подтверждены, но не завершены</div>
              </div>

              {/* Cancelled */}
              <div className="revenue-card card">
                <div className="revenue-card-header">
                  <span className="revenue-card-icon">❌</span>
                  <span className="revenue-card-title">Отменены</span>
                </div>
                <div className="revenue-card-value">{cancelledCount}</div>
                <div className="revenue-card-detail">Отменены</div>
              </div>
            </div>

            {/* Conversion funnel */}
            <div className="card full-width">
              <h3>📊 Конверсия записей</h3>
              <div className="funnel-container">
                {stats.total_appointments > 0 ? (
                  <>
                    <div className="funnel-step">
                      <div className="funnel-bar" style={{ width: '100%' }}>
                        <span className="funnel-label">Всего записей</span>
                        <span className="funnel-value">{stats.total_appointments}</span>
                      </div>
                    </div>
                    <div className="funnel-step">
                      <div className="funnel-bar confirmed-bar" style={{ width: `${(confirmedCount / stats.total_appointments) * 100}%` }}>
                        <span className="funnel-label">Подтверждено</span>
                        <span className="funnel-value">{confirmedCount} ({Math.round((confirmedCount / stats.total_appointments) * 100)}%)</span>
                      </div>
                    </div>
                    <div className="funnel-step">
                      <div className="funnel-bar completed-bar" style={{ width: `${(completedCount / stats.total_appointments) * 100}%` }}>
                        <span className="funnel-label">Завершено</span>
                        <span className="funnel-value">{completedCount} ({Math.round((completedCount / stats.total_appointments) * 100)}%)</span>
                      </div>
                    </div>
                    <div className="funnel-step">
                      <div className="funnel-bar cancelled-bar" style={{ width: `${(cancelledCount / stats.total_appointments) * 100}%` }}>
                        <span className="funnel-label">Отменено</span>
                        <span className="funnel-value">{cancelledCount} ({Math.round((cancelledCount / stats.total_appointments) * 100)}%)</span>
                      </div>
                    </div>
                  </>
                ) : (
                  <EmptyState icon="📊" title="Нет данных" description="Конверсия появится после первых записей" />
                )}
              </div>
            </div>
          </div>

          {/* ─── Bottom grid ─── */}
          <div className="dashboard-grid">
            <div className="card"><h3>Статусы записей</h3>
              <div className="status-list">
                {Object.entries(statusCounts).map(([s, c]) => (
                  <div key={s} className="status-row">
                    <span>{statusLabels[s] || s}</span>
                    <span className="status-count">{c}</span>
                  </div>
                ))}
                {Object.keys(statusCounts).length === 0 && <EmptyState icon="📅" title="Нет записей" description="Записи появятся после бронирования" />}
              </div>
            </div>
            <div className="card">
              <div className="card-header"><h3>Ближайшие записи</h3><Link to="/admin/appointments" className="link">Все →</Link></div>
              <div className="appointment-list">
                {(g.recent_appointments || []).slice(0, 5).map(a => (
                  <div key={a.id} className="appointment-row">
                    <div className="appt-info">
                      {isGlobal && 'master_name' in a && (
                        <span className="appt-master">{(a as any).master_name || '—'}</span>
                      )}
                      <span className="appt-client">{a.client_name || '—'}</span>
                      <span className="appt-service">{a.service_name || '—'}</span>
                    </div>
                    <span className="appt-date">{new Date(a.appointment_date).toLocaleString('ru-RU', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })}</span>
                    <span className={`appt-status status-${a.status}`}>{statusLabels[a.status] || a.status}</span>
                  </div>
                ))}
                {(!g.recent_appointments || g.recent_appointments.length === 0) && <EmptyState icon="📭" title="Нет записей" description="Ближайшие записи появятся здесь" />}
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
export default DashboardPage
