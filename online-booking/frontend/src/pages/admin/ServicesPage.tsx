import { useEffect, useState } from 'react'
import { toast } from 'sonner'
import { adminApi } from '../../api/client'
import { ConfirmDialog, ResizableTh, useColumnWidths, Skeleton, EmptyState } from '../../components/common'
import type { Service } from '../../api/types'
import { formatPrice } from '../../components/schedule/helpers'
import { getApiErrorMessage, getApiErrorStatus } from '../../utils/apiError'
import '../../styles/tables.css'
import './ServicesPage.css'

function ServicesPage() {
  const { widths: colW, setWidth: setColW } = useColumnWidths('services', {
    name: 220, desc: 300, duration: 120, price: 110, actions: 120,
  })
  const [services, setServices] = useState<Service[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
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
    } catch (err: unknown) {
      if (getApiErrorStatus(err) === 401) { window.location.href = '/admin/login' }
      else setError('Ошибка загрузки')
    } finally { setLoading(false) }
  }

  useEffect(() => { fetchData() }, [])

  const resetForm = () => { setName(''); setDescription(''); setDuration(30); setPrice(1000); setEditingId(null); setShowForm(false) }

  const showError = (err: unknown) => {
    setError(getApiErrorMessage(err, 'Ошибка сервера'))
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    try {
      if (editingId) {
        await adminApi.updateService(editingId, { name, description, duration_minutes: duration, price })
        toast.success('Услуга обновлена')
      } else {
        await adminApi.createService({ name, description, duration_minutes: duration, price })
        toast.success('Услуга создана')
      }
      resetForm(); fetchData()
    } catch (err: unknown) { showError(err) }
  }

  const handleEdit = (s: Service) => {
    setName(s.name)
    setDescription(s.description || '')
    setDuration(s.duration_minutes)
    setPrice(Number(s.price))
    setEditingId(s.id)
    setShowForm(true)
    setError('')
  }

  const handleDelete = async (id: number) => {
    try {
      await adminApi.deleteService(id)
      toast.success('Услуга удалена')
      fetchData()
    } catch (err: unknown) { showError(err) }
    finally { setDeletingId(null) }
  }

  if (loading) return <div><Skeleton rows={6} /></div>
  if (error) return <div><div className="error-message">{error}</div></div>

  return (
    <div>
      <div className="page-header"><h1>Управление услугами</h1><p>Добавление, редактирование и удаление услуг</p></div>
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
        {services.length === 0 ? <EmptyState title="Нет услуг" actionLabel="Добавить услугу" onAction={() => setShowForm(true)} /> : (
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
