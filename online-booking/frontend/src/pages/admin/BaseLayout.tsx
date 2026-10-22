import { useState, useEffect, useRef, useCallback, type ReactNode } from 'react';
import { Outlet, Link, useNavigate, useLocation } from 'react-router-dom';
import {
  adminApi,
  authApi,
  billingApi,
  cabinetApi,
  reviewsApi,
  type BillingSummary,
} from '../../api/client';
import {
  Breadcrumb,
  KeyboardShortcutsHint,
  NotificationBell,
  SupportModal,
} from '../../components/common';
import { getCookie, decodeJwtPayload, getUserRole, clearAuthCookies } from '../../utils/cookies';
import { allowMasterDraftEntry } from '../../utils/masterDraftEntry';
import { getImpersonation, stopImpersonation } from '../../utils/impersonation';
import { SUPER_PREFIX } from '../../utils/section';
import { APP_VERSION } from '../../constants';
import './AdminLayout.css';

export interface BaseNavItem {
  path: string;
  label: string;
  /** Visible in the shell, but the section only unlocks after activation. */
  locked?: boolean;
}

interface BaseLayoutProps {
  navItems: BaseNavItem[];
  layoutTitle: string;
  userRole: string;
  userFallbackName: string;
  /** Extra root class for section theming (e.g. "super-layout"). */
  themeClass?: string;
  /** Inactive master preview: keep cabinet links/bell on the client side. */
  draftMode?: boolean;
  /** Optional page-wide status notice (draft activation banner). */
  notice?: ReactNode;
}

interface LayoutUser {
  id: number;
  name: string;
}

function formatBalance(value: number): string {
  return `${Number(value ?? 0).toLocaleString('ru-RU', {
    minimumFractionDigits: Number.isInteger(Number(value ?? 0)) ? 0 : 2,
    maximumFractionDigits: 2,
  })} ₽`;
}

const TARIFF_LABELS: Record<string, string> = {
  trial: 'Триал',
  basic: 'Базовый',
  pro: 'Профи',
  business: 'Бизнес',
};

