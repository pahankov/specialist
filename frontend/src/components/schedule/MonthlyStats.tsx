import type { MonthlyStats } from '../../api/types'
import { buildMonthlyStats, getMonthName } from './helpers'
import './ScheduleComponents.css'

interface MonthlyStatsComponentProps {
  currentMonth: Date
  stats: MonthlyStats | null
}

export function MonthlyStatsComponent({ currentMonth, stats }: MonthlyStatsComponentProps) {
  const items = buildMonthlyStats(stats)

  return (
    <div className="schedule-stats">
      <h3 className="stats-title">📊 Статистика за {getMonthName(currentMonth)}</h3>
      <div className="stats-grid">
        {stats ? items.map(item => (
          <div key={item.label} className="stat-card">
            <span className="stat-value">{item.value}</span>
            <span className="stat-label">{item.label}</span>
          </div>
        )) : (
          <div className="stat-loading">Загрузка...</div>
        )}
      </div>
    </div>
  )
}
