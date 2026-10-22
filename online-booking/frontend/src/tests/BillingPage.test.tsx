import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { billingApi, type BillingSummary } from '../api/client';
import BillingPage from '../pages/admin/BillingPage';

vi.mock('../api/client', () => ({
  billingApi: {
    my: vi.fn(),
    prepay: vi.fn(),
    cancelPrepay: vi.fn(),
  },
}));
vi.mock('sonner', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

const mockedMy = vi.mocked(billingApi.my);
const mockedPrepay = vi.mocked(billingApi.prepay);
const mockedCancel = vi.mocked(billingApi.cancelPrepay);

function quote(months: number, amount: number, baseAmount: number, discount: number) {
  return {
    months,
    base_amount: baseAmount,
    amount,
    discount_percent: discount,
    starts_at: '2026-11-06T12:00:00+00:00',
    ends_at: '2026-12-06T12:00:00+00:00',
    period_index: 1,
    available: true,
    reason: null,
    open_invoice_id: null,
  };
}

function summary(overrides: Partial<BillingSummary> = {}): BillingSummary {
  return {
    master_id: 1,
    master_name: 'Анна',
    access_status: 'trial',
    access_status_label: 'Пробный период',
    is_blocked: false,
    trial_started_at: '2026-10-22T12:00:00+00:00',
    trial_ends_at: '2026-11-05T12:00:00+00:00',
    billing_started_at: '2026-10-22T12:00:00+00:00',
    trial_days_left: 14,
    review_flag: false,
    bonus_blocked_until: null,
    referral_code: 'ABC123',
    referral_link: 'https://beauty-specialist.ru/r/ABC123',
    next_payment_at: '2026-11-06T12:00:00+00:00',
    next_payment_amount: 250,
    prepaid_until: null,
    balance: { due: 0, credit: 0, net: 0 },
    prepay: {
      available: true,
      reason: null,
      open_invoice_id: null,
      month: quote(1, 250, 250, 0),
      year: quote(12, 4400, 5500, 20),
    },
    invoices: [],
    credits: [],
    client_bonus: {
      eligible_count: 0,
      max_count: 10,
      amount: 0,
      max_amount: 250,
      status: 'pending',
      total_candidates: 0,
      unconfirmed_count: 0,
      prompted_count: 0,
      unconfirmed_ratio: 0,
      review_flag: false,
      evaluated_at: null,
      evaluation_at: null,
    },
    referral: {
      qualified_count: 0,
      max_count: 2,
      bonus_total: 0,
      max_amount: 250,
      click_days: 60,
      credit_days: 90,
    },
    referrals: [],
    payment_instructions: 'Переведите сумму администратору.',
    ...overrides,
  };
}

describe('BillingPage prepayment', () => {
  beforeEach(() => {
    mockedMy.mockReset();
    mockedPrepay.mockReset();
    mockedCancel.mockReset();
    Element.prototype.scrollIntoView = vi.fn();
  });

  it('shows the annual price with a 20% discount and creates an invoice', async () => {
    const initial = summary();
    const updated = summary({
      invoices: [
        {
          id: 7,
          period_index: -1,
          amount: 4400,
          base_amount: 5500,
          credits_applied: 0,
          paid_amount: 0,
          due_amount: 4400,
          status: 'open',
          status_label: 'К оплате',
          kind: 'prepay_year',
          months: 12,
          is_prepay: true,
          issue_at: '2026-10-22T12:00:00+00:00',
          due_at: '2026-11-12T12:00:00+00:00',
          period_start: '2026-11-06T12:00:00+00:00',
          period_end: '2027-11-06T12:00:00+00:00',
        },
      ],
      prepay: {
        available: false,
        reason: 'Счёт на предоплату уже выставлен',
        open_invoice_id: 7,
        month: quote(1, 250, 250, 0),
        year: quote(12, 4400, 5500, 20),
      },
    });
    mockedMy.mockResolvedValue({ data: initial } as never);
    mockedPrepay.mockResolvedValue({
      data: { ok: true, invoice_id: 7, prepay: updated.prepay.year, billing: updated },
    } as never);

    render(
      <MemoryRouter>
        <BillingPage />
      </MemoryRouter>,
    );

    const yearButton = await screen.findByRole('button', { name: /12 месяцев/i });
    expect(yearButton).toHaveTextContent(/5.500/);
    expect(yearButton).toHaveTextContent(/4.400/);
    expect(yearButton).toHaveTextContent(/20%/);

    fireEvent.click(yearButton);

    await waitFor(() => expect(mockedPrepay).toHaveBeenCalledWith(12));
    expect(await screen.findByText('Предоплата · 12 мес.')).toBeInTheDocument();
    expect(screen.getByText(/Счёт на предоплату уже выставлен/)).toBeInTheDocument();

    const cancelled = summary({
      invoices: [
        {
          ...updated.invoices[0],
          status: 'void',
          status_label: 'Отменён',
          due_amount: 0,
        },
      ],
      prepay: {
        ...updated.prepay,
        available: true,
        reason: null,
        open_invoice_id: null,
      },
    });
    mockedCancel.mockResolvedValue({ data: { ok: true, billing: cancelled } } as never);

    fireEvent.click(screen.getByRole('button', { name: 'Отменить заявку' }));
    expect(await screen.findByText('Отменить заявку на предоплату?')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Да, отменить' }));

    await waitFor(() => expect(mockedCancel).toHaveBeenCalledTimes(1));
    await waitFor(() =>
      expect(screen.queryByText(/Счёт на предоплату уже выставлен/)).not.toBeInTheDocument(),
    );
    expect(screen.getByRole('button', { name: /12 месяцев/i })).toBeEnabled();
    expect(await screen.findByText('Счетов пока нет')).toBeInTheDocument();
  });

  it('disables prepayment while a monthly invoice is unpaid', async () => {
    mockedMy.mockResolvedValue({
      data: summary({
        prepay: {
          available: false,
          reason: 'Сначала оплатите текущий счёт',
          open_invoice_id: null,
          month: quote(1, 250, 250, 0),
          year: quote(12, 4400, 5500, 20),
        },
      }),
    } as never);

    render(
      <MemoryRouter>
        <BillingPage />
      </MemoryRouter>,
    );

    expect(await screen.findByText('Сначала оплатите текущий счёт')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /1 месяц/i })).toBeDisabled();
    expect(screen.getByRole('button', { name: /12 месяцев/i })).toBeDisabled();
  });
});
