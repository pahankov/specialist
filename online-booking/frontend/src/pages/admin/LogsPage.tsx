import { useEffect, useMemo, useState } from 'react';
import { adminApi } from '../../api/client';
import type { AuditLogEntry } from '../../api/types';
import { getApiErrorMessage, getApiErrorStatus } from '../../utils/apiError';
import { getCookie, decodeJwtPayload } from '../../utils/cookies';
import { Pager, Skeleton, EmptyState, DataTable } from '../../components/common';
import type { FitColumnDef } from '../../components/common';
import { usePersistentState } from '../../utils/persistentState';
import '../../styles/tables.css';
import './LogsPage.css';
import { entityLabels, actionLabels, levelLabels } from '../../constants/statusLabels';

function getIsAdmin(): boolean {
  const token = getCookie('access_token');
  if (!token) return false;
  return decodeJwtPayload(token)?.is_admin === true;
}

function LogsPage() {
  const isAdmin = getIsAdmin();
  const [logs, setLogs] = useState<AuditLogEntry[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [entityFilter, setEntityFilter] = usePersistentState('logs.entity', '');
  const [levelFilter, setLevelFilter] = usePersistentState('logs.level', '');
  const [actionFilter, setActionFilter] = usePersistentState('logs.action', '');
  const [quickSearch, setQuickSearch] = usePersistentState('logs.search', '');
  const [masterFilter, setMasterFilter] = usePersistentState('logs.master', '');
  const [currentPage, setCurrentPage] = usePersistentState('logs.page', 0);
  const pageSize = 20;

  const fetchLogs = async () => {
    try {
      const params: Record<string, string | number> = {
        limit: pageSize,
        offset: currentPage * pageSize,
      };
      if (entityFilter) params.entity_type = entityFilter;
      if (masterFilter) params.master_id = masterFilter;

      // Superadmin uses /audit-logs/all, regular master uses /audit-logs (own logs)
      const resp = isAdmin
        ? await adminApi.getAuditLogsAll(params)
        : await adminApi.getAuditLogs(params);
      setLogs(resp.data.logs);
      setTotal(resp.data.total);
    } catch (err: unknown) {
      if (getApiErrorStatus(err) === 401) {
        window.location.href = '/admin/login';
      } else {
        const detail = getApiErrorMessage(err, 'Ошибка загрузки логов');
        setError(typeof detail === 'string' ? detail : JSON.stringify(detail));
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    setLoading(true);
    fetchLogs();
  }, [entityFilter, masterFilter, currentPage]);

  // Hooks must run before any early return (loading/error): otherwise the
  // hook count changes between renders and React unmounts the page.
  const columns: FitColumnDef<AuditLogEntry>[] = useMemo(
    () => [
      {
        id: 'date',
        header: 'Дата и время',
        accessorFn: (log) => log.created_at || '',
        cell: ({ row }) => {
          const log = row.original;
          return log.created_at
            ? new Date(log.created_at).toLocaleString('ru-RU', {
                day: '2-digit',
                month: '2-digit',
                year: 'numeric',
                hour: '2-digit',
                minute: '2-digit',
              })
            : '—';
        },
        meta: { minWidth: 130, label: 'Дата и время' },
      },
      {
        id: 'level',
        header: 'Уровень',
        accessorFn: (log) => log.level,
        cell: ({ row }) => (
          <span className={`level-badge level-${row.original.level}`}>
            {levelLabels[row.original.level] || row.original.level}
          </span>
        ),
        meta: { minWidth: 90, maxWidth: 140, label: 'Уровень' },
      },
      {
        id: 'action',
        header: 'Действие',
        accessorFn: (log) => log.action,
        cell: ({ row }) => {
          const log = row.original;
          return (
            <span
              className={`status-badge ${
                log.action === 'delete'
                  ? 'status-cancelled'
                  : log.action === 'confirm'
                    ? 'status-confirmed'
                    : log.action === 'cancel'
                      ? 'status-cancelled'
                      : log.action === 'complete'
                        ? 'status-completed'
                        : log.action === 'create'
                          ? 'status-pending'
                          : 'status-pending'
              }`}
            >
              {actionLabels[log.action] || log.action}
            </span>
          );
        },
        meta: { minWidth: 110, label: 'Действие' },
      },
      {
        id: 'object',
        header: 'Объект',
        accessorFn: (log) => log.entity_type,
        cell: ({ row }) => entityLabels[row.original.entity_type] || row.original.entity_type,
        meta: { minWidth: 90, maxWidth: 150, label: 'Объект' },
      },
      {
        id: 'object_id',
        header: 'ID объекта',
        accessorFn: (log) => log.entity_id ?? 0,
        cell: ({ row }) => <code>{row.original.entity_id || '—'}</code>,
        meta: { minWidth: 70, maxWidth: 110, label: 'ID объекта' },
      },
      {
        id: 'master',
        header: 'Мастер',
        accessorFn: (log) => log.master_name || '—',
        cell: ({ row }) => row.original.master_name || '—',
        meta: { minWidth: 110, label: 'Мастер' },
      },
      {
        id: 'details',
        header: 'Детали',
        accessorFn: (log) => log.details || '—',
        cell: ({ row }) => row.original.details || '—',
        meta: { minWidth: 160, maxWidth: 600, label: 'Детали' },
      },
    ],
    [],
  );

  const visibleLogs = logs.filter((log) => {
    if (levelFilter && log.level !== levelFilter) return false;
    if (actionFilter && log.action !== actionFilter) return false;
    const q = quickSearch.trim().toLowerCase();
    if (q) {
      const haystack = [
        log.action,
        log.entity_type,
        log.details ?? '',
        log.master_name ?? '',
        String(log.entity_id ?? ''),
      ]
        .join(' ')
        .toLowerCase();
      if (!haystack.includes(q)) return false;
    }
    return true;
  });

  const entityFilters = [
    { value: '', label: 'Все' },
    { value: 'appointment', label: '📅 Записи' },
    { value: 'service', label: '💇 Услуги' },
    { value: 'client', label: '👤 Клиенты' },
    { value: 'master', label: '👨‍💼 Мастера' },
    { value: 'auth', label: '🔑 Входы/выходы' },
  ];

  if (loading)
    return (
      <div>
        <Skeleton rows={8} />
      </div>
    );
  if (error)
    return (
      <div>
        <div className="error-message">{error}</div>
      </div>
    );

  return (
    <div>
      <div className="page-header">
        <h1>📋 Журнал действий</h1>
        <p>История всех операций в системе</p>
      </div>

      {/* Entity filter */}
      <div className="filters-bar">
        {entityFilters.map((f) => (
          <button
            key={f.value}
            className={`filter-btn ${entityFilter === f.value ? 'active' : ''}`}
            onClick={() => {
              setEntityFilter(f.value);
              setCurrentPage(0);
            }}
          >
            {f.label}
          </button>
        ))}
      </div>

      {/* Master filter (superadmin only) */}
      {isAdmin && (
        <div className="filters-bar" style={{ marginTop: 8 }}>
          <input
            type="text"
            placeholder="Фильтр по ID мастера..."
            value={masterFilter}
            onChange={(e) => {
              setMasterFilter(e.target.value);
              setCurrentPage(0);
            }}
            className="filter-input"
            style={{ width: 200 }}
          />
        </div>
      )}

      {/* Level + action + quick search (over the loaded page) */}
      <div className="filters-bar" style={{ marginTop: 8 }}>
        <select
          value={levelFilter}
          onChange={(e) => setLevelFilter(e.target.value)}
          className="filter-input"
          style={{ width: 160 }}
          title="Уровень"
        >
          <option value="">Все уровни</option>
          <option value="info">ℹ️ INFO</option>
          <option value="warning">⚠️ WARNING</option>
          <option value="error">🚫 ERROR</option>
        </select>
        <select
          value={actionFilter}
          onChange={(e) => setActionFilter(e.target.value)}
          className="filter-input"
          style={{ width: 200 }}
          title="Действие"
        >
          <option value="">Все действия</option>
          {Object.entries(actionLabels).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
        <input
          type="text"
          placeholder="Быстрый поиск по странице..."
          value={quickSearch}
          onChange={(e) => setQuickSearch(e.target.value)}
          className="filter-input"
          style={{ width: 240 }}
        />
      </div>

      <div className="card">
        {visibleLogs.length === 0 ? (
          <EmptyState
            title={logs.length === 0 ? 'Нет записей в журнале' : 'Ничего не найдено'}
            description={logs.length === 0 ? undefined : 'Измените фильтры'}
          />
        ) : (
          <DataTable tableId="logs" columns={columns} data={visibleLogs} />
        )}
      </div>

      {/* Pagination */}
      <Pager
        page={currentPage}
        totalPages={Math.ceil(total / pageSize) || 1}
        onChange={setCurrentPage}
        label={`Страница ${currentPage + 1} из ${Math.ceil(total / pageSize) || 1} (${total} записей)`}
      />
    </div>
  );
}

export default LogsPage;
