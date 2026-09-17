import { useEffect, useState } from 'react'
import { adminApi } from '../api/adminClient'
import './LogsPage.css'

function LogsPage() {
  const [logs, setLogs] = useState<any[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [entityFilter, setEntityFilter] = useState('')
  const [currentPage, setCurrentPage] = useState(0)
  const pageSize = 20

  const entityLabels: Record<string, string> = {
    appointment: '📅 Запись',
    service: '💇 Услуга',
    client: '👤 Клиент',
    working_hour: '🕐 Расписание'
  }

  const actionLabels: Record<string, string> = {
    confirm: '✅ Подтверждение',
    cancel: '❌ Отмена',
    complete: '🏁 Завершение',
    delete: '🗑️ Удаление',
    create: '➕ Создание',
    update: '✏️ Обновление'
  }

  const fetchLogs = async () => {
    try {
      const params: any = { limit: pageSize, offset: currentPage * pageSize }
      if (entityFilter) params.entity_type = entityFilter
      const resp = await adminApi.getAuditLogs(params)
      setLogs(resp.data.logs)
      setTotal(resp.data.total)
    } catch (err: any) {
      if (err.response?.status === 401) {
        localStorage.removeItem('access_token')
        window.location.href = '/admin/login'
      } else {
        setError('Ошибка загрузки логов')
      }
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    setLoading(true)
    fetchLogs()
  }, [entityFilter, currentPage])

  if (loading) return <div className="admin-main"><div className="loading">Загрузка...</div></div>
  if (error) return <div className="admin-main"><div className="error-message">{error}</div></div>

  const filters = [
    { value: '', label: 'Все' },
    { value: 'appointment', label: '📅 Записи' },
    { value: 'service', label: '💇 Услуги' },
    { value: 'client', label: '👤 Клиенты' }
  ]

  return (
    <div className="admin-main">
      <div className="page-header"><h1>📋 Журнал действий</h1><p>История всех операций в админ-панели</p></div>

      <div className="filters-bar">
        {filters.map(f => (
          <button
            key={f.value}
            className={`filter-btn ${entityFilter === f.value ? 'active' : ''}`}
            onClick={() => setEntityFilter(f.value)}
          >
            {f.label}
          </button>
        ))}
      </div>

      <div className="card">
        {logs.length === 0 ? (
          <p className="empty-state">Нет записей в журнале</p>
        ) : (
          <table className="logs-table">
            <thead>
              <tr>
                <th>Дата и время</th>
                <th>Действие</th>
                <th>Объект</th>
                <th>ID объекта</th>
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
                    <span className={`status-badge ${
                      log.action === 'delete' ? 'status-cancelled' :
                      log.action === 'confirm' ? 'status-confirmed' :
                      log.action === 'cancel' ? 'status-cancelled' :
                      'status-pending'
                    }`}>
                      {actionLabels[log.action] || log.action}
                    </span>
                  </td>
                  <td>{entityLabels[log.entity_type] || log.entity_type}</td>
                  <td><code>{log.entity_id || '—'}</code></td>
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
