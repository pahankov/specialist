import { useEffect, useState } from 'react'
import { adminApi } from '../../api/client'
import type { Appointment } from '../../api/types'
import { Skeleton, EmptyState, Tooltip } from '../../components/common'
import { useToast } from '../../components/Toast'
import './AppointmentsPage.css'

type SortField = 'appointment_date' | 'client_name' | 'service_name' | 'service_price' | 'status'
type SortDirection = 'asc' | 'desc'

function AppointmentsPage() {
  const { addToast } = useToast()
  const [appointments, setAppointments] = useState<(Appointment & { client_name?: string; client_phone?: string; service_name?: string; service_price?: number })[]>([])
  const [statusFilter, setStatusFilter] = useState('')
  const [masterIdFilter, setMasterIdFilter] = useState<number | ''>('')
  const [clientIdFilter, setClientIdFilter] = useState<number | ''>('')
  const [serviceIdFilter, setServiceIdFilter] = useState<number | ''>('')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [deletingId, setDeletingId] = useState<number | null>(null)
  const [cancelingId, setCancelingId] = useState<number | null>(null)
  const [noShowingId, setNoShowingId] = useState<number | null>(null)
  const [cancelReason, setCancelReason] = useState('')
  const [currentPage, setCurrentPage] = useState(0)
  const [sortField, setSortField] = useState<SortField>('appointment_date')
  const [sortDirection, setSortDirection] = useState<SortDirection>('asc')
  const [showCompleted, setShowCompleted] = useState(false)
  const [totalPages, setTotalPages] = useState(1)
  const [allMasters, setAllMasters] = useState<Array<{ id: number; name: string }>>([])
  const [allClients, setAllClients] = useState<Array<{ id: number; name: string }>>([])
  const [allServices, setAllServices] = useState<Array<{ id: number; name: string }>>([])
  const [showFilters, setShowFilters] = useState(false)
  const pageSize = 20

  const fetchOptions = async () => {
    try {
      // Fetch masters (superadmin only)
      try {
        const mastersResp = await adminApi.get('/api/v1/admin/masters')
        setAllMasters(mastersResp.data.map((m: any) => ({ id: m.id, name: m.name })))
      } catch { /* not superadmin */ }
      
      // Fetch clients for filter dropdown
      try {
        const clientsResp = await adminApi.getClients({ page: 1, page_size: 500 })
        setAllClients(clientsResp.data.items.map((c: any) => ({ id: c.id, name: c.name })))
      } catch { /* ignore */ }
      
      // Fetch services for filter dropdown
      try {
        const servicesResp = await adminApi.getServices({ page: 1, page_size: 500, active_only: false })
        setAllServices(servicesResp.data.items.map((s: any) => ({ id: s.id, name: s.name })))
      } catch { /* ignore */ }
    } catch { /* ignore */ }
  }

  useEffect(() => { fetchOptions() }, [])

  const fetch = async () => {
    setLoading(true)
    try {
      const params: Record<string, any> = { page: currentPage + 1, page_size: pageSize }
      if (statusFilter) params.status = statusFilter
      if (masterIdFilter !== '') params.master_id = masterIdFilter
      if (clientIdFilter !== '') params.client_id = clientIdFilter
      if (serviceIdFilter !== '') params.service_id = serviceIdFilter
      if (dateFrom) params.date_from = dateFrom
      if (dateTo) params.date_to = dateTo
      
      const resp = await adminApi.getAppointments(params)
      setAppointments(resp.data.items)
      setTotalPages(resp.data.total_pages)
    } catch (err: any) {
      if (err.response?.status === 401) { localStorage.removeItem('access_token'); window.location.href = '/admin/login' }
      else setError('Ошибка загрузки')
    } finally { setLoading(false) }
  }

  useEffect(() => { setCurrentPage(0); fetch() }, [statusFilter, masterIdFilter, clientIdFilter, serviceIdFilter, dateFrom, dateTo])

  const showError = (err: any) => {
    const detail = err.response?.data?.detail
    if (typeof detail === 'string') setError(detail)
    else if (detail && typeof detail === 'object') setError(JSON.stringify(detail))
    else setError('Произошла ошибка')
  }

  const handleConfirm = async (id: number) => {
    try {
      await adminApi.confirmAppointment(id)
      fetch()
      addToast('Запись подтверждена', 'success')
    } catch (err: any) {
      showError(err)
    }
  }

  const handleCancel = async (id: number) => {
    setCancelingId(id)
  }

  const handleComplete = async (id: number) => {
    try {
      await adminApi.completeAppointment(id)
      fetch()
      addToast('Запись завершена', 'success')
    } catch (err: any) {
      showError(err)
    }
  }

  const handleDelete = async (id: number) => {
    const appointment = appointments.find(a => a.id === id)
    if (!appointment) return

    const undoAction = () => {
      addToast('Удаление отменено', 'info')
    }

    try {
      await adminApi.deleteAppointment(id)
      addToast(
        'Запись удалена',
        'success',
        undoAction,
        'Отменить'
      )
      fetch()
    } catch (err: any) {
      showError(err)
    } finally {
      setDeletingId(null)
    }
  }

  const handleConfirmCancel = async () => {
    if (!cancelingId || !cancelReason.trim()) return
    try {
      await adminApi.cancelAppointment(cancelingId, cancelReason.trim())
      fetch()
      addToast('Запись отменена', 'success')
    } catch (err: any) {
      showError(err)
    } finally {
      setCancelingId(null)
      setCancelReason('')
    }
  }

  const handleNoShow = async (id: number) => {
    try {
      await adminApi.noShowAppointment(id)
      addToast('Отмечено как неявка', 'warning')
      fetch()
    } catch (err: any) {
      showError(err)
    } finally {
      setNoShowingId(null)
    }
  }

  const isAppointmentTimePassed = (dateStr: string) => new Date(dateStr) <= new Date()

  const statusLabels: Record<string, string> = { pending: '⏳ Ожидает', confirmed: '✅ Подтверждена', cancelled: '❌ Отменена', completed: '🏁 Завершена' }
  const filters = [{ value: '', label: 'Все' }, { value: 'pending', label: '⏳ Ожидает' }, { value: 'confirmed', label: '✅ Подтверждена' }, { value: 'cancelled', label: '❌ Отменена' }, { value: 'completed', label: '🏁 Завершена' }]

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDirection(d => d === 'asc' ? 'desc' : 'asc')
    } else {
      setSortField(field)
      setSortDirection('asc')
    }
  }

  const sortedAppointments = [...appointments].sort((a, b) => {
    let valA: string | number | Date = a[sortField] ?? ''
    let valB: string | number | Date = b[sortField] ?? ''

    if (sortField === 'appointment_date') {
      valA = new Date(valA as string).getTime()
      valB = new Date(valB as string).getTime()
    }

    if (valA < valB) return sortDirection === 'asc' ? -1 : 1
    if (valA > valB) return sortDirection === 'asc' ? 1 : -1
    return 0
  })

  const filteredAppointments = sortedAppointments.filter(a => {
    if (a.status === 'completed' && !showCompleted) return false
    if (a.status !== 'completed' && a.status !== 'cancelled' && isAppointmentTimePassed(a.appointment_date)) return false
    return true
  })

  return (
    <div className="appointments-page">
      <div className="page-header" style={{ display: 'flex', alignItems: 'center', gap: 16, justifyContent: 'center' }}>
        <div>
          <h1>Управление записями</h1>
          <p>Подтверждение, завершение и отмена записей</p>
        </div>
          <button
            className="btn btn-ghost"
            onClick={() => {
              const { VITE_API_URL = 'http://localhost:8000' } = import.meta.env
              const params = new URLSearchParams()
              if (statusFilter) params.set('status', statusFilter)
              if (masterIdFilter !== '') params.set('master_id', String(masterIdFilter))
              if (clientIdFilter !== '') params.set('client_id', String(clientIdFilter))
              if (serviceIdFilter !== '') params.set('service_id', String(serviceIdFilter))
              if (dateFrom) params.set('date_from', dateFrom)
              if (dateTo) params.set('date_to', dateTo)
              window.open(`${VITE_API_URL}/api/v1/admin/export/appointments?${params.toString()}`, '_blank')
            }}
          >
            📥 Экспорт CSV
          </button>
      </div>

      {error && <div className="error-message">{error}</div>}

      <div className="filters-bar">
        {filters.map(f => (<button key={f.value} className={`filter-btn ${statusFilter === f.value ? 'active' : ''}`} onClick={() => setStatusFilter(f.value)}>{f.label}</button>))}
      </div>

      {/* Advanced filters toggle */}
      <div style={{ marginBottom: 12, display: 'flex', justifyContent: 'center' }}>
        <button className="btn btn-ghost" onClick={() => setShowFilters(p => !p)} style={{ fontSize: 13 }}>
          {showFilters ? '▲ Скрыть фильтры' : '▼ Расширенные фильтры'}
        </button>
      </div>

      {/* Advanced filters */}
      {showFilters && (
        <div className="card" style={{ marginBottom: 16, padding: 16 }}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 12 }}>
            {/* Master filter */}
            <div className="form-group" style={{ marginBottom: 0 }}>
              <label style={{ fontSize: 12, color: '#666', marginBottom: 4, display: 'block' }}>Мастер</label>
              <select value={masterIdFilter} onChange={(e) => setMasterIdFilter(e.target.value as any)} style={{ width: '100%', padding: 8, border: '2px solid #e0e0e0', borderRadius: 8, fontSize: 14 }}>
                <option value="">Все мастера</option>
                {allMasters.map(m => (<option key={m.id} value={m.id}>{m.name}</option>))}
              </select>
            </div>

            {/* Client filter */}
            <div className="form-group" style={{ marginBottom: 0 }}>
              <label style={{ fontSize: 12, color: '#666', marginBottom: 4, display: 'block' }}>Клиент</label>
              <select value={clientIdFilter} onChange={(e) => setClientIdFilter(e.target.value as any)} style={{ width: '100%', padding: 8, border: '2px solid #e0e0e0', borderRadius: 8, fontSize: 14 }}>
                <option value="">Все клиенты</option>
                {allClients.map(c => (<option key={c.id} value={c.id}>{c.name}</option>))}
              </select>
            </div>

            {/* Service filter */}
            <div className="form-group" style={{ marginBottom: 0 }}>
              <label style={{ fontSize: 12, color: '#666', marginBottom: 4, display: 'block' }}>Услуга</label>
              <select value={serviceIdFilter} onChange={(e) => setServiceIdFilter(e.target.value as any)} style={{ width: '100%', padding: 8, border: '2px solid #e0e0e0', borderRadius: 8, fontSize: 14 }}>
                <option value="">Все услуги</option>
                {allServices.map(s => (<option key={s.id} value={s.id}>{s.name}</option>))}
              </select>
            </div>

            {/* Date from */}
            <div className="form-group" style={{ marginBottom: 0 }}>
              <label style={{ fontSize: 12, color: '#666', marginBottom: 4, display: 'block' }}>Дата от</label>
              <input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} style={{ width: '100%', padding: 8, border: '2px solid #e0e0e0', borderRadius: 8, fontSize: 14 }} />
            </div>

            {/* Date to */}
            <div className="form-group" style={{ marginBottom: 0 }}>
              <label style={{ fontSize: 12, color: '#666', marginBottom: 4, display: 'block' }}>Дата до</label>
              <input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} style={{ width: '100%', padding: 8, border: '2px solid #e0e0e0', borderRadius: 8, fontSize: 14 }} />
            </div>

            {/* Reset filters button */}
            <div className="form-group" style={{ marginBottom: 0, display: 'flex', alignItems: 'flex-end' }}>
              <button className="btn btn-ghost" onClick={() => { setStatusFilter(''); setMasterIdFilter(''); setClientIdFilter(''); setServiceIdFilter(''); setDateFrom(''); setDateTo('') }} style={{ width: '100%', fontSize: 13 }}>
                ✕ Сбросить
              </button>
            </div>
          </div>
        </div>
      )}

      <div style={{ marginBottom: 16, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 16 }}>
        <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer', fontSize: 14, color: '#666' }}>
          <input type="checkbox" checked={showCompleted} onChange={() => setShowCompleted(p => !p)} style={{ width: 16, height: 16, accentColor: '#667eea' }} />
          Показать завершённые
        </label>
      </div>

      {loading ? (
        <div className="card">
          <Skeleton rows={5} height="48px" />
        </div>
      ) : filteredAppointments.length === 0 ? (
        <EmptyState
          icon="📅"
          title="Нет записей"
          description={showCompleted ? 'Завершённые записи не найдены' : 'Активных записей не найдено'}
        />
      ) : (
        <div className="card">
          <table className="appointments-table">
            <thead><tr>
              <th className={`sortable ${sortField === 'appointment_date' ? 'active' : ''}`} onClick={() => handleSort('appointment_date')}>Дата <span className="sort-arrow">{sortField === 'appointment_date' ? (sortDirection === 'asc' ? '↑' : '↓') : '⇅'}</span></th>
              <th className={`sortable ${sortField === 'client_name' ? 'active' : ''}`} onClick={() => handleSort('client_name')}>Клиент <span className="sort-arrow">{sortField === 'client_name' ? (sortDirection === 'asc' ? '↑' : '↓') : '⇅'}</span></th>
              <th>Телефон</th>
              <th className={`sortable ${sortField === 'service_name' ? 'active' : ''}`} onClick={() => handleSort('service_name')}>Услуга <span className="sort-arrow">{sortField === 'service_name' ? (sortDirection === 'asc' ? '↑' : '↓') : '⇅'}</span></th>
              <th className={`sortable ${sortField === 'service_price' ? 'active' : ''}`} onClick={() => handleSort('service_price')}>Сумма <span className="sort-arrow">{sortField === 'service_price' ? (sortDirection === 'asc' ? '↑' : '↓') : '⇅'}</span></th>
              <th className={`sortable ${sortField === 'status' ? 'active' : ''}`} onClick={() => handleSort('status')}>Статус <span className="sort-arrow">{sortField === 'status' ? (sortDirection === 'asc' ? '↑' : '↓') : '⇅'}</span></th>
              <th>Действия</th>
              <th></th>
            </tr></thead>
            <tbody>
              {filteredAppointments.map(a => (<tr key={a.id}>
                <td>{new Date(a.appointment_date).toLocaleString('ru-RU')}</td>
                <td><strong>{a.client_name || '—'}</strong></td>
                <td><a href={`tel:${a.client_phone || ''}`}>{a.client_phone || '—'}</a></td>
                <td>{a.service_name || '—'}</td>
                <td>{a.service_price ? `${Number(a.service_price).toLocaleString('ru-RU')} ₽` : '—'}</td>
                <td>
                  <Tooltip content={statusLabels[a.status] || a.status} position="top">
                    <span className={`status-badge status-${a.status}`}>{statusLabels[a.status] || a.status}</span>
                  </Tooltip>
                </td>
                <td className="actions-cell">
                  {a.status === 'pending' && (
                    <>
                      <Tooltip content="Подтвердить запись"><button className="btn btn-sm btn-confirm" onClick={() => handleConfirm(a.id)}>✅</button></Tooltip>
                      <Tooltip content="Отменить запись"><button className="btn btn-sm btn-cancel" onClick={() => handleCancel(a.id)}>❌</button></Tooltip>
                    </>
                  )}
                  {a.status === 'confirmed' && (
                    <>
                      <Tooltip content="Завершить запись">
                        <button className="btn btn-sm btn-complete" onClick={() => handleComplete(a.id)} disabled={!isAppointmentTimePassed(a.appointment_date)}>🏁</button>
                      </Tooltip>
                      <Tooltip content="Отменить запись"><button className="btn btn-sm btn-cancel" onClick={() => handleCancel(a.id)}>❌</button></Tooltip>
                    </>
                  )}
                  {a.status === 'confirmed' && isAppointmentTimePassed(a.appointment_date) && (
                    <Tooltip content="Отметить неявку"><button className="btn btn-sm btn-no-show" onClick={() => setNoShowingId(a.id)}>👤</button></Tooltip>
                  )}
                  {a.status === 'completed' && <span className="text-muted">Завершена</span>}
                  {a.status === 'cancelled' && <span className="text-muted">Отменена</span>}
                </td>
                <td>
                  <Tooltip content="Удалить запись">
                    <button className="btn btn-sm btn-delete" onClick={() => setDeletingId(a.id)}>🗑️</button>
                  </Tooltip>
                </td>
              </tr>))}
            </tbody>
          </table>
        </div>
      )}

      {/* Delete confirmation modal */}
      {deletingId && (
        <div className="modal-overlay" onClick={() => setDeletingId(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h3>🗑️ Удалить запись?</h3>
            <p>Это действие нельзя отменить.</p>
            <div className="modal-actions">
              <button className="btn btn-ghost" onClick={() => setDeletingId(null)}>Отмена</button>
              <button className="btn btn-delete" onClick={() => handleDelete(deletingId)}>Удалить</button>
            </div>
          </div>
        </div>
      )}

      {/* Cancel confirmation modal */}
      {cancelingId && (
        <div className="modal-overlay" onClick={() => setCancelingId(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h3>❌ Отменить запись?</h3>
            <div className="form-group">
              <label>Причина отмены</label>
              <textarea
                value={cancelReason}
                onChange={(e) => setCancelReason(e.target.value)}
                placeholder="Укажите причину..."
                rows={3}
                style={{ width: '100%', padding: 10, border: '2px solid #e0e0e0', borderRadius: 8, fontSize: 14, resize: 'vertical' }}
              />
            </div>
            <div className="modal-actions">
              <button className="btn btn-ghost" onClick={() => setCancelingId(null)}>Отмена</button>
              <button className="btn btn-delete" onClick={handleConfirmCancel} disabled={!cancelReason.trim()}>Отменить</button>
            </div>
          </div>
        </div>
      )}

      {/* No-show confirmation modal */}
      {noShowingId && (
        <div className="modal-overlay" onClick={() => setNoShowingId(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h3>👤 Отметить неявку?</h3>
            <p>Клиент не появился на записи. Запись будет отменена, счётчик неяв увеличен.</p>
            <div className="modal-actions">
              <button className="btn btn-ghost" onClick={() => setNoShowingId(null)}>Отмена</button>
              <button className="btn btn-delete" onClick={() => handleNoShow(noShowingId)}>Неявка</button>
            </div>
          </div>
        </div>
      )}

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
          Страница {currentPage + 1}
        </span>
        <button
          className="btn btn-ghost"
          onClick={() => setCurrentPage(p => p + 1)}
          disabled={currentPage + 1 >= totalPages}
          style={{ opacity: currentPage + 1 >= totalPages ? 0.5 : 1 }}
        >
          Вперёд →
        </button>
      </div>
    </div>
  )
}
export default AppointmentsPage
