import { useEffect, useState } from 'react'
import { toast } from 'sonner'
import { adminApi } from '../../api/client'
import type { Client } from '../../api/types'
import { PHONE_PLACEHOLDER, EMAIL_PLACEHOLDER } from '../../constants'
import { formatPhone } from '../../utils/formatPhone'
import { getApiErrorMessage, getApiErrorStatus } from '../../utils/apiError'
import { Skeleton, EmptyState, Tooltip, ConfirmDialog, MasterSelect } from '../../components/common'
import './ClientsPage.css'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

function ClientsPage() {
  const [clients, setClients] = useState<Client[]>([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [deletingId, setDeletingId] = useState<number | null>(null)
  const [name, setName] = useState('')
  const [phone, setPhone] = useState('')
  const [email, setEmail] = useState('')
  const [search, setSearch] = useState('')
  const [searchInput, setSearchInput] = useState('')
  const [masterIdFilter, setMasterIdFilter] = useState<number | ''>('')
  const [totalClients, setTotalClients] = useState(0)
  const [sortKey, setSortKey] = useState<'name' | 'no_show' | null>(null)
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc')

  // Debounce search input (400ms) — no request per keystroke
  useEffect(() => {
    const t = setTimeout(() => setSearch(searchInput), 400)
    return () => clearTimeout(t)
  }, [searchInput])

  const toggleSort = (key: 'name' | 'no_show') => {
    if (sortKey !== key) {
      setSortKey(key)
      setSortDir('asc')
    } else if (sortDir === 'asc') {
      setSortDir('desc')
    } else {
      setSortKey(null)
      setSortDir('asc')
    }
  }

  const sortArrow = (key: 'name' | 'no_show') =>
    sortKey !== key ? '' : (sortDir === 'asc' ? ' ▲' : ' ▼')

  const fetchData = async () => {
    setLoading(true)
    try {
      const params: { page: number; page_size: number; search?: string; master_id?: number; sort_by?: string; sort_dir?: string } = { page: 1, page_size: 200 }
      if (search?.trim()) params.search = search.trim()
      if (masterIdFilter !== '') params.master_id = masterIdFilter
      if (sortKey) { params.sort_by = sortKey; params.sort_dir = sortDir }
      const c = await adminApi.getClients(params)
      setClients(c.data.items)
      setTotalClients(c.data.total)
    } catch (err: unknown) {
      if (getApiErrorStatus(err) === 401) { window.location.href = '/admin/login' }
      else toast.error('Ошибка загрузки')
    } finally { setLoading(false) }
  }

  useEffect(() => { fetchData() }, [search, masterIdFilter, sortKey, sortDir])

  const resetForm = () => { setName(''); setPhone(''); setEmail(''); setEditingId(null); setShowForm(false) }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      if (editingId) {
        await adminApi.updateClient(editingId, { name, phone, email: email || undefined })
        toast.success('Клиент обновлён')
      } else {
        await adminApi.createClient({ name, phone, email: email || undefined })
        toast.success('Клиент создан')
      }
      resetForm()
      fetchData()
    } catch (err: unknown) {
      toast.error(getApiErrorMessage(err, 'Произошла ошибка'))
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
    try {
      await adminApi.deleteClient(id)
      // No undo: backend has no undelete, a fake "cancel" toast would lie.
      toast.success('Клиент удалён')
      fetchData()
    } catch {
      toast.error('Ошибка удаления')
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

      {/* Search and filter bar */}
      <div className="card" style={{ marginBottom: 16, padding: 16 }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: 12 }}>
          <div className="form-group" style={{ marginBottom: 0 }}>
            <label style={{ fontSize: 12, color: '#666', marginBottom: 4, display: 'block' }}>🔍 Поиск по имени или телефону</label>
            <input
              type="text"
              placeholder="Введите имя или телефон..."
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              style={{ width: '100%', padding: 8, border: '2px solid #e0e0e0', borderRadius: 8, fontSize: 14 }}
            />
          </div>
          <MasterSelect
            value={masterIdFilter}
            onChange={setMasterIdFilter}
            allLabel="Все клиенты"
            style={{ marginBottom: 0 }}
          />
          {(search || masterIdFilter !== '') && (
            <div className="form-group" style={{ marginBottom: 0, display: 'flex', alignItems: 'flex-end' }}>
              <button className="btn btn-ghost" onClick={() => { setSearch(''); setMasterIdFilter('') }} style={{ width: '100%', fontSize: 13 }}>
                ✕ Сбросить
              </button>
            </div>
          )}
        </div>
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
            <h3>Список клиентов <span className="client-count">({clients.length}{totalClients > 200 ? ` из ${totalClients}` : ''})</span></h3>
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
          <div style={{ overflowX: 'auto' }}>
            <table className="clients-table" style={{ minWidth: 640 }}>
              <thead><tr>
                <th onClick={() => toggleSort('name')} style={{ cursor: 'pointer', userSelect: 'none' }} title="Сортировать по имени">
                  Имя{sortArrow('name')}
                </th>
                <th>Телефон</th>
                <th>Email</th>
                <th onClick={() => toggleSort('no_show')} style={{ cursor: 'pointer', userSelect: 'none' }} title="Сортировать по неявкам">
                  Неявки{sortArrow('no_show')}
                </th>
                <th>Действия</th>
              </tr></thead>
              <tbody>
                {clients.map(c => (
                  <tr key={c.id}>
                    <td><strong>{c.name}</strong></td>
                    <td><a href={`tel:${c.phone}`}>{c.phone}</a></td>
                    <td>{c.email || '—'}</td>
                    <td>{(c.no_show_count ?? 0) > 0 ? `⚠️ ${c.no_show_count}` : '—'}</td>
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
          </div>
          )}
        </div>
      )}

      <ConfirmDialog
        open={deletingId !== null}
        onClose={() => setDeletingId(null)}
        title="🗑️ Удалить клиента?"
        message="Клиент будет удалён вместе со всеми записями. Это действие нельзя отменить."
        confirmLabel="Удалить"
        danger
        onConfirm={() => deletingId !== null && handleDelete(deletingId)}
      />
    </div>
  )
}

export default ClientsPage
