import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { adminApi } from '../../api/client'
import type { DashboardStats, AdminStats } from '../../api/types'
import './DashboardPage.css'

function DashboardPage() {
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

  if (loading) return <div><div className="loading">Загрузка...</div></div>
  if (error) return <div><div className="error-message">{error}</div></div>
  if (!stats) return null

  const statusLabels: Record<string, string> = { pending: '⏳ Ожидает', confirmed: '✅ Подтверждена', cancelled: '❌ Отменена', completed: '🏁 Завершена' }

  // Check if this is global stats (superadmin)
  const isGlobal = 'total_masters' in stats

  return (
    <div>
      <div className="page-header">
        <h1>{isGlobal ? '🍬 Глобальный дашборд' : 'Дашборд'}</h1>
        <p>{isGlobal ? 'Общая статистика по всей системе' : 'Обзор вашей записи и статистики'}</p>
      </div>
      <div className="stats-grid">
        {isGlobal && (
          <>
            <div className="stat-card card"><div className="stat-icon">👨‍💼</div><div className="stat-value">{(stats as AdminStats).total_masters || 0}</div><div className="stat-label">Всего мастеров</div></div>
            {(stats as AdminStats).active_masters != null && (
              <div className="stat-card card"><div className="stat-icon">✅</div><div className="stat-value">{(stats as AdminStats).active_masters}</div><div className="stat-label">Активных мастеров</div></div>
            )}
          </>
        )}
        <div className="stat-card card"><div className="stat-icon">📅</div><div className="stat-value">{stats.total_appointments}</div><div className="stat-label">Всего записей</div></div>
        <div className="stat-card card"><div className="stat-icon">👥</div><div className="stat-value">{stats.total_clients}</div><div className="stat-label">Клиентов</div></div>
        <div className="stat-card card"><div className="stat-icon">💇</div><div className="stat-value">{stats.total_services}</div><div className="stat-label">Услуг</div></div>
        <div className="stat-card card"><div className="stat-icon">💰</div><div className="stat-value">{stats.total_revenue.toLocaleString('ru-RU')} ₽</div><div className="stat-label">Доход</div></div>
      </div>
      <div className="dashboard-grid">
        <div className="card"><h3>Статусы записей</h3>
          <div className="status-list">
            {Object.entries(stats.status_counts).map(([s, c]) => (<div key={s} className="status-row"><span>{statusLabels[s] || s}</span><span className="status-count">{c}</span></div>))}
            {Object.keys(stats.status_counts).length === 0 && <p className="empty-state">Нет записей</p>}
          </div>
        </div>
        <div className="card">
          <div className="card-header"><h3>Ближайшие записи</h3><Link to="/admin/appointments" className="link">Все →</Link></div>
          <div className="appointment-list">
            {(stats.recent_appointments || []).slice(0, 5).map(a => (<div key={a.id} className="appointment-row">
              <div className="appt-info">
                {isGlobal && 'master_name' in a && (
                  <span className="appt-master">{(a as any).master_name || '—'}</span>
                )}
                <span className="appt-client">{a.client_name || '—'}</span>
                <span className="appt-service">{a.service_name || '—'}</span>
              </div>
              <span className="appt-date">{new Date(a.appointment_date).toLocaleString('ru-RU', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })}</span>
              <span className={`appt-status status-${a.status}`}>{statusLabels[a.status] || a.status}</span>
            </div>))}
            {(!stats.recent_appointments || stats.recent_appointments.length === 0) && <p className="empty-state">Нет записей</p>}
          </div>
        </div>
      </div>
    </div>
  )
}
export default DashboardPage
