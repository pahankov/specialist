import { useEffect, useState } from 'react'
import { superAdminApi } from '../../api/client'
import type { AdminStats } from '../../api/types'
import './GlobalStatsPage.css'

function GlobalStatsPage() {
  const [stats, setStats] = useState<AdminStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const loadStats = async () => {
      try {
        const { data } = await superAdminApi.getGlobalStats()
        setStats(data)
      } catch (err: any) {
        setError(err.response?.data?.detail || 'Ошибка загрузки статистики')
      } finally {
        setLoading(false)
      }
    }
    loadStats()
  }, [])

  if (loading) return <div className="loading-state">Загрузка статистики...</div>
  if (error) return <div className="error-state">{error}</div>
  if (!stats) return null

  const formatNumber = (n: number) => n.toLocaleString('ru-RU')
  const formatCurrency = (n: number) => n.toLocaleString('ru-RU', { minimumFractionDigits: 0, maximumFractionDigits: 0 }) + ' ₽'

  return (
    <div className="global-stats-page">
      <div className="page-header">
        <h1>📊 Глобальная статистика</h1>
      </div>

      {/* Summary cards */}
      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-icon">👨‍💼</div>
          <div className="stat-value">{formatNumber(stats.total_masters || 0)}</div>
          <div className="stat-label">Всего мастеров</div>
          <div className="stat-sub">{stats.active_masters != null ? formatNumber(stats.active_masters) + ' активных' : ''}</div>
        </div>
        <div className="stat-card">
          <div className="stat-icon">📅</div>
          <div className="stat-value">{formatNumber(stats.total_appointments || 0)}</div>
          <div className="stat-label">Всего записей</div>
        </div>
        <div className="stat-card">
          <div className="stat-icon">👥</div>
          <div className="stat-value">{formatNumber(stats.total_clients || 0)}</div>
          <div className="stat-label">Всего клиентов</div>
        </div>
        <div className="stat-card">
          <div className="stat-icon">💇</div>
          <div className="stat-value">{formatNumber(stats.total_services || 0)}</div>
          <div className="stat-label">Всего услуг</div>
        </div>
        <div className="stat-card stat-card-highlight">
          <div className="stat-icon">💰</div>
          <div className="stat-value">{formatCurrency(stats.total_revenue || 0)}</div>
          <div className="stat-label">Общий доход</div>
          <div className="stat-sub">завершённые записи</div>
        </div>
      </div>

      {/* Status breakdown */}
      {stats.status_counts && Object.keys(stats.status_counts).length > 0 && (
        <div className="stats-section">
          <h2>Записи по статусам</h2>
          <div className="status-breakdown">
            {Object.entries(stats.status_counts).map(([status, count]) => {
              const labels: Record<string, string> = {
                pending: '⏳ Ожидание',
                confirmed: '✅ Подтверждено',
                completed: '✔️ Завершено',
                cancelled: '❌ Отменено',
              }
              return (
                <div key={status} className="status-item">
                  <span className="status-label">{labels[status] || status}</span>
                  <span className="status-count">{formatNumber(count)}</span>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Recent appointments */}
      {stats.recent_appointments && stats.recent_appointments.length > 0 && (
        <div className="stats-section">
          <h2>Последние записи</h2>
          <div className="recent-appointments">
            {stats.recent_appointments.slice(0, 10).map((appt) => (
              <div key={appt.id} className="appointment-row">
                <div className="appt-master">{appt.master_name || '—'}</div>
                <div className="appt-client">{appt.client_name || '—'}</div>
                <div className="appt-date">{new Date(appt.appointment_date).toLocaleDateString('ru-RU')}</div>
                <div className={`appt-status appt-status-${appt.status}`}>
                  {appt.status === 'pending' && '⏳'}
                  {appt.status === 'confirmed' && '✅'}
                  {appt.status === 'completed' && '✔️'}
                  {appt.status === 'cancelled' && '❌'}
                  {' '}{appt.status}
                </div>
                {appt.service_price && (
                  <div className="appt-price">{formatCurrency(appt.service_price as number)}</div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Upcoming appointments */}
      {stats.upcoming_appointments && stats.upcoming_appointments.length > 0 && (
        <div className="stats-section">
          <h2>Предстоящие записи (7 дней)</h2>
          <div className="upcoming-appointments">
            {stats.upcoming_appointments.slice(0, 10).map((appt) => (
              <div key={appt.id} className="upcoming-row">
                <div className="appt-date">{new Date(appt.appointment_date).toLocaleDateString('ru-RU')}</div>
                <div className="appt-master">{appt.master_name || '—'}</div>
                <div className={`appt-status appt-status-${appt.status}`}>
                  {appt.status === 'pending' && '⏳'}
                  {appt.status === 'confirmed' && '✅'}
                  {appt.status === 'completed' && '✔️'}
                  {appt.status === 'cancelled' && '❌'}
                  {' '}{appt.status}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

export default GlobalStatsPage
