import { useEffect, useState } from 'react'
import { adminApi } from '../../api/client'
import type { DashboardStats, AdminStats } from '../../api/types'
import { Skeleton, EmptyState } from '../../components/common'
import './RevenuePage.css'

interface RevenueBreakdown {
  breakdown: Array<{ name: string; revenue: number; count: number }>
  total_revenue: number
}

function RevenuePage() {
  const [stats, setStats] = useState<DashboardStats | AdminStats | null>(null)
  const [revenueBreakdown, setRevenueBreakdown] = useState<RevenueBreakdown | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [isGlobal, setIsGlobal] = useState(false)
  const [groupBy, setGroupBy] = useState<'overall' | 'master' | 'service'>('overall')
  const [masterIdFilter, setMasterIdFilter] = useState<number | ''>('')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [allMasters, setAllMasters] = useState<Array<{ id: number; name: string }>>([])

  useEffect(() => {
    setLoading(true)
    adminApi.getDashboard()
      .then(r => { setStats(r.data); setIsGlobal('total_masters' in r.data) })
      .catch((err: any) => {
        if (err.response?.status === 401) { localStorage.removeItem('access_token'); window.location.href = '/admin/login' }
        else setError(err.response?.data?.detail || 'Ошибка загрузки')
      })
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    adminApi.get('/api/v1/admin/masters')
      .then(r => setAllMasters(r.data.map((m: any) => ({ id: m.id, name: m.name }))))
      .catch(() => {})
  }, [])

  useEffect(() => {
    if (!isGlobal) return
    setLoading(true)
    const params: Record<string, any> = { by_master: groupBy === 'master', by_service: groupBy === 'service' }
    if (masterIdFilter !== '') params.master_id = masterIdFilter
    if (dateFrom) params.date_from = dateFrom
    if (dateTo) params.date_to = dateTo
    adminApi.getRevenueBreakdown(params)
      .then(r => setRevenueBreakdown(r.data))
      .catch(() => setRevenueBreakdown(null))
      .finally(() => setLoading(false))
  }, [groupBy, masterIdFilter, dateFrom, dateTo, isGlobal])

  if (error) return <div className="error-message">{error}</div>
  if (!stats) return null

  if (!isGlobal) {
    return (
      <div className="revenue-page">
        <div className="page-header"><h1>Доход</h1><p>Доступно только суперпользователю</p></div>
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
  const avgRev = completedCount > 0 ? (g.total_revenue || 0) / completedCount : 0
  const revPerClient = g.total_clients > 0 ? (g.total_revenue || 0) / g.total_clients : 0
  const fmt = (v: number) => v.toLocaleString('ru-RU', { maximumFractionDigits: 0 })

  return (
    <div className="revenue-page">
      <div className="page-header"><h1>Доход</h1><p>Финансовая аналитика</p></div>
      <div className="card" style={{ marginBottom: 16, padding: 16 }}>
        <h3 style={{ margin: '0 0 12px', fontSize: 16 }}>Фильтры дохода</h3>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 12 }}>
          <div className="form-group" style={{ marginBottom: 0 }}>
            <label style={{ fontSize: 12, color: '#666', marginBottom: 4, display: 'block' }}>Группировка</label>
            <select value={groupBy} onChange={(e) => setGroupBy(e.target.value as any)} style={{ width: '100%', padding: 8, border: '2px solid #e0e0e0', borderRadius: 8, fontSize: 14 }}>
              <option value="overall">Общий доход</option>
              <option value="master">По мастерам</option>
              <option value="service">По услугам</option>
            </select>
          </div>
          <div className="form-group" style={{ marginBottom: 0 }}>
            <label style={{ fontSize: 12, color: '#666', marginBottom: 4, display: 'block' }}>Мастер</label>
            <select value={masterIdFilter} onChange={(e) => setMasterIdFilter(e.target.value as any)} style={{ width: '100%', padding: 8, border: '2px solid #e0e0e0', borderRadius: 8, fontSize: 14 }}>
              <option value="">Все мастера</option>
              {allMasters.map(m => (<option key={m.id} value={m.id}>{m.name}</option>))}
            </select>
          </div>
          <div className="form-group" style={{ marginBottom: 0 }}>
            <label style={{ fontSize: 12, color: '#666', marginBottom: 4, display: 'block' }}>Дата от</label>
            <input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} style={{ width: '100%', padding: 8, border: '2px solid #e0e0e0', borderRadius: 8, fontSize: 14 }} />
          </div>
          <div className="form-group" style={{ marginBottom: 0 }}>
            <label style={{ fontSize: 12, color: '#666', marginBottom: 4, display: 'block' }}>Дата до</label>
            <input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} style={{ width: '100%', padding: 8, border: '2px solid #e0e0e0', borderRadius: 8, fontSize: 14 }} />
          </div>
          {(groupBy !== 'overall' || masterIdFilter !== '' || dateFrom || dateTo) && (
            <div className="form-group" style={{ marginBottom: 0, display: 'flex', alignItems: 'flex-end' }}>
              <button className="btn btn-ghost" onClick={() => { setGroupBy('overall'); setMasterIdFilter(''); setDateFrom(''); setDateTo('') }} style={{ width: '100%', fontSize: 13 }}>Сбросить</button>
            </div>
          )}
        </div>
      </div>
      {loading && !stats ? (
        <div className="revenue-stats-grid">
          <Skeleton width="100%" height="120px" /><Skeleton width="100%" height="120px" /><Skeleton width="100%" height="120px" /><Skeleton width="100%" height="120px" />
        </div>
      ) : (
        <>
          <div className="revenue-stats-grid">
            <div className="revenue-card main"><div className="revenue-card-icon">💰</div><div className="revenue-card-value">{revenueBreakdown ? fmt(revenueBreakdown.total_revenue) + ' ₽' : fmt(g.total_revenue) + ' ₽'}</div><div className="revenue-card-label">Общий доход</div><div className="revenue-card-sub">Завершённые записи</div></div>
            <div className="revenue-card"><div className="revenue-card-icon">🏁</div><div className="revenue-card-value">{completedCount}</div><div className="revenue-card-label">Завершённых</div><div className="revenue-card-sub">Ср. чек: {avgRev > 0 ? fmt(avgRev) : '—'} ₽</div></div>
            <div className="revenue-card"><div className="revenue-card-icon">👥</div><div className="revenue-card-value">{revPerClient > 0 ? fmt(revPerClient) : '—'} ₽</div><div className="revenue-card-label">Доход на клиента</div><div className="revenue-card-sub">{g.total_clients || 0} клиентов</div></div>
            <div className="revenue-card"><div className="revenue-card-icon">📅</div><div className="revenue-card-value">{g.total_appointments}</div><div className="revenue-card-label">Всего записей</div><div className="revenue-card-sub">Конверсия: {g.total_appointments > 0 ? Math.round((completedCount / g.total_appointments) * 100) : 0}%</div></div>
          </div>
          {groupBy !== 'overall' && revenueBreakdown && revenueBreakdown.breakdown.length > 0 && (
            <div className="card full-width" style={{ marginBottom: 16 }}>
              <h3>Детализация дохода <span style={{ fontSize: 13, color: '#666', fontWeight: 'normal', marginLeft: 12 }}>({groupBy === 'master' ? 'по мастерам' : 'по услугам'})</span></h3>
              <table style={{ width: '100%', borderCollapse: 'collapse', marginTop: 12 }}>
                <thead><tr style={{ borderBottom: '2px solid #e0e0e0' }}><th style={{ padding: '10px 12px', textAlign: 'left', fontSize: 13, color: '#666' }}>Название</th><th style={{ padding: '10px 12px', textAlign: 'right', fontSize: 13, color: '#666' }}>Записей</th><th style={{ padding: '10px 12px', textAlign: 'right', fontSize: 13, color: '#666' }}>Доход</th><th style={{ padding: '10px 12px', textAlign: 'right', fontSize: 13, color: '#666' }}>Доля</th></tr></thead>
                <tbody>
                  {revenueBreakdown.breakdown.map((item, idx) => {
                    const share = revenueBreakdown.total_revenue > 0 ? (item.revenue / revenueBreakdown.total_revenue * 100) : 0
                    return (<tr key={idx} style={{ borderBottom: '1px solid #f0f0f0' }}><td style={{ padding: '10px 12px', fontWeight: 500 }}>{item.name}</td><td style={{ padding: '10px 12px', textAlign: 'right' }}>{item.count}</td><td style={{ padding: '10px 12px', textAlign: 'right', fontWeight: 600 }}>{fmt(item.revenue)} ₽</td><td style={{ padding: '10px 12px', textAlign: 'right' }}><span style={{ background: '#e8eaf6', padding: '2px 8px', borderRadius: 12, fontSize: 12 }}>{share.toFixed(1)}%</span></td></tr>)
                  })}
                </tbody>
              </table>
            </div>
          )}
          <div className="revenue-section"><h2>Статусы записей</h2><div className="status-cards">
            <div className="status-card status-pending"><div className="status-card-icon">⏳</div><div className="status-card-value">{pendingCount}</div><div className="status-card-label">Ожидают</div></div>
            <div className="status-card status-confirmed"><div className="status-card-icon">✅</div><div className="status-card-value">{confirmedCount}</div><div className="status-card-label">Подтверждены</div></div>
            <div className="status-card status-completed"><div className="status-card-icon">🏁</div><div className="status-card-value">{completedCount}</div><div className="status-card-label">Завершены</div></div>
            <div className="status-card status-cancelled"><div className="status-card-icon">❌</div><div className="status-card-value">{cancelledCount}</div><div className="status-card-label">Отменены</div></div>
          </div></div>
          <div className="card full-width"><h3>Воронка конверсии</h3><div className="funnel-container">
            {g.total_appointments > 0 ? <>
              <div className="funnel-step"><div className="funnel-bar" style={{ width: '100%' }}><span className="funnel-label">Всего записей</span><span className="funnel-value">{g.total_appointments}</span></div></div>
              <div className="funnel-step"><div className="funnel-bar confirmed-bar" style={{ width: `${(confirmedCount / g.total_appointments) * 100}%` }}><span className="funnel-label">Подтверждено</span><span className="funnel-value">{confirmedCount} ({Math.round((confirmedCount / g.total_appointments) * 100)}%)</span></div></div>
              <div className="funnel-step"><div className="funnel-bar completed-bar" style={{ width: `${(completedCount / g.total_appointments) * 100}%` }}><span className="funnel-label">Завершено</span><span className="funnel-value">{completedCount} ({Math.round((completedCount / g.total_appointments) * 100)}%)</span></div></div>
              <div className="funnel-step"><div className="funnel-bar cancelled-bar" style={{ width: `${(cancelledCount / g.total_appointments) * 100}%` }}><span className="funnel-label">Отменено</span><span className="funnel-value">{cancelledCount} ({Math.round((cancelledCount / g.total_appointments) * 100)}%)</span></div></div>
            </> : <EmptyState icon="📊" title="Нет данных" description="Воронка появится после первых записей" />}
          </div></div>
        </>
      )}
    </div>
  )
}

export default RevenuePage
