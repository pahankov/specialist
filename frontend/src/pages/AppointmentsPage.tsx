import { useEffect, useState } from 'react'
import { adminApi } from '../api/adminClient'
import type { Appointment } from '../api/types'
import './AppointmentsPage.css'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

function AppointmentsPage() {
  const [appointments, setAppointments] = useState<(Appointment & { client_name?: string; client_phone?: string; service_name?: string; service_price?: number })[]>([])
  const [filter, setFilter] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [successMsg, setSuccessMsg] = useState('')
  const [deletingId, setDeletingId] = useState<number | null>(null)
  const [cancelingId, setCancelingId] = useState<number | null>(null)
  const [cancelReason, setCancelReason] = useState('')
  const [currentPage, setCurrentPage] = useState(0)
  const pageSize = 20

  const fetch = async () => {
    try {
      const resp = await adminApi.getAppointments(filter, pageSize, currentPage)
      setAppointments(resp.data)
    } catch (err: any) {
      if (err.response?.status === 401) { localStorage.removeItem('access_token'); window.location.href = '/admin/login' }
      else setError('Ошибка загрузки')
    } finally { setLoading(false) }
  }

  useEffect(() => { setCurrentPage(0); fetch() }, [filter])

  const clearSuccess = () => { setSuccessMsg(''); setError('') }

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
      setSuccessMsg('Запись подтверждена')
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
      setSuccessMsg('Запись завершена')
    } catch (err: any) {
      showError(err)
    }
  }
  const handleDelete = async (id: number) => {
    clearSuccess()
    try {
      await adminApi.deleteAppointment(id)
      fetch()
      setSuccessMsg('Запись удалена')
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
      setSuccessMsg('Запись отменена')
    } catch (err: any) {
      showError(err)
    } finally {
      setCancelingId(null)
      setCancelReason('')
    }
  }

  const statusLabels: Record<string, string> = { pending: '⏳ Ожидает', confirmed: '✅ Подтверждена', cancelled: '❌ Отменена', completed: '🏁 Завершена' }
  const filters = [{ value: '', label: 'Все' }, { value: 'pending', label: '⏳ Ожидает' }, { value: 'confirmed', label: '✅ Подтверждена' }, { value: 'cancelled', label: '❌ Отменена' }, { value: 'completed', label: '🏁 Завершена' }]

  if (loading) return <div className="admin-main"><div className="loading">Загрузка...</div></div>
  if (error) return <div className="admin-main"><div className="error-message">{error}</div></div>

  return (
    <div className="admin-main">
      <div className="page-header">
        <h1>Управление записями</h1>
        <p>Подтверждение, завершение и отмена записей</p>
        <button
          className="btn btn-ghost"
          onClick={() => {
            const statusParam = filter ? `?status=${filter}` : ''
            window.open(`${API_URL}/admin/export/appointments${statusParam}`, '_blank')
          }}
          style={{ marginLeft: 'auto' }}
        >
          📥 Экспорт CSV
        </button>
      </div>
      {successMsg && <div className="success-message" style={{ background: '#e8f5e9', color: '#2e7d32', padding: '12px 16px', borderRadius: 8, marginBottom: 20 }}>{successMsg}</div>}
      {error && <div className="error-message">{error}</div>}
      <div className="filters-bar">
        {filters.map(f => (<button key={f.value} className={`filter-btn ${filter === f.value ? 'active' : ''}`} onClick={() => setFilter(f.value)}>{f.label}</button>))}
      </div>
      <div className="card">
        {appointments.length === 0 ? <p className="empty-state">Нет записей</p> : (
          <table className="appointments-table">
            <thead><tr><th>Дата</th><th>Клиент</th><th>Телефон</th><th>Услуга</th><th>Сумма</th><th>Статус</th><th>Действия</th><th></th></tr></thead>
            <tbody>
              {appointments.map(a => (<tr key={a.id}>
                <td>{new Date(a.appointment_date).toLocaleString('ru-RU')}</td>
                <td><strong>{a.client_name || '—'}</strong></td>
                <td><a href={`tel:${a.client_phone || ''}`}>{a.client_phone || '—'}</a></td>
                <td>{a.service_name || '—'}</td>
                <td>{a.service_price ? `${Number(a.service_price).toLocaleString('ru-RU')} ₽` : '—'}</td>
                <td><span className={`status-badge status-${a.status}`}>{statusLabels[a.status] || a.status}</span></td>
                <td className="actions-cell">
                  {a.status === 'pending' && (<><button className="btn btn-sm btn-confirm" onClick={() => handleConfirm(a.id)}>✅ Подтвердить</button><button className="btn btn-sm btn-cancel" onClick={() => handleCancel(a.id)}>❌ Отменить</button></>)}
                  {a.status === 'confirmed' && (<><button className="btn btn-sm btn-complete" onClick={() => handleComplete(a.id)}>🏁 Завершить</button><button className="btn btn-sm btn-cancel" onClick={() => handleCancel(a.id)}>❌ Отменить</button></>)}
                  {a.status === 'completed' && <span className="text-muted">Завершена</span>}
                  {a.status === 'cancelled' && <span className="text-muted">Отменена</span>}
                </td>
                <td><button className="btn btn-sm btn-delete" onClick={() => setDeletingId(a.id)}>🗑️</button></td>
              </tr>))}
            </tbody>
          </table>
        )}
      </div>

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
          disabled={appointments.length < pageSize}
          style={{ opacity: appointments.length < pageSize ? 0.5 : 1 }}
        >
          Вперёд →
        </button>
      </div>
    </div>
  )
}
export default AppointmentsPage