function getLayoutUser(fallbackName: string): LayoutUser | null {
  const token = getCookie('access_token');
  if (!token) return null;
  const payload = decodeJwtPayload(token);
  if (!payload?.sub) return null;
  // Full display name: `name` may already carry the surname ("set_names"
  // writes «Имя Фамилия»), tokens minted since 1.79.3 also ship last_name —
  // append it only when it is not there yet. Older sessions (no claim) show
  // the name as-is until the next login.
  const name = payload.name || '';
  const lastName = payload.last_name || '';
  const fullName = lastName && !name.includes(lastName) ? `${name} ${lastName}`.trim() : name;
  return {
    id: parseInt(payload.sub, 10),
    name: fullName || fallbackName,
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
  draftMode = false,
  notice,
}: BaseLayoutProps) {
  const navigate = useNavigate();
  const location = useLocation();
  const [user, setUser] = useState<LayoutUser | null>(null);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [impersonatedName, setImpersonatedName] = useState<string | null>(null);
  const [unread, setUnread] = useState(0);
  const [supportOpen, setSupportOpen] = useState(false);

  const bellLink = draftMode
    ? '/cabinet/notifications'
    : location.pathname.startsWith(SUPER_PREFIX)
      ? `${SUPER_PREFIX}/notifications`
      : location.pathname.startsWith('/admin')
        ? '/admin/notifications'
        : '/cabinet/notifications';

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
    // Role-first: clients must not hammer the panel counter (401 + refresh
    // storm on every poll) — and vice versa. Section decides for dual-role
    // masters (panel badge in panel, cabinet badge in cabinet).
    const inCabinetSection = window.location.pathname.startsWith('/cabinet');
    const role = getUserRole();
    const counters =
      role === 'CLIENT' || inCabinetSection
        ? [cabinetApi.notificationsUnread]
        : [adminApi.getNotificationsUnread, cabinetApi.notificationsUnread];
    for (const fetch of counters) {
      try {
        const { data } = await fetch();
        failStreak.current = 0;
        if (mountedRef.current) setUnread(data.unread || 0);
        return;
      } catch {
        /* next scope */
      }
    }
    /* logged out, dead token or dead backend — hide badge */
    if (mountedRef.current) setUnread(0);
    failStreak.current += 1;
    if (failStreak.current >= 3 && timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
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
    const sync = () => {
      setUser(getLayoutUser(userFallbackName));
      setImpersonatedName(getImpersonation()?.masterName ?? null);
    };
    sync();
    // A profile name change re-mints the token — re-read it in place.
    window.addEventListener('auth:user-updated', sync);
    return () => window.removeEventListener('auth:user-updated', sync);
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

  // Lock page scroll while the mobile drawer is open and close it on Esc.
  useEffect(() => {
    if (!mobileMenuOpen) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setMobileMenuOpen(false);
    };
    window.addEventListener('keydown', onKey);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener('keydown', onKey);
    };
  }, [mobileMenuOpen]);

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

  // Dual-role switch: masters move between their panel and the client
  // cabinet; plain clients open the master profile draft and self-activate.
  const role = getUserRole();
  const inCabinet = location.pathname.startsWith('/cabinet');
  const inMasterSection =
    location.pathname.startsWith('/admin') && !location.pathname.startsWith(SUPER_PREFIX);

  const isActive = (path: string) => location.pathname === path;

  // Master meta for the sidebar: tariff badge + live rating.
  const [masterMeta, setMasterMeta] = useState<{
    tariff: string;
    trialEnds: string | null;
    rating: number | null;
    reviews: number;
  } | null>(null);
  const [masterBalance, setMasterBalance] = useState<{
    due: number;
    credit: number;
    net: number;
    prepaidUntil: string | null;
  } | null>(null);

  const applyBalance = useCallback((summary: BillingSummary) => {
    setMasterBalance({
      due: summary.balance.due,
      credit: summary.balance.credit,
      net: summary.balance.net,
      prepaidUntil: summary.prepaid_until ?? null,
    });
    setMasterMeta((prev) => (prev && summary.tariff ? { ...prev, tariff: summary.tariff } : prev));
  }, []);

  useEffect(() => {
    if (role !== 'MASTER' || !inMasterSection) {
      setMasterBalance(null);
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const { data } = await adminApi.getProfile();
        if (!data.profile_id) return;
        let rating: number | null = null;
        let reviews = 0;
        try {
          const avg = await reviewsApi.getAverage(data.profile_id);
          rating = avg.data.average_rating ?? null;
          reviews = avg.data.review_count ?? 0;
        } catch {
          /* rating stays hidden */
        }
        if (!cancelled) {
          setMasterMeta({
            tariff: data.tariff || 'trial',
            trialEnds: data.trial_ends_at ?? null,
            rating,
            reviews,
          });
        }
        try {
          const billing = await billingApi.my();
          if (!cancelled) applyBalance(billing.data);
        } catch {
          /* balance stays hidden; the billing page has the full picture */
        }
      } catch {
        /* sidebar works without meta */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [role, inMasterSection, applyBalance]);

  // BillingPage dispatches the full summary after every load/payment so the
  // sidebar does not need another expensive read-model request.
  useEffect(() => {
    const onBilling = (event: Event) => {
      const detail = (event as CustomEvent<BillingSummary>).detail;
      if (detail?.balance) applyBalance(detail);
    };
    window.addEventListener('billing:updated', onBilling);
    return () => window.removeEventListener('billing:updated', onBilling);
  }, [applyBalance]);

  // Drag-to-reorder nav (order persists per section in localStorage).
  const navSection = draftMode
    ? 'master-draft'
    : location.pathname.startsWith(SUPER_PREFIX)
      ? 'super'
      : location.pathname.startsWith('/cabinet')
        ? 'cabinet'
        : 'admin';
  const [navOrder, setNavOrder] = useState<string[] | null>(null);
  const dragFrom = useRef<number | null>(null);
  const [dropAt, setDropAt] = useState<number | null>(null);
  useEffect(() => {
    try {
      const raw = localStorage.getItem(`navorder:${navSection}`);
      setNavOrder(raw ? (JSON.parse(raw) as string[]) : null);
    } catch {
      setNavOrder(null);
    }
  }, [navSection]);
  const orderedNav = navOrder
    ? [...navItems].sort((a, b) => {
        const ia = navOrder.indexOf(a.path);
        const ib = navOrder.indexOf(b.path);
        return (ia === -1 ? 999 : ia) - (ib === -1 ? 999 : ib);
      })
    : navItems;
  const persistOrder = (paths: string[]) => {
    setNavOrder(paths);
    try {
      localStorage.setItem(`navorder:${navSection}`, JSON.stringify(paths));
    } catch {
      /* ignore */
    }
  };

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
        type="button"
        className={`hamburger-btn${mobileMenuOpen ? ' active' : ''}`}
        onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
        aria-label={mobileMenuOpen ? 'Закрыть меню' : 'Открыть меню'}
        aria-expanded={mobileMenuOpen}
        aria-controls="app-sidebar"
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
        id="app-sidebar"
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
              scope={bellLink === '/cabinet/notifications' ? 'cabinet' : 'panel'}
              onRead={refreshUnread}
            />
          </div>
          {user && !sidebarCollapsed && <p className="sidebar-user">👤 {user.name}</p>}
          {masterMeta && !sidebarCollapsed && (
            <div className="sidebar-master-meta">
              <span
                className="tariff-badge"
                title={
                  masterMeta.tariff === 'trial' && masterMeta.trialEnds
                    ? `Пробный период до ${new Date(masterMeta.trialEnds).toLocaleDateString('ru-RU')}`
                    : `Тариф «${TARIFF_LABELS[masterMeta.tariff] ?? masterMeta.tariff}»`
                }
              >
                💎 {TARIFF_LABELS[masterMeta.tariff] ?? masterMeta.tariff}
              </span>
              {masterMeta.rating !== null && (
                <Link
                  to="/admin/profile#reviews"
                  className="rating-badge"
                  title="Мои отзывы и оценки — открыть"
                >
                  ★ {masterMeta.rating.toFixed(1)}
                  {masterMeta.reviews > 0 ? ` (${masterMeta.reviews})` : ''}
                </Link>
              )}
            </div>
          )}
          {role === 'MASTER' && inMasterSection && masterBalance && !sidebarCollapsed && (
            <Link
              to="/admin/billing"
              className={`sidebar-balance ${
                masterBalance.net < 0
                  ? 'sidebar-balance-negative'
                  : masterBalance.net > 0
                    ? 'sidebar-balance-positive'
                    : ''
              }`}
              title={
                masterBalance.prepaidUntil
                  ? `Предоплачено до ${new Date(masterBalance.prepaidUntil).toLocaleDateString('ru-RU')}. К оплате: ${formatBalance(masterBalance.due)} · Баланс и бонусы: ${formatBalance(masterBalance.credit)}`
                  : `К оплате: ${formatBalance(masterBalance.due)} · Баланс и бонусы: ${formatBalance(masterBalance.credit)}`
              }
            >
              <span className="sidebar-balance-label">Баланс</span>
              <strong>{formatBalance(masterBalance.net)}</strong>
            </Link>
          )}
        </div>
        <nav className="sidebar-nav">
          {orderedNav.map((item, idx) => (
            <Link
              key={item.path}
              to={item.path}
              state={draftMode ? { fromClient: true } : undefined}
              draggable={!item.locked}
              onDragStart={() => {
                if (!item.locked) dragFrom.current = idx;
              }}
              onDragOver={(e) => {
                if (item.locked) return;
                e.preventDefault();
                setDropAt(idx);
              }}
              onDrop={(e) => {
                e.preventDefault();
                const from = dragFrom.current;
                dragFrom.current = null;
                setDropAt(null);
                if (from === null || from === idx || item.locked) return;
                const paths = orderedNav.map((n) => n.path);
                const [moved] = paths.splice(from, 1);
                paths.splice(idx, 0, moved);
                persistOrder(paths);
              }}
              onDragEnd={() => {
                dragFrom.current = null;
                setDropAt(null);
              }}
              className={`nav-item ${isActive(item.path) ? 'active' : ''}${item.locked ? ' nav-item-locked' : ''}${dropAt === idx ? ' nav-drop-target' : ''}`}
              onClick={() => setMobileMenuOpen(false)}
              title={
                item.locked
                  ? 'Доступно после активации кабинета мастера'
                  : sidebarCollapsed
                    ? item.label
                    : 'Потяните, чтобы поменять порядок'
              }
            >
              <span className="nav-icon">{item.label.split(' ')[0]}</span>
              {!sidebarCollapsed && (
                <>
                  <span className="nav-label">{item.label.split(' ').slice(1).join(' ')}</span>
                  {item.locked && (
                    <span className="nav-lock" aria-hidden="true">
                      🔒
                    </span>
                  )}
                </>
              )}
            </Link>
          ))}
        </nav>
        <div className="sidebar-footer">
          {(draftMode || (role === 'MASTER' && inMasterSection)) && (
            <button
              className="btn btn-ghost"
              onClick={() => navigate('/cabinet')}
              title={
                draftMode
                  ? 'Вернуться в кабинет клиента'
                  : 'Записаться к другому мастеру как клиент'
              }
            >
              <span className="nav-icon">👤</span>
              {!sidebarCollapsed && <span className="nav-label">Кабинет клиента</span>}
            </button>
          )}
          {role === 'MASTER' && inCabinet && (
            <button
              className="btn btn-ghost"
              onClick={() => navigate('/admin/dashboard')}
              title="Вернуться в панель мастера"
            >
              <span className="nav-icon">💼</span>
              {!sidebarCollapsed && <span className="nav-label">Панель мастера</span>}
            </button>
          )}
          {role === 'CLIENT' && inCabinet && (
            <button
              className="btn btn-ghost"
              onClick={() => {
                allowMasterDraftEntry();
                navigate('/admin/become-master', { state: { fromClient: true } });
              }}
              title="Открыть неактивный кабинет мастера и заполнить профиль"
            >
              <span className="nav-icon">✨</span>
              {!sidebarCollapsed && <span className="nav-label">Стать мастером</span>}
            </button>
          )}
          {(role === 'CLIENT' || role === 'MASTER') &&
            !location.pathname.startsWith(SUPER_PREFIX) && (
              <button
                className="btn btn-ghost"
                onClick={() => setSupportOpen(true)}
                title="Написать в поддержку"
                aria-haspopup="dialog"
              >
                <span className="nav-icon">💬</span>
                {!sidebarCollapsed && <span className="nav-label">Связаться с поддержкой</span>}
              </button>
            )}
          <button className="btn btn-ghost btn-logout" onClick={handleLogout} title="Выйти">
            <span className="nav-icon">⏻</span>
            {!sidebarCollapsed && <span className="nav-label">Выйти</span>}
          </button>
          {!sidebarCollapsed && (
            <div className="sidebar-version" title="Версия интерфейса (для проверки обновлений)">
              v{APP_VERSION}
            </div>
          )}
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
        {!draftMode && breadcrumbs.length > 0 && <Breadcrumb items={breadcrumbs} />}
        <div className="main-content">
          {notice}
          <Outlet />
        </div>
      </main>

      <SupportModal open={supportOpen} onClose={() => setSupportOpen(false)} />

      <KeyboardShortcutsHint />
    </div>
  );
}

export default BaseLayout;
