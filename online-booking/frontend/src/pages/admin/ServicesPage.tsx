import { useEffect, useState } from 'react'
import { adminApi } from '../../api/client'
import { ConfirmDialog, ResizableTh, useColumnWidths } from '../../components/common'
import type { Service } from '../../api/types'
import { formatPrice } from '../../components/schedule/helpers'
import { getApiErrorMessage } from '../../utils/apiError'
import '../../styles/tables.css'
import './ServicesPage.css'

function ServicesPage() {
  const { widths: colW, setWidth: setColW } = useColumnWidths('services', {
    name: 220, desc: 300, duration: 120, price: 110, actions: 120,
  })
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
      setServices(s.data.items)
    } catch (err: any) {
      if (err.response?.status === 401) { window.location.href = '/admin/login' }
      else setError('Ошибка загрузки')
    } finally { setLoading(false) }
  }

  useEffect(() => { fetchData() }, [])

  const resetForm = () => { setName(''); setDescription(''); setDuration(30); setPrice(1000); setEditingId(null); setShowForm(false) }
  const clearSuccess = () => { setSuccessMsg(''); setError('') }

  const showError = (err: unknown) => {
    setError(getApiErrorMessage(err, 'Ошибка сервера'))
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

  if (loading) return <div><div className="loading">Загрузка...</div></div>
  if (error) return <div><div className="error-message">{error}</div></div>

  return (
    <div>
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
          <table className="services-table resizable-table">
            <thead><tr><ResizableTh width={colW.name} onResize={(w) => setColW('name', w)}>Название</ResizableTh><ResizableTh width={colW.desc} onResize={(w) => setColW('desc', w)}>Описание</ResizableTh><ResizableTh width={colW.duration} onResize={(w) => setColW('duration', w)}>Длительность</ResizableTh><ResizableTh width={colW.price} onResize={(w) => setColW('price', w)}>Цена</ResizableTh><ResizableTh width={colW.actions} onResize={(w) => setColW('actions', w)}>Действия</ResizableTh></tr></thead>
            <tbody>
              {services.map(s => (
                <tr key={s.id}>
                  <td><strong>{s.name}</strong></td>
                  <td>{s.description || '—'}</td>
                  <td>{s.duration_minutes} мин</td>
                  <td>{formatPrice(s.price)} ₽</td>
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

      <ConfirmDialog
        open={!!deletingId}
        onClose={() => setDeletingId(null)}
        title="🗑️ Удалить услугу?"
        message="Это действие нельзя отменить. Услуга будет скрыта из списка."
        confirmLabel="Удалить"
        danger
        onConfirm={() => deletingId !== null && handleDelete(deletingId)}
      />
    </div>
  )
}
export default ServicesPage
