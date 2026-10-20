import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import MasterDraftLayout from '../pages/admin/MasterDraftLayout';

const NAV = [
  { path: '/admin/become-master', label: '👤 Профиль' },
  { path: '/admin/become-master/dashboard', label: '📊 Обзор', locked: true },
  { path: '/admin/become-master/schedule', label: '🕐 Расписание', locked: true },
];

function authCookie() {
  const payload = btoa(JSON.stringify({ sub: '7', name: 'Client', role: 'CLIENT' }))
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
    .replace(/=+$/, '');
  document.cookie = `access_token=h.${payload}.s; path=/`;
}

describe('MasterDraftLayout', () => {
  beforeEach(() => {
    document.cookie = 'access_token=; path=/; max-age=0';
    authCookie();
  });

  it('renders the real master shell with an inactive status, not the client cabinet', () => {
    render(
      <MemoryRouter initialEntries={['/admin/become-master']}>
        <Routes>
          <Route path="/admin/become-master" element={<MasterDraftLayout navItems={NAV} />}>
            <Route index element={<div>draft profile</div>} />
          </Route>
        </Routes>
      </MemoryRouter>,
    );

    expect(screen.getByText('🍬 Мастерская')).toBeInTheDocument();
    expect(screen.getByText('Мастер · неактивен')).toBeInTheDocument();
    expect(screen.getByText('Кабинет мастера неактивен')).toBeInTheDocument();
    expect(screen.getByText('draft profile')).toBeInTheDocument();
    expect(screen.queryByText('💅 Кабинет')).not.toBeInTheDocument();
  });

  it('shows all master sections, marks locked ones and keeps the client switch', () => {
    render(
      <MemoryRouter initialEntries={['/admin/become-master']}>
        <Routes>
          <Route path="/admin/become-master" element={<MasterDraftLayout navItems={NAV} />}>
            <Route index element={<div>draft profile</div>} />
          </Route>
        </Routes>
      </MemoryRouter>,
    );

    const profile = screen.getByText('Профиль').closest('a');
    const dashboard = screen.getByText('Обзор').closest('a');
    const schedule = screen.getByText('Расписание').closest('a');
    expect(profile?.className).not.toContain('nav-item-locked');
    expect(dashboard?.className).toContain('nav-item-locked');
    expect(schedule?.className).toContain('nav-item-locked');
    expect(dashboard?.getAttribute('href')).toBe('/admin/become-master/dashboard');

    expect(screen.getByTitle('Вернуться в кабинет клиента')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Кабинет клиента' })).toHaveAttribute(
      'href',
      '/cabinet',
    );
  });

  it('opens a locked section page instead of bouncing to the client cabinet', () => {
    render(
      <MemoryRouter initialEntries={['/admin/become-master']}>
        <Routes>
          <Route path="/admin/become-master" element={<MasterDraftLayout navItems={NAV} />}>
            <Route index element={<div>draft profile</div>} />
            <Route path="dashboard" element={<div>locked dashboard</div>} />
          </Route>
        </Routes>
      </MemoryRouter>,
    );

    fireEvent.click(screen.getByText('Обзор'));
    expect(screen.getByText('locked dashboard')).toBeInTheDocument();
  });
});
