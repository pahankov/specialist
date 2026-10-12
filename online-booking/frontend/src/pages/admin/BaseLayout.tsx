import { useState, useEffect, useRef, useCallback } from 'react';
import { Outlet, Link, useNavigate, useLocation } from 'react-router-dom';
import { adminApi, authApi, cabinetApi } from '../../api/client';
import { Breadcrumb, KeyboardShortcutsHint, NotificationBell } from '../../components/common';
import { getCookie, decodeJwtPayload, clearAuthCookies } from '../../utils/cookies';
import { getImpersonation, stopImpersonation } from '../../utils/impersonation';
import { SUPER_PREFIX } from '../../utils/section';
import './AdminLayout.css';

export interface BaseNavItem {
  path: string;
  label: string;
}

interface BaseLayoutProps {
  navItems: BaseNavItem[];
  layoutTitle: string;
  userRole: string;
  userFallbackName: string;
  /** Extra root class for section theming (e.g. "super-layout"). */
  themeClass?: string;
}

interface LayoutUser {
  id: number;
  name: string;
}

function getLayoutUser(fallbackName: string): LayoutUser | null {
  const token = getCookie('access_token');
  if (!token) return null;
  const payload = decodeJwtPayload(token);
  if (!payload?.sub) return null;
  return {
    id: parseInt(payload.sub, 10),
    name: payload.name || fallbackName,
  };
}

/**
 * Shared sidebar shell for /admin and /super sections.
 * Sections differ only by nav items, title/role labels and theme class —
 * DOM structure and classNames are identical so section CSS keeps working.
 */
