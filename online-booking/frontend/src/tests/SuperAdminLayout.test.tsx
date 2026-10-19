import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import SuperAdminLayout from '../pages/admin/SuperAdminLayout';

function adminCookie() {
  const payload = btoa(JSON.stringify({ sub: '1', name: 'Boss', is_admin: true }))
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
    .replace(/=+$/, '');
  document.cookie = `access_token=h.${payload}.s; path=/`;
}

describe('SuperAdminLayout', () => {
  beforeEach(() => {
    document.cookie = 'access_token=; path=/; max-age=0';
    adminCookie();
  });

  it('renders its own nav under /super, not /admin', () => {
    render(
      <MemoryRouter initialEntries={['/super/masters']}>
        <Routes>
          <Route path="/super" element={<SuperAdminLayout />}>
            <Route path="masters" element={<div>child</div>} />
          </Route>
        </Routes>
      </MemoryRouter>,
    );
    expect(screen.getByText('🛡️ Суперпанель')).toBeInTheDocument();
    const mastersLink = screen.getByText('Мастера').closest('a');
    expect(mastersLink?.getAttribute('href')).toBe('/super/masters');
    const profileLink = screen.getByText(/Профиль/).closest('a');
    expect(profileLink?.getAttribute('href')).toBe('/super/profile');
    expect(screen.queryByText('Мои услуги')).not.toBeInTheDocument();
  });

  function renderLayout() {
    render(
      <MemoryRouter initialEntries={['/super/masters']}>
        <Routes>
          <Route path="/super" element={<SuperAdminLayout />}>
            <Route path="masters" element={<div>child</div>} />
          </Route>
        </Routes>
      </MemoryRouter>,
    );
  }

  function cookieWith(claims: Record<string, unknown>) {
    document.cookie = 'access_token=; path=/; max-age=0';
    const payload = btoa(JSON.stringify(claims))
      .replace(/\+/g, '-')
      .replace(/\//g, '_')
      .replace(/=+$/, '');
    document.cookie = `access_token=h.${payload}.s; path=/`;
  }

  it('appends last_name when the token name is a bare first name', () => {
    cookieWith({ sub: '1', name: 'Pavel', last_name: 'Khankov', is_admin: true });
    renderLayout();
    expect(screen.getByText('👤 Pavel Khankov')).toBeInTheDocument();
  });

  it('never doubles the surname (name already carries it)', () => {
    cookieWith({ sub: '1', name: 'Pavel Khankov', last_name: 'Khankov', is_admin: true });
    renderLayout();
    expect(screen.getByText('👤 Pavel Khankov')).toBeInTheDocument();
  });
});
