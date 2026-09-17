import { useEffect, useState } from 'react'
import { adminApi } from '../api/adminClient'
import type { Service } from '../api/types'
import './ServicesPage.css'

function ServicesPage() {
  const [services, setServices] = useState<Service[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [successMsg, setSuccessMsg] = useState('')
  const [showForm, setShowForm] = useState(false)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [deletingId, setDeletingId] = useState<number | null>(null)
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [duration, setDuration] = useState(30)
  const [price, setPrice] = useState(1000)

  const fetchData = async () => {
    try {
      const s = await adminApi.getServices()
      setServices(s.data)
    } catch (err: any) {
      if (err.response?.status === 401) { localStorage.removeItem('access_token'); window.location.href = '/admin/login' }
      else setError('Ошибка загрузки')
    } finally { setLoading(false) }
  }

  useEffect(() => { fetchData() }, [])

  const resetForm = () => { setName(''); setDescription(''); setDuration(30); setPrice(1000); setEditingId(null); setShowForm(false) }
  const clearSuccess = () => { setSuccessMsg(''); setError('') }

  const showError = (err: any) => {
    const detail = err.response?.data?.detail
    if (typeof detail === 'string') setError(detail)
    else if (detail && typeof detail === 'object') setError(JSON.stringify(detail))
    else setError('Произошла ошибка')
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    clearSuccess()
    try {
      if (editingId) {
        await adminApi.updateService(editingId, { name, description, duration_minutes: duration, price })
        setSuccessMsg('Услуга обновлена')
      } else {
        await adminApi.createService({ name, description, duration_minutes: duration, price })
        setSuccessMsg('Услуга создана')
      }
      resetForm(); fetchData()
    } catch (err: any) { showError(err) }
  }

  const handleEdit = (s: Service) => {
    setName(s.name)
    setDescription(s.description || '')
    setDuration(s.duration_minutes)
    setPrice(Number(s.price))
    setEditingId(s.id)
    setShowForm(true)
    clearSuccess()
  }

  const handleDelete = async (id: number) => {
    try {
      await adminApi.deleteService(id)
      setSuccessMsg('Услуга удалена')
      fetchData()
    } catch (err: any) { showError(err) }
    finally { setDeletingId(null) }
  }

  if (loading) return <div className="admin-main"><div className="loading">Загрузка...</div></div>
  if (error) return <div className="admin-main"><div className="error-message">{error}</div></div>

  return (
    <div className="admin-main">
      <div className="page-header"><h1>Управление услугами</h1><p>Добавление, редактирование и удаление услуг</p></div>
      {successMsg && <div className="success-message" style={{ background: '#e8f5e9', color: '#2e7d32', padding: '12px 16px', borderRadius: 8, marginBottom: 20 }}>{successMsg}</div>}
      {error && <div className="error-message">{error}</div>}

      {showForm && (
        <div className="card form-card">
          <h3>{editingId ? 'Редактировать услугу' : 'Новая услуга'}</h3>
          <form onSubmit={handleSubmit}>
            <div className="form-row">
              <div className="form-group"><label>Название</label><input value={name} onChange={(e) => setName(e.target.value)} required placeholder="Шугаринг ног" /></div>
              <div className="form-group"><label>Длительность (мин)</label><input type="number" value={duration} onChange={(e) => setDuration(+e.target.value)} required min="5" /></div>
              <div className="form-group"><label>Цена (₽)</label><input type="number" value={price} onChange={(e) => setPrice(+e.target.value)} required min="0" /></div>
            </div>
            <div className="form-group"><label>Описание</label><input value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Описание услуги" /></div>
            <div className="form-actions">
              <button type="submit" className="btn btn-primary">{editingId ? 'Сохранить' : 'Создать'}</button>
              <button type="button" className="btn btn-ghost" onClick={resetForm}>Отмена</button>
            </div>
          </form>
        </div>
      )}

      <div className="card">
        <div className="card-header"><h3>Список услуг ({services.length})</h3><button className="btn btn-primary" onClick={() => setShowForm(true)}>+ Добавить услугу</button></div>
        {services.length === 0 ? <p className="empty-state">Нет услуг</p> : (
          <table className="services-table">
            <thead><tr><th>Название</th><th>Описание</th><th>Длительность</th><th>Цена</th><th>Действия</th></tr></thead>
            <tbody>
              {services.map(s => (
                <tr key={s.id}>
                  <td><strong>{s.name}</strong></td>
                  <td>{s.description || '—'}</td>
                  <td>{s.duration_minutes} мин</td>
                  <td>{s.price.toLocaleString('ru-RU')} ₽</td>
                  <td className="actions-cell">
                    <button className="btn btn-sm btn-edit" onClick={() => handleEdit(s)}>✏️ Редактировать</button>
                    <button className="btn btn-sm btn-delete" onClick={() => setDeletingId(s.id)}>🗑️ Удалить</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {deletingId && (
        <div className="modal-overlay" onClick={() => setDeletingId(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h3>🗑️ Удалить услугу?</h3>
            <p>Это действие нельзя отменить. Услуга будет скрыта из списка.</p>
            <div className="modal-actions">
              <button className="btn btn-ghost" onClick={() => setDeletingId(null)}>Отмена</button>
              <button className="btn btn-delete" onClick={() => handleDelete(deletingId)}>Удалить</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
export default ServicesPage
