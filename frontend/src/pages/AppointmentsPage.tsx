import { useEffect, useState } from 'react'
import { adminApi } from '../../api/adminClient'
import type { Appointment } from '../../api/types'
import './AppointmentsPage.css'

function AppointmentsPage() {
  const [appointments, setAppointments] = useState<Appointment[]>([])
  const [filter, setFilter] = useState<string>('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const fetchAppointments = async () => {
    try {
      const params: any = {}
      if (filter) params.status = filter
      const resp = await adminApi.getAppointments(filter)
      setAppointments(resp.data)
    } catch (err: any) {
      if (err.response?.status === 401) {
        localStorage.removeItem('access_token')
        window.location.href = '/admin/login'
      } else {
        setError('Ошибка загрузки записей')
      }
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchAppointments()
  }, [filter])

  const handleConfirm = async (id: number) => {
    try {
      await adminApi.confirmAppointment(id)
      fetchAppointments()
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Ошибка')
    }
  }

  const handleCancel = async (id: number) => {
    const reason = prompt('Причина отмены:')
    if (!reason) return
    try {
      await adminApi.cancelAppointment(id, reason)
      fetchAppointments()
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Ошибка')
    }
  }

  const statusLabels: Record<string, string> = {
    pending: '⏳ Ожидает',
    confirmed: '✅ Подтверждена',
    cancelled: '❌ Отменена',
    completed: '🏁 Завершена',
  }

  const filters = [
    { value: '', label: 'Все' },
    { value: 'pending', label: '⏳ Ожидает' },
    { value: 'confirmed', label: '✅ Подтверждена' },
    { value: 'cancelled', label: '❌ Отменена' },
    { value: 'completed', label: '🏁 Завершена' },
  ]

  if (loading) return <div className="admin-main"><div className="loading">Загрузка...</div></div>
  if (error) return <div className="admin-main"><div className="error-message">{error}</div></div>

  return (
    <div className="admin-main">
      <div className="page-header">
        <h1>Управление записями</h1>
        <p>Подтверждение и отмена записей клиентов</p>
      </div>

      {/* Filters */}
      <div className="filters-bar">
        {filters.map((f) => (
          <button
            key={f.value}
            className={`filter-btn ${filter === f.value ? 'active' : ''}`}
            onClick={() => setFilter(f.value)}
          >
            {f.label}
          </button>
        ))}
      </div>

      {/* Table */}
      <div className="card">
        {appointments.length === 0 ? (
          <p className="empty-state">Нет записей</p>
        ) : (
          <table className="appointments-table">
            <thead>
              <tr>
                <th>Дата</th>
                <th>Статус</th>
                <th>Действия</th>
              </tr>
            </thead>
            <tbody>
              {appointments.map((appt) => (
                <tr key={appt.id}>
                  <td>
                    {new Date(appt.appointment_date).toLocaleString('ru-RU')}
                  </td>
                  <td>
                    <span className={`status-badge status-${appt.status}`}>
                      {statusLabels[appt.status] || appt.status}
                    </span>
                  </td>
                  <td className="actions-cell">
                    {appt.status === 'pending' && (
                      <>
                        <button
                          className="btn btn-sm btn-confirm"
                          onClick={() => handleConfirm(appt.id)}
                        >
                          ✅ Подтвердить
                        </button>
                        <button
                          className="btn btn-sm btn-cancel"
                          onClick={() => handleCancel(appt.id)}
                        >
                          ❌ Отменить
                        </button>
                      </>
                    )}
                    {appt.status === 'confirmed' && (
                      <button
                        className="btn btn-sm btn-cancel"
                        onClick={() => handleCancel(appt.id)}
                      >
                        ❌ Отменить
                      </button>
                    )}
                    {appt.status === 'cancelled' && (
                      <span className="text-muted">Отменена</span>
                    )}
                    {appt.status === 'completed' && (
                      <span className="text-muted">Завершена</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}

export default AppointmentsPage
