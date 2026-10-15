import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import Stars from '../components/reviews/Stars';

describe('Stars', () => {
  it('paints a fractional fill for 4.8', () => {
    render(<Stars value={4.8} />);
    expect(screen.getByRole('img', { name: 'Оценка 4.8 из 5' })).toBeInTheDocument();
  });

  it('clamps out-of-range values', () => {
    const { container } = render(<Stars value={9} />);
    expect(container.textContent).toContain('★★★★★');
  });
});
