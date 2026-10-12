import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import BackendImg from '../components/common/BackendImg';

describe('BackendImg', () => {
  it('renders the image when a src is given', () => {
    render(<BackendImg src="http://x/a.png" alt="A" className="thumb" />);
    expect(screen.getByRole('img', { name: 'A' })).toHaveAttribute(
      'src',
      'http://x/a.png',
    );
  });

  it('renders a placeholder without src', () => {
    render(<BackendImg src={null} alt="Missing" className="thumb" />);
    expect(screen.getByRole('img', { name: 'Missing' })).toHaveTextContent('🖼️');
  });

  it('falls back when the file is gone (no broken icon)', () => {
    render(<BackendImg src="http://x/gone.png" alt="Gone" className="thumb" />);
    fireEvent.error(screen.getByRole('img', { name: 'Gone' }));
    expect(screen.getByRole('img', { name: 'Gone' })).toHaveTextContent('🖼️');
  });
});
