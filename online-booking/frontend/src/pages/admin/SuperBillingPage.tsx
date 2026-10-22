import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { billingApi, type BillingOverview } from '../../api/client';
import { EmptyState, Skeleton } from '../../components/common';
import { getApiErrorMessage } from '../../utils/apiError';
import { SUPER_PREFIX } from '../../utils/section';
import './SuperBillingPage.css';

function money(value: number | undefined | null): string {
  return `${Number(value ?? 0).toLocaleString('ru-RU', {
    minimumFractionDigits: Number.isInteger(Number(value ?? 0)) ? 0 : 2,
    maximumFractionDigits: 2,
  })} ₽`;
}

function date(value?: string | null): string {
  if (!value) return '—';
  return new Date(value).toLocaleDateString('ru-RU');
}

const STATUS_OPTIONS = [
  { value: 'all', label: 'Все статусы' },
  { value: 'trial', label: 'Пробный период' },
  { value: 'active', label: 'Активные' },
  { value: 'readonly', label: 'Только чтение' },
  { value: 'paused', label: 'Приостановлены' },
  { value: 'suspended', label: 'Заблокированы' },
];

function SuperBillingPage() {
  const navigate = useNavigate();
  const [data, setData] = useState<BillingOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [searchInput, setSearchInput] = useState('');
  const [search, setSearch] = useState('');
  const [status, setStatus] = useState('all');

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const response = await billingApi.overview({
        search: search.trim() || undefined,
        status,
      });
      setData(response.data);
    } catch (err) {
      toast.error(getApiErrorMessage(err, 'Не удалось загрузить биллинг'));
    } finally {
      setLoading(false);
    }
  }, [search, status]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <div className="super-billing-page">
      <div className="page-header">
        <div>
          <h1>💳 Биллинг мастеров</h1>
          <p className="super-billing-subtitle">
            Пробные периоды, счета, баланс, бонусы и блокировки. Оплата подтверждается вручную.
          </p>
        </div>
        <button className="btn btn-secondary" onClick={load} disabled={loading}>
          {loading ? 'Обновляем…' : '↻ Обновить'}
        </button>
      </div>

      {data && (
        <div className="super-billing-summary">
          <div className="card super-billing-summary-card">
            <span>К оплате</span>
            <strong>{money(data.summary.due)}</strong>
          </div>
          <div className="card super-billing-summary-card credit">
            <span>Баланс</span>
            <strong>{money(data.summary.credit)}</strong>
          </div>
          <div className="card super-billing-summary-card warn">
            <span>В режиме чтения</span>
            <strong>{data.summary.readonly}</strong>
          </div>
          <div className="card super-billing-summary-card danger">
            <span>Приостановлены</span>
            <strong>{data.summary.paused}</strong>
          </div>
          <div className="card super-billing-summary-card review">
            <span>На проверке качества</span>
            <strong>{data.summary.review}</strong>
          </div>
        </div>
      )}

      <div className="card super-billing-filters">
        <input
          className="form-input"
          value={searchInput}
          onChange={(event) => setSearchInput(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter') setSearch(searchInput.trim());
          }}
          placeholder="Поиск по имени, email или ID"
          aria-label="Поиск мастера"
        />
        <select
          className="form-input"
          value={status}
          onChange={(event) => setStatus(event.target.value)}
          aria-label="Статус доступа"
        >
          {STATUS_OPTIONS.map((option) => (
            <option value={option.value} key={option.value}>
              {option.label}
            </option>
          ))}
        </select>
        <button
          className="btn btn-primary"
          onClick={() => setSearch(searchInput.trim())}
          disabled={loading}
        >
          Найти
        </button>
      </div>

      {loading ? (
        <Skeleton rows={6} height="52px" />
      ) : !data || data.items.length === 0 ? (
        <div className="card">
          <EmptyState icon="💳" title="Мастера не найдены" />
        </div>
      ) : (
        <div className="card super-billing-table-card">
          <div className="super-billing-table-wrap">
            <table className="super-billing-table">
              <thead>
                <tr>
                  <th>Мастер</th>
                  <th>Доступ</th>
                  <th>Пробный до</th>
                  <th>К оплате</th>
                  <th>Баланс</th>
                  <th>Реферал</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {data.items.map((row) => (
                  <tr
                    key={row.master_id}
                    onClick={() => navigate(`${SUPER_PREFIX}/masters/${row.master_id}?tab=billing`)}
                  >
                    <td>
                      <div className="super-billing-master">
                        <strong>{row.master_name}</strong>
                        <span>{row.email || `ID ${row.master_id}`}</span>
                      </div>
                    </td>
                    <td>
                      <span className={`super-billing-status status-${row.access_status}`}>
                        {row.access_status_label}
                      </span>
                      {row.review_flag && (
                        <span className="super-billing-review" title="Проверка качества">
                          ⚠️
                        </span>
                      )}
                    </td>
                    <td>{date(row.trial_ends_at)}</td>
                    <td className={row.balance_due > 0 ? 'super-billing-due' : ''}>
                      {money(row.balance_due)}
                    </td>
                    <td className="super-billing-credit">{money(row.balance_credit)}</td>
                    <td>
                      <code>{row.referral_code}</code>
                    </td>
                    <td className="super-billing-open">Открыть →</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

export default SuperBillingPage;
