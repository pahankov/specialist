import { useEffect, useState } from 'react'
import { adminApi } from '../api/adminClient'
import './SchedulePage.css'

const dayNames = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье']

function SchedulePage() {
  const [hours, setHours] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [showForm, setShowForm] = useState(false)
  const [dayOfWeek, setDayOfWeek] = useState(0)
  const [startTime, setStartTime] = useState('10:00')
  const [endTime, setEndTime] = useState('18:00')

  const fetch = async () => {
    try { const resp = await adminApi.getWorkingHours(); setHours(resp.data) }
    catch (err: any) { if (err.response?.status === 401) { localStorage.removeItem('access_token'); window.location.href = '/admin/login' } else setError('Ошибка загрузки') }
    finally { setLoading(false) }
  }

  useEffect(() => { fetch() }, [])

  const handleSubmit = async (e: React.FormEvent) => { e.preventDefault(); try { await adminApi.createWorkingHour({ day_of_week: dayOfWeek, start_time: startTime, end_time: endTime }); setShowForm(false); fetch() } catch { alert('Ошибка') } }
  const handleDelete = async (id: number) => { if (!confirm('Удалить?')) return; try { await adminApi.deleteWorkingHour(id); fetch() } catch { alert('Ошибка') } }

  if (loading) return <div className="admin-main"><div className="loading">Загрузка...</div></div>
  if (error) return <div className="admin-main"><div className="error-message">{error}</div></div>

  return (
    <div className="admin-main">
      <div className="page-header"><h1>Управление расписанием</h1><p>Настройка рабочих часов мастера</p></div>
      {showForm && (
        <div className="card form-card">
          <h3>Добавить рабочий день</h3>
          <form onSubmit={handleSubmit}>
            <div className="form-row">
              <div className="form-group"><label>День недели</label><select value={dayOfWeek} onChange={(e) => setDayOfWeek(+e.target.value)}>{dayNames.map((n, i) => <option key={i} value={i}>{n}</option>)}</select></div>
              <div className="form-group"><label>Начало</label><input type="time" value={startTime} onChange={(e) => setStartTime(e.target.value)} required /></div>
              <div className="form-group"><label>Конец</label><input type="time" value={endTime} onChange={(e) => setEndTime(e.target.value)} required /></div>
            </div>
            <div className="form-actions"><button type="submit" className="btn btn-primary">Добавить</button><button type="button" className="btn btn-ghost" onClick={() => setShowForm(false)}>Отмена</button></div>
          </form>
        </div>
      )}
      <div className="card">
        <div className="card-header"><h3>Рабочее расписание</h3><button className="btn btn-primary" onClick={() => setShowForm(true)}>+ Добавить день</button></div>
        {hours.length === 0 ? <p className="empty-state">Нет расписания</p> : (
          <table className="schedule-table">
            <thead><tr><th>День</th><th>Время работы</th><th>Действия</th></tr></thead>
            <tbody>
              {hours.map(h => (<tr key={h.id}><td><strong>{dayNames[h.day_of_week]}</strong></td><td>{h.start_time?.slice(0,5)} — {h.end_time?.slice(0,5)}</td><td><button className="btn btn-sm btn-delete" onClick={() => handleDelete(h.id)}>🗑️ Удалить</button></td></tr>))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
export default SchedulePage
