import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { adminApi } from '../../api/client';
import type { Client } from '../../api/types';
import { PHONE_PLACEHOLDER, EMAIL_PLACEHOLDER } from '../../constants';
import { isCompletePhone } from '../../components/common/PhoneInput';
import { getApiErrorMessage, getApiErrorStatus } from '../../utils/apiError';
import { downloadCsv } from '../../api/export';
import { usePersistentState } from '../../utils/persistentState';
import { useAdminSort } from '../../utils/useAdminSort';
import {
  Skeleton,
  EmptyState,
  Tooltip,
  ConfirmDialog,
  MasterSelect,
  PhoneInput,
  ResizableTh,
  useColumnWidths,
  Pager,
  CitySelect,
} from '../../components/common';
import type { CityOption } from '../../components/common/CitySelect';
import { useSectionPrefix } from '../../utils/section';
import '../../styles/filters.css';
import '../../styles/tables.css';
import './ClientsPage.css';

function ClientsPage() {
  const navigate = useNavigate();
  const section = useSectionPrefix();
  const { widths: colW, setWidth: setColW } = useColumnWidths('clients2', {
    check: 44,
    name: 180,
    phone: 140,
    email: 180,
    city: 150,
    noshow: 90,
    actions: 170,
  });
  const [selectedClients, setSelectedClients] = useState<Set<number>>(new Set());
  const [editingCityId, setEditingCityId] = useState<number | null>(null);
  const [clients, setClients] = useState<Client[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [name, setName] = useState('');
  const [phone, setPhone] = useState('');
  const [email, setEmail] = useState('');
  const [city, setCity] = useState<CityOption | null>(null);
  const [search, setSearch] = usePersistentState('clients.search', '');
  const [searchInput, setSearchInput] = usePersistentState('clients.searchInput', '');
  const [masterIdFilter, setMasterIdFilter] = usePersistentState<number | ''>('clients.master', '');
  const [totalClients, setTotalClients] = useState(0);
  const [currentPage, setCurrentPage] = usePersistentState('clients.page', 0);
  const [totalPages, setTotalPages] = useState(1);
  const pageSize = 50;
  const { sortKey, sortDir, toggleSort, sortArrow } = useAdminSort<'name' | 'no_show'>('clients');

  // Debounce search input (400ms) — no request per keystroke
  useEffect(() => {
    const t = setTimeout(() => setSearch(searchInput), 400);
    return () => clearTimeout(t);
  }, [searchInput]);

  const handleToggleActive = async (id: number) => {
    try {
      await adminApi.toggleClientActive(id);
      toast.success('Статус клиента изменён');
      fetchData();
    } catch (err: unknown) {
      toast.error(getApiErrorMessage(err, 'Не удалось изменить статус'));
    }
  };

  const fetchData = async () => {
    setLoading(true);
    try {
      const params: {
        page: number;
        page_size: number;
        search?: string;
        master_id?: number;
        sort_by?: string;
        sort_dir?: string;
      } = { page: currentPage + 1, page_size: pageSize };
      if (search?.trim()) params.search = search.trim();
      if (masterIdFilter !== '') params.master_id = masterIdFilter;
      if (sortKey) {
        params.sort_by = sortKey;
        params.sort_dir = sortDir;
      }
      const c = await adminApi.getClients(params);
      setClients(c.data.items);
      setTotalClients(c.data.total);
      setTotalPages(c.data.total_pages || 1);
    } catch (err: unknown) {
      if (getApiErrorStatus(err) === 401) {
        window.location.href = '/admin/login';
      } else toast.error('Ошибка загрузки');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    setCurrentPage(0);
  }, [search, masterIdFilter, sortKey, sortDir]);

  useEffect(() => {
    fetchData();
  }, [currentPage, search, masterIdFilter, sortKey, sortDir]);

  const resetForm = () => {
    setName('');
    setPhone('');
    setEmail('');
    setCity(null);
    setEditingId(null);
    setShowForm(false);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (phone && !isCompletePhone(phone)) {
      toast.error('Введите корректный номер телефона (11 цифр)');
      return;
    }
    try {
      if (editingId) {
        await adminApi.updateClient(editingId, {
          name,
          phone,
          email: email || undefined,
          city_id: city?.id ?? null,
        });
        toast.success('Клиент обновлён');
      } else {
        await adminApi.createClient({
          name,
          phone,
          email: email || undefined,
          city_id: city?.id ?? null,
        });
        toast.success('Клиент создан');
      }
      resetForm();
      fetchData();
    } catch (err: unknown) {
      toast.error(getApiErrorMessage(err, 'Произошла ошибка'));
    }
  };

  const handleEdit = (c: Client) => {
    setName(c.name);
    setPhone(c.phone);
    setEmail(c.email || '');
    setCity(c.city_id != null ? { id: c.city_id, name: c.city_name || '', source: 'local' } : null);
    setEditingId(c.id);
    setShowForm(true);
  };

  const handleDelete = async (id: number) => {
    try {
      await adminApi.deleteClient(id);
      // No undo: backend has no undelete, a fake "cancel" toast would lie.
      toast.success('Клиент удалён');
      fetchData();
    } catch {
      toast.error('Ошибка удаления');
    } finally {
      setDeletingId(null);
    }
  };

  return (
    <div>
      <div
        className="page-header"
        style={{ display: 'flex', alignItems: 'center', gap: 16, justifyContent: 'center' }}
      >
        <div>
          <h1>Управление клиентами</h1>
          <p>Добавление, редактирование и удаление клиентов</p>
        </div>
        <button
          className="btn btn-ghost"
          onClick={async () => {
            try {
              const params = new URLSearchParams();
              if (selectedClients.size > 0) {
                params.set('ids', [...selectedClients].join(','));
              } else {
                if (search?.trim()) params.set('search', search.trim());
                if (masterIdFilter !== '') params.set('master_id', String(masterIdFilter));
              }
              const qs = params.toString();
              await downloadCsv(`/api/v1/admin/export/clients${qs ? `?${qs}` : ''}`, 'clients.csv');
              toast.success(
                selectedClients.size > 0 ? `Выгружено: ${selectedClients.size}` : 'CSV выгружен',
              );
            } catch (err: unknown) {
              toast.error(getApiErrorMessage(err, 'Не удалось выгрузить CSV'));
            }
          }}
          title={selectedClients.size > 0 ? 'Выгрузить отмеченных' : 'Выгрузить всех по фильтру'}
        >
          📥 Экспорт CSV{selectedClients.size > 0 ? ` (${selectedClients.size})` : ''}
        </button>
      </div>

      {/* Search and filter bar */}
      <div className="card" style={{ marginBottom: 16, padding: 16 }}>
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))',
            gap: 12,
          }}
        >
          <div className="filter-cell">
            <label className="filter-label">🔍 Поиск по имени или телефону</label>
            <input
              type="text"
              placeholder="Введите имя или телефон..."
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              className="filter-control"
            />
          </div>
          <MasterSelect
            value={masterIdFilter}
            onChange={setMasterIdFilter}
            allLabel="Все клиенты"
            style={{ marginBottom: 0 }}
          />
          {(search || masterIdFilter !== '') && (
            <div className="filter-cell-bottom">
              <button
                className="btn btn-ghost"
                onClick={() => {
                  setSearch('');
                  setMasterIdFilter('');
                }}
                style={{ width: '100%', fontSize: 13, height: 38 }}
              >
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
              <div className="form-group">
                <label>Имя</label>
                <input
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  required
                  placeholder="Иван Иванов"
                />
              </div>
              <div className="form-group">
                <label>Телефон</label>
                <PhoneInput
                  value={phone}
                  onChange={setPhone}
                  required
                  placeholder={PHONE_PLACEHOLDER}
                />
              </div>
              <div className="form-group">
                <label>Email</label>
                <input
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder={EMAIL_PLACEHOLDER}
                />
              </div>
              <CitySelect
                value={city?.id ?? null}
                valueName={city?.name ?? ''}
                onChange={setCity}
                style={{ marginBottom: 0 }}
              />
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

      {loading ? (
        <div className="card">
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              marginBottom: 16,
            }}
          >
            <Skeleton width="200px" height="24px" />
            <Skeleton width="140px" height="36px" />
          </div>
          <Skeleton rows={5} height="48px" />
        </div>
      ) : (
        <div className="card">
          <div className="card-header">
            <h3>
              Список клиентов{' '}
              <span className="client-count">
                ({clients.length}
                {totalClients > pageSize ? ` из ${totalClients}` : ''})
              </span>
            </h3>
            <Tooltip content="Добавить нового клиента">
              <button className="btn btn-primary" onClick={() => setShowForm(true)}>
                + Добавить клиента
              </button>
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
              <table className="clients-table resizable-table" style={{ minWidth: 640 }}>
                <thead>
                  <tr>
                    <ResizableTh
                      width={colW.check}
                      onResize={(w) => setColW('check', w)}
                      className="col-checkbox"
                    >
                      <input
                        type="checkbox"
                        checked={clients.length > 0 && selectedClients.size === clients.length}
                        onChange={() => {
                          if (selectedClients.size === clients.length)
                            setSelectedClients(new Set());
                          else setSelectedClients(new Set(clients.map((c) => c.id)));
                        }}
                        title="Выбрать всех на странице"
                      />
                    </ResizableTh>
                    <ResizableTh
                      width={colW.name}
                      onResize={(w) => setColW('name', w)}
                      onClick={() => toggleSort('name')}
                      style={{ cursor: 'pointer', userSelect: 'none' }}
                      title="Сортировать по имени"
                    >
                      Имя{sortArrow('name')}
                    </ResizableTh>
                    <ResizableTh width={colW.phone} onResize={(w) => setColW('phone', w)}>
                      Телефон
                    </ResizableTh>
                    <ResizableTh width={colW.email} onResize={(w) => setColW('email', w)}>
                      Email
                    </ResizableTh>
                    <ResizableTh width={colW.city} onResize={(w) => setColW('city', w)}>
                      Город
                    </ResizableTh>
                    <ResizableTh
                      width={colW.noshow}
                      onResize={(w) => setColW('noshow', w)}
                      onClick={() => toggleSort('no_show')}
                      style={{ cursor: 'pointer', userSelect: 'none' }}
                      title="Сортировать по неявкам"
                    >
                      Неявки{sortArrow('no_show')}
                    </ResizableTh>
                    <ResizableTh
                      width={colW.actions}
                      minWidth={150}
                      defaultWidth={170}
                      onResize={(w) => setColW('actions', w)}
                    >
                      Действия
                    </ResizableTh>
                  </tr>
                </thead>
                <tbody>
                  {clients.map((c) => (
                    <tr key={c.id}>
                      <td className="col-checkbox">
                        <input
                          type="checkbox"
                          checked={selectedClients.has(c.id)}
                          onChange={() =>
                            setSelectedClients((prev) => {
                              const next = new Set(prev);
                              if (next.has(c.id)) next.delete(c.id);
                              else next.add(c.id);
                              return next;
                            })
                          }
                          title="Выбрать для экспорта"
                        />
                      </td>
                      <td>
                        <Tooltip content="Показать записи клиента">
                          <button
                            className="link-button"
                            onClick={() => navigate(`${section}/appointments?client_id=${c.id}`)}
                          >
                            <strong>{c.name}</strong>
                          </button>
                        </Tooltip>
                      </td>
                      <td>
                        <a href={`tel:${c.phone}`}>{c.phone}</a>
                      </td>
                      <td>{c.email || '—'}</td>
                      <td>
                        {editingCityId === c.id ? (
                          <CitySelect
                            value={c.city_id ?? null}
                            valueName={c.city_name || ''}
                            label=""
                            onChange={async (opt) => {
                              try {
                                await adminApi.updateClient(c.id, { city_id: opt?.id ?? null });
                                toast.success('Город обновлён');
                                setEditingCityId(null);
                                fetchData();
                              } catch (err: unknown) {
                                toast.error(getApiErrorMessage(err, 'Не удалось обновить город'));
                              }
                            }}
                          />
                        ) : (
                          <Tooltip content="Нажмите, чтобы назначить город">
                            <button className="link-button" onClick={() => setEditingCityId(c.id)}>
                              {c.city_name || '—'}
                            </button>
                          </Tooltip>
                        )}
                      </td>
                      <td>{(c.no_show_count ?? 0) > 0 ? `⚠️ ${c.no_show_count}` : '—'}</td>
                      <td className="actions-cell">
                        <Tooltip
                          content={
                            c.is_active === false
                              ? 'Разблокировать (сейчас заблокирован)'
                              : 'Заблокировать (сейчас активен)'
                          }
                          position="top"
                        >
                          <button
                            className={`btn btn-sm ${c.is_active === false ? 'btn-danger' : 'btn-ghost'}`}
                            onClick={() => handleToggleActive(c.id)}
                          >
                            {c.is_active === false ? '🔒' : '🔓'}
                          </button>
                        </Tooltip>
                        <Tooltip content="Редактировать">
                          <button className="btn btn-sm btn-edit" onClick={() => handleEdit(c)}>
                            ✏️
                          </button>
                        </Tooltip>
                        <Tooltip content="Удалить">
                          <button
                            className="btn btn-sm btn-delete"
                            onClick={() => setDeletingId(c.id)}
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

      {/* Pagination */}
      <Pager page={currentPage} totalPages={totalPages} onChange={setCurrentPage} />
    </div>
  );
}

export default ClientsPage;
