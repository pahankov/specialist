import { useEffect, useState } from 'react'
import { adminApi } from '../../api/client'
import './LogsPage.css'

function getCookie(name: string): string | null {
  const match = document.cookie.match(new RegExp('(^| )' + name + '=([^;]+)'))
  return match ? match[2] : null
}

function getIsAdmin(): boolean {
  const token = getCookie('access_token')
  if (!token) return false
  try {
    const payload = JSON.parse(atob(token.split('.')[1]))
    return payload.is_admin === true
  } catch {
    return false
  }
}

function LogsPage() {
  const isAdmin = getIsAdmin()
  const [logs, setLogs] = useState<any[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [entityFilter, setEntityFilter] = useState('')
  const [masterFilter, setMasterFilter] = useState('')
  const [currentPage, setCurrentPage] = useState(0)
  const pageSize = 20

  const entityLabels: Record<string, string> = {
    appointment: '📅 Запись',
    service: '💇 Услуга',
    client: '👤 Клиент',
    working_hour: '🕐 Расписание',
    master: '👨‍💼 Мастер'
  }

  const actionLabels: Record<string, string> = {
    confirm: '✅ Подтверждение',
    cancel: '❌ Отмена',
    complete: '🏁 Завершение',
    delete: '🗑️ Удаление',
    create: '➕ Создание',
    update: '✏️ Обновление',
    toggle_active: '🔒 Блокировка',
    toggle_admin: '👑 Смена прав',
    'no-show': '⚠️ Неявка'
  }

  const levelLabels: Record<string, string> = {
    info: 'ℹ️ INFO',
    warning: '⚠️ WARNING',
    error: '🚫 ERROR'
  }

  const fetchLogs = async () => {
    try {
      const params: Record<string, any> = { limit: pageSize, offset: currentPage * pageSize }
      if (entityFilter) params.entity_type = entityFilter
      if (masterFilter) params.master_id = masterFilter

      // Superadmin uses /audit-logs/all, regular master uses /audit-logs (filtered by master_id)
      const endpoint = isAdmin ? '/api/v1/admin/audit-logs/all' : '/api/v1/admin/audit-logs'
      const resp = await adminApi.get(endpoint, { params })
      setLogs(resp.data.logs)
      setTotal(resp.data.total)
    } catch (err: any) {
      if (err.response?.status === 401) {
        window.location.href = '/admin/login'
      } else {
        const detail = err.response?.data?.detail || err.message || 'Ошибка загрузки логов'
        setError(typeof detail === 'string' ? detail : JSON.stringify(detail))
      }
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    setLoading(true)
    fetchLogs()
  }, [entityFilter, masterFilter, currentPage])

  if (loading) return <div><div className="loading">Загрузка...</div></div>
  if (error) return <div><div className="error-message">{error}</div></div>

  const entityFilters = [
    { value: '', label: 'Все' },
    { value: 'appointment', label: '📅 Записи' },
    { value: 'service', label: '💇 Услуги' },
    { value: 'client', label: '👤 Клиенты' },
    { value: 'master', label: '👨‍💼 Мастера' }
  ]

  return (
    <div>
      <div className="page-header"><h1>📋 Журнал действий</h1><p>История всех операций в системе</p></div>

      {/* Entity filter */}
      <div className="filters-bar">
        {entityFilters.map(f => (
          <button
            key={f.value}
            className={`filter-btn ${entityFilter === f.value ? 'active' : ''}`}
            onClick={() => { setEntityFilter(f.value); setCurrentPage(0) }}
          >
            {f.label}
          </button>
        ))}
      </div>

      {/* Master filter (superadmin only) */}
      {isAdmin && (
        <div className="filters-bar" style={{ marginTop: 8 }}>
          <input
            type="text"
            placeholder="Фильтр по ID мастера..."
            value={masterFilter}
            onChange={(e) => { setMasterFilter(e.target.value); setCurrentPage(0) }}
            className="filter-input"
            style={{ width: 200 }}
          />
        </div>
      )}

      <div className="card">
        {logs.length === 0 ? (
          <p className="empty-state">Нет записей в журнале</p>
        ) : (
          <table className="logs-table">
            <thead>
              <tr>
                <th>Дата и время</th>
                <th>Уровень</th>
                <th>Действие</th>
                <th>Объект</th>
                <th>ID объекта</th>
                <th>Мастер</th>
                <th>Детали</th>
              </tr>
            </thead>
            <tbody>
              {logs.map(log => (
                <tr key={log.id}>
                  <td>
                    {new Date(log.created_at).toLocaleString('ru-RU', {
                      day: '2-digit',
                      month: '2-digit',
                      year: 'numeric',
                      hour: '2-digit',
                      minute: '2-digit'
                    })}
                  </td>
                  <td>
                    <span className={`level-badge level-${log.level}`}>
                      {levelLabels[log.level] || log.level}
                    </span>
                  </td>
                  <td>
                    <span className={`status-badge ${
                      log.action === 'delete' ? 'status-cancelled' :
                      log.action === 'confirm' ? 'status-confirmed' :
                      log.action === 'cancel' ? 'status-cancelled' :
                      log.action === 'complete' ? 'status-completed' :
                      log.action === 'create' ? 'status-pending' :
                      'status-pending'
                    }`}>
                      {actionLabels[log.action] || log.action}
                    </span>
                  </td>
                  <td>{entityLabels[log.entity_type] || log.entity_type}</td>
                  <td><code>{log.entity_id || '—'}</code></td>
                  <td>{log.master_name || '—'}</td>
                  <td style={{ maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {log.details || '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Pagination */}
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: 16, marginTop: 20 }}>
        <button
          className="btn btn-ghost"
          onClick={() => setCurrentPage(p => Math.max(0, p - 1))}
          disabled={currentPage === 0}
          style={{ opacity: currentPage === 0 ? 0.5 : 1 }}
        >
          ← Назад
        </button>
        <span style={{ fontSize: 14, color: '#666' }}>
          Страница {currentPage + 1} из {Math.ceil(total / pageSize) || 1} ({total} записей)
        </span>
        <button
          className="btn btn-ghost"
          onClick={() => setCurrentPage(p => p + 1)}
          disabled={logs.length < pageSize}
          style={{ opacity: logs.length < pageSize ? 0.5 : 1 }}
        >
          Вперёд →
        </button>
      </div>
    </div>
  )
}

export default LogsPage