function BaseLayout({
  navItems,
  layoutTitle,
  userRole,
  userFallbackName,
  themeClass = '',
}: BaseLayoutProps) {
  const navigate = useNavigate();
  const location = useLocation();
  const [user, setUser] = useState<LayoutUser | null>(null);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [impersonatedName, setImpersonatedName] = useState<string | null>(null);
  const [unread, setUnread] = useState(0);

  const bellLink = location.pathname.startsWith(SUPER_PREFIX)
    ? `${SUPER_PREFIX}/notifications`
    : location.pathname.startsWith('/admin')
      ? '/admin/notifications'
      : '/cabinet';

  // Bell badge: panels hit the admin counter, cabinet the client one.
  // No token → skip quietly. After 3 straight failures the interval stops
  // (dead backend / dead session must not spam the console); the next route
  // change restarts it.
  const failStreak = useRef(0);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const mountedRef = useRef(true);
  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  const refreshUnread = useCallback(async () => {
    if (!getCookie('access_token')) {
      if (mountedRef.current) setUnread(0);
      return;
    }
    try {
      const { data } = await adminApi.getNotificationsUnread();
      failStreak.current = 0;
      if (mountedRef.current) setUnread(data.unread || 0);
      return;
    } catch {
      /* not a panel token — try the cabinet counter */
    }
    try {
      const { data } = await cabinetApi.notificationsUnread();
      failStreak.current = 0;
      if (mountedRef.current) setUnread(data.unread || 0);
    } catch {
      /* logged out, dead token or dead backend — hide badge */
      if (mountedRef.current) setUnread(0);
      failStreak.current += 1;
      if (failStreak.current >= 3 && timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    }
  }, []);

  useEffect(() => {
    failStreak.current = 0;
    refreshUnread();
    if (timerRef.current) clearInterval(timerRef.current);
    timerRef.current = setInterval(refreshUnread, 30000);
    return () => {
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    };
  }, [location.pathname, refreshUnread]);

  const exitImpersonation = () => {
    stopImpersonation();
    setImpersonatedName(null);
    // Admin token restored → hard-land in the superadmin section
    window.location.href = `${SUPER_PREFIX}/masters`;
  };

  useEffect(() => {
    setUser(getLayoutUser(userFallbackName));
    setImpersonatedName(getImpersonation()?.masterName ?? null);
  }, [userFallbackName]);

  // Close mobile menu on route change
  useEffect(() => {
    setMobileMenuOpen(false);
  }, [location.pathname]);

  // Close mobile menu on resize to desktop
  useEffect(() => {
    const handleResize = () => {
      if (window.innerWidth > 1024) {
        setMobileMenuOpen(false);
      }
    };
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  const handleLogout = async () => {
    // Revoke server-side (httpOnly refresh cookie) first, then drop the
    // readable access token.
    try {
      await authApi.logout();
    } catch {
      /* ignore: proceed with local cleanup anyway */
    }

    clearAuthCookies();
    navigate('/');
  };

  const isActive = (path: string) => location.pathname === path;

  // Build breadcrumb from current path
  const breadcrumbs = location.pathname
    .split('/')
    .filter(Boolean)
    .map((segment, index, array) => {
      const path = '/' + array.slice(0, index + 1).join('/');
      const label = segment.charAt(0).toUpperCase() + segment.slice(1);
      return { label, path };
    });

  return (
    <div className={`admin-layout ${themeClass}`.trim()}>
      {/* Mobile hamburger button */}
      <button
        className="hamburger-btn"
        onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
        aria-label="Меню"
      >
        <span className="hamburger-line"></span>
        <span className="hamburger-line"></span>
        <span className="hamburger-line"></span>
      </button>

      {/* Mobile overlay */}
      {mobileMenuOpen && (
        <div className="sidebar-overlay" onClick={() => setMobileMenuOpen(false)} />
      )}

      <aside
        className={`admin-sidebar ${sidebarCollapsed ? 'collapsed' : ''} ${mobileMenuOpen ? 'mobile-open' : ''}`}
      >
        <div className="sidebar-header">
          <div className="sidebar-header-top">
            <button
              className="collapse-btn"
              onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
              aria-label="Свернуть меню"
              title={sidebarCollapsed ? 'Развернуть меню' : 'Свернуть меню'}
            >
              {sidebarCollapsed ? '›' : '‹'}
            </button>
            <div className="sidebar-brand">
              <h2>{layoutTitle}</h2>
              {!sidebarCollapsed && <p className="sidebar-subtitle">{userRole}</p>}
            </div>
            <NotificationBell
              unread={unread}
              bellLink={bellLink}
              scope={bellLink === '/cabinet' ? 'cabinet' : 'panel'}
              onRead={refreshUnread}
            />
          </div>
          {user && !sidebarCollapsed && <p className="sidebar-user">👤 {user.name}</p>}
        </div>
        <nav className="sidebar-nav">
          {navItems.map((item) => (
            <Link
              key={item.path}
              to={item.path}
              className={`nav-item ${isActive(item.path) ? 'active' : ''}`}
              onClick={() => setMobileMenuOpen(false)}
              title={sidebarCollapsed ? item.label : undefined}
            >
              <span className="nav-icon">{item.label.split(' ')[0]}</span>
              {!sidebarCollapsed && (
                <span className="nav-label">{item.label.split(' ').slice(1).join(' ')}</span>
              )}
            </Link>
          ))}
        </nav>
        <div className="sidebar-footer">
          <button className="btn btn-ghost btn-logout" onClick={handleLogout} title="Выйти">
            <span className="nav-icon">🚪</span>
            {!sidebarCollapsed && <span className="nav-label">Выйти</span>}
          </button>
        </div>
      </aside>

      <main className="admin-main">
        {impersonatedName !== null && (
          <div className="impersonation-banner" role="alert">
            <span>
              👁 Вы смотрите глазами мастера <strong>{impersonatedName}</strong> (режим поддержки)
            </span>
            <button className="btn btn-sm btn-primary" onClick={exitImpersonation}>
              Выйти из режима
            </button>
          </div>
        )}
        {breadcrumbs.length > 0 && <Breadcrumb items={breadcrumbs} />}
        <div className="main-content">
          <Outlet />
        </div>
      </main>

      <KeyboardShortcutsHint />
    </div>
  );
}

export default BaseLayout;
