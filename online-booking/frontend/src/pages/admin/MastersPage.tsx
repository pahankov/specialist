import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import { superAdminApi } from '../../api/client'
import type { Master } from '../../api/types'
import { Skeleton, EmptyState, Tooltip, Modal, ConfirmDialog, CitySelect, PhoneInput } from '../../components/common'
import type { CityOption } from '../../components/common/CitySelect'
import { isCompletePhone } from '../../components/common/PhoneInput'
import { PHONE_PLACEHOLDER, PASSWORD_PLACEHOLDER, PASSWORD_EDIT_PLACEHOLDER, TELEGRAM_PLACEHOLDER } from '../../constants'
import { getApiErrorMessage } from '../../utils/apiError'
import { getCookie } from '../../utils/cookies'
import { startImpersonation } from '../../utils/impersonation'
import './MastersPage.css'

function MastersPage() {
  const navigate = useNavigate()
  const [masters, setMasters] = useState<Master[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [searchInput, setSearchInput] = useState('')
  const [filterActive, setFilterActive] = useState<'all' | 'active' | 'inactive'>('all')
  const [filterAdmin, setFilterAdmin] = useState<'all' | 'admin' | 'user'>('all')
  const [sortKey, setSortKey] = useState<'name' | 'email' | 'status' | null>(null)
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc')
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [showEditModal, setShowEditModal] = useState(false)
  const [editingMaster, setEditingMaster] = useState<Master | null>(null)
  const [deleteConfirm, setDeleteConfirm] = useState<number | null>(null)
  const [selectedMasters, setSelectedMasters] = useState<Set<number>>(new Set())

  const [createForm, setCreateForm] = useState({
    name: '', email: '', password: '', phone: '', telegram_username: '',
  })
  const [createCity, setCreateCity] = useState<CityOption | null>(null)

  const [editForm, setEditForm] = useState({
    name: '', phone: '', telegram_username: '', description: '', password: '',
  })

  const loadMasters = async () => {
    setLoading(true)
    try {
      const params: Record<string, string> = {}
      if (search?.trim()) params.search = search.trim()
      if (filterActive === 'active') params.is_active = 'true'
      if (filterActive === 'inactive') params.is_active = 'false'
      if (filterAdmin === 'admin') params.is_admin = 'true'
      if (filterAdmin === 'user') params.is_admin = 'false'
      if (sortKey) { params.sort_by = sortKey; params.sort_dir = sortDir }

      const { data } = await superAdminApi.getAllMasters(Object.keys(params).length ? params : undefined)
      setMasters(data)
    } catch (err: unknown) {
      toast.error(handleError(err))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { loadMasters() }, [search, filterActive, filterAdmin, sortKey, sortDir])

  // Debounce search input (400ms) — no request per keystroke
  useEffect(() => {
    const t = setTimeout(() => setSearch(searchInput), 400)
    return () => clearTimeout(t)
  }, [searchInput])

  const toggleSort = (key: 'name' | 'email' | 'status') => {
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

  const sortArrow = (key: 'name' | 'email' | 'status') =>
    sortKey !== key ? ' ⇅' : (sortDir === 'asc' ? ' ▲' : ' ▼')

  const handleSearch = () => setSearch(searchInput)

  useEffect(() => { loadMasters() }, [])

  const handleError = (err: unknown): string => getApiErrorMessage(err)

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    if (createForm.phone && !isCompletePhone(createForm.phone)) {
      toast.error('Введите корректный номер телефона (11 цифр)')
      return
    }
    try {
      await superAdminApi.createMaster({
        ...createForm,
        ...(createCity ? { city_id: createCity.id } : {}),
      })
      toast.success('Мастер успешно создан')
      setShowCreateModal(false)
      setCreateForm({ name: '', email: '', password: '', phone: '', telegram_username: '' })
      setCreateCity(null)
      loadMasters()
    } catch (err: unknown) {
      toast.error(handleError(err))
    }
  }

  const handleEdit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!editingMaster) return
    if (editForm.phone && !isCompletePhone(editForm.phone)) {
      toast.error('Введите корректный номер телефона (11 цифр)')
      return
    }
    try {
      const data: Record<string, string> = { ...editForm }
      if (!data.password) delete data.password
      await superAdminApi.updateMaster(editingMaster.id, data)
      toast.success('Мастер обновлён')
      setShowEditModal(false)
      setEditingMaster(null)
      loadMasters()
    } catch (err: unknown) {
      toast.error(handleError(err))
    }
  }

  const handleToggleActive = async (id: number) => {
    const master = masters.find(m => m.id === id)
    if (!master) return

    const isCurrentlyActive = master.is_active
    const undoAction = () => {
      superAdminApi.toggleMasterActive(id).catch(() => { /* ignore */ })
    }

    try {
      await superAdminApi.toggleMasterActive(id)
      toast.success(
        isCurrentlyActive ? 'Мастер заблокирован' : 'Мастер разблокирован',
        { action: { label: 'Отменить', onClick: undoAction } }
      )
      loadMasters()
    } catch (err: unknown) {
      toast.error(handleError(err))
    }
  }

  // Bulk operations
  const toggleSelect = (masterId: number) => {
    const next = new Set(selectedMasters)
    if (next.has(masterId)) next.delete(masterId)
    else next.add(masterId)
    setSelectedMasters(next)
  }

  const handleBulkToggle = async () => {
    const ids = Array.from(selectedMasters)
    if (ids.length === 0) return
    try {
      const { data } = await superAdminApi.bulkToggleActive(ids)
      toast.success(`Выбрано мастеров: ${data.toggled?.length || 0}`)
      setSelectedMasters(new Set())
      loadMasters()
    } catch (err: unknown) {
      toast.error(handleError(err))
    }
  }

  const handleBulkSuspend = async () => {
    const ids = Array.from(selectedMasters)
    if (ids.length === 0) return
    try {
      const { data } = await superAdminApi.bulkSuspend(ids)
      toast.success(`Заблокировано мастеров: ${data.suspended?.length || 0}`)
      setSelectedMasters(new Set())
      loadMasters()
    } catch (err: unknown) {
      toast.error(handleError(err))
    }
  }

  const handleDelete = async (id: number) => {
    try {
      await superAdminApi.deleteMaster(id)
      // No undo: backend has no undelete, a fake "cancel" toast would lie.
      toast.success('Мастер удалён')
      setDeleteConfirm(null)
      loadMasters()
    } catch (err: unknown) {
      toast.error(handleError(err))
    }
  }

  const handleImpersonate = async (master: Master) => {
    try {
      const { data } = await superAdminApi.impersonateMaster(master.id)
      const adminToken = getCookie('access_token') ?? ''
      startImpersonation(adminToken, data.access_token, data.name)
      toast.success(`Вы вошли как ${data.name}`)
      navigate('/admin/dashboard')
      window.location.reload()
    } catch (err: unknown) {
      toast.error(handleError(err))
    }
  }

  const openEditModal = (master: Master) => {    setEditingMaster(master)
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
        <div className="page-header-actions">
          {selectedMasters.size > 0 && (
            <div className="bulk-actions">
              <span className="bulk-count">Выбрано: {selectedMasters.size}</span>
              <button className="btn btn-sm btn-secondary" onClick={handleBulkToggle}>Toggle Active</button>
              <button className="btn btn-sm btn-warn" onClick={handleBulkSuspend}>Suspend</button>
              <button className="btn btn-sm btn-ghost" onClick={() => setSelectedMasters(new Set())}>Отменить</button>
            </div>
          )}
          <button className="btn btn-primary" onClick={() => setShowCreateModal(true)}>+ Добавить мастера</button>
        </div>
      </div>

      <div className="masters-filters">
        <div className="filter-row">
          <input
            type="text"
            placeholder="Поиск по имени или email..."
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
            className="filter-input"
          />
          <button className="btn btn-secondary" onClick={handleSearch}>Найти</button>
          <select value={filterActive} onChange={(e) => setFilterActive(e.target.value as 'all' | 'active' | 'inactive')} className="filter-select">
            <option value="all">Все статусы</option>
            <option value="active">Активные</option>
            <option value="inactive">Заблокированные</option>
          </select>
          <select value={filterAdmin} onChange={(e) => setFilterAdmin(e.target.value as 'all' | 'admin' | 'user')} className="filter-select">
            <option value="all">Все роли</option>
            <option value="admin">Суперпользователи</option>
            <option value="user">Обычные мастера</option>
          </select>
        </div>
      </div>

      {loading ? (
        <div className="skeleton-table">
          <Skeleton rows={5} height="52px" />
        </div>
      ) : masters.length === 0 ? (
        <EmptyState
          icon="👨‍💼"
          title="Мастера не найдены"
          description="Добавьте первого мастера или измените фильтры"
          actionLabel="+ Добавить мастера"
          onAction={() => setShowCreateModal(true)}
        />
      ) : (
        <div className="masters-table-wrapper">
          <table className="masters-table">
            <thead>
              <tr>
                <th className="col-checkbox">
                  <input
                    type="checkbox"
                    checked={masters.length > 0 && selectedMasters.size === masters.length}
                    onChange={() => {
                      if (selectedMasters.size === masters.length) {
                        setSelectedMasters(new Set())
                      } else {
                        setSelectedMasters(new Set(masters.map(m => m.id)))
                      }
                    }}
                  />
                </th>
                <th onClick={() => toggleSort('name')} style={{ cursor: 'pointer', userSelect: 'none' }} title="Сортировать по имени">
                  Имя{sortArrow('name')}
                </th>
                <th onClick={() => toggleSort('email')} style={{ cursor: 'pointer', userSelect: 'none' }} title="Сортировать по email">
                  Email{sortArrow('email')}
                </th>
                <th>Телефон</th>
                <th onClick={() => toggleSort('status')} style={{ cursor: 'pointer', userSelect: 'none' }} title="Сортировать по статусу">
                  Статус{sortArrow('status')}
                </th>
                <th>Роль</th>
                <th>Тариф</th>
                <th>Действия</th>
              </tr>
            </thead>
            <tbody>
              {masters.map((master) => (
                <tr key={master.id} className={selectedMasters.has(master.id) ? 'selected' : ''}>
                  <td className="col-checkbox">
                    <input
                      type="checkbox"
                      checked={selectedMasters.has(master.id)}
                      onChange={() => toggleSelect(master.id)}
                    />
                  </td>
                  <td>
                    <button
                      className="master-name-link"
                      onClick={() => navigate(`/admin/masters/${master.id}`)}
                    >
                      <div className="master-name">{master.name}</div>
                      {master.telegram_username && (
                        <div className="master-telegram">@{master.telegram_username}</div>
                      )}
                    </button>
                  </td>
                  <td>{master.email}</td>
                  <td>{master.phone || '—'}</td>
                  <td>
                    <Tooltip content={master.is_active ? 'Активен' : 'Заблокирован'} position="top">
                      <span className={`status-badge ${master.is_active ? 'status-active' : 'status-inactive'}`}>
                        {master.is_active ? 'Активен' : 'Заблокирован'}
                      </span>
                    </Tooltip>
                  </td>
                  <td>
                    <Tooltip content={master.is_admin ? 'Суперпользователь' : 'Обычный мастер'} position="top">
                      <span className={`role-badge ${master.is_admin ? 'role-admin' : 'role-user'}`}>
                        {master.is_admin ? '👑 Суперпользователь' : '👤 Мастер'}
                      </span>
                    </Tooltip>
                  </td>
                  <td>
                    <Tooltip content={master.trial_ends_at ? `Триал до ${new Date(master.trial_ends_at).toLocaleDateString('ru-RU')}` : 'Тариф'} position="top">
                      <span className="tariff-badge">
                        {master.tariff === 'trial' ? '🆓 Триал' : (master.tariff || '—')}
                      </span>
                    </Tooltip>
                    {master.trial_ends_at && (
                      <div className="tariff-ends">{new Date(master.trial_ends_at).toLocaleDateString('ru-RU')}</div>
                    )}
                  </td>
                  <td className="actions-cell">
                    <Tooltip content="Редактировать" position="top">
                      <button className="btn btn-sm btn-secondary" onClick={() => openEditModal(master)}>✏️</button>
                    </Tooltip>
                    <Tooltip content={master.is_active ? 'Заблокировать' : 'Разблокировать'} position="top">
                      <button
                        className={`btn btn-sm ${master.is_active ? 'btn-warn' : 'btn-success'}`}
                        onClick={() => handleToggleActive(master.id)}
                      >
                        {master.is_active ? '🔒' : '🔓'}
                      </button>
                    </Tooltip>
                    <Tooltip content="Войти как мастер (поддержка)" position="top">
                      <button
                        className="btn btn-sm btn-secondary"
                        onClick={() => handleImpersonate(master)}
                      >
                        👁
                      </button>
                    </Tooltip>
                    <Tooltip content="Удалить" position="top">
                      <button
                        className="btn btn-sm btn-danger"
                        onClick={() => setDeleteConfirm(master.id)}
                      >
                        🗑️
                      </button>
                    </Tooltip>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <ConfirmDialog
        open={deleteConfirm !== null}
        onClose={() => setDeleteConfirm(null)}
        title="🗑️ Удалить мастера?"
        message="Мастер будет удалён вместе со всеми данными. Это действие нельзя отменить."
        confirmLabel="Удалить"
        danger
        onConfirm={() => deleteConfirm !== null && handleDelete(deleteConfirm)}
      />

      <Modal open={showCreateModal} onClose={() => setShowCreateModal(false)} title="Добавить мастера" wide>
          <form onSubmit={handleCreate} className="master-form">
            <div className="form-group">
              <label>Имя *</label>
              <input type="text" value={createForm.name} onChange={(e) => setCreateForm({ ...createForm, name: e.target.value })} required placeholder="Иван Иванов" />
            </div>
            <div className="form-group">
              <label>Email *</label>
              <input type="email" value={createForm.email} onChange={(e) => setCreateForm({ ...createForm, email: e.target.value })} required placeholder="master@example.com" />
            </div>
            <div className="form-group">
              <label>Пароль *</label>
              <input type="password" value={createForm.password} onChange={(e) => setCreateForm({ ...createForm, password: e.target.value })} required placeholder={PASSWORD_PLACEHOLDER} />
            </div>
            <div className="form-group">
              <label>Телефон</label>
              <PhoneInput value={createForm.phone} onChange={(phone) => setCreateForm({ ...createForm, phone })} placeholder={PHONE_PLACEHOLDER} />
            </div>
            <div className="form-group">
              <label>Telegram</label>
              <input type="text" value={createForm.telegram_username} onChange={(e) => setCreateForm({ ...createForm, telegram_username: e.target.value })} placeholder={TELEGRAM_PLACEHOLDER} />
            </div>
            <CitySelect
              value={createCity?.id ?? null}
              valueName={createCity?.name ?? ''}
              onChange={setCreateCity}
            />
            <div className="modal-actions">
              <button type="submit" className="btn btn-primary">Создать</button>
            </div>
          </form>
      </Modal>

      <Modal open={showEditModal} onClose={() => setShowEditModal(false)} title="Редактировать мастера" wide>
          {editingMaster && (
            <form onSubmit={handleEdit} className="master-form">
              <div className="form-group">
                <label>Имя *</label>
                <input type="text" value={editForm.name} onChange={(e) => setEditForm({ ...editForm, name: e.target.value })} required />
              </div>
              <div className="form-group">
                <label>Email</label>
                <input type="text" value={editingMaster.email} disabled className="input-disabled" />
              </div>
              <div className="form-group">
                <label>Телефон</label>
                <PhoneInput value={editForm.phone} onChange={(phone) => setEditForm({ ...editForm, phone })} placeholder={PHONE_PLACEHOLDER} />
              </div>
              <div className="form-group">
                <label>Telegram</label>
                <input type="text" value={editForm.telegram_username} onChange={(e) => setEditForm({ ...editForm, telegram_username: e.target.value })} placeholder={TELEGRAM_PLACEHOLDER} />
              </div>
              <div className="form-group">
                <label>Описание</label>
                <textarea value={editForm.description} onChange={(e) => setEditForm({ ...editForm, description: e.target.value })} rows={3} />
              </div>
              <div className="form-group">
                <label>Новый пароль (оставьте пустым, если не меняете)</label>
                <input type="password" value={editForm.password} onChange={(e) => setEditForm({ ...editForm, password: e.target.value })} placeholder={PASSWORD_EDIT_PLACEHOLDER} />
              </div>
              <div className="modal-actions">
                <button type="submit" className="btn btn-primary">Сохранить</button>
              </div>
            </form>
          )}
      </Modal>
    </div>
  )
}

export default MastersPage
