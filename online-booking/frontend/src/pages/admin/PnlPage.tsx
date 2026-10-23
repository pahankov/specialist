import { useEffect, useState } from 'react';
import { superAdminApi } from '../../api/client';
import type { PnlCategoryTotal, PnlReport } from '../../api/types';
import { EmptyState, Skeleton } from '../../components/common';
import { getApiErrorMessage } from '../../utils/apiError';
import { goLogin } from '../../utils/redirect';
import '../../styles/filters.css';
import './PnlPage.css';

function formatMoney(value: number) {
  const formatted = Math.abs(value).toLocaleString('ru-RU', {
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  });
  return `${value < 0 ? '−' : ''}${formatted} ₽`;
}

function formatDate(value: string) {
  const [year, month, day] = value.split('-');
  return year && month && day ? `${day}.${month}.${year}` : value;
}

/** Russian plural for the operation counter («1 операция», «2 операции»). */
function operationsLabel(count: number): string {
  const mod10 = count % 10;
  const mod100 = count % 100;
  if (mod10 === 1 && mod100 !== 11) return `${count} операция`;
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) {
    return `${count} операции`;
  }
  return `${count} операций`;
}

function CategoryTable({
  title,
  icon,
  lines,
  count,
  total,
  emptyHint,
}: {
  title: string;
  icon: string;
  lines: PnlCategoryTotal[];
  count: number;
  total: number;
  emptyHint: string;
}) {
  return (
    <div className="card pnl-table-card">
      <div className="pnl-table-header">
        <h2>
          {icon} {title}
        </h2>
        <span className="pnl-count">{operationsLabel(count)}</span>
      </div>
      <table className="pnl-table">
        <thead>
          <tr>
            <th>Статья</th>
            <th className="pnl-amount">Сумма</th>
            <th className="pnl-share">Доля</th>
          </tr>
        </thead>
        <tbody>
          {lines.length === 0 ? (
            <tr>
              <td colSpan={3} className="pnl-empty-row">
                {emptyHint}
              </td>
            </tr>
          ) : (
            lines.map((line) => (
              <tr key={line.category_id}>
                <td className="pnl-category">{line.name}</td>
                <td className="pnl-amount">{formatMoney(line.amount)}</td>
                <td className="pnl-share">
                  <div className="pnl-share-cell">
                    <div className="pnl-share-track" aria-hidden="true">
                      <div
                        className="pnl-share-fill"
                        style={{ width: `${Math.max(0, Math.min(100, line.share))}%` }}
                      />
                    </div>
                    <span>{line.share.toFixed(1)}%</span>
                  </div>
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>
      <div className="pnl-table-total">
        <span>Итого</span>
        <strong>{formatMoney(total)}</strong>
      </div>
    </div>
  );
}

/**
 * Superadmin P&L. Reads the period report and renders zeros until income and
 * expense entries appear, so the layout is stable from day one.
 */
function PnlPage() {
  const [report, setReport] = useState<PnlReport | null>(null);
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError('');

    const params: { date_from?: string; date_to?: string } = {};
    if (dateFrom) params.date_from = dateFrom;
    if (dateTo) params.date_to = dateTo;

    superAdminApi
      .getPnlReport(params)
      .then(({ data }) => {
        if (!cancelled) setReport(data);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        const status = (err as { response?: { status?: number } }).response?.status;
        if (status === 401) {
          goLogin();
          return;
        }
        setError(getApiErrorMessage(err, 'Не удалось загрузить отчёт P&L'));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [dateFrom, dateTo]);

  const resetPeriod = () => {
    setDateFrom('');
    setDateTo('');
  };

  const hasCustomPeriod = Boolean(dateFrom || dateTo);

  return (
    <div className="pnl-page">
      <div className="page-header">
        <h1>📈 P&L · Прибыль и убытки</h1>
        <p>
          Финансовый результат за период
          {report && ` · ${formatDate(report.date_from)} — ${formatDate(report.date_to)}`}
        </p>
      </div>

      <div className="card pnl-filters">
        <div className="filter-cell">
          <label className="filter-label" htmlFor="pnl-date-from">
            Дата от
          </label>
          <input
            id="pnl-date-from"
            type="date"
            className="filter-control"
            value={dateFrom}
            max={dateTo || undefined}
            onChange={(event) => setDateFrom(event.target.value)}
          />
        </div>
        <div className="filter-cell">
          <label className="filter-label" htmlFor="pnl-date-to">
            Дата до
          </label>
          <input
            id="pnl-date-to"
            type="date"
            className="filter-control"
            value={dateTo}
            min={dateFrom || undefined}
            onChange={(event) => setDateTo(event.target.value)}
          />
        </div>
        <div className="pnl-filter-actions">
          <button
            type="button"
            className="btn pnl-reset"
            onClick={resetPeriod}
            disabled={!hasCustomPeriod}
          >
            Текущий месяц
          </button>
        </div>
        <p className="pnl-filter-hint">
          Даты включительно. Без фильтра показывается текущий месяц.
        </p>
      </div>

      {error && <div className="error-message pnl-error">{error}</div>}

      {loading && !report ? (
        <div className="pnl-summary-grid">
          <Skeleton width="100%" height="120px" />
          <Skeleton width="100%" height="120px" />
          <Skeleton width="100%" height="120px" />
          <Skeleton width="100%" height="120px" />
        </div>
      ) : report ? (
        <>
          <div className={`pnl-summary-grid ${loading ? 'pnl-loading' : ''}`}>
            <div className="pnl-card pnl-income">
              <div className="pnl-card-icon">💵</div>
              <div className="pnl-card-value">{formatMoney(report.revenue)}</div>
              <div className="pnl-card-label">Доходы</div>
              <div className="pnl-card-sub">{operationsLabel(report.income_count)}</div>
            </div>
            <div className="pnl-card pnl-expense">
              <div className="pnl-card-icon">🧾</div>
              <div className="pnl-card-value">{formatMoney(report.expenses)}</div>
              <div className="pnl-card-label">Расходы</div>
              <div className="pnl-card-sub">{operationsLabel(report.expense_count)}</div>
            </div>
            <div className={`pnl-card pnl-profit ${report.profit < 0 ? 'negative' : ''}`}>
              <div className="pnl-card-icon">{report.profit < 0 ? '📉' : '📈'}</div>
              <div className="pnl-card-value">{formatMoney(report.profit)}</div>
              <div className="pnl-card-label">Прибыль</div>
              <div className="pnl-card-sub">Доходы минус расходы</div>
            </div>
            <div className={`pnl-card pnl-margin ${report.margin < 0 ? 'negative' : ''}`}>
              <div className="pnl-card-icon">🎯</div>
              <div className="pnl-card-value">{report.margin.toFixed(1)}%</div>
              <div className="pnl-card-label">Маржа</div>
              <div className="pnl-card-sub">Прибыль / доходы</div>
            </div>
          </div>

          {!report.has_data && (
            <div className="pnl-empty-note">
              <EmptyState
                icon="🗂️"
                title="Пока нет проводок за период"
                description="Отчёт показывает нулевые значения. Доходы и расходы появятся здесь после внесения данных."
              />
            </div>
          )}

          <div className="pnl-tables">
            <CategoryTable
              title="Доходы по статьям"
              icon="💵"
              lines={report.revenue_by_category}
              count={report.income_count}
              total={report.revenue}
              emptyHint="Статьи доходов ещё не заведены"
            />
            <CategoryTable
              title="Расходы по статьям"
              icon="🧾"
              lines={report.expenses_by_category}
              count={report.expense_count}
              total={report.expenses}
              emptyHint="Статьи расходов ещё не заведены"
            />
          </div>
        </>
      ) : null}
    </div>
  );
}

export default PnlPage;
