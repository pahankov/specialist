import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { adminApi } from '../../api/adminClient'
import type { DashboardStats } from '../../api/types'
import './DashboardPage.css'

function DashboardPage() {
  const [stats, setStats] = useState<DashboardStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    const fetchStats = async () => {
      try {
        const resp = await adminApi.getDashboard()
        setStats(resp.data)
      } catch (err: any) {
        if (err.response?.status === 401) {
          localStorage.removeItem('access_token')
          window.location.href = '/admin/login'
        } else {
          setError('Ошибка загрузки данных')
        }
      } finally {
        setLoading(false)
      }
    }

    fetchStats()
  }, [])

  if (loading) return <div className="admin-main"><div className="loading">Загрузка...</div></div>
  if (error) return <div className="admin-main"><div className="error-message">{error}</div></div>
  if (!stats) return null

  const statusLabels: Record<string, string> = {
    pending: '⏳ Ожидает',
    confirmed: '✅ Подтверждена',
    cancelled: '❌ Отменена',
    completed: '🏁 Завершена',
  }

  return (
    <div className="admin-main">
      <div className="page-header">
        <h1>Дашборд</h1>
        <p>Обзор вашей записи и статистики</p>
      </div>

      {/* Stats cards */}
      <div className="stats-grid">
        <div className="stat-card card">
          <div className="stat-icon">📅</div>
          <div className="stat-value">{stats.total_appointments}</div>
          <div className="stat-label">Всего записей</div>
        </div>

        <div className="stat-card card">
          <div className="stat-icon">👥</div>
          <div className="stat-value">{stats.total_clients}</div>
          <div className="stat-label">Клиентов</div>
        </div>

        <div className="stat-card card">
          <div className="stat-icon">💇</div>
          <div className="stat-value">{stats.total_services}</div>
          <div className="stat-label">Услуг</div>
        </div>

        <div className="stat-card card">
          <div className="stat-icon">💰</div>
          <div className="stat-value">{stats.total_revenue.toLocaleString('ru-RU')} ₽</div>
          <div className="stat-label">Доход</div>
        </div>
      </div>

      <div className="dashboard-grid">
        {/* Status breakdown */}
        <div className="card">
          <h3>Статусы записей</h3>
          <div className="status-list">
            {Object.entries(stats.status_counts).map(([status, count]) => (
              <div key={status} className="status-row">
                <span>{statusLabels[status] || status}</span>
                <span className="status-count">{count}</span>
              </div>
            ))}
            {Object.keys(stats.status_counts).length === 0 && (
              <p className="empty-state">Нет записей</p>
            )}
          </div>
        </div>

        {/* Upcoming appointments */}
        <div className="card">
          <div className="card-header">
            <h3>Ближайшие записи</h3>
            <Link to="/admin/appointments" className="link">Все →</Link>
          </div>
          <div className="appointment-list">
            {stats.upcoming_appointments.slice(0, 5).map((appt) => (
              <div key={appt.id} className="appointment-row">
                <span className="appt-date">
                  {new Date(appt.appointment_date).toLocaleDateString('ru-RU')}
                </span>
                <span className={`appt-status status-${appt.status}`}>
                  {statusLabels[appt.status] || appt.status}
                </span>
              </div>
            ))}
            {stats.upcoming_appointments.length === 0 && (
              <p className="empty-state">Нет ближайших записей</p>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

export default DashboardPage
