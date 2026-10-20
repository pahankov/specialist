import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import ClientLayout from '../pages/cabinet/ClientLayout';

function authCookie(role: 'CLIENT' | 'MASTER') {
  const payload = btoa(
    JSON.stringify({ sub: '7', name: role === 'MASTER' ? 'Master' : 'Client', role }),
  )
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
    .replace(/=+$/, '');
  document.cookie = `access_token=h.${payload}.s; path=/`;
}

describe('ClientLayout', () => {
  beforeEach(() => {
    document.cookie = 'access_token=; path=/; max-age=0';
    authCookie('CLIENT');
  });

  it('renders its own nav under /cabinet, not master items', () => {
    render(
      <MemoryRouter initialEntries={['/cabinet']}>
        <Routes>
          <Route path="/cabinet" element={<ClientLayout />}>
            <Route index element={<div>child</div>} />
          </Route>
        </Routes>
      </MemoryRouter>,
    );
    expect(screen.getByText('💅 Кабинет')).toBeInTheDocument();
    const cabinetLink = screen.getByText('Мои записи').closest('a');
    expect(cabinetLink?.getAttribute('href')).toBe('/cabinet');
    const bookingLink = screen.getByText('Записаться').closest('a');
    expect(bookingLink?.getAttribute('href')).toBe('/cabinet/book');
    const profileLink = screen.getByText('Профиль').closest('a');
    expect(profileLink?.getAttribute('href')).toBe('/cabinet/profile');
    expect(screen.queryByText('Мои услуги')).not.toBeInTheDocument();
    expect(screen.getByText('Клиент')).toBeInTheDocument();
  });

  it('keeps the master status when an activated master uses the client cabinet', () => {
    authCookie('MASTER');
    render(
      <MemoryRouter initialEntries={['/cabinet']}>
        <Routes>
          <Route path="/cabinet" element={<ClientLayout />}>
            <Route index element={<div>child</div>} />
          </Route>
        </Routes>
      </MemoryRouter>,
    );
    expect(screen.getByText('Мастер')).toBeInTheDocument();
  });
});
