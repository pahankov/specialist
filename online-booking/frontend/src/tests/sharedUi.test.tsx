import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import StatusBadge from '../components/common/StatusBadge';
import { statusLabels } from '../constants/statusLabels';
import { useAdminSort } from '../utils/useAdminSort';

function SortProbe() {
  const { sortKey, sortDir, toggleSort, sortArrow } = useAdminSort<'name' | 'no_show'>('probe');
  return (
    <div>
      <span data-testid="state">{`${sortKey ?? 'none'}:${sortDir}`}</span>
      <button onClick={() => toggleSort('name')}>sort-name{sortArrow('name')}</button>
    </div>
  );
}

describe('StatusBadge', () => {
  it('renders shared label with status class', () => {
    render(<StatusBadge status="pending" />);
    const el = screen.getByText(statusLabels.pending);
    expect(el.className).toContain('status-badge');
    expect(el.className).toContain('status-pending');
  });

  it('falls back to raw status for unknown values', () => {
    render(<StatusBadge status="weird" />);
    expect(screen.getByText('weird')).toBeInTheDocument();
  });
});

describe('useAdminSort', () => {
  it('cycles asc -> desc -> none', () => {
    render(<SortProbe />, { wrapper: MemoryRouter });
    const state = screen.getByTestId('state');
    const btn = screen.getByText(/sort-name/);
    expect(state.textContent).toBe('none:asc');
    fireEvent.click(btn);
    expect(state.textContent).toBe('name:asc');
    fireEvent.click(btn);
    expect(state.textContent).toBe('name:desc');
    fireEvent.click(btn);
    expect(state.textContent).toBe('none:asc');
  });
});
