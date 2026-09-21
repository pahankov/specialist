import { useEffect, useState } from 'react'
import { superAdminApi } from '../../api/client'
import type { Master } from '../../api/types'
import Modal from '../../components/common/Modal'
import './MastersPage.css'

function MastersPage() {
  const [masters, setMasters] = useState<Master[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [filterActive, setFilterActive] = useState<'all' | 'active' | 'inactive'>('all')
  const [filterAdmin, setFilterAdmin] = useState<'all' | 'admin' | 'user'>('all')
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [showEditModal, setShowEditModal] = useState(false)
  const [editingMaster, setEditingMaster] = useState<Master | null>(null)
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)
  const [deleteConfirm, setDeleteConfirm] = useState<number | null>(null)

  // Create form
  const [createForm, setCreateForm] = useState({
    name: '', email: '', password: '', phone: '', telegram_username: '',
  })

  // Edit form
  const [editForm, setEditForm] = useState({
    name: '', phone: '', telegram_username: '', description: '', password: '',
  })

  const showMessage = (type: 'success' | 'error', text: string) => {
    setMessage({ type, text })
    setTimeout(() => setMessage(null), 4000)
  }

  const loadMasters = async () => {
    setLoading(true)
    try {
      const params: Record<string, string> = {}
      if (search?.trim()) params.search = search.trim()
      if (filterActive === 'active') params.is_active = 'true'
      if (filterActive === 'inactive') params.is_active = 'false'
      if (filterAdmin === 'admin') params.is_admin = 'true'
      if (filterAdmin === 'user') params.is_admin = 'false'

      // Remove empty params — axios sends them as ?param= which can cause 422
      const cleanParams: Record<string, string> = {}
      for (const [key, value] of Object.entries(params)) {
        if (value && value.trim()) cleanParams[key] = value.trim()
      }

      const { data } = await superAdminApi.getAllMasters(cleanParams)
      setMasters(data)
    } catch (err: any) {
      const detail = err.response?.data?.detail
      const msg = typeof detail === 'string' ? detail : (err.response?.data?.message || 'Ошибка загрузки мастеров')
      showMessage('error', msg)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadMasters()
  }, [])

  const handleSearch = () => loadMasters()

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      await superAdminApi.createMaster(createForm)
      showMessage('success', 'Мастер успешно создан')
      setShowCreateModal(false)
      setCreateForm({ name: '', email: '', password: '', phone: '', telegram_username: '' })
      loadMasters()
    } catch (err: any) {
      showMessage('error', err.response?.data?.detail || 'Ошибка создания мастера')
    }
  }

  const handleEdit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!editingMaster) return
    try {
      const data: any = { ...editForm }
      if (!data.password) delete data.password
      await superAdminApi.updateMaster(editingMaster.id, data)
      showMessage('success', 'Мастер обновлён')
      setShowEditModal(false)
      setEditingMaster(null)
      loadMasters()
    } catch (err: any) {
      showMessage('error', err.response?.data?.detail || 'Ошибка обновления мастера')
    }
  }

  const handleToggleActive = async (id: number) => {
    try {
      await superAdminApi.toggleMasterActive(id)
      showMessage('success', 'Статус мастера изменён')
      loadMasters()
    } catch (err: any) {
      showMessage('error', err.response?.data?.detail || 'Ошибка изменения статуса')
    }
  }

  const handleToggleAdmin = async (id: number) => {
    try {
      await superAdminApi.toggleMasterAdmin(id)
      showMessage('success', 'Права суперпользователя изменены')
      loadMasters()
    } catch (err: any) {
      showMessage('error', err.response?.data?.detail || 'Ошибка изменения прав')
    }
  }

  const handleDelete = async (id: number) => {
    try {
      await superAdminApi.deleteMaster(id)
      showMessage('success', 'Мастер удалён')
      setDeleteConfirm(null)
      loadMasters()
    } catch (err: any) {
      showMessage('error', err.response?.data?.detail || 'Ошибка удаления мастера')
    }
  }

  const openEditModal = (master: Master) => {
    setEditingMaster(master)
    setEditForm({
      name: master.name,
      phone: master.phone || '',
      telegram_username: master.telegram_username || '',
      description: master.description || '',
      password: '',
    })
    setShowEditModal(true)
  }

  return (
    <div className="masters-page">
      <div className="page-header">
        <h1>👨‍💼 Управление мастерами</h1>
        <button className="btn btn-primary" onClick={() => setShowCreateModal(true)}>+ Добавить мастера</button>
      </div>

      {message && (
        <div className={`message-bar message-bar-${message.type}`}>
          {message.type === 'success' ? '✅' : '❌'} {message.text}
        </div>
      )}

      {/* Filters */}
      <div className="masters-filters">
        <div className="filter-row">
          <input
            type="text"
            placeholder="Поиск по имени или email..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
            className="filter-input"
          />
          <button className="btn btn-secondary" onClick={handleSearch}>Найти</button>
          <select value={filterActive} onChange={(e) => setFilterActive(e.target.value as any)} className="filter-select">
            <option value="all">Все статусы</option>
            <option value="active">Активные</option>
            <option value="inactive">Заблокированные</option>
          </select>
          <select value={filterAdmin} onChange={(e) => setFilterAdmin(e.target.value as any)} className="filter-select">
            <option value="all">Все роли</option>
            <option value="admin">Суперпользователи</option>
            <option value="user">Обычные мастера</option>
          </select>
        </div>
      </div>

      {/* Masters table */}
      {loading ? (
        <div className="loading-state">Загрузка...</div>
      ) : masters.length === 0 ? (
        <div className="empty-state">Мастера не найдены</div>
      ) : (
        <div className="masters-table-wrapper">
          <table className="masters-table">
            <thead>
              <tr>
                <th>Имя</th>
                <th>Email</th>
                <th>Телефон</th>
                <th>Статус</th>
                <th>Роль</th>
                <th>Действия</th>
              </tr>
            </thead>
            <tbody>
              {masters.map((master) => (
                <tr key={master.id}>
                  <td>
                    <div className="master-name">{master.name}</div>
                    {master.telegram_username && (
                      <div className="master-telegram">@{master.telegram_username}</div>
                    )}
                  </td>
                  <td>{master.email}</td>
                  <td>{master.phone || '—'}</td>
                  <td>
                    <span className={`status-badge ${master.is_active ? 'status-active' : 'status-inactive'}`}>
                      {master.is_active ? 'Активен' : 'Заблокирован'}
                    </span>
                  </td>
                  <td>
                    <span className={`role-badge ${master.is_admin ? 'role-admin' : 'role-user'}`}>
                      {master.is_admin ? '👑 Суперпользователь' : '👤 Мастер'}
                    </span>
                  </td>
                  <td className="actions-cell">
                    <button className="btn btn-sm btn-secondary" onClick={() => openEditModal(master)}>✏️</button>
                    <button
                      className={`btn btn-sm ${master.is_active ? 'btn-warn' : 'btn-success'}`}
                      onClick={() => handleToggleActive(master.id)}
                      title={master.is_active ? 'Заблокировать' : 'Разблокировать'}
                    >
                      {master.is_active ? '🔒' : '🔓'}
                    </button>
                    <button
                      className={`btn btn-sm ${master.is_admin ? 'btn-warn' : 'btn-info'}`}
                      onClick={() => handleToggleAdmin(master.id)}
                      title={master.is_admin ? 'Убрать права' : 'Дать права'}
                    >
                      {master.is_admin ? '👑' : '👤'}
                    </button>
                    {deleteConfirm === master.id ? (
                      <div className="delete-confirm">
                        <button className="btn btn-sm btn-danger" onClick={() => handleDelete(master.id)}>✓</button>
                        <button className="btn btn-sm btn-ghost" onClick={() => setDeleteConfirm(null)}>✗</button>
                      </div>
                    ) : (
                      <button
                        className="btn btn-sm btn-danger"
                        onClick={() => setDeleteConfirm(master.id)}
                        title="Удалить"
                      >
                        🗑️
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Create Modal */}
      <Modal isOpen={showCreateModal} onClose={() => setShowCreateModal(false)} title="Добавить мастера" actions={[
        { label: 'Отмена', onClick: () => setShowCreateModal(false), variant: 'ghost' },
      ]}>
        <form onSubmit={handleCreate} className="master-form">
          <div className="form-group">
            <label>Имя *</label>
            <input
              type="text"
              value={createForm.name}
              onChange={(e) => setCreateForm({ ...createForm, name: e.target.value })}
              required
              placeholder="Иван Иванов"
            />
          </div>
          <div className="form-group">
            <label>Email *</label>
            <input
              type="email"
              value={createForm.email}
              onChange={(e) => setCreateForm({ ...createForm, email: e.target.value })}
              required
              placeholder="master@example.com"
            />
          </div>
          <div className="form-group">
            <label>Пароль *</label>
            <input
              type="password"
              value={createForm.password}
              onChange={(e) => setCreateForm({ ...createForm, password: e.target.value })}
              required
              placeholder="Минимум 8 символов, заглавная буква, цифра"
            />
          </div>
          <div className="form-group">
            <label>Телефон</label>
            <input
              type="tel"
              value={createForm.phone}
              onChange={(e) => setCreateForm({ ...createForm, phone: e.target.value })}
              placeholder="+7 (999) 123-45-67"
            />
          </div>
          <div className="form-group">
            <label>Telegram</label>
            <input
              type="text"
              value={createForm.telegram_username}
              onChange={(e) => setCreateForm({ ...createForm, telegram_username: e.target.value })}
              placeholder="@username"
            />
          </div>
          <div className="form-actions">
            <button type="submit" className="btn btn-primary">Создать</button>
          </div>
        </form>
      </Modal>

      {/* Edit Modal */}
      <Modal isOpen={showEditModal} onClose={() => setShowEditModal(false)} title="Редактировать мастера" actions={[
        { label: 'Отмена', onClick: () => setShowEditModal(false), variant: 'ghost' },
      ]}>
        {editingMaster && (
          <form onSubmit={handleEdit} className="master-form">
            <div className="form-group">
              <label>Имя *</label>
              <input
                type="text"
                value={editForm.name}
                onChange={(e) => setEditForm({ ...editForm, name: e.target.value })}
                required
              />
            </div>
            <div className="form-group">
              <label>Email</label>
              <input type="text" value={editingMaster.email} disabled className="input-disabled" />
            </div>
            <div className="form-group">
              <label>Телефон</label>
              <input
                type="tel"
                value={editForm.phone}
                onChange={(e) => setEditForm({ ...editForm, phone: e.target.value })}
              />
            </div>
            <div className="form-group">
              <label>Telegram</label>
              <input
                type="text"
                value={editForm.telegram_username}
                onChange={(e) => setEditForm({ ...editForm, telegram_username: e.target.value })}
              />
            </div>
            <div className="form-group">
              <label>Описание</label>
              <textarea
                value={editForm.description}
                onChange={(e) => setEditForm({ ...editForm, description: e.target.value })}
                rows={3}
              />
            </div>
            <div className="form-group">
              <label>Новый пароль (оставьте пустым, если не меняете)</label>
              <input
                type="password"
                value={editForm.password}
                onChange={(e) => setEditForm({ ...editForm, password: e.target.value })}
                placeholder="Минимум 8 символов"
              />
            </div>
            <div className="form-actions">
              <button type="submit" className="btn btn-primary">Сохранить</button>
            </div>
          </form>
        )}
      </Modal>
    </div>
  )
}

export default MastersPage
