import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { useState } from 'react';
import RecipientPicker from '../components/common/RecipientPicker';

const ITEMS = [
  { id: 1, name: 'Анна', sub: '+79990001111' },
  { id: 2, name: 'Мария', sub: '+79990002222' },
  { id: 3, name: 'Ольга', sub: '+79990003333' },
];

function Harness({ onChange }: { onChange: (s: Set<number>) => void }) {
  const [selected, setSelected] = useState<Set<number>>(new Set());
  return (
    <RecipientPicker
      items={ITEMS}
      selected={selected}
      onChange={(next) => {
        setSelected(next);
        onChange(next);
      }}
    />
  );
}

describe('RecipientPicker', () => {
  it('filters by name search', () => {
    render(<Harness onChange={vi.fn()} />);
    fireEvent.change(screen.getByLabelText('Поиск получателей'), { target: { value: 'мар' } });
    expect(screen.getByText('Мария')).toBeInTheDocument();
    expect(screen.queryByText('Анна')).not.toBeInTheDocument();
  });

  it('header checkbox selects all visible', () => {
    const onChange = vi.fn();
    render(<Harness onChange={onChange} />);
    fireEvent.click(screen.getByTitle('Выбрать всех видимых'));
    expect(onChange).toHaveBeenCalledWith(new Set([1, 2, 3]));
    expect(screen.getByText('Выбрано: 3')).toBeInTheDocument();
  });

  it('row checkbox toggles one recipient', () => {
    render(<Harness onChange={vi.fn()} />);
    const boxes = screen.getAllByRole('checkbox');
    fireEvent.click(boxes[1]); // first row (header is boxes[0])
    expect(screen.getByText('Выбрано: 1')).toBeInTheDocument();
  });
});
