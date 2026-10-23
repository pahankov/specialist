import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { superAdminApi } from '../api/client';
import type { PnlReport } from '../api/types';
import PnlPage from '../pages/admin/PnlPage';

vi.mock('../api/client', () => ({
  superAdminApi: {
    getPnlReport: vi.fn(),
  },
}));

const mockedReport = vi.mocked(superAdminApi.getPnlReport);

function report(overrides: Partial<PnlReport> = {}): PnlReport {
  return {
    date_from: '2026-10-01',
    date_to: '2026-10-24',
    currency: 'RUB',
    revenue: 0,
    expenses: 0,
    profit: 0,
    margin: 0,
    income_count: 0,
    expense_count: 0,
    has_data: false,
    revenue_by_category: [],
    expenses_by_category: [],
    ...overrides,
  };
}

function renderPage() {
  return render(
    <MemoryRouter>
      <PnlPage />
    </MemoryRouter>,
  );
}

function card(label: string) {
  return screen.getByText(label).closest('.pnl-card') as HTMLElement;
}

describe('PnlPage', () => {
  beforeEach(() => {
    mockedReport.mockReset();
  });

  it('renders zero placeholders when no entries exist yet', async () => {
    mockedReport.mockResolvedValue({ data: report() } as never);

    renderPage();

    expect(await screen.findByText('Пока нет проводок за период')).toBeInTheDocument();
    expect(within(card('Доходы')).getByText('0 ₽')).toBeInTheDocument();
    expect(within(card('Расходы')).getByText('0 ₽')).toBeInTheDocument();
    expect(within(card('Прибыль')).getByText('0 ₽')).toBeInTheDocument();
    expect(within(card('Маржа')).getByText('0.0%')).toBeInTheDocument();
    expect(screen.getByText(/01\.10\.2026 — 24\.10\.2026/)).toBeInTheDocument();
    expect(screen.getByText('Статьи доходов ещё не заведены')).toBeInTheDocument();
    expect(screen.getByText('Статьи расходов ещё не заведены')).toBeInTheDocument();
  });

  it('renders revenue, expenses, profit, margin and category breakdown', async () => {
    mockedReport.mockResolvedValue({
      data: report({
        revenue: 10000,
        expenses: 4000,
        profit: 6000,
        margin: 60,
        income_count: 3,
        expense_count: 2,
        has_data: true,
        revenue_by_category: [
          { category_id: 1, name: 'Услуги', amount: 9000, share: 90 },
          { category_id: 2, name: 'Товары', amount: 1000, share: 10 },
        ],
        expenses_by_category: [
          { category_id: 3, name: 'Аренда', amount: 2500, share: 62.5 },
          { category_id: 4, name: 'Материалы', amount: 1500, share: 37.5 },
        ],
      }),
    } as never);

    renderPage();

    await screen.findByText('Услуги');
    expect(screen.queryByText('Пока нет проводок за период')).not.toBeInTheDocument();
    expect(within(card('Доходы')).getByText('10 000 ₽')).toBeInTheDocument();
    expect(within(card('Расходы')).getByText('4 000 ₽')).toBeInTheDocument();
    expect(within(card('Прибыль')).getByText('6 000 ₽')).toBeInTheDocument();
    expect(within(card('Маржа')).getByText('60.0%')).toBeInTheDocument();
    expect(screen.getAllByText('3 операции')).toHaveLength(2);
    expect(screen.getAllByText('2 операции')).toHaveLength(2);
    expect(screen.getByText('Товары')).toBeInTheDocument();
    expect(screen.getByText('90.0%')).toBeInTheDocument();
    expect(screen.getByText('62.5%')).toBeInTheDocument();
  });

  it('shows a loss with a negative profit and margin', async () => {
    mockedReport.mockResolvedValue({
      data: report({
        revenue: 1000,
        expenses: 4000,
        profit: -3000,
        margin: -300,
        has_data: true,
      }),
    } as never);

    renderPage();

    await screen.findByText('Прибыль');
    expect(within(card('Прибыль')).getByText('−3 000 ₽')).toBeInTheDocument();
    expect(within(card('Маржа')).getByText('-300.0%')).toBeInTheDocument();
    expect(card('Прибыль')).toHaveClass('negative');
  });

  it('requests the selected period and resets to the current month', async () => {
    mockedReport.mockResolvedValue({ data: report() } as never);

    renderPage();
    await screen.findByText('Пока нет проводок за период');
    expect(mockedReport).toHaveBeenLastCalledWith({});

    fireEvent.change(screen.getByLabelText('Дата от'), {
      target: { value: '2026-01-01' },
    });

    await waitFor(() => expect(mockedReport).toHaveBeenLastCalledWith({ date_from: '2026-01-01' }));

    fireEvent.click(screen.getByRole('button', { name: 'Текущий месяц' }));

    await waitFor(() => expect(mockedReport).toHaveBeenLastCalledWith({}));
  });

  it('shows the backend error for an invalid period', async () => {
    mockedReport.mockRejectedValue({
      response: { status: 400, data: { detail: 'Дата начала позже даты окончания' } },
    });

    renderPage();

    expect(await screen.findByText('Дата начала позже даты окончания')).toBeInTheDocument();
  });
});
