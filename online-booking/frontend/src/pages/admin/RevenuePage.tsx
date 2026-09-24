import { useEffect, useState } from 'react'
import { adminApi } from '../../api/client'
import type { DashboardStats, AdminStats } from '../../api/types'
import { Skeleton, EmptyState } from '../../components/common'
import './RevenuePage.css'

function RevenuePage() {
  const [stats, setStats] = useState<DashboardStats | AdminStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [isGlobal, setIsGlobal] = useState(false)

  useEffect(() => {
    setLoading(true)
    adminApi.getDashboard()
      .then(r => {
        setStats(r.data)
        setIsGlobal('total_masters' in r.data)
      })
      .catch((err: any) => {
        console.error('Revenue error:', err)
        if (err.response?.status === 401) {
          localStorage.removeItem('access_token')
          window.location.href = '/admin/login'
        } else {
          setError(err.response?.data?.detail || 'Ошибка загрузки')
        }
      })
      .finally(() => setLoading(false))
  }, [])

  if (error) return <div className="error-message">{error}</div>
  if (!stats) return null

  // Only show revenue for superadmin
  if (!isGlobal) {
    return (
      <div className="revenue-page">
        <div className="page-header">
          <h1>💰 Доход</h1>
          <p>Эта страница доступна только суперпользователю</p>
        </div>
        <EmptyState icon="🔒" title="Доступ ограничен" description="Страница дохода доступна только суперпользователю" />
      </div>
    )
  }

  const g = stats as AdminStats
  const statusCounts = g.status_counts || {}
  const completedCount = statusCounts['completed'] || 0
  const confirmedCount = statusCounts['confirmed'] || 0
  const cancelledCount = statusCounts['cancelled'] || 0
  const pendingCount = statusCounts['pending'] || 0

  const avgRevenuePerAppointment = completedCount > 0 ? (g.total_revenue || 0) / completedCount : 0
  const revenuePerClient = g.total_clients > 0 ? (g.total_revenue || 0) / g.total_clients : 0

  return (
    <div className="revenue-page">
      <div className="page-header">
        <h1>💰 Доход</h1>
        <p>Финансовая аналитика по записям и клиентам</p>
      </div>

      {loading ? (
        <div className="revenue-stats-grid">
          <Skeleton width="100%" height="120px" />
          <Skeleton width="100%" height="120px" />
          <Skeleton width="100%" height="120px" />
          <Skeleton width="100%" height="120px" />
        </div>
      ) : (
        <>
          {/* Top revenue cards */}
          <div className="revenue-stats-grid">
            <div className="revenue-card main">
              <div className="revenue-card-icon">💰</div>
              <div className="revenue-card-value">{g.total_revenue.toLocaleString('ru-RU')} ₽</div>
              <div className="revenue-card-label">Общий доход</div>
              <div className="revenue-card-sub">Завершённые записи</div>
            </div>
            <div className="revenue-card">
              <div className="revenue-card-icon">🏁</div>
              <div className="revenue-card-value">{completedCount}</div>
              <div className="revenue-card-label">Завершённых</div>
              <div className="revenue-card-sub">
                Ср. чек: {avgRevenuePerAppointment > 0 ? avgRevenuePerAppointment.toLocaleString('ru-RU', { maximumFractionDigits: 0 }) : '—'} ₽
              </div>
            </div>
            <div className="revenue-card">
              <div className="revenue-card-icon">👥</div>
              <div className="revenue-card-value">{revenuePerClient > 0 ? revenuePerClient.toLocaleString('ru-RU', { maximumFractionDigits: 0 }) : '—'} ₽</div>
              <div className="revenue-card-label">Доход на клиента</div>
              <div className="revenue-card-sub">{g.total_clients || 0} клиентов</div>
            </div>
            <div className="revenue-card">
              <div className="revenue-card-icon">📅</div>
              <div className="revenue-card-value">{g.total_appointments}</div>
              <div className="revenue-card-label">Всего записей</div>
              <div className="revenue-card-sub">
                Конверсия: {g.total_appointments > 0 ? Math.round((completedCount / g.total_appointments) * 100) : 0}%
              </div>
            </div>
          </div>

          {/* Status breakdown */}
          <div className="revenue-section">
            <h2>📊 Статусы записей</h2>
            <div className="status-cards">
              <div className="status-card status-pending">
                <div className="status-card-icon">⏳</div>
                <div className="status-card-value">{pendingCount}</div>
                <div className="status-card-label">Ожидают</div>
              </div>
              <div className="status-card status-confirmed">
                <div className="status-card-icon">✅</div>
                <div className="status-card-value">{confirmedCount}</div>
                <div className="status-card-label">Подтверждены</div>
              </div>
              <div className="status-card status-completed">
                <div className="status-card-icon">🏁</div>
                <div className="status-card-value">{completedCount}</div>
                <div className="status-card-label">Завершены</div>
              </div>
              <div className="status-card status-cancelled">
                <div className="status-card-icon">❌</div>
                <div className="status-card-value">{cancelledCount}</div>
                <div className="status-card-label">Отменены</div>
              </div>
            </div>
          </div>

          {/* Conversion funnel */}
          <div className="card full-width">
            <h3>📈 Воронка конверсии</h3>
            <div className="funnel-container">
              {g.total_appointments > 0 ? (
                <>
                  <div className="funnel-step">
                    <div className="funnel-bar" style={{ width: '100%' }}>
                      <span className="funnel-label">Всего записей</span>
                      <span className="funnel-value">{g.total_appointments}</span>
                    </div>
                  </div>
                  <div className="funnel-step">
                    <div className="funnel-bar confirmed-bar" style={{ width: `${(confirmedCount / g.total_appointments) * 100}%` }}>
                      <span className="funnel-label">Подтверждено</span>
                      <span className="funnel-value">{confirmedCount} ({Math.round((confirmedCount / g.total_appointments) * 100)}%)</span>
                    </div>
                  </div>
                  <div className="funnel-step">
                    <div className="funnel-bar completed-bar" style={{ width: `${(completedCount / g.total_appointments) * 100}%` }}>
                      <span className="funnel-label">Завершено</span>
                      <span className="funnel-value">{completedCount} ({Math.round((completedCount / g.total_appointments) * 100)}%)</span>
                    </div>
                  </div>
                  <div className="funnel-step">
                    <div className="funnel-bar cancelled-bar" style={{ width: `${(cancelledCount / g.total_appointments) * 100}%` }}>
                      <span className="funnel-label">Отменено</span>
                      <span className="funnel-value">{cancelledCount} ({Math.round((cancelledCount / g.total_appointments) * 100)}%)</span>
                    </div>
                  </div>
                </>
              ) : (
                <EmptyState icon="📊" title="Нет данных" description="Воронка появится после первых записей" />
              )}
            </div>
          </div>
        </>
      )}
    </div>
  )
}

export default RevenuePage
