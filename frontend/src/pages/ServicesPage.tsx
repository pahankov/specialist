import { useEffect, useState } from 'react'
import { mastersApi, servicesApi } from '../../api/client'
import type { Master, Service } from '../../api/types'
import { adminApi } from '../../api/adminClient'
import './ServicesPage.css'

function ServicesPage() {
  const [services, setServices] = useState<Service[]>([])
  const [masters, setMasters] = useState<Master[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [showForm, setShowForm] = useState(false)
  const [editingId, setEditingId] = useState<number | null>(null)

  // Form state
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [duration, setDuration] = useState(30)
  const [price, setPrice] = useState(1000)

  const fetchData = async () => {
    try {
      const [mastersResp, servicesResp] = await Promise.all([
        mastersApi.getAll(),
        servicesApi.getAll(),
      ])
      setMasters(mastersResp.data)
      setServices(servicesResp.data)
    } catch (err: any) {
      if (err.response?.status === 401) {
        localStorage.removeItem('access_token')
        window.location.href = '/admin/login'
      } else {
        setError('Ошибка загрузки данных')
      }
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchData()
  }, [])

  const resetForm = () => {
    setName('')
    setDescription('')
    setDuration(30)
    setPrice(1000)
    setEditingId(null)
    setShowForm(false)
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      if (editingId) {
        await adminApi.updateService(editingId, { name, description, duration_minutes: duration, price })
      } else {
        const masterId = masters[0]?.id || 1
        await adminApi.createService({ name, description, duration_minutes: duration, price, master_id: masterId })
      }
      resetForm()
      fetchData()
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Ошибка')
    }
  }

  const handleEdit = (service: Service) => {
    setName(service.name)
    setDescription(service.description || '')
    setDuration(service.duration_minutes)
    setPrice(service.price)
    setEditingId(service.id)
    setShowForm(true)
  }

  const handleDelete = async (id: number) => {
    if (!confirm('Удалить услугу?')) return
    try {
      await adminApi.deleteService(id)
      fetchData()
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Ошибка')
    }
  }

  if (loading) return <div className="admin-main"><div className="loading">Загрузка...</div></div>
  if (error) return <div className="admin-main"><div className="error-message">{error}</div></div>

  return (
    <div className="admin-main">
      <div className="page-header">
        <h1>Управление услугами</h1>
        <p>Добавление, редактирование и удаление услуг</p>
      </div>

      {/* Form */}
      {showForm && (
        <div className="card form-card">
          <h3>{editingId ? 'Редактировать услугу' : 'Новая услуга'}</h3>
          <form onSubmit={handleSubmit}>
            <div className="form-row">
              <div className="form-group">
                <label>Название</label>
                <input value={name} onChange={(e) => setName(e.target.value)} required placeholder="Шугаринг ног" />
              </div>
              <div className="form-group">
                <label>Длительность (мин)</label>
                <input type="number" value={duration} onChange={(e) => setDuration(+e.target.value)} required min="5" />
              </div>
              <div className="form-group">
                <label>Цена (₽)</label>
                <input type="number" value={price} onChange={(e) => setPrice(+e.target.value)} required min="0" />
              </div>
            </div>
            <div className="form-group">
              <label>Описание</label>
              <input value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Описание услуги" />
            </div>
            <div className="form-actions">
              <button type="submit" className="btn btn-primary">
                {editingId ? 'Сохранить' : 'Создать'}
              </button>
              <button type="button" className="btn btn-ghost" onClick={resetForm}>
                Отмена
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Services list */}
      <div className="card">
        <div className="card-header">
          <h3>Список услуг ({services.length})</h3>
          <button className="btn btn-primary" onClick={() => setShowForm(true)}>
            + Добавить услугу
          </button>
        </div>

        {services.length === 0 ? (
          <p className="empty-state">Нет услуг. Добавьте первую!</p>
        ) : (
          <table className="services-table">
            <thead>
              <tr>
                <th>Название</th>
                <th>Описание</th>
                <th>Длительность</th>
                <th>Цена</th>
                <th>Действия</th>
              </tr>
            </thead>
            <tbody>
              {services.map((s) => (
                <tr key={s.id}>
                  <td><strong>{s.name}</strong></td>
                  <td>{s.description || '—'}</td>
                  <td>{s.duration_minutes} мин</td>
                  <td>{s.price.toLocaleString('ru-RU')} ₽</td>
                  <td className="actions-cell">
                    <button className="btn btn-sm btn-edit" onClick={() => handleEdit(s)}>
                      ✏️
                    </button>
                    <button className="btn btn-sm btn-delete" onClick={() => handleDelete(s.id)}>
                      🗑️
                    </button>
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

export default ServicesPage
