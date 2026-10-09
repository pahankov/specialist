import { useEffect, useState } from 'react'
import { adminApi } from '../../api/client'
import type { AuditLogEntry } from '../../api/types'
import { getApiErrorMessage, getApiErrorStatus } from '../../utils/apiError'
import { getCookie, decodeJwtPayload } from '../../utils/cookies'
import { Pager } from '../../components/common'
import './LogsPage.css'

function getIsAdmin(): boolean {
  const token = getCookie('access_token')
  if (!token) return false
  return decodeJwtPayload(token)?.is_admin === true
}

function LogsPage() {
  const isAdmin = getIsAdmin()
  const [logs, setLogs] = useState<AuditLogEntry[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [entityFilter, setEntityFilter] = useState('')
  const [levelFilter, setLevelFilter] = useState('')
  const [actionFilter, setActionFilter] = useState('')
  const [quickSearch, setQuickSearch] = useState('')
  const [masterFilter, setMasterFilter] = useState('')
  const [currentPage, setCurrentPage] = useState(0)
  const pageSize = 20

  const entityLabels: Record<string, string> = {
    appointment: '📅 Запись',
    service: '💇 Услуга',
    client: '👤 Клиент',
    working_hour: '🕐 Расписание',
    master: '👨‍💼 Мастер',
    auth: '🔑 Вход/выход'
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
      const params: Record<string, string | number> = { limit: pageSize, offset: currentPage * pageSize }
      if (entityFilter) params.entity_type = entityFilter
      if (masterFilter) params.master_id = masterFilter

      // Superadmin uses /audit-logs/all, regular master uses /audit-logs (filtered by master_id)
      const endpoint = isAdmin ? '/api/v1/admin/audit-logs/all' : '/api/v1/admin/audit-logs'
      const resp = await adminApi.get(endpoint, { params })
      setLogs(resp.data.logs)
      setTotal(resp.data.total)
    } catch (err: unknown) {
      if (getApiErrorStatus(err) === 401) {
        window.location.href = '/admin/login'
      } else {
        const detail = getApiErrorMessage(err, 'Ошибка загрузки логов')
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

  const visibleLogs = logs.filter(log => {
    if (levelFilter && log.level !== levelFilter) return false
    if (actionFilter && log.action !== actionFilter) return false
    const q = quickSearch.trim().toLowerCase()
    if (q) {
      const haystack = [
        log.action, log.entity_type, log.details ?? '',
        log.master_name ?? '', String(log.entity_id ?? ''),
      ].join(' ').toLowerCase()
      if (!haystack.includes(q)) return false
    }
    return true
  })

  const entityFilters = [
    { value: '', label: 'Все' },
    { value: 'appointment', label: '📅 Записи' },
    { value: 'service', label: '💇 Услуги' },
    { value: 'client', label: '👤 Клиенты' },
    { value: 'master', label: '👨‍💼 Мастера' },
    { value: 'auth', label: '🔑 Входы/выходы' }
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

      {/* Level + action + quick search (over the loaded page) */}
      <div className="filters-bar" style={{ marginTop: 8 }}>
        <select
          value={levelFilter}
          onChange={(e) => setLevelFilter(e.target.value)}
          className="filter-input"
          style={{ width: 160 }}
          title="Уровень"
        >
          <option value="">Все уровни</option>
          <option value="info">ℹ️ INFO</option>
          <option value="warning">⚠️ WARNING</option>
          <option value="error">🚫 ERROR</option>
        </select>
        <select
          value={actionFilter}
          onChange={(e) => setActionFilter(e.target.value)}
          className="filter-input"
          style={{ width: 200 }}
          title="Действие"
        >
          <option value="">Все действия</option>
          {Object.entries(actionLabels).map(([value, label]) => (
            <option key={value} value={value}>{label}</option>
          ))}
        </select>
        <input
          type="text"
          placeholder="Быстрый поиск по странице..."
          value={quickSearch}
          onChange={(e) => setQuickSearch(e.target.value)}
          className="filter-input"
          style={{ width: 240 }}
        />
      </div>

      <div className="card">
        {visibleLogs.length === 0 ? (
          <p className="empty-state">
            {logs.length === 0 ? 'Нет записей в журнале' : 'Ничего не найдено — измените фильтры'}
          </p>
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
              {visibleLogs.map(log => (
                <tr key={log.id}>
                    <td>
                      {log.created_at ? new Date(log.created_at).toLocaleString('ru-RU', {
                        day: '2-digit',
                        month: '2-digit',
                        year: 'numeric',
                        hour: '2-digit',
                        minute: '2-digit'
                      }) : '—'}
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
      <Pager
        page={currentPage}
        totalPages={Math.ceil(total / pageSize) || 1}
        onChange={setCurrentPage}
        label={`Страница ${currentPage + 1} из ${Math.ceil(total / pageSize) || 1} (${total} записей)`}
      />
    </div>
  )
}

export default LogsPage
