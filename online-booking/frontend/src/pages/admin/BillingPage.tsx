import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { toast } from 'sonner';
import { billingApi, type BillingSummary } from '../../api/client';
import { ConfirmDialog, EmptyState, Skeleton } from '../../components/common';
import { getApiErrorMessage } from '../../utils/apiError';
import './BillingPage.css';

function money(value: number | undefined | null): string {
  return `${Number(value ?? 0).toLocaleString('ru-RU', {
    minimumFractionDigits: Number.isInteger(Number(value ?? 0)) ? 0 : 2,
    maximumFractionDigits: 2,
  })} ₽`;
}

function date(value?: string | null): string {
  if (!value) return '—';
  return new Date(value).toLocaleDateString('ru-RU', {
    day: '2-digit',
    month: 'long',
    year: 'numeric',
  });
}

function statusTone(status: string): string {
  if (status === 'active') return 'ok';
  if (status === 'trial') return 'trial';
  if (status === 'readonly') return 'warn';
  return 'danger';
}

function BillingPage() {
  const [data, setData] = useState<BillingSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [prepaying, setPrepaying] = useState<1 | 12 | null>(null);
  const [cancelOpen, setCancelOpen] = useState(false);
  const [cancelling, setCancelling] = useState(false);

  const applyBilling = useCallback((next: BillingSummary) => {
    setData(next);
    // Keep the sidebar balance in sync without an extra API round-trip.
    window.dispatchEvent(new CustomEvent('billing:updated', { detail: next }));
  }, []);

  const load = useCallback(
    async (quiet = false) => {
      if (quiet) setRefreshing(true);
      else setLoading(true);
      try {
        const response = await billingApi.my();
        applyBilling(response.data);
      } catch (err) {
        toast.error(getApiErrorMessage(err, 'Не удалось загрузить тариф и оплату'));
      } finally {
        setLoading(false);
        setRefreshing(false);
      }
    },
    [applyBilling],
  );

  useEffect(() => {
    load();
  }, [load]);

  const requestPrepay = async (months: 1 | 12) => {
    setPrepaying(months);
    try {
      const response = await billingApi.prepay(months);
      applyBilling(response.data.billing);
      toast.success(
        months === 12 ? 'Счёт на годовую предоплату создан' : 'Счёт на предоплату создан',
      );
      document.getElementById('invoices')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    } catch (err) {
      toast.error(getApiErrorMessage(err, 'Не удалось создать счёт на предоплату'));
    } finally {
      setPrepaying(null);
    }
  };

  const cancelPrepay = async () => {
    setCancelling(true);
    try {
      const response = await billingApi.cancelPrepay();
      applyBilling(response.data.billing);
      setCancelOpen(false);
      toast.success('Заявка на предоплату отменена');
    } catch (err) {
      toast.error(getApiErrorMessage(err, 'Не удалось отменить заявку на предоплату'));
    } finally {
      setCancelling(false);
    }
  };

  const copyReferral = async () => {
    if (!data) return;
    const url = `${window.location.origin}${data.referral_link}`;
    try {
      await navigator.clipboard.writeText(url);
      toast.success('Ссылка скопирована');
    } catch {
      toast.error(`Скопируйте вручную: ${url}`);
    }
  };

  if (loading) {
    return (
      <div className="billing-page">
        <div className="page-header">
          <h1>💳 Тариф и оплата</h1>
        </div>
        <Skeleton rows={4} height="90px" />
      </div>
    );
  }

  if (!data) {
    return (
      <div className="billing-page">
        <div className="page-header">
          <h1>💳 Тариф и оплата</h1>
        </div>
        <EmptyState icon="💳" title="Данные биллинга недоступны" />
      </div>
    );
  }

  const bonus = data.client_bonus;
  const bonusPercent = Math.min(100, (bonus.eligible_count / bonus.max_count) * 100);
  const referralPercent = Math.min(
    100,
    (data.referral.qualified_count / data.referral.max_count) * 100,
  );
  const openInvoices = data.invoices.filter((invoice) => invoice.status === 'open');
  const paidInvoices = data.invoices.filter((invoice) => invoice.status === 'paid');

  return (
    <div className="billing-page">
      <div className="page-header billing-header">
        <div>
          <h1>💳 Тариф и оплата</h1>
          <p className="billing-subtitle">
            14 дней бесплатно, затем 250 ₽ × 2 месяца и 500 ₽/мес. Годовая предоплата — −20%.
            Комиссия с записей — 0%.
          </p>
        </div>
        <div className="billing-header-actions">
          <Link to="/master-rules" className="btn btn-ghost">
            Правила
          </Link>
          <button className="btn btn-secondary" onClick={() => load(true)} disabled={refreshing}>
            {refreshing ? 'Обновляем…' : '↻ Обновить'}
          </button>
        </div>
      </div>

      {data.is_blocked && (
        <div className={`billing-banner billing-banner-${statusTone(data.access_status)}`}>
          <div>
            <strong>{data.access_status_label}</strong>
            {data.access_status === 'readonly' && (
              <span>
                {' '}
                — счёт просрочен. Кабинет доступен только для чтения, публичная ссылка скрыта.
              </span>
            )}
            {data.access_status === 'paused' && (
              <span>
                {' '}
                — кабинет приостановлен из-за неоплаты более 30 дней. Оплата разблокирует его в тот
                же день.
              </span>
            )}
          </div>
          <a href="#invoices" className="btn btn-sm btn-primary">
            К счетам
          </a>
        </div>
      )}

      <div className="billing-cards">
        <div className="card billing-status-card">
          <div className="billing-card-label">Доступ</div>
          <div className={`billing-status billing-status-${statusTone(data.access_status)}`}>
            {data.access_status_label}
          </div>
          {data.access_status === 'trial' && (
            <p className="billing-muted">
              Пробный период до {date(data.trial_ends_at)} · осталось {data.trial_days_left} дн.
            </p>
          )}
          {data.prepaid_until ? (
            <p className="billing-muted billing-prepaid-label">
              Предоплачено до {date(data.prepaid_until)}
            </p>
          ) : (
            data.access_status !== 'trial' && (
              <p className="billing-muted">
                Следующий счёт: {date(data.next_payment_at)} на {money(data.next_payment_amount)}
              </p>
            )
          )}
        </div>

        <div className="card billing-balance-card">
          <div className="billing-card-label">Баланс</div>
          <div className="billing-balance-row">
            <span>К оплате</span>
            <strong>{money(data.balance.due)}</strong>
          </div>
          <div className="billing-balance-row billing-balance-credit">
            <span>Кредиты и бонусы</span>
            <strong>{money(data.balance.credit)}</strong>
          </div>
        </div>

        <div className="card billing-status-card">
          <div className="billing-card-label">Оплата</div>
          <div className="billing-payment-title">Вручную</div>
          <p className="billing-muted">
            После перевода администратор подтвердит платёж и отметит счёт оплаченным.
          </p>
        </div>
      </div>

      <div className="billing-grid">
        <section className="card billing-section">
          <div className="billing-section-head">
            <div>
              <h2>🎁 Бонус за клиентов</h2>
              <p className="billing-muted">
                25 ₽ за клиента, максимум 10 клиентов и 250 ₽. Засчитываются только записи,
                созданные клиентом из кабинета.
              </p>
            </div>
            <span className={`billing-pill ${bonus.review_flag ? 'danger' : 'ok'}`}>
              {bonus.status === 'pending'
                ? 'Проверка на 21-й день'
                : bonus.status === 'credited'
                  ? 'Начислен'
                  : bonus.status === 'blocked'
                    ? 'Заблокирован'
                    : 'Не начислен'}
            </span>
          </div>
          <div className="billing-progress-row">
            <span>
              {bonus.eligible_count} из {bonus.max_count} клиентов
            </span>
            <strong>{money(bonus.amount)}</strong>
          </div>
          <div className="billing-progress">
            <div style={{ width: `${bonusPercent}%` }} />
          </div>
          <p className="billing-muted">
            {bonus.status === 'pending'
              ? `Итог подведём ${date(bonus.evaluation_at)}. Записей-кандидатов: ${bonus.total_candidates}.`
              : bonus.status === 'credited'
                ? `Бонус зачтён в счёт оплаты или сохранён как кредит на 90 дней.`
                : 'Бонус не начислен.'}
          </p>
          {bonus.review_flag && (
            <div className="billing-note danger">
              Более 30% визитов не подтверждены клиентами ({bonus.unconfirmed_count} из{' '}
              {bonus.prompted_count}). Бонус за текущий месяц сохранён, но будущие бонусы
              приостановлены до проверки администратором.
            </div>
          )}
        </section>

        <section className="card billing-section">
          <div className="billing-section-head">
            <div>
              <h2>🤝 Пригласите коллегу</h2>
              <p className="billing-muted">
                125 ₽ за мастера, максимум 2 приглашения и 250 ₽. Коллега должен прийти по ссылке,
                подключить другую соцсеть и собрать 7 записей за первые 14 дней.
              </p>
            </div>
            <span className="billing-pill ok">
              {data.referral.qualified_count} / {data.referral.max_count}
            </span>
          </div>
          <div className="billing-progress">
            <div style={{ width: `${referralPercent}%` }} />
          </div>
          <div className="billing-referral-link">
            <input
              readOnly
              value={`${window.location.origin}${data.referral_link}`}
              aria-label="Реферальная ссылка"
              onFocus={(event) => event.currentTarget.select()}
            />
            <button className="btn btn-sm btn-primary" onClick={copyReferral}>
              Копировать
            </button>
          </div>
          <p className="billing-muted">
            Ссылка действует {data.referral.click_days} дней. Бонус —{' '}
            {money(data.referral.bonus_total)} из {money(data.referral.max_amount)}.
          </p>
          {data.referrals.length > 0 && (
            <div className="billing-referrals">
              {data.referrals.map((referral) => (
                <div className="billing-referral-row" key={referral.id}>
                  <div>
                    <strong>{referral.referred_name}</strong>
                    <div className="billing-muted">
                      {referral.qualified_count} из {referral.required_count} записей ·{' '}
                      {referral.status_label}
                      {referral.reject_reason ? ` · ${referral.reject_reason}` : ''}
                    </div>
                  </div>
                  <span
                    className={`billing-pill ${referral.status === 'qualified' ? 'ok' : referral.status === 'rejected' ? 'danger' : 'trial'}`}
                  >
                    {money(referral.amount)}
                  </span>
                </div>
              ))}
            </div>
          )}
        </section>
      </div>

      <section className="card billing-section" id="invoices">
        <div className="billing-section-head">
          <div>
            <h2>🧾 Счета</h2>
            <p className="billing-muted">
              Счёт выставляется на 15-й день, затем каждые 30 дней. Неоплаченный счёт переводит
              кабинет в режим чтения.
            </p>
          </div>
        </div>

        <div className="billing-prepay">
          <div className="billing-prepay-head">
            <div>
              <h3>Оплатить заранее</h3>
              <p className="billing-muted">
                Предоплата зачисляется на баланс и автоматически закрывает следующие счета. Цена
                года — минус 20% от суммы следующих 12 месячных счетов.
              </p>
            </div>
            <Link to="/master-rules" className="billing-link">
              Как это работает →
            </Link>
          </div>
          <div className="billing-prepay-grid">
            <button
              type="button"
              className="billing-prepay-option"
              onClick={() => requestPrepay(1)}
              disabled={!data.prepay.available || prepaying !== null}
            >
              <span className="billing-prepay-kicker">1 месяц</span>
              <strong>{money(data.prepay.month.amount)}</strong>
              <span className="billing-prepay-hint">До {date(data.prepay.month.ends_at)}</span>
            </button>
            <button
              type="button"
              className="billing-prepay-option billing-prepay-option-year"
              onClick={() => requestPrepay(12)}
              disabled={!data.prepay.available || prepaying !== null}
            >
              <span className="billing-prepay-kicker">
                12 месяцев <span className="billing-prepay-discount">−20%</span>
              </span>
              <span className="billing-prepay-price">
                <s>{money(data.prepay.year.base_amount)}</s>
                <strong>{money(data.prepay.year.amount)}</strong>
              </span>
              <span className="billing-prepay-hint">
                Выгода {money(data.prepay.year.base_amount - data.prepay.year.amount)} · до{' '}
                {date(data.prepay.year.ends_at)}
              </span>
            </button>
          </div>
          {prepaying !== null && <p className="billing-muted">Создаём счёт на предоплату…</p>}
          {!data.prepay.available && data.prepay.reason && (
            <div className="billing-note">
              {data.prepay.reason}
              {data.prepay.open_invoice_id && (
                <>
                  {' '}
                  <a href="#invoices" className="billing-link">
                    Перейти к счёту
                  </a>
                  {' · '}
                  <button
                    type="button"
                    className="billing-link billing-link-button"
                    onClick={() => setCancelOpen(true)}
                  >
                    Отменить заявку
                  </button>
                </>
              )}
            </div>
          )}
        </div>

        {openInvoices.length === 0 && paidInvoices.length === 0 ? (
          <EmptyState icon="🧾" title="Счетов пока нет" />
        ) : (
          <div className="billing-table-wrap">
            <table className="billing-table">
              <thead>
                <tr>
                  <th>Период</th>
                  <th>Сумма</th>
                  <th>Зачтено</th>
                  <th>К оплате</th>
                  <th>Срок</th>
                  <th>Статус</th>
                </tr>
              </thead>
              <tbody>
                {[...openInvoices, ...paidInvoices].map((invoice) => (
                  <tr key={invoice.id}>
                    <td>
                      {invoice.is_prepay
                        ? `Предоплата · ${invoice.months ?? 1} мес.`
                        : `Месяц ${invoice.period_index}`}
                    </td>
                    <td>
                      {money(invoice.amount)}
                      {invoice.is_prepay && invoice.base_amount ? (
                        <span className="billing-muted billing-invoice-base">
                          вместо {money(invoice.base_amount)}
                        </span>
                      ) : null}
                    </td>
                    <td>{money(invoice.credits_applied)}</td>
                    <td>
                      <strong>{money(invoice.due_amount)}</strong>
                    </td>
                    <td>{date(invoice.due_at)}</td>
                    <td>
                      <span className={`billing-pill ${invoice.status === 'paid' ? 'ok' : 'warn'}`}>
                        {invoice.status_label}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <div className="billing-instructions">
          <strong>Как оплатить:</strong> {data.payment_instructions}
        </div>
        <p className="billing-muted">
          Нужна помощь с оплатой? Напишите в{' '}
          <Link to="/admin/notifications" className="billing-link">
            уведомления
          </Link>{' '}
          или администратору.
        </p>
      </section>

      <section className="card billing-section">
        <h2>💎 Кредиты и бонусы</h2>
        <p className="billing-muted">
          Кредиты сначала закрывают старые счета, остаток переносится на 90 дней.
        </p>
        {data.credits.length === 0 ? (
          <EmptyState icon="💎" title="Кредитов пока нет" />
        ) : (
          <div className="billing-credit-list">
            {data.credits.map((credit) => (
              <div className="billing-credit-row" key={credit.id}>
                <div>
                  <strong>{credit.source_label}</strong>
                  <div className="billing-muted">
                    {credit.note || 'Начисление'} · до {date(credit.expires_at)}
                  </div>
                </div>
                <div className="billing-credit-value">
                  <strong>{money(credit.remaining)}</strong>
                  <span className="billing-muted">из {money(credit.amount)}</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      <p className="billing-muted billing-footnote">
        Тариф: 14 дней бесплатно · 15-й день — 250 ₽ · 45-й день — 250 ₽ · с 75-го дня — 500 ₽/мес.
        Годовая предоплата — минус 20%. Комиссия с записей — 0%.{' '}
        <Link to="/master-rules" className="billing-link">
          Правила тарифов, бонусов и рефералов
        </Link>
        .
      </p>

      <ConfirmDialog
        open={cancelOpen}
        onClose={() => {
          if (!cancelling) setCancelOpen(false);
        }}
        title="Отменить заявку на предоплату?"
        message="Неоплаченный счёт будет отменён, и можно будет создать новую заявку. Если оплата уже отправлена, сначала свяжитесь с поддержкой."
        confirmLabel={cancelling ? 'Отменяем…' : 'Да, отменить'}
        onConfirm={cancelPrepay}
        confirmDisabled={cancelling}
        danger
      />
    </div>
  );
}

export default BillingPage;
