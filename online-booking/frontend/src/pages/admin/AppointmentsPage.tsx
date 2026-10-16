import { useEffect, useMemo, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { toast } from 'sonner';
import { adminApi } from '../../api/client';
import type { Appointment } from '../../api/types';
import {
  Skeleton,
  EmptyState,
  Tooltip,
  ConfirmDialog,
  MasterSelect,
  Modal,
  DataTable,
  AutoConfirmSwitch,
  AutoCompleteSwitch,
  Pager,
  StatusBadge,
} from '../../components/common';
import type { FitColumnDef } from '../../components/common';
import { downloadCsv } from '../../api/export';
import { usePersistentState } from '../../utils/persistentState';
import { useSectionPrefix, SUPER_PREFIX } from '../../utils/section';
import { goLogin } from '../../utils/redirect';
import { getApiErrorMessage } from '../../utils/apiError';
import '../../styles/filters.css';
import '../../styles/tables.css';
import './AppointmentsPage.css';
import { statusLabels } from '../../constants/statusLabels';

type SortField =
  'appointment_date' | 'client_name' | 'service_name' | 'service_price' | 'status' | 'master_name';
type SortDirection = 'asc' | 'desc';

function AppointmentsPage() {
  const section = useSectionPrefix();
  const isSuperSection = section === SUPER_PREFIX;
  const [selectedAppointments, setSelectedAppointments] = useState<Set<number>>(new Set());

  const [appointments, setAppointments] = useState<
    (Appointment & {
      client_name?: string;
      client_phone?: string;
      service_name?: string;
      service_price?: number;
    })[]
  >([]);
  const [searchParams, setSearchParams] = useSearchParams();
  // Filters persist across tab switches (sessionStorage), deep-links win on mount
  const [statusFilter, setStatusFilter] = usePersistentState('appointments.status', '');
  const [masterIdFilter, setMasterIdFilter] = usePersistentState<number | ''>(
    'appointments.master',
    '',
  );
  const [clientIdFilter, setClientIdFilter] = usePersistentState<number | ''>(
    'appointments.client',
    '',
  );
  const [serviceIdFilter, setServiceIdFilter] = usePersistentState<number | ''>(
    'appointments.service',
    '',
  );
  const [dateFrom, setDateFrom] = usePersistentState('appointments.from', '');
  const [dateTo, setDateTo] = usePersistentState('appointments.to', '');
  const [showCompleted, setShowCompleted] = usePersistentState('appointments.showCompleted', false);
  const [showCancelled, setShowCancelled] = usePersistentState('appointments.showCancelled', true);
  const [allTime, setAllTime] = usePersistentState('appointments.allTime', true);
  const [showFilters, setShowFilters] = usePersistentState('appointments.showFilters', false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [cancelingId, setCancelingId] = useState<number | null>(null);
  const [noShowingId, setNoShowingId] = useState<number | null>(null);
  const [cancelReason, setCancelReason] = useState('');
  const [currentPage, setCurrentPage] = usePersistentState('appointments.page', 0);
  const [sortField, setSortField] = usePersistentState<SortField>(
    'appointments.sort',
    'appointment_date',
  );
  const [sortDirection, setSortDirection] = usePersistentState<SortDirection>(
    'appointments.dir',
    'asc',
  );
  // Date order is server-side (a 20-row page can't re-sort other pages).
  // Default asc: today first — matches the ↑ header and worklist usage.
  const [dateSort, setDateSort] = usePersistentState<'asc' | 'desc'>('appointments.dateDir', 'asc');
  const [totalPages, setTotalPages] = useState(1);
  // Row flashed when jumping from a bell (?highlight=id).
  const [highlightId, setHighlightId] = useState<number | null>(null);
  const [allClients, setAllClients] = useState<{ id: number; name: string }[]>([]);
  const [allServices, setAllServices] = useState<
    { id: number; name: string; master_id?: number }[]
  >([]);
  const pageSize = 20;
  // Quick booking from the list (no schedule round-trip).
  const [showCreate, setShowCreate] = useState(false);
  const [createMasterId, setCreateMasterId] = useState<number | ''>('');
  const [createClientId, setCreateClientId] = useState<number | ''>('');
  const [createServiceId, setCreateServiceId] = useState<number | ''>('');
  const [createDateTime, setCreateDateTime] = useState('');
  const [createStatus, setCreateStatus] = useState('confirmed');
  const [createNotes, setCreateNotes] = useState('');
  const [creating, setCreating] = useState(false);
  // Guards the list against out-of-order responses: a drill-down fires two
  // fetches on mount (persisted filters, then deep-link filters) and the
  // first one must never overwrite the second.
  const fetchSeq = useRef(0);

  const fetchOptions = async () => {
    try {
      // Fetch clients for filter dropdown
      try {
        const clientsResp = await adminApi.getClients({ page: 1, page_size: 500 });
        setAllClients(
          clientsResp.data.items.map((c: { id: number; name: string }) => ({
            id: c.id,
            name: c.name,
          })),
        );
      } catch (err) {
        console.warn('[Appointments] clients filter failed', err);
      }

      // Fetch services for filter dropdown
      try {
        const servicesResp = await adminApi.getServices({
          page: 1,
          page_size: 500,
          active_only: false,
        });
        setAllServices(
          servicesResp.data.items.map((s: { id: number; name: string }) => ({
            id: s.id,
            name: s.name,
          })),
        );
      } catch (err) {
        console.warn('[Appointments] services filter failed', err);
      }
    } catch {
      /* ignore */
    }
  };

  useEffect(() => {
    fetchOptions();
  }, []);

  const fetch = async () => {
    const seq = ++fetchSeq.current;
    setLoading(true);
    try {
      const params: Record<string, any> = {
        page: currentPage + 1,
        page_size: pageSize,
        show_completed: showCompleted,
        show_cancelled: showCancelled,
        sort_dir: dateSort,
      };
      if (statusFilter) params.status = statusFilter;
      if (masterIdFilter !== '') params.master_id = masterIdFilter;
      if (clientIdFilter !== '') params.client_id = clientIdFilter;
      if (serviceIdFilter !== '') params.service_id = serviceIdFilter;
      if (!allTime) {
        if (dateFrom) params.date_from = dateFrom;
        if (dateTo) params.date_to = dateTo;
      }

      const resp = await adminApi.getAppointments(params);
      if (fetchSeq.current !== seq) return; // stale response — a newer fetch won
      setAppointments(resp.data.items);
      setTotalPages(resp.data.total_pages);
    } catch (err: any) {
      if (fetchSeq.current !== seq) return;
      if (err.response?.status === 401) {
        goLogin();
      } else setError('Ошибка загрузки');
    } finally {
      if (fetchSeq.current === seq) setLoading(false);
    }
  };

  // Deep-link support: <section>/appointments?status=X&client_id=Y&master_id=Z
  // (e.g. "appointments of this client" from Clients, stat cards from Revenue).
  // status=all explicitly resets the tab (dashboard "Все →").
  useEffect(() => {
    const qp = searchParams.get('client_id');
    if (qp !== null && qp !== '') {
      const id = Number(qp);
      if (Number.isFinite(id)) setClientIdFilter(id);
    }
    const mp = searchParams.get('master_id');
    if (mp !== null && mp !== '') {
      const id = Number(mp);
      if (Number.isFinite(id)) setMasterIdFilter(id);
    }
    const sp = searchParams.get('status');
    if (sp === 'all') {
      setStatusFilter('');
    } else if (
      sp !== null &&
      sp !== '' &&
      ['pending', 'confirmed', 'cancelled', 'completed'].includes(sp)
    ) {
      setStatusFilter(sp);
    }
    const hl = searchParams.get('highlight');
    if (hl !== null && hl !== '') {
      const id = Number(hl);
      if (Number.isFinite(id)) {
        // Cancelled/completed targets must be visible for the flash.
        setShowCompleted(true);
        setShowCancelled(true);
        // The target may sit on any page — start from the first one.
        setCurrentPage(0);
        setHighlightId(id);
      }
    }
    // consume once so back/forward stays clean
    if (
      searchParams.has('client_id') ||
      searchParams.has('master_id') ||
      searchParams.has('status') ||
      searchParams.has('highlight')
    ) {
      // A drill-down promises "everything matching": reveal completed rows
      // (hidden by default) so counts match the card that was clicked
      setShowCompleted(true);
      // Deep-linked filters live in the collapsible panel — open it so the
      // user sees what is applied instead of a "wrong" list
      setShowFilters(true);
      setSearchParams({}, { replace: true });
    }
  }, []);

  useEffect(() => {
    setCurrentPage(0);
  }, [
    statusFilter,
    masterIdFilter,
    clientIdFilter,
    serviceIdFilter,
    dateFrom,
    dateTo,
    allTime,
    showCompleted,
    showCancelled,
    dateSort,
  ]);

  useEffect(() => {
    fetch();
  }, [
    currentPage,
    statusFilter,
    masterIdFilter,
    clientIdFilter,
    serviceIdFilter,
    dateFrom,
    dateTo,
    allTime,
    showCompleted,
    showCancelled,
    dateSort,
  ]);

  // Bell deep-link: scroll to the row and flash it, then let go.
  useEffect(() => {
    if (highlightId === null || loading) return;
    const t = setTimeout(() => {
      const el = document.querySelector(`[data-row-id="${highlightId}"]`);
      if (el) {
        el.scrollIntoView({ behavior: 'smooth', block: 'center' });
        el.classList.add('row-flash');
        setTimeout(() => el.classList.remove('row-flash'), 3500);
      }
      setHighlightId(null);
    }, 300);
    return () => clearTimeout(t);
  }, [highlightId, loading, appointments]);

  const showError = (err: unknown) => {
    setError(getApiErrorMessage(err, 'Ошибка сервера'));
  };

  const handleConfirm = async (id: number) => {
    try {
      await adminApi.confirmAppointment(id);
      fetch();
      toast.success('Запись подтверждена');
    } catch (err: unknown) {
      showError(err);
    }
  };

  const handleCancel = async (id: number) => {
    setCancelingId(id);
  };

  const handleComplete = async (id: number) => {
    try {
      await adminApi.completeAppointment(id);
      fetch();
      toast.success('Запись завершена');
    } catch (err: unknown) {
      showError(err);
    }
  };

  const handleReopen = async (id: number) => {
    try {
      await adminApi.reopenAppointment(id);
      fetch();
      toast.success('Запись снова в работе');
    } catch (err: unknown) {
      showError(err);
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await adminApi.deleteAppointment(id);
      // No undo: backend has no undelete, a fake "cancel" toast would lie.
      toast.success('Запись удалена');
      fetch();
    } catch (err: unknown) {
      showError(err);
    } finally {
      setDeletingId(null);
    }
  };

  const handleConfirmCancel = async () => {
    if (!cancelingId || !cancelReason.trim()) return;
    try {
      await adminApi.cancelAppointment(cancelingId, cancelReason.trim());
      fetch();
      toast.success('Запись отменена');
    } catch (err: unknown) {
      showError(err);
    } finally {
      setCancelingId(null);
      setCancelReason('');
    }
  };

  const handleNoShow = async (id: number) => {
    try {
      await adminApi.noShowAppointment(id);
      toast.warning('Отмечено как неявка');
      fetch();
    } catch (err: unknown) {
      showError(err);
    } finally {
      setNoShowingId(null);
    }
  };

  const isAppointmentTimePassed = (dateStr: string) => new Date(dateStr) <= new Date();

  const openCreate = () => {
    setCreateMasterId(isSuperSection && masterIdFilter !== '' ? masterIdFilter : '');
    setCreateClientId('');
    setCreateServiceId('');
    setCreateDateTime('');
    setCreateStatus('confirmed');
    setCreateNotes('');
    setShowCreate(true);
  };

  const handleCreate = async () => {
    if (createClientId === '' || createServiceId === '' || !createDateTime) {
      toast.error('Выберите клиента, услугу и время');
      return;
    }
    if (isSuperSection && createMasterId === '') {
      toast.error('Выберите мастера');
      return;
    }
    setCreating(true);
    try {
      await adminApi.bookAppointment({
        client_id: createClientId,
        service_id: createServiceId,
        appointment_date: new Date(createDateTime).toISOString(),
        status: createStatus,
        notes: createNotes.trim() || undefined,
        ...(isSuperSection && createMasterId !== '' ? { master_id: createMasterId } : {}),
      });
      toast.success('Запись создана');
      setShowCreate(false);
      fetch();
    } catch (err: unknown) {
      toast.error(getApiErrorMessage(err, 'Не удалось создать запись'));
    } finally {
      setCreating(false);
    }
  };

  const filters = [
    { value: '', label: 'Все' },
    { value: 'pending', label: statusLabels['pending'] },
    { value: 'confirmed', label: statusLabels['confirmed'] },
    { value: 'cancelled', label: statusLabels['cancelled'] },
    { value: 'completed', label: statusLabels['completed'] },
  ];

  const handleSort = (field: SortField) => {
    // Dates are ordered by the server (cross-page); the rest re-sorts
    // the loaded page client-side.
    if (field === 'appointment_date') {
      setDateSort((d) => (d === 'asc' ? 'desc' : 'asc'));
      return;
    }
    if (sortField === field) {
      setSortDirection((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortField(field);
      setSortDirection('asc');
    }
  };

  const sortedAppointments = [...appointments].sort((a, b) => {
    // Server already ordered by date — re-sorting here would only
    // shuffle the visible page and lie about the rest.
    if (sortField === 'appointment_date') return 0;
    const valA: string | number | Date = a[sortField] ?? '';
    const valB: string | number | Date = b[sortField] ?? '';

    if (valA < valB) return sortDirection === 'asc' ? -1 : 1;
    if (valA > valB) return sortDirection === 'asc' ? 1 : -1;
    return 0;
  });

  const filteredAppointments = sortedAppointments;

  type Row = (typeof filteredAppointments)[number];
  const sortMark = (field: SortField) => {
    if (field === 'appointment_date') return dateSort === 'asc' ? ' ↑' : ' ↓';
    return sortField === field ? (sortDirection === 'asc' ? ' ↑' : ' ↓') : ' ⇅';
  };
  const sortHead = (field: SortField, label: string) => (
    <span
      onClick={() => handleSort(field)}
      style={{ cursor: 'pointer', userSelect: 'none' }}
      title={`Сортировать: ${label}`}
    >
      {label}
      <span className="sort-arrow">{sortMark(field)}</span>
    </span>
  );

  const columns: FitColumnDef<Row>[] = useMemo(
    () => [
      {
        id: 'check',
        header: () => (
          <input
            type="checkbox"
            checked={
              filteredAppointments.length > 0 &&
              selectedAppointments.size === filteredAppointments.length
            }
            onChange={() => {
              if (selectedAppointments.size === filteredAppointments.length)
                setSelectedAppointments(new Set());
              else setSelectedAppointments(new Set(filteredAppointments.map((a) => a.id)));
            }}
            title="Выбрать все на странице"
          />
        ),
        cell: ({ row }) => {
          const a = row.original;
          return (
            <input
              type="checkbox"
              checked={selectedAppointments.has(a.id)}
              onChange={() =>
                setSelectedAppointments((prev) => {
                  const next = new Set(prev);
                  if (next.has(a.id)) next.delete(a.id);
                  else next.add(a.id);
                  return next;
                })
              }
              title="Выбрать для экспорта"
            />
          );
        },
        meta: { defaultWidth: 48, hideable: false, resizable: false, label: '✓' },
      },
      {
        id: 'date',
        header: () => sortHead('appointment_date', 'Дата'),
        accessorFn: (a) => a.appointment_date,
        cell: ({ row }) => (
          <span style={{ whiteSpace: 'nowrap', fontVariantNumeric: 'tabular-nums' }}>
            {new Date(row.original.appointment_date).toLocaleString('ru-RU', {
              day: '2-digit',
              month: '2-digit',
              year: 'numeric',
              hour: '2-digit',
              minute: '2-digit',
            })}
          </span>
        ),
        meta: { minWidth: 130, label: 'Дата' },
      },
      {
        id: 'client',
        header: () => sortHead('client_name', 'Клиент'),
        accessorFn: (a) => a.client_name || '—',
        cell: ({ row }) => {
          const a = row.original;
          return (
            <>
              <strong>{a.client_name || '—'}</strong>
              {a.notes ? (
                <span className="notes-dot" title={`💬 ${a.notes}`}>
                  {' '}
                  💬
                </span>
              ) : null}
            </>
          );
        },
        meta: { minWidth: 120, label: 'Клиент' },
      },
      {
        id: 'phone',
        header: 'Телефон',
        accessorFn: (a) => a.client_phone || '—',
        cell: ({ row }) => {
          const a = row.original;
          return <a href={`tel:${a.client_phone || ''}`}>{a.client_phone || '—'}</a>;
        },
        meta: { minWidth: 110, label: 'Телефон' },
      },
      {
        id: 'service',
        header: () => sortHead('service_name', 'Услуга'),
        accessorFn: (a) => a.service_name || '—',
        cell: ({ row }) => row.original.service_name || '—',
        meta: { minWidth: 120, label: 'Услуга' },
      },
      {
        id: 'price',
        header: () => sortHead('service_price', 'Сумма'),
        accessorFn: (a) => a.service_price ?? 0,
        cell: ({ row }) => {
          const p = row.original.service_price;
          const coupon = row.original.coupon_code;
          const label = row.original.discount_label;
          const titleBits = [
            coupon ? `Промокод: ${coupon}` : '',
            label && (!coupon || !label.includes(coupon)) ? `Скидка: ${label}` : '',
          ].filter(Boolean);
          return (
            <span title={titleBits.length > 0 ? titleBits.join(' · ') : undefined}>
              {p ? `${Number(p).toLocaleString('ru-RU')} ₽` : '—'}
              {label ? (
                <span style={{ marginLeft: 6, whiteSpace: 'nowrap' }} title={`Скидка: ${label}`}>
                  🏷 {label}
                </span>
              ) : coupon ? (
                <span title={`Промокод: ${coupon}`} style={{ marginLeft: 6, whiteSpace: 'nowrap' }}>
                  🎟 {coupon}
                </span>
              ) : null}
            </span>
          );
        },
        meta: { minWidth: 80, maxWidth: 200, label: 'Сумма' },
      },
      {
        id: 'status',
        header: () => sortHead('status', 'Статус'),
        accessorFn: (a) => a.status,
        cell: ({ row }) => (
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
            <Tooltip
              content={statusLabels[row.original.status] || row.original.status}
              position="top"
            >
              <StatusBadge status={row.original.status} />
            </Tooltip>
            <span
              title={
                row.original.status === 'pending' || row.original.status === 'confirmed'
                  ? isAppointmentTimePassed(row.original.appointment_date)
                    ? 'Время записи прошло — подтвердите или завершите'
                    : ''
                  : ''
              }
              style={{ width: 18, textAlign: 'center' }}
            >
              {(row.original.status === 'pending' || row.original.status === 'confirmed') &&
                isAppointmentTimePassed(row.original.appointment_date) &&
                '⏰'}
            </span>
          </span>
        ),
        meta: { minWidth: 120, label: 'Статус' },
      },
      ...(isSuperSection
        ? [
            {
              id: 'master',
              header: () => sortHead('master_name', 'Мастер'),
              accessorFn: (a: Row) => a.master_name || '—',
              cell: ({ row }: { row: { original: Row } }) => (
                <span title={row.original.master_name || ''}>
                  {row.original.master_name || '—'}
                </span>
              ),
              meta: { minWidth: 110, label: 'Мастер' },
            } as FitColumnDef<Row>,
          ]
        : []),
      {
        id: 'actions',
        header: 'Действия',
        cell: ({ row }) => {
          const a = row.original;
          return (
            <span style={{ display: 'inline-flex', gap: 4 }}>
              {a.status === 'pending' && (
                <>
                  <Tooltip content="Подтвердить запись">
                    <button className="btn btn-sm btn-confirm" onClick={() => handleConfirm(a.id)}>
                      ✅
                    </button>
                  </Tooltip>
                  <Tooltip content="Отменить запись">
                    <button className="btn btn-sm btn-cancel" onClick={() => handleCancel(a.id)}>
                      ❌
                    </button>
                  </Tooltip>
                </>
              )}
              {a.status === 'confirmed' && (
                <>
                  <Tooltip content="Завершить запись">
                    <button
                      className="btn btn-sm btn-complete"
                      onClick={() => handleComplete(a.id)}
                      disabled={!isAppointmentTimePassed(a.appointment_date)}
                    >
                      🏁
                    </button>
                  </Tooltip>
                  <Tooltip content="Отменить запись">
                    <button className="btn btn-sm btn-cancel" onClick={() => handleCancel(a.id)}>
                      ❌
                    </button>
                  </Tooltip>
                </>
              )}
              {a.status === 'confirmed' && isAppointmentTimePassed(a.appointment_date) && (
                <Tooltip content="Отметить неявку">
                  <button className="btn btn-sm btn-no-show" onClick={() => setNoShowingId(a.id)}>
                    👤
                  </button>
                </Tooltip>
              )}
              {a.status === 'completed' && (
                <Tooltip content="Вернуть в работу (снова подтверждена: доступны неявка и отмена)">
                  <button className="btn btn-sm btn-ghost" onClick={() => handleReopen(a.id)}>
                    ↩️
                  </button>
                </Tooltip>
              )}
              <Tooltip content="Удалить запись">
                <button className="btn btn-sm btn-delete" onClick={() => setDeletingId(a.id)}>
                  ✖
                </button>
              </Tooltip>
            </span>
          );
        },
        meta: { minWidth: 150, hideable: false, label: 'Действия' },
      },
    ],
    [filteredAppointments, selectedAppointments, sortField, sortDirection, isSuperSection],
  );

  return (
    <div className="appointments-page">
      <div className="page-header">
        <div>
          <h1>Управление записями</h1>
          <p>
            {isSuperSection
              ? 'Подтверждение, завершение и отмена записей'
              : 'Мои записи — подтверждение, завершение и отмена'}
          </p>
        </div>
        <div className="page-header-actions">
          <button
            type="button"
            className="btn btn-primary"
            onClick={openCreate}
            title="Создать запись прямо здесь (без расписания)"
          >
            ＋ Новая запись
          </button>
          <button
            className="btn btn-ghost"
            onClick={async () => {
              const params = new URLSearchParams();
              if (selectedAppointments.size > 0) {
                params.set('ids', [...selectedAppointments].join(','));
              } else {
                if (statusFilter) params.set('status', statusFilter);
                if (masterIdFilter !== '') params.set('master_id', String(masterIdFilter));
                if (clientIdFilter !== '') params.set('client_id', String(clientIdFilter));
                if (serviceIdFilter !== '') params.set('service_id', String(serviceIdFilter));
                if (dateFrom) params.set('date_from', dateFrom);
                if (dateTo) params.set('date_to', dateTo);
              }
              if (isSuperSection) params.set('include_master', 'true');
              try {
                await downloadCsv(
                  `/api/v1/admin/export/appointments?${params.toString()}`,
                  'appointments.csv',
                );
                toast.success(
                  selectedAppointments.size > 0
                    ? `Выгружено: ${selectedAppointments.size}`
                    : 'CSV выгружен',
                );
              } catch (err: unknown) {
                toast.error(getApiErrorMessage(err, 'Не удалось выгрузить CSV'));
              }
            }}
            title={
              selectedAppointments.size > 0 ? 'Выгрузить отмеченные' : 'Выгрузить все по фильтру'
            }
          >
            📥 Экспорт CSV{selectedAppointments.size > 0 ? ` (${selectedAppointments.size})` : ''}
          </button>
        </div>
      </div>

      {error && <div className="error-message">{error}</div>}

      <div className="filters-bar">
        {filters.map((f) => (
          <button
            key={f.value}
            className={`filter-btn ${statusFilter === f.value ? 'active' : ''}`}
            onClick={() => {
              setStatusFilter(f.value);
              // The completed/cancelled tabs promise those rows — reveal them
              // even if the toggles below are off.
              if (f.value === 'completed') setShowCompleted(true);
              if (f.value === 'cancelled') setShowCancelled(true);
            }}
          >
            {f.label}
          </button>
        ))}
      </div>

      {/* Advanced filters toggle */}
      <div style={{ marginBottom: 12, display: 'flex', justifyContent: 'center', gap: 8 }}>
        <button
          className="btn btn-ghost"
          onClick={() => setShowFilters((p) => !p)}
          style={{ fontSize: 13 }}
        >
          {showFilters ? '▲ Скрыть фильтры' : '▼ Расширенные фильтры'}
        </button>
      </div>

      {/* Advanced filters */}
      {showFilters && (
        <div className="card" style={{ marginBottom: 16, padding: 16 }}>
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
              gap: 12,
            }}
          >
            {/* Master filter — superadmin only; masters see only their own rows */}
            {isSuperSection && (
              <div style={{ gridColumn: '1 / -1' }}>
                <MasterSelect
                  value={masterIdFilter}
                  onChange={setMasterIdFilter}
                  style={{ marginBottom: 0, maxWidth: 480 }}
                />
              </div>
            )}

            {/* Client filter */}
            <div className="filter-cell">
              <label className="filter-label">Клиент</label>
              <select
                className="filter-control"
                value={clientIdFilter}
                onChange={(e) =>
                  setClientIdFilter(e.target.value === '' ? '' : Number(e.target.value))
                }
              >
                <option value="">Все клиенты</option>
                {allClients.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
            </div>

            {/* Service filter */}
            <div className="filter-cell">
              <label className="filter-label">Услуга</label>
              <select
                className="filter-control"
                value={serviceIdFilter}
                onChange={(e) =>
                  setServiceIdFilter(e.target.value === '' ? '' : Number(e.target.value))
                }
              >
                <option value="">Все услуги</option>
                {allServices.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name}
                  </option>
                ))}
              </select>
            </div>

            {/* Date from */}
            <div className="filter-cell">
              <label className="filter-label">Дата от</label>
              <input
                type="date"
                className="filter-control"
                value={dateFrom}
                disabled={allTime}
                onChange={(e) => setDateFrom(e.target.value)}
              />
            </div>

            {/* Date to */}
            <div className="filter-cell">
              <label className="filter-label">Дата до</label>
              <input
                type="date"
                className="filter-control"
                value={dateTo}
                disabled={allTime}
                onChange={(e) => setDateTo(e.target.value)}
              />
            </div>

            {/* All time — same row, right after the dates */}
            <div className="filter-cell-bottom">
              <label className="filter-check">
                <input type="checkbox" checked={allTime} onChange={() => setAllTime((v) => !v)} />
                За всё время
              </label>
            </div>
          </div>
          {/* Reset filters button — centered, visible */}
          <div style={{ display: 'flex', justifyContent: 'center', marginTop: 12 }}>
            <button
              className="btn filter-reset"
              onClick={() => {
                setStatusFilter('');
                setMasterIdFilter('');
                setClientIdFilter('');
                setServiceIdFilter('');
                setDateFrom('');
                setDateTo('');
              }}
            >
              ✕ Сбросить фильтры
            </button>
          </div>
        </div>
      )}

      <div
        style={{
          marginBottom: 16,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          gap: 16,
        }}
      >
        <label
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            cursor: 'pointer',
            fontSize: 14,
            color: '#666',
          }}
        >
          <input
            type="checkbox"
            checked={showCompleted}
            onChange={() => setShowCompleted((p) => !p)}
            style={{ width: 16, height: 16, accentColor: '#667eea' }}
          />
          Показать завершённые
        </label>
        <label
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            cursor: 'pointer',
            fontSize: 14,
            color: '#666',
          }}
        >
          <input
            type="checkbox"
            checked={showCancelled}
            onChange={() => setShowCancelled((p) => !p)}
            style={{ width: 16, height: 16, accentColor: '#667eea' }}
          />
          Показать отменённые
        </label>
        {!isSuperSection && <AutoConfirmSwitch />}
        {!isSuperSection && <AutoCompleteSwitch />}
      </div>

      {loading ? (
        <div className="card">
          <Skeleton rows={5} height="48px" />
        </div>
      ) : filteredAppointments.length === 0 ? (
        <EmptyState
          icon="📅"
          title="Нет записей"
          description={
            showCompleted ? 'Завершённые записи не найдены' : 'Активных записей не найдено'
          }
        />
      ) : (
        <div className="card">
          <div className="appointments-table-wrapper">
            <DataTable
              tableId="appointments"
              columns={columns}
              data={filteredAppointments}
              rowId={(a) => a.id}
            />
          </div>
        </div>
      )}

      {/* Delete confirmation modal */}
      <ConfirmDialog
        open={deletingId !== null}
        onClose={() => setDeletingId(null)}
        title="🗑 Удалить запись?"
        message="Это действие нельзя отменить."
        confirmLabel="Удалить"
        danger
        onConfirm={() => deletingId !== null && handleDelete(deletingId)}
      />

      {/* Cancel confirmation modal */}
      <ConfirmDialog
        open={cancelingId !== null}
        onClose={() => setCancelingId(null)}
        title="❌ Отменить запись?"
        confirmLabel="Отменить"
        danger
        confirmDisabled={!cancelReason.trim()}
        onConfirm={handleConfirmCancel}
      >
        <div className="form-group">
          <label>Причина отмены</label>
          <textarea
            value={cancelReason}
            onChange={(e) => setCancelReason(e.target.value)}
            placeholder="Укажите причину..."
            rows={3}
            style={{
              width: '100%',
              padding: 10,
              border: '2px solid #e0e0e0',
              borderRadius: 8,
              fontSize: 14,
              resize: 'vertical',
            }}
          />
        </div>
      </ConfirmDialog>

      {/* No-show confirmation modal */}
      <ConfirmDialog
        open={noShowingId !== null}
        onClose={() => setNoShowingId(null)}
        title="👤 Отметить неявку?"
        message="Клиент не появился на записи. Запись будет отменена, счётчик неявок увеличен."
        confirmLabel="Неявка"
        danger
        onConfirm={() => noShowingId !== null && handleNoShow(noShowingId)}
      />

      {/* Quick booking modal */}
      <Modal open={showCreate} onClose={() => setShowCreate(false)} title="📅 Новая запись">
        {isSuperSection && (
          <div className="form-group">
            <label>Мастер</label>
            <MasterSelect value={createMasterId} onChange={setCreateMasterId} />
          </div>
        )}
        <div className="form-group">
          <label>Клиент</label>
          <select
            className="filter-control"
            value={createClientId}
            onChange={(e) => setCreateClientId(e.target.value === '' ? '' : Number(e.target.value))}
          >
            <option value="">Выберите клиента…</option>
            {allClients.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        </div>
        <div className="form-group">
          <label>Услуга</label>
          <select
            className="filter-control"
            value={createServiceId}
            onChange={(e) =>
              setCreateServiceId(e.target.value === '' ? '' : Number(e.target.value))
            }
          >
            <option value="">Выберите услугу…</option>
            {allServices
              .filter(
                (s) =>
                  !isSuperSection ||
                  createMasterId === '' ||
                  s.master_id === undefined ||
                  s.master_id === createMasterId,
              )
              .map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
          </select>
        </div>
        <div className="form-row">
          <div className="form-group">
            <label>Дата и время</label>
            <input
              type="datetime-local"
              value={createDateTime}
              onChange={(e) => setCreateDateTime(e.target.value)}
            />
          </div>
          <div className="form-group">
            <label>Статус</label>
            <select value={createStatus} onChange={(e) => setCreateStatus(e.target.value)}>
              <option value="confirmed">✅ Подтверждена</option>
              <option value="pending">⏳ Ожидает</option>
            </select>
          </div>
        </div>
        <div className="form-group">
          <label>Комментарий (необязательно)</label>
          <input
            value={createNotes}
            onChange={(e) => setCreateNotes(e.target.value.slice(0, 140))}
            placeholder="Пожелания..."
            maxLength={140}
          />
        </div>
        <div className="modal-actions">
          <button type="button" className="btn btn-ghost" onClick={() => setShowCreate(false)}>
            Отмена
          </button>
          <button
            type="button"
            className="btn btn-primary"
            disabled={creating}
            onClick={handleCreate}
          >
            {creating ? 'Создаём…' : 'Создать запись'}
          </button>
        </div>
      </Modal>

      {/* Pagination */}
      <Pager page={currentPage} totalPages={totalPages} onChange={setCurrentPage} />
    </div>
  );
}
export default AppointmentsPage;
