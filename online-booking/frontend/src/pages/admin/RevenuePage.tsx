import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { adminApi, superAdminApi } from '../../api/client'
import type { DashboardStats, AdminStats } from '../../api/types'
import { Skeleton, EmptyState, MasterSelect } from '../../components/common'
import { getApiErrorMessage } from '../../utils/apiError'
import { useSectionPrefix } from '../../utils/section'
import '../../styles/filters.css'
import './RevenuePage.css'

interface RevenueBreakdown {
  breakdown: { name: string; revenue: number; count: number }[]
  total_revenue: number
}

function RevenuePage() {
  const navigate = useNavigate()
  const section = useSectionPrefix()
  const [stats, setStats] = useState<DashboardStats | AdminStats | null>(null)
  const [revenueBreakdown, setRevenueBreakdown] = useState<RevenueBreakdown | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [isGlobal, setIsGlobal] = useState(false)
  const [masterStats, setMasterStats] = useState<AdminStats | null>(null)
  const [groupBy, setGroupBy] = useState<'overall' | 'master' | 'service'>('overall')
  const [masterIdFilter, setMasterIdFilter] = useState<number | ''>('')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [allTime, setAllTime] = useState(true)

  useEffect(() => {
    setLoading(true)
    adminApi.getDashboard()
      .then(r => { setStats(r.data); setIsGlobal('total_masters' in r.data) })
      .catch((err: any) => {
        if (err.response?.status === 401) { window.location.href = '/admin/login' }
        else setError(getApiErrorMessage(err, 'Ошибка загрузки'))
      })
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    if (!isGlobal) return
    if (masterIdFilter === '') {
      setMasterStats(null)
      return
    }
    // Per-master mode: reload the WHOLE stat block for the master (with dates)
    const params: { date_from?: string; date_to?: string } = {}
    if (!allTime) {
      if (dateFrom) params.date_from = dateFrom
      if (dateTo) params.date_to = dateTo
    }
    superAdminApi.getMasterStats(masterIdFilter, params)
      .then(r => setMasterStats(r.data))
      .catch(() => setMasterStats(null))
  }, [masterIdFilter, dateFrom, dateTo, allTime, isGlobal])

  useEffect(() => {
    if (!isGlobal) return
    setLoading(true)
    const params: Record<string, unknown> = { by_master: groupBy === 'master', by_service: groupBy === 'service' }
    if (masterIdFilter !== '') params.master_id = masterIdFilter
    if (!allTime) {
      if (dateFrom) params.date_from = dateFrom
      if (dateTo) params.date_to = dateTo
    }
    adminApi.getRevenueBreakdown(params)
      .then(r => setRevenueBreakdown(r.data))
      .catch(() => setRevenueBreakdown(null))
      .finally(() => setLoading(false))
  }, [groupBy, masterIdFilter, dateFrom, dateTo, allTime, isGlobal])

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

  const g = (masterStats ?? stats) as AdminStats
  const statsScope = masterIdFilter === '' ? 'по всей системе' : 'по выбранному мастеру'
  const statusCounts = g.status_counts || {}
  const completedCount = statusCounts['completed'] || 0
  const confirmedCount = statusCounts['confirmed'] || 0
  const cancelledCount = statusCounts['cancelled'] || 0
  const pendingCount = statusCounts['pending'] || 0
  const avgRev = completedCount > 0 ? (g.total_revenue || 0) / completedCount : 0
  const revPerClient = g.total_clients > 0 ? (g.total_revenue || 0) / g.total_clients : 0
  const fmt = (v: number) => v.toLocaleString('ru-RU', { maximumFractionDigits: 0 })

  // Stat banners drill down: appointments (optionally by status) or clients,
  // scoped to the selected master when one is picked.
  const masterScope = masterIdFilter !== '' ? `&master_id=${masterIdFilter}` : ''
  const goAppointments = (status?: string) =>
    navigate(`${section}/appointments?${status ? `status=${status}&` : ''}${masterScope.replace(/^&/, '')}`)
  const goClients = () =>
    navigate(`${section}/clients${masterScope ? `?${masterScope.replace(/^&/, '')}` : ''}`)

  return (
    <div className="revenue-page">
      <div className="page-header"><h1>Доход</h1><p>Финансовая аналитика · {statsScope}</p></div>
      <div className="card" style={{ marginBottom: 16, padding: 16 }}>
        <h3 style={{ margin: '0 0 12px', fontSize: 16 }}>Фильтры дохода</h3>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 12 }}>
          <div className="filter-cell">
            <label className="filter-label">Группировка</label>
            <select className="filter-control" value={groupBy} onChange={(e) => setGroupBy(e.target.value as 'overall' | 'master' | 'service')}>
              <option value="overall">Общий доход</option>
              <option value="master">По мастерам</option>
              <option value="service">По услугам</option>
            </select>
          </div>
          <MasterSelect
            value={masterIdFilter}
            onChange={setMasterIdFilter}
            style={{ marginBottom: 0 }}
          />
          <div className="filter-cell">
            <label className="filter-label">Дата от</label>
            <input type="date" className="filter-control" value={dateFrom} disabled={allTime} onChange={(e) => setDateFrom(e.target.value)} />
          </div>
          <div className="filter-cell">
            <label className="filter-label">Дата до</label>
            <input type="date" className="filter-control" value={dateTo} disabled={allTime} onChange={(e) => setDateTo(e.target.value)} />
          </div>
          {/* Tied to the date fields: same row, right edge */}
          <div className="filter-cell-bottom" style={{ justifySelf: 'end' }}>
            <label className="filter-check">
              <input type="checkbox" checked={allTime} onChange={() => setAllTime(v => !v)} />
              За всё время
            </label>
          </div>
        </div>
        {(groupBy !== 'overall' || masterIdFilter !== '' || dateFrom || dateTo) && (
          <div style={{ display: 'flex', justifyContent: 'center', marginTop: 12 }}>
            <button className="btn filter-reset" onClick={() => { setGroupBy('overall'); setMasterIdFilter(''); setDateFrom(''); setDateTo('') }}>✕ Сбросить фильтры</button>
          </div>
        )}
      </div>
      {loading && !stats ? (
        <div className="revenue-stats-grid">
          <Skeleton width="100%" height="120px" /><Skeleton width="100%" height="120px" /><Skeleton width="100%" height="120px" /><Skeleton width="100%" height="120px" />
        </div>
      ) : (
        <>
          <div className="revenue-stats-grid">
            <div className="revenue-card main"><div className="revenue-card-icon">💰</div><div className="revenue-card-value">{revenueBreakdown ? fmt(revenueBreakdown.total_revenue) + ' ₽' : fmt(g.total_revenue) + ' ₽'}</div><div className="revenue-card-label">Общий доход</div><div className="revenue-card-sub">Завершённые записи</div></div>
            <div className="revenue-card clickable" onClick={() => goAppointments('completed')} title="Открыть завершённые записи"><div className="revenue-card-icon">🏁</div><div className="revenue-card-value">{completedCount}</div><div className="revenue-card-label">Завершённых</div><div className="revenue-card-sub">Ср. чек: {avgRev > 0 ? fmt(avgRev) : '—'} ₽</div></div>
            <div className="revenue-card clickable" onClick={goClients} title="Открыть клиентов"><div className="revenue-card-icon">👥</div><div className="revenue-card-value">{revPerClient > 0 ? fmt(revPerClient) : '—'} ₽</div><div className="revenue-card-label">Доход на клиента</div><div className="revenue-card-sub">{g.total_clients || 0} клиентов</div></div>
            <div className="revenue-card clickable" onClick={() => goAppointments()} title="Открыть все записи"><div className="revenue-card-icon">📅</div><div className="revenue-card-value">{g.total_appointments}</div><div className="revenue-card-label">Всего записей</div><div className="revenue-card-sub">Конверсия: {g.total_appointments > 0 ? Math.round((completedCount / g.total_appointments) * 100) : 0}%</div></div>
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
            <div className="status-card status-pending clickable" onClick={() => goAppointments('pending')} title="Открыть ожидающие"><div className="status-card-icon">⏳</div><div className="status-card-value">{pendingCount}</div><div className="status-card-label">Ожидают</div></div>
            <div className="status-card status-confirmed clickable" onClick={() => goAppointments('confirmed')} title="Открыть подтверждённые"><div className="status-card-icon">✅</div><div className="status-card-value">{confirmedCount}</div><div className="status-card-label">Подтверждены</div></div>
            <div className="status-card status-completed clickable" onClick={() => goAppointments('completed')} title="Открыть завершённые"><div className="status-card-icon">🏁</div><div className="status-card-value">{completedCount}</div><div className="status-card-label">Завершены</div></div>
            <div className="status-card status-cancelled clickable" onClick={() => goAppointments('cancelled')} title="Открыть отменённые"><div className="status-card-icon">❌</div><div className="status-card-value">{cancelledCount}</div><div className="status-card-label">Отменены</div></div>
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
