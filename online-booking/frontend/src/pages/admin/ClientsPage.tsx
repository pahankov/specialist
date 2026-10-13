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
  AddressSelect,
} from '../../components/common';
import { useSectionPrefix, SUPER_PREFIX } from '../../utils/section';
import { capitalizeWords } from '../../utils/names';
import '../../styles/filters.css';
import '../../styles/tables.css';
import './ClientsPage.css';

function ClientsPage() {
  const navigate = useNavigate();
  const section = useSectionPrefix();
  const isSuperSection = section === SUPER_PREFIX;
  const {
    widths: colW,
    setWidth: setColW,
    resetWidths,
  } = useColumnWidths('clients2', {
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
  const [blockingId, setBlockingId] = useState<number | null>(null);
  const [showArchive, setShowArchive] = useState(false);
  const [hideReason, setHideReason] = useState('inactive');
  const [blockCause, setBlockCause] = useState('no_show');
  const [causeNote, setCauseNote] = useState('');
  const [name, setName] = useState('');
  const [phone, setPhone] = useState('');
  const [email, setEmail] = useState('');
  // Single address field (city is parsed from the DaData pick for matching).
  const [address, setAddress] = useState('');
  const [addressCity, setAddressCity] = useState('');
  // Panel user's own location: prefill for new clients so both sides match.
  const [myDefaults, setMyDefaults] = useState<{ city: string; address: string } | null>(null);
  const [myDefaultsLoaded, setMyDefaultsLoaded] = useState(false);
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
        include_hidden?: boolean;
      } = { page: currentPage + 1, page_size: pageSize };
      if (search?.trim()) params.search = search.trim();
      if (isSuperSection && masterIdFilter !== '') params.master_id = masterIdFilter;
      if (showArchive) params.include_hidden = true;
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
  }, [search, masterIdFilter, sortKey, sortDir, showArchive]);

  useEffect(() => {
    fetchData();
  }, [currentPage, search, masterIdFilter, sortKey, sortDir, showArchive]);

  const resetForm = () => {
    setName('');
    setPhone('');
    setEmail('');
    setAddress('');
    setAddressCity('');
    setEditingClient(null);
    setEditingId(null);
    setShowForm(false);
  };

  const ensureMyDefaults = async (): Promise<{ city: string; address: string } | null> => {
    if (myDefaultsLoaded) return myDefaults;
    try {
      const { data } = await adminApi.getProfile();
      const d = {
        city: data.city_name || '',
        address: (data as { cabinet_address?: string }).cabinet_address || '',
      };
      setMyDefaults(d);
      return d;
    } catch {
      return null;
    } finally {
      setMyDefaultsLoaded(true);
    }
  };

  const openCreateForm = async () => {
    setName('');
    setPhone('');
    setEmail('');
    const d = await ensureMyDefaults();
    setAddress(d?.address || '');
    setAddressCity(d?.city || '');
    setEditingId(null);
    setShowForm(true);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (phone && !isCompletePhone(phone)) {
      toast.error('Введите корректный номер телефона (11 цифр)');
      return;
    }
    // City for matching: parsed from the address pick, else the stored one,
    // else the panel user's own city.
    const cityName = addressCity.trim() || editingClient?.city_name || '' || myDefaults?.city || '';
    try {
      if (editingId) {
        await adminApi.updateClient(editingId, {
          name,
          phone,
          email: email || undefined,
          city_name: cityName || undefined,
          address: address.trim() || null,
        });
        toast.success('Клиент обновлён');
      } else {
        await adminApi.createClient({
          name,
          phone,
          email: email || undefined,
          city_name: cityName || undefined,
          address: address.trim() || null,
        });
        toast.success('Клиент создан');
      }
      resetForm();
      fetchData();
    } catch (err: unknown) {
      toast.error(getApiErrorMessage(err, 'Произошла ошибка'));
    }
  };

  const [editingClient, setEditingClient] = useState<Client | null>(null);

  const handleEdit = (c: Client) => {
    setName(c.name);
    setPhone(c.phone);
    setEmail(c.email || '');
    setAddress(c.address || '');
    setAddressCity(c.city_name || '');
    setEditingClient(c);
    setEditingId(c.id);
    setShowForm(true);
  };

  const handleDelete = async (id: number) => {
    try {
      await adminApi.deleteClient(id, hideReason || undefined, causeNote || undefined);
      // No undo: backend has no unhide/undelete, a fake "cancel" toast would lie.
      toast.success(isSuperSection ? 'Клиент заблокирован у всех' : 'Клиент убран в архив');
      fetchData();
    } catch {
      toast.error('Ошибка удаления');
    } finally {
      setDeletingId(null);
      setCauseNote('');
    }
  };

  const scopedMasterId =
    isSuperSection && typeof masterIdFilter === 'number' ? masterIdFilter : undefined;

  const handleBlock = async (id: number) => {
    try {
      const { data } = await adminApi.blockClient(
        id,
        scopedMasterId,
        hideReason || undefined,
        blockCause || undefined,
        causeNote || undefined,
      );
      if (data.cancelled_appointments > 0) {
        toast.info(`Отменено будущих записей: ${data.cancelled_appointments}`);
      }
      toast.success(
        isSuperSection && scopedMasterId === undefined
          ? 'Клиент заблокирован у всех мастеров'
          : 'Клиент заблокирован',
      );
      fetchData();
    } catch (err: unknown) {
      toast.error(getApiErrorMessage(err, 'Не удалось заблокировать'));
    } finally {
      setBlockingId(null);
      setCauseNote('');
    }
  };

  const handleUnblock = async (id: number) => {
    try {
      await adminApi.unblockClient(id, scopedMasterId);
      toast.success('Клиент разблокирован');
      fetchData();
    } catch (err: unknown) {
      toast.error(getApiErrorMessage(err, 'Не удалось разблокировать'));
    }
  };

  const handleRestore = async (id: number) => {
    try {
      await adminApi.restoreClient(id, scopedMasterId);
      toast.success('Клиент возвращён в списки');
      fetchData();
    } catch (err: unknown) {
      toast.error(getApiErrorMessage(err, 'Не удалось вернуть клиента'));
    }
  };

  const REASON_LABELS: Record<string, string> = {
    inactive: 'Неактивен',
    moved: 'Переехал',
    left: 'Ушёл к другому мастеру',
    deceased: 'Умер',
    other: 'Другое',
  };

  const BLOCK_LABELS: Record<string, string> = {
    no_show: 'Не приходит на записи',
    rude: 'Грубость',
    spam: 'Спам',
    debt: 'Неоплата',
    other: 'Другое',
  };

  /** "Скрыт: Иван (переехал), Мария (чёрный список: спам — текст)" */
  const attributionTitle = (c: Client): string | undefined => {
    if (!c.hidden_by || c.hidden_by.length === 0) return undefined;
    return c.hidden_by
      .map((h) => {
        const who = h.master_name || `мастер #${h.master_id}`;
        const what = h.is_blocked
          ? `чёрный список${h.block_reason ? `: ${BLOCK_LABELS[h.block_reason] || h.block_reason}` : ''}`
          : `архив${h.reason ? `: ${REASON_LABELS[h.reason] || h.reason}` : ''}`;
        return `${who} — ${what}${h.note ? ` («${h.note}»)` : ''}`;
      })
      .join('; ');
  };

  return (
    <div className="clients-page">
      <div className="page-header">
        <div>
          <h1>Управление клиентами</h1>
          <p>
            {isSuperSection
              ? 'Добавление, редактирование и удаление клиентов'
              : 'Ваши клиенты — создавайте новых и записывайте на услуги'}
          </p>
        </div>
        <div className="page-header-actions">
          <label
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              fontSize: 13,
              cursor: 'pointer',
            }}
            title="Показать клиентов, убранных в архив"
          >
            <input
              type="checkbox"
              checked={showArchive}
              onChange={(e) => setShowArchive(e.target.checked)}
            />
            📦 Архив
          </label>
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
                await downloadCsv(
                  `/api/v1/admin/export/clients${qs ? `?${qs}` : ''}`,
                  'clients.csv',
                );
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
          {isSuperSection && (
            <MasterSelect
              value={masterIdFilter}
              onChange={setMasterIdFilter}
              allLabel="Все клиенты"
              style={{ marginBottom: 0 }}
            />
          )}
          {(search || (isSuperSection && masterIdFilter !== '')) && (
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
                  onChange={(e) => setName(capitalizeWords(e.target.value))}
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
              <AddressSelect
                value={address}
                onChange={(a, pickedCity) => {
                  setAddress(a);
                  if (pickedCity) setAddressCity(pickedCity);
                }}
                label="Адрес"
                placeholder="Город, улица, дом... (подсказки DaData)"
                style={{ marginBottom: 0 }}
              />
              {(addressCity || editingClient?.city_name || (!editingId && myDefaults?.city)) && (
                <span style={{ fontSize: 12, color: '#666' }}>
                  Город для подбора: {addressCity || editingClient?.city_name || myDefaults?.city}
                  {!editingId && myDefaults?.address && address === myDefaults.address
                    ? ' — ваш адрес, подставлен автоматически'
                    : ''}
                </span>
              )}
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
            {clients.length > 0 && (
              <div style={{ display: 'flex', gap: 8 }}>
                <button
                  className="btn btn-ghost btn-sm"
                  onClick={resetWidths}
                  title="Вернуть стандартную ширину колонок таблицы"
                >
                  ⟲ Колонки
                </button>
                <Tooltip content="Добавить нового клиента">
                  <button className="btn btn-primary" onClick={openCreateForm}>
                    + Добавить клиента
                  </button>
                </Tooltip>
              </div>
            )}
          </div>

          {clients.length === 0 ? (
            <EmptyState
              icon="👥"
              title="Клиенты не найдены"
              description="Добавьте первого клиента или измените параметры поиска"
              actionLabel="+ Добавить клиента"
              onAction={openCreateForm}
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
                      minWidth={130}
                      onResize={(w) => setColW('name', w)}
                      onClick={() => toggleSort('name')}
                      style={{ cursor: 'pointer', userSelect: 'none' }}
                      title="Сортировать по имени"
                    >
                      Имя{sortArrow('name')}
                    </ResizableTh>
                    <ResizableTh
                      width={colW.phone}
                      minWidth={120}
                      onResize={(w) => setColW('phone', w)}
                    >
                      Телефон
                    </ResizableTh>
                    <ResizableTh
                      width={colW.email}
                      minWidth={140}
                      onResize={(w) => setColW('email', w)}
                    >
                      Email
                    </ResizableTh>
                    <ResizableTh
                      width={colW.city}
                      minWidth={100}
                      onResize={(w) => setColW('city', w)}
                    >
                      Город
                    </ResizableTh>
                    <ResizableTh
                      width={colW.noshow}
                      minWidth={80}
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
                        {c.is_blocked && (
                          <span
                            style={{
                              marginLeft: 6,
                              fontSize: 12,
                              color: '#fff',
                              background: '#e5484d',
                              borderRadius: 10,
                              padding: '1px 8px',
                              whiteSpace: 'nowrap',
                            }}
                            title={`Клиент в чёрном списке: не видит расписание и не может записываться${attributionTitle(c) ? `\n${attributionTitle(c)}` : ''}`}
                          >
                            ⛔ Заблокирован
                          </span>
                        )}
                        {c.is_hidden && !c.is_blocked && (
                          <span
                            style={{
                              marginLeft: 6,
                              fontSize: 12,
                              color: '#666',
                              background: '#eee',
                              borderRadius: 10,
                              padding: '1px 8px',
                              whiteSpace: 'nowrap',
                            }}
                            title={`Клиент в архиве — скрыт из списков, история сохранена${attributionTitle(c) ? `\n${attributionTitle(c)}` : ''}`}
                          >
                            📦 Архив{/* reason below in tooltip */}
                            {c.hidden_reason
                              ? `: ${REASON_LABELS[c.hidden_reason] || c.hidden_reason}`
                              : ''}
                          </span>
                        )}
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
                        {c.is_hidden && !c.is_blocked && (
                          <Tooltip content="Вернуть из архива в списки" position="top">
                            <button
                              className="btn btn-sm btn-ghost"
                              onClick={() => handleRestore(c.id)}
                            >
                              ↩️
                            </button>
                          </Tooltip>
                        )}
                        {c.is_blocked ? (
                          <Tooltip
                            content="Разблокировать — клиент снова сможет записываться"
                            position="top"
                          >
                            <button
                              className="btn btn-sm btn-ghost"
                              onClick={() => handleUnblock(c.id)}
                            >
                              ✅
                            </button>
                          </Tooltip>
                        ) : (
                          <Tooltip
                            content="Заблокировать — скроет из списков и запретит запись"
                            position="top"
                          >
                            <button
                              className="btn btn-sm btn-ghost"
                              onClick={() => setBlockingId(c.id)}
                            >
                              🚫
                            </button>
                          </Tooltip>
                        )}
                        <Tooltip
                          content={
                            c.is_active === false
                              ? 'Включить аккаунт (сейчас выключен)'
                              : 'Выключить аккаунт (сейчас активен)'
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
        title={isSuperSection ? '🗑️ Заблокировать клиента у всех?' : '🗑️ Убрать клиента в архив?'}
        message={
          isSuperSection
            ? 'Клиент будет заблокирован у ВСЕХ мастеров (обратимо, разблокировка одной кнопкой). Полное стирание из базы — только по запросу, через API ?purge=true.'
            : 'Клиент пропадёт из ваших списков, будущие записи с вами отменятся. Прошлые визиты останутся как «Удалённый клиент». Вернуть можно из архива (галочка 📦 сверху).'
        }
        confirmLabel={isSuperSection ? 'Заблокировать у всех' : 'Убрать в архив'}
        danger
        onConfirm={() => deletingId !== null && handleDelete(deletingId)}
      >
        <div style={{ marginTop: 8, display: 'flex', flexDirection: 'column', gap: 8 }}>
          <label style={{ fontSize: 13 }}>
            Причина:{' '}
            <select value={hideReason} onChange={(e) => setHideReason(e.target.value)}>
              {Object.entries(REASON_LABELS).map(([v, label]) => (
                <option key={v} value={v}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <label style={{ fontSize: 13 }}>
            Заметка (необязательно):{' '}
            <input
              value={causeNote}
              onChange={(e) => setCauseNote(e.target.value)}
              placeholder="Детали для себя и админа"
              maxLength={500}
              style={{ width: '100%' }}
            />
          </label>
        </div>
      </ConfirmDialog>

      <ConfirmDialog
        open={blockingId !== null}
        onClose={() => setBlockingId(null)}
        title="🚫 Заблокировать клиента?"
        message={
          isSuperSection && scopedMasterId === undefined
            ? 'Клиент будет заблокирован у ВСЕХ мастеров: пропадёт из списков, не сможет видеть расписания и записываться. Прошлые визиты останутся как «Удалённый клиент».'
            : 'Клиент пропадёт из ваших списков, не сможет видеть ваше расписание и записываться (ни из кабинета, ни с публичной формы). Прошлые визиты останутся как «Удалённый клиент».'
        }
        confirmLabel="Заблокировать"
        danger
        onConfirm={() => blockingId !== null && handleBlock(blockingId)}
      >
        <div style={{ marginTop: 8, display: 'flex', flexDirection: 'column', gap: 8 }}>
          <label style={{ fontSize: 13 }}>
            Причина блока:{' '}
            <select value={blockCause} onChange={(e) => setBlockCause(e.target.value)}>
              {Object.entries(BLOCK_LABELS).map(([v, label]) => (
                <option key={v} value={v}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <label style={{ fontSize: 13 }}>
            Заметка (необязательно):{' '}
            <input
              value={causeNote}
              onChange={(e) => setCauseNote(e.target.value)}
              placeholder="Например: три неявки подряд"
              maxLength={500}
              style={{ width: '100%' }}
            />
          </label>
        </div>
      </ConfirmDialog>

      {/* Pagination */}
      <Pager page={currentPage} totalPages={totalPages} onChange={setCurrentPage} />
    </div>
  );
}

export default ClientsPage;
