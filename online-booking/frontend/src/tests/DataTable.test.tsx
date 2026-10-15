import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import DataTable, { type FitColumnDef } from '../components/common/DataTable';

interface Row {
  name: string;
  phone: string;
}

const columns: FitColumnDef<Row>[] = [
  {
    id: 'name',
    header: 'Имя',
    accessorFn: (r) => r.name,
    cell: ({ row }) => row.original.name,
    meta: { minWidth: 100, label: 'Имя' },
  },
  {
    id: 'phone',
    header: 'Телефон',
    accessorFn: (r) => r.phone,
    cell: ({ row }) => row.original.phone,
    meta: { minWidth: 110, label: 'Телефон' },
  },
];

const data: Row[] = [
  { name: 'Анна Иванова', phone: '+7 (999) 111-22-33' },
  { name: 'Петр', phone: '+7 (999) 000-00-00' },
];

const TABLE = 'test-datatable';

beforeEach(() => {
  localStorage.clear();
});

describe('DataTable', () => {
  it('renders headers and rows', () => {
    render(<DataTable tableId={TABLE} columns={columns} data={data} />);
    expect(screen.getByText('Имя')).toBeTruthy();
    expect(screen.getByText('Анна Иванова')).toBeTruthy();
    expect(screen.getAllByRole('row')).toHaveLength(3); // header + 2
  });

  it('exposes data-row-id for bell deep-links', () => {
    const { container } = render(
      <DataTable tableId={TABLE} columns={columns} data={data} rowId={(r) => r.phone} />,
    );
    const rows = container.querySelectorAll('tbody tr[data-row-id]');
    expect(rows).toHaveLength(2);
    expect(rows[0].getAttribute('data-row-id')).toBe('+7 (999) 111-22-33');
  });

  it('hides a column via the Столбцы menu and persists it', () => {
    render(<DataTable tableId={TABLE} columns={columns} data={data} />);
    fireEvent.click(screen.getByText('☰ Столбцы'));
    fireEvent.click(screen.getByLabelText('Телефон'));
    expect(screen.queryByText('+7 (999) 111-22-33')).toBeNull();
    expect(JSON.parse(localStorage.getItem(`colvis:${TABLE}`)!)).toMatchObject({
      phone: false,
    });
  });

  it('reset restores hidden columns', () => {
    render(<DataTable tableId={TABLE} columns={columns} data={data} />);
    fireEvent.click(screen.getByText('☰ Столбцы'));
    fireEvent.click(screen.getByLabelText('Телефон'));
    fireEvent.click(screen.getByText('↺ Сбросить layout'));
    expect(screen.getByText('+7 (999) 111-22-33')).toBeTruthy();
  });

  it('applies stored widths instead of breaking layout', () => {
    localStorage.setItem(`colwidths:${TABLE}`, JSON.stringify({ name: 250 }));
    render(<DataTable tableId={TABLE} columns={columns} data={data} />);
    const th = screen.getByText('Имя').closest('th')!;
    expect(th.style.width).toBe('250px');
  });

  it('closes the columns menu on outside click and on Escape', () => {
    render(
      <div>
        <button>outside</button>
        <DataTable tableId={TABLE} columns={columns} data={data} />
      </div>,
    );
    fireEvent.click(screen.getByText('☰ Столбцы'));
    expect(screen.getByLabelText('Телефон')).toBeTruthy();
    fireEvent.pointerDown(document.body);
    expect(screen.queryByLabelText('Телефон')).toBeNull();

    fireEvent.click(screen.getByText('☰ Столбцы'));
    expect(screen.getByLabelText('Телефон')).toBeTruthy();
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(screen.queryByLabelText('Телефон')).toBeNull();
  });

  it('pins non-resizable columns and hides their handle', () => {
    const cols: FitColumnDef<Row>[] = [
      {
        id: 'check',
        header: '✓',
        cell: () => null,
        meta: { defaultWidth: 48, hideable: false, resizable: false },
      },
      ...columns,
    ];
    render(<DataTable tableId={TABLE} columns={cols} data={data} />);
    const th = screen.getByText('✓').closest('th')!;
    expect(th.style.width).toBe('48px');
    expect(th.querySelector('.col-resizer')).toBeNull();
  });
});
