import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { toast } from 'sonner'
import { adminApi } from '../../api/client'
import type { Appointment } from '../../api/types'
import { Skeleton, EmptyState, Tooltip, ConfirmDialog, MasterSelect, ResizableTh, useColumnWidths, Pager } from '../../components/common'
import { downloadCsv } from '../../api/export'
import { usePersistentState } from '../../utils/persistentState'
import { useSectionPrefix, SUPER_PREFIX } from '../../utils/section'
import { getApiErrorMessage } from '../../utils/apiError'
import '../../styles/filters.css'
import '../../styles/tables.css'
import './AppointmentsPage.css'

type SortField = 'appointment_date' | 'client_name' | 'service_name' | 'service_price' | 'status' | 'master_name'
type SortDirection = 'asc' | 'desc'

function AppointmentsPage() {
  const section = useSectionPrefix()
  const isSuperSection = section === SUPER_PREFIX
  const { widths: colW, setWidth: setColW } = useColumnWidths('appointments2', {
    date: 150, client: 160, phone: 130, service: 180, price: 90, status: 140, master: 150, actions: 150,
  })

  const [appointments, setAppointments] = useState<(Appointment & { client_name?: string; client_phone?: string; service_name?: string; service_price?: number })[]>([])
  const [searchParams, setSearchParams] = useSearchParams()
  // Filters persist across tab switches (sessionStorage), deep-links win on mount
  const [statusFilter, setStatusFilter] = usePersistentState('appointments.status', '')
  const [masterIdFilter, setMasterIdFilter] = usePersistentState<number | ''>('appointments.master', '')
  const [clientIdFilter, setClientIdFilter] = usePersistentState<number | ''>('appointments.client', '')
  const [serviceIdFilter, setServiceIdFilter] = usePersistentState<number | ''>('appointments.service', '')
  const [dateFrom, setDateFrom] = usePersistentState('appointments.from', '')
  const [dateTo, setDateTo] = usePersistentState('appointments.to', '')
  const [showCompleted, setShowCompleted] = usePersistentState('appointments.showCompleted', false)
  const [allTime, setAllTime] = usePersistentState('appointments.allTime', true)
  const [showFilters, setShowFilters] = usePersistentState('appointments.showFilters', false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [deletingId, setDeletingId] = useState<number | null>(null)
  const [cancelingId, setCancelingId] = useState<number | null>(null)
  const [noShowingId, setNoShowingId] = useState<number | null>(null)
  const [cancelReason, setCancelReason] = useState('')
  const [currentPage, setCurrentPage] = usePersistentState('appointments.page', 0)
  const [sortField, setSortField] = usePersistentState<SortField>('appointments.sort', 'appointment_date')
  const [sortDirection, setSortDirection] = usePersistentState<SortDirection>('appointments.dir', 'asc')
  const [totalPages, setTotalPages] = useState(1)
  const [allClients, setAllClients] = useState<{ id: number; name: string }[]>([])
  const [allServices, setAllServices] = useState<{ id: number; name: string }[]>([])
  const pageSize = 20

  const fetchOptions = async () => {
    try {
      // Fetch clients for filter dropdown
      try {
        const clientsResp = await adminApi.getClients({ page: 1, page_size: 500 })
        setAllClients(clientsResp.data.items.map((c: { id: number; name: string }) => ({ id: c.id, name: c.name })))
      } catch { /* ignore */ }

      // Fetch services for filter dropdown
      try {
        const servicesResp = await adminApi.getServices({ page: 1, page_size: 500, active_only: false })
        setAllServices(servicesResp.data.items.map((s: { id: number; name: string }) => ({ id: s.id, name: s.name })))
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
      if (!allTime) {
        if (dateFrom) params.date_from = dateFrom
        if (dateTo) params.date_to = dateTo
      }
      
      const resp = await adminApi.getAppointments(params)
      setAppointments(resp.data.items)
      setTotalPages(resp.data.total_pages)
    } catch (err: any) {
      if (err.response?.status === 401) { window.location.href = '/admin/login' }
      else setError('Ошибка загрузки')
    } finally { setLoading(false) }
  }

  // Deep-link support: <section>/appointments?status=X&client_id=Y&master_id=Z
  // (e.g. "appointments of this client" from Clients, stat cards from Revenue)
  useEffect(() => {
    const qp = searchParams.get('client_id')
    if (qp !== null && qp !== '') {
      const id = Number(qp)
      if (Number.isFinite(id)) setClientIdFilter(id)
    }
    const mp = searchParams.get('master_id')
    if (mp !== null && mp !== '') {
      const id = Number(mp)
      if (Number.isFinite(id)) setMasterIdFilter(id)
    }
    const sp = searchParams.get('status')
    if (sp !== null && sp !== '' && ['pending', 'confirmed', 'cancelled', 'completed'].includes(sp)) {
      setStatusFilter(sp)
    }
    // consume once so back/forward stays clean
    if (searchParams.has('client_id') || searchParams.has('master_id') || searchParams.has('status')) {
      // A drill-down promises "everything matching": reveal completed rows
      // (hidden by default) so counts match the card that was clicked
      setShowCompleted(true)
      // Deep-linked filters live in the collapsible panel — open it so the
      // user sees what is applied instead of a "wrong" list
      setShowFilters(true)
      setSearchParams({}, { replace: true })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => { setCurrentPage(0) }, [statusFilter, masterIdFilter, clientIdFilter, serviceIdFilter, dateFrom, dateTo, allTime])

  useEffect(() => { fetch() }, [currentPage, statusFilter, masterIdFilter, clientIdFilter, serviceIdFilter, dateFrom, dateTo, allTime])

  const showError = (err: unknown) => {
    setError(getApiErrorMessage(err, 'Ошибка сервера'))
  }

  const handleConfirm = async (id: number) => {
    try {
      await adminApi.confirmAppointment(id)
      fetch()
      toast.success('Запись подтверждена')
    } catch (err: unknown) {
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
      toast.success('Запись завершена')
    } catch (err: unknown) {
      showError(err)
    }
  }

  const handleDelete = async (id: number) => {
    try {
      await adminApi.deleteAppointment(id)
      // No undo: backend has no undelete, a fake "cancel" toast would lie.
      toast.success('Запись удалена')
      fetch()
    } catch (err: unknown) {
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
      toast.success('Запись отменена')
    } catch (err: unknown) {
      showError(err)
    } finally {
      setCancelingId(null)
      setCancelReason('')
    }
  }

  const handleNoShow = async (id: number) => {
    try {
      await adminApi.noShowAppointment(id)
      toast.warning('Отмечено как неявка')
      fetch()
    } catch (err: unknown) {
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
            onClick={async () => {
              const params = new URLSearchParams()
              if (statusFilter) params.set('status', statusFilter)
              if (masterIdFilter !== '') params.set('master_id', String(masterIdFilter))
              if (clientIdFilter !== '') params.set('client_id', String(clientIdFilter))
              if (serviceIdFilter !== '') params.set('service_id', String(serviceIdFilter))
              if (dateFrom) params.set('date_from', dateFrom)
              if (dateTo) params.set('date_to', dateTo)
              try {
                await downloadCsv(`/api/v1/admin/export/appointments?${params.toString()}`, 'appointments.csv')
                toast.success('CSV выгружен')
              } catch (err: unknown) {
                toast.error(getApiErrorMessage(err, 'Не удалось выгрузить CSV'))
              }
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
            {/* Master filter — full-width first row */}
            <div style={{ gridColumn: '1 / -1' }}>
              <MasterSelect
                value={masterIdFilter}
                onChange={setMasterIdFilter}
                style={{ marginBottom: 0, maxWidth: 480 }}
              />
            </div>

            {/* Client filter */}
            <div className="filter-cell">
              <label className="filter-label">Клиент</label>
              <select className="filter-control" value={clientIdFilter} onChange={(e) => setClientIdFilter(e.target.value === '' ? '' : Number(e.target.value))}>
                <option value="">Все клиенты</option>
                {allClients.map(c => (<option key={c.id} value={c.id}>{c.name}</option>))}
              </select>
            </div>

            {/* Service filter */}
            <div className="filter-cell">
              <label className="filter-label">Услуга</label>
              <select className="filter-control" value={serviceIdFilter} onChange={(e) => setServiceIdFilter(e.target.value === '' ? '' : Number(e.target.value))}>
                <option value="">Все услуги</option>
                {allServices.map(s => (<option key={s.id} value={s.id}>{s.name}</option>))}
              </select>
            </div>

            {/* Date from */}
            <div className="filter-cell">
              <label className="filter-label">Дата от</label>
              <input type="date" className="filter-control" value={dateFrom} disabled={allTime} onChange={(e) => setDateFrom(e.target.value)} />
            </div>

            {/* Date to */}
            <div className="filter-cell">
              <label className="filter-label">Дата до</label>
              <input type="date" className="filter-control" value={dateTo} disabled={allTime} onChange={(e) => setDateTo(e.target.value)} />
            </div>

            {/* All time — tied to the date fields, right edge */}
            <div className="filter-cell-bottom" style={{ justifySelf: 'end' }}>
              <label className="filter-check">
                <input type="checkbox" checked={allTime} onChange={() => setAllTime(v => !v)} />
                За всё время
              </label>
            </div>
          </div>
          {/* Reset filters button — centered, visible */}
          <div style={{ display: 'flex', justifyContent: 'center', marginTop: 12 }}>
            <button className="btn filter-reset" onClick={() => { setStatusFilter(''); setMasterIdFilter(''); setClientIdFilter(''); setServiceIdFilter(''); setDateFrom(''); setDateTo('') }}>
              ✕ Сбросить фильтры
            </button>
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
          <div className="appointments-table-wrapper">
          <table className="appointments-table resizable-table">
            <thead><tr>
              <ResizableTh width={colW.date} onResize={(w) => setColW('date', w)} className={`sortable ${sortField === 'appointment_date' ? 'active' : ''}`} onClick={() => handleSort('appointment_date')}>Дата <span className="sort-arrow">{sortField === 'appointment_date' ? (sortDirection === 'asc' ? '↑' : '↓') : '⇅'}</span></ResizableTh>
              <ResizableTh width={colW.client} onResize={(w) => setColW('client', w)} className={`sortable ${sortField === 'client_name' ? 'active' : ''}`} onClick={() => handleSort('client_name')}>Клиент <span className="sort-arrow">{sortField === 'client_name' ? (sortDirection === 'asc' ? '↑' : '↓') : '⇅'}</span></ResizableTh>
              <ResizableTh width={colW.phone} onResize={(w) => setColW('phone', w)}>Телефон</ResizableTh>
              <ResizableTh width={colW.service} onResize={(w) => setColW('service', w)} className={`sortable ${sortField === 'service_name' ? 'active' : ''}`} onClick={() => handleSort('service_name')}>Услуга <span className="sort-arrow">{sortField === 'service_name' ? (sortDirection === 'asc' ? '↑' : '↓') : '⇅'}</span></ResizableTh>
              <ResizableTh width={colW.price} onResize={(w) => setColW('price', w)} className={`sortable ${sortField === 'service_price' ? 'active' : ''}`} onClick={() => handleSort('service_price')}>Сумма <span className="sort-arrow">{sortField === 'service_price' ? (sortDirection === 'asc' ? '↑' : '↓') : '⇅'}</span></ResizableTh>
              <ResizableTh width={colW.status} onResize={(w) => setColW('status', w)} className={`sortable ${sortField === 'status' ? 'active' : ''}`} onClick={() => handleSort('status')}>Статус <span className="sort-arrow">{sortField === 'status' ? (sortDirection === 'asc' ? '↑' : '↓') : '⇅'}</span></ResizableTh>
              {isSuperSection && (
                <ResizableTh width={colW.master} onResize={(w) => setColW('master', w)} className={`sortable ${sortField === 'master_name' ? 'active' : ''}`} onClick={() => handleSort('master_name')}>Мастер <span className="sort-arrow">{sortField === 'master_name' ? (sortDirection === 'asc' ? '↑' : '↓') : '⇅'}</span></ResizableTh>
              )}
              <ResizableTh width={colW.actions} minWidth={150} defaultWidth={150} onResize={(w) => setColW('actions', w)}>Действия</ResizableTh>
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
                {isSuperSection && (
                  <td title={a.master_name || ''}>{a.master_name || '—'}</td>
                )}
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
                  <Tooltip content="Удалить запись">
                    <button className="btn btn-sm btn-delete" onClick={() => setDeletingId(a.id)}>🗑️</button>
                  </Tooltip>
                </td>
              </tr>))}
            </tbody>
          </table>
          </div>
        </div>
      )}

      {/* Delete confirmation modal */}
      <ConfirmDialog
        open={deletingId !== null}
        onClose={() => setDeletingId(null)}
        title="🗑️ Удалить запись?"
        message="Это действие нельзя отменить."
        confirmLabel="Удалить"
        danger
        onConfirm={() => deletingId !== null && handleDelete(deletingId)}
      />

      {/* Cancel confirmation modal */}
      <ConfirmDialog
        open={cancelingId !== null}
        onClose={() => setCancelingId(null)}
        title="❌ Отменить запись?"
        confirmLabel="Отменить"
        danger
        confirmDisabled={!cancelReason.trim()}
        onConfirm={handleConfirmCancel}
      >
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
      </ConfirmDialog>

      {/* No-show confirmation modal */}
      <ConfirmDialog
        open={noShowingId !== null}
        onClose={() => setNoShowingId(null)}
        title="👤 Отметить неявку?"
        message="Клиент не появился на записи. Запись будет отменена, счётчик неявок увеличен."
        confirmLabel="Неявка"
        danger
        onConfirm={() => noShowingId !== null && handleNoShow(noShowingId)}
      />

      {/* Pagination */}
      <Pager page={currentPage} totalPages={totalPages} onChange={setCurrentPage} />
    </div>
  )
}
export default AppointmentsPage
