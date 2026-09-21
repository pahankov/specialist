import { useEffect, useState } from 'react'
import { adminApi } from '../../api/client'
import type { Client } from '../../api/types'
import { PHONE_PLACEHOLDER, EMAIL_PLACEHOLDER } from '../../constants'
import './ClientsPage.css'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

function ClientsPage() {
  const [clients, setClients] = useState<Client[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [successMsg, setSuccessMsg] = useState('')
  const [showForm, setShowForm] = useState(false)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [deletingId, setDeletingId] = useState<number | null>(null)
  const [name, setName] = useState('')
  const [phone, setPhone] = useState('')
  const [email, setEmail] = useState('')

  const fetchData = async () => {
    try {
      const c = await adminApi.getClients()
      setClients(c.data)
    } catch (err: any) {
      if (err.response?.status === 401) { localStorage.removeItem('access_token'); window.location.href = '/admin/login' }
      else setError('Ошибка загрузки')
    } finally { setLoading(false) }
  }

  useEffect(() => { fetchData() }, [])

  const resetForm = () => { setName(''); setPhone(''); setEmail(''); setEditingId(null); setShowForm(false) }
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
        await adminApi.updateClient(editingId, { name, phone, email: email || undefined })
        setSuccessMsg('Клиент обновлён')
      } else {
        await adminApi.createClient({ name, phone, email: email || undefined })
        setSuccessMsg('Клиент создан')
      }
      resetForm()
      fetchData()
    } catch (err: any) { showError(err) }
  }

  const handleEdit = (c: Client) => {
    setName(c.name)
    setPhone(c.phone)
    setEmail(c.email || '')
    setEditingId(c.id)
    setShowForm(true)
    clearSuccess()
  }

  const handleDelete = async (id: number) => {
    clearSuccess()
    try {
      await adminApi.deleteClient(id)
      setSuccessMsg('Клиент удалён')
      fetchData()
    } catch (err: any) { showError(err) }
    finally { setDeletingId(null) }
  }

  const formatPhoneInput = (value: string) => {
    const digits = value.replace(/\D/g, '')
    if (digits.length === 0) return digits
    if (digits.length <= 3) return digits
    if (digits.length <= 6) return `${digits.slice(0, 3)} ${digits.slice(3)}`
    if (digits.length <= 9) return `${digits.slice(0, 3)} ${digits.slice(3, 6)} ${digits.slice(6)}`
    return `${digits.slice(0, 3)} ${digits.slice(3, 6)} ${digits.slice(6, 8)} ${digits.slice(8, 10)}`
  }

  const handlePhoneChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const raw = e.target.value.replace(/\D/g, '').slice(0, 10)
    const formatted = formatPhoneInput(raw)
    setPhone(formatted)
  }

  if (loading) return <div><div className="loading">Загрузка...</div></div>

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
      {successMsg && <div className="success-message" style={{ background: '#e8f5e9', color: '#2e7d32', padding: '12px 16px', borderRadius: 8, marginBottom: 20 }}>{successMsg}</div>}
      {error && <div className="error-message">{error}</div>}

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

      <div className="card">
        <div className="card-header"><h3>Список клиентов ({clients.length})</h3><button className="btn btn-primary" onClick={() => setShowForm(true)}>+ Добавить клиента</button></div>
        {clients.length === 0 ? <p className="empty-state">Нет клиентов</p> : (
          <table className="clients-table">
            <thead><tr><th>Имя</th><th>Телефон</th><th>Email</th><th>Действия</th></tr></thead>
            <tbody>
              {clients.map(c => (
                <tr key={c.id}>
                  <td><strong>{c.name}</strong></td>
                  <td><a href={`tel:${c.phone}`}>{c.phone}</a></td>
                  <td>{c.email || '—'}</td>
                  <td className="actions-cell">
                    <button className="btn btn-sm btn-edit" onClick={() => handleEdit(c)}>✏️ Редактировать</button>
                    <button className="btn btn-sm btn-delete" onClick={() => setDeletingId(c.id)}>🗑️ Удалить</button>
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
