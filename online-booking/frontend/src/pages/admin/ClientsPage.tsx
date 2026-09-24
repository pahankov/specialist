import { useEffect, useState } from 'react'
import { adminApi } from '../../api/client'
import type { Client } from '../../api/types'
import { PHONE_PLACEHOLDER, EMAIL_PLACEHOLDER } from '../../constants'
import { formatPhone } from '../../utils/formatPhone'
import { useToast } from '../../components/Toast'
import { Skeleton, EmptyState, Tooltip } from '../../components/common'
import './ClientsPage.css'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

function ClientsPage() {
  const { addToast } = useToast()
  const [clients, setClients] = useState<Client[]>([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [deletingId, setDeletingId] = useState<number | null>(null)
  const [name, setName] = useState('')
  const [phone, setPhone] = useState('')
  const [email, setEmail] = useState('')

  const fetchData = async () => {
    try {
      const c = await adminApi.getClients()
      setClients(c.data.items)
    } catch (err: any) {
      if (err.response?.status === 401) { localStorage.removeItem('access_token'); window.location.href = '/admin/login' }
      else addToast('Ошибка загрузки', 'error')
    } finally { setLoading(false) }
  }

  useEffect(() => { fetchData() }, [])

  const resetForm = () => { setName(''); setPhone(''); setEmail(''); setEditingId(null); setShowForm(false) }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      if (editingId) {
        await adminApi.updateClient(editingId, { name, phone, email: email || undefined })
        addToast('Клиент обновлён', 'success')
      } else {
        await adminApi.createClient({ name, phone, email: email || undefined })
        addToast('Клиент создан', 'success')
      }
      resetForm()
      fetchData()
    } catch (err: any) {
      const detail = err.response?.data?.detail
      const msg = typeof detail === 'string' ? detail : 'Произошла ошибка'
      addToast(msg, 'error')
    }
  }

  const handleEdit = (c: Client) => {
    setName(c.name)
    setPhone(c.phone)
    setEmail(c.email || '')
    setEditingId(c.id)
    setShowForm(true)
  }

  const handleDelete = async (id: number) => {
    const client = clients.find(c => c.id === id)
    if (!client) return

    const undoAction = () => {
      addToast('Удаление отменено', 'info')
    }

    try {
      await adminApi.deleteClient(id)
      addToast(
        'Клиент удалён',
        'success',
        undoAction,
        'Отменить'
      )
      fetchData()
    } catch (err: any) {
      addToast('Ошибка удаления', 'error')
    } finally { setDeletingId(null) }
  }

  const handlePhoneChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setPhone(formatPhone(e.target.value))
  }

  return (
    <div>
      <div className="page-header" style={{ display: 'flex', alignItems: 'center', gap: 16, justifyContent: 'center' }}>
        <div>
          <h1>Управление клиентами</h1>
          <p>Добавление, редактирование и удаление клиентов</p>
        </div>
        <button
          className="btn btn-ghost"
          onClick={() => { window.open(`${API_URL}/api/v1/admin/export/clients`, '_blank') }}
        >
          📥 Экспорт CSV
        </button>
      </div>

      {showForm && (
        <div className="card form-card">
          <h3>{editingId ? 'Редактировать клиента' : 'Новый клиент'}</h3>
          <form onSubmit={handleSubmit}>
            <div className="form-row">
              <div className="form-group"><label>Имя</label><input value={name} onChange={(e) => setName(e.target.value)} required placeholder="Иван Иванов" /></div>
              <div className="form-group"><label>Телефон</label><input value={phone} onChange={handlePhoneChange} required placeholder={PHONE_PLACEHOLDER} /></div>
              <div className="form-group"><label>Email</label><input value={email} onChange={(e) => setEmail(e.target.value)} placeholder={EMAIL_PLACEHOLDER} /></div>
            </div>
            <div className="form-actions">
              <button type="submit" className="btn btn-primary">{editingId ? 'Сохранить' : 'Создать'}</button>
              <button type="button" className="btn btn-ghost" onClick={resetForm}>Отмена</button>
            </div>
          </form>
        </div>
      )}

      {loading ? (
        <div className="card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
            <Skeleton width="200px" height="24px" />
            <Skeleton width="140px" height="36px" />
          </div>
          <Skeleton rows={5} height="48px" />
        </div>
      ) : (
        <div className="card">
          <div className="card-header">
            <h3>Список клиентов <span className="client-count">({clients.length})</span></h3>
            <Tooltip content="Добавить нового клиента">
              <button className="btn btn-primary" onClick={() => setShowForm(true)}>+ Добавить клиента</button>
            </Tooltip>
          </div>

          {clients.length === 0 ? (
            <EmptyState
              icon="👥"
              title="Клиенты не найдены"
              description="Добавьте первого клиента или измените параметры поиска"
              actionLabel="+ Добавить клиента"
              onAction={() => setShowForm(true)}
            />
          ) : (
            <table className="clients-table">
              <thead><tr><th>Имя</th><th>Телефон</th><th>Email</th><th>Действия</th></tr></thead>
              <tbody>
                {clients.map(c => (
                  <tr key={c.id}>
                    <td><strong>{c.name}</strong></td>
                    <td><a href={`tel:${c.phone}`}>{c.phone}</a></td>
                    <td>{c.email || '—'}</td>
                    <td className="actions-cell">
                      <Tooltip content="Редактировать">
                        <button className="btn btn-sm btn-edit" onClick={() => handleEdit(c)}>✏️</button>
                      </Tooltip>
                      <Tooltip content="Удалить">
                        <button className="btn btn-sm btn-delete" onClick={() => setDeletingId(c.id)}>🗑️</button>
                      </Tooltip>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {deletingId && (
        <div className="modal-overlay" onClick={() => setDeletingId(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h3>🗑️ Удалить клиента?</h3>
            <p>Клиент будет удалён вместе со всеми записями. Это действие нельзя отменить.</p>
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

export default ClientsPage
