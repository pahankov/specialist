import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import RoleSwitch from '../components/common/RoleSwitch';

describe('RoleSwitch', () => {
  it('highlights the active choice and switches on click', () => {
    const onChange = vi.fn();
    const { rerender } = render(<RoleSwitch value="client" onChange={onChange} />);
    const buttons = screen.getAllByRole('button');
    expect(buttons).toHaveLength(2);
    expect(buttons[0].getAttribute('aria-pressed')).toBe('true');

    fireEvent.click(buttons[1]);
    expect(onChange).toHaveBeenCalledWith('master');

    rerender(<RoleSwitch value="master" onChange={onChange} />);
    expect(screen.getAllByRole('button')[1].getAttribute('aria-pressed')).toBe('true');
  });

  it('uses custom labels', () => {
    render(
      <RoleSwitch
        value="client"
        onChange={() => undefined}
        labels={{ client: 'Войти как клиент', master: 'Войти как мастер' }}
      />,
    );
    expect(screen.getByText('Войти как клиент')).toBeTruthy();
    expect(screen.getByText('Войти как мастер')).toBeTruthy();
  });
});
