import { useEffect, Suspense, lazy } from 'react';
import { Routes, Route, Navigate, useLocation, useNavigate } from 'react-router-dom';
import { Toaster, toast } from 'sonner';
import {
  HomePage,
  BookingPage,
  PrivacyPolicyPage,
  OfferPage,
  MasterRulesPage,
  ReferralPage,
} from './pages/public';
import VkCallbackPage from './pages/public/VkCallbackPage';
import YandexCallbackPage from './pages/public/YandexCallbackPage';
import { AdminLayout, MasterDraftLayout, MasterDraftLockedPage } from './pages/admin';
import SuperAdminLayout from './pages/admin/SuperAdminLayout';
import { PageLoader } from './lib/lazy-pages';
import ErrorBoundary from './components/ErrorBoundary';
import { getCookie, decodeJwtPayload, getUserRole } from './utils/cookies';
import { allowMasterDraftEntry, isMasterDraftEntryAllowed } from './utils/masterDraftEntry';
import { ADMIN_PREFIX, SUPER_PREFIX } from './utils/section';
import { referralApi } from './api/client';
import './App.css';

// ─── Lazy-loaded pages (code-split) ────────────────────────────
const DashboardPage = lazy(() => import('./pages/admin/DashboardPage'));
const AppointmentsPage = lazy(() => import('./pages/admin/AppointmentsPage'));
const ServicesPage = lazy(() => import('./pages/admin/ServicesPage'));
const ClientsPage = lazy(() => import('./pages/admin/ClientsPage'));
const SchedulePage = lazy(() => import('./pages/admin/SchedulePage'));
const BillingPage = lazy(() => import('./pages/admin/BillingPage'));
const SuperBillingPage = lazy(() => import('./pages/admin/SuperBillingPage'));
const MastersPage = lazy(() => import('./pages/admin/MastersPage'));
const MasterDetailPage = lazy(() => import('./pages/admin/MasterDetailPage'));
const LogsPage = lazy(() => import('./pages/admin/LogsPage'));
const RevenuePage = lazy(() => import('./pages/admin/RevenuePage'));
const NotificationsPage = lazy(() => import('./pages/admin/NotificationsPage'));
const ProfilePage = lazy(() => import('./pages/admin/ProfilePage'));

const CabinetPage = lazy(() => import('./pages/cabinet/CabinetPage'));
const CabinetBookPage = lazy(() => import('./pages/cabinet/CabinetBookPage'));
const CabinetNotificationsPage = lazy(() => import('./pages/cabinet/CabinetNotificationsPage'));
const ClientCouponsPage = lazy(() => import('./pages/cabinet/ClientCouponsPage'));
const ClientProfilePage = lazy(() => import('./pages/cabinet/ClientProfilePage'));
const ClientLayout = lazy(() => import('./pages/cabinet/ClientLayout'));

function getIsAuthenticated() {
  return getCookie('access_token') !== null;
}

function getIsAdmin() {
  const token = getCookie('access_token');
  if (!token) return false;
  try {
    return decodeJwtPayload(token)?.is_admin === true;
  } catch {
    return false;
  }
}

/** Superadmin section: non-admins are sent to their own home. */
function RequireSuperAdmin({ children }: { children: React.ReactNode }) {
  const location = useLocation();
  if (!getIsAuthenticated()) {
    return <Navigate to="/" replace state={{ from: location.pathname + location.search }} />;
  }
  if (!getIsAdmin()) {
    return <Navigate to={`${ADMIN_PREFIX}/dashboard`} replace />;
  }
  return <>{children}</>;
}

/** Master section: superadmins have their own section under /super,
    clients land on booking (no master UI for CLIENT role). */
function RequireMasterSection({ children }: { children: React.ReactNode }) {
  const location = useLocation();
  if (!getIsAuthenticated()) {
    return <Navigate to="/" replace state={{ from: location.pathname + location.search }} />;
  }
  if (getIsAdmin()) {
    return <Navigate to={`${SUPER_PREFIX}/dashboard`} replace />;
  }
  if (getUserRole() === 'CLIENT') {
    return <Navigate to="/cabinet" replace />;
  }
  return <>{children}</>;
}

/** Inactive master shell: accessible to CLIENTs filling the master draft.
    Active masters go straight to their real panel, admins to /super. */
function RequireMasterDraft({ children }: { children: React.ReactNode }) {
  const location = useLocation();
  if (!getIsAuthenticated()) {
    return <Navigate to="/" replace state={{ from: location.pathname + location.search }} />;
  }
  if (getIsAdmin()) {
    return <Navigate to={`${SUPER_PREFIX}/dashboard`} replace />;
  }
  const role = getUserRole();
  if (role === 'MASTER') {
    return <Navigate to={`${ADMIN_PREFIX}/profile`} replace />;
  }
  if (role !== 'CLIENT') {
    return <Navigate to="/cabinet" replace />;
  }
  if (!isMasterDraftEntryAllowed()) {
    return <Navigate to="/cabinet" replace />;
  }
  return <>{children}</>;
}

/** Legacy bookmark /cabinet/become-master: count it as explicit intent and
    replace the URL with the real draft shell. */
function LegacyMasterDraftEntry() {
  const navigate = useNavigate();
  useEffect(() => {
    allowMasterDraftEntry();
    navigate(DRAFT_MASTER_ROOT, { replace: true, state: { fromClient: true } });
  }, [navigate]);
  return null;
}

/** Client cabinet: CLIENT and MASTER roles (dual-role: masters book as clients). */
function RequireClient({ children }: { children: React.ReactNode }) {
  const location = useLocation();
  if (!getIsAuthenticated()) {
    return <Navigate to="/" replace state={{ from: location.pathname + location.search }} />;
  }
  if (getIsAdmin()) {
    return <Navigate to={`${SUPER_PREFIX}/dashboard`} replace />;
  }
  return <>{children}</>;
}

// Master navigation (section /admin). Profile sits second: settings and
// own reviews at hand, daily flow (records/services/schedule) right below.
const masterNavItems = [
  { path: `${ADMIN_PREFIX}/dashboard`, label: '📊 Обзор' },
  { path: `${ADMIN_PREFIX}/profile`, label: '👤 Профиль' },
  { path: `${ADMIN_PREFIX}/appointments`, label: '📅 Мои записи' },
  { path: `${ADMIN_PREFIX}/services`, label: '💇 Мои услуги' },
  { path: `${ADMIN_PREFIX}/clients`, label: '👥 Клиенты' },
  { path: `${ADMIN_PREFIX}/schedule`, label: '🕐 Расписание' },
  { path: `${ADMIN_PREFIX}/billing`, label: '💳 Тариф и оплата' },
  { path: `${ADMIN_PREFIX}/notifications`, label: '🔔 Уведомления' },
];

const DRAFT_MASTER_ROOT = `${ADMIN_PREFIX}/become-master`;
const masterDraftNavItems = [
  { path: DRAFT_MASTER_ROOT, label: '👤 Профиль' },
  { path: `${DRAFT_MASTER_ROOT}/dashboard`, label: '📊 Обзор', locked: true },
  { path: `${DRAFT_MASTER_ROOT}/appointments`, label: '📅 Мои записи', locked: true },
  { path: `${DRAFT_MASTER_ROOT}/services`, label: '💇 Мои услуги', locked: true },
  { path: `${DRAFT_MASTER_ROOT}/clients`, label: '👥 Клиенты', locked: true },
  { path: `${DRAFT_MASTER_ROOT}/schedule`, label: '🕐 Расписание', locked: true },
  { path: `${DRAFT_MASTER_ROOT}/notifications`, label: '🔔 Уведомления', locked: true },
];

const REFERRAL_CLICK_KEY = 'bs_referral_click';

function App() {
  const location = useLocation();
  const isAdminRoute =
    location.pathname.startsWith(ADMIN_PREFIX) || location.pathname.startsWith(SUPER_PREFIX);

  // A /r/<code> click stores a 60-day attribution token. The moment the
  // visitor is authenticated (any role), bind them to the inviting master.
  useEffect(() => {
    if (!getIsAuthenticated()) return;
    const raw = localStorage.getItem(REFERRAL_CLICK_KEY);
    if (!raw) return;
    localStorage.removeItem(REFERRAL_CLICK_KEY);
    try {
      const parsed = JSON.parse(raw) as { token?: string; at?: number };
      if (!parsed.token) return;
      if (parsed.at && Date.now() - parsed.at > 60 * 24 * 60 * 60 * 1000) return;
      referralApi
        .attribute(parsed.token)
        .then(({ data }) => {
          if (data.status === 'pending') {
            toast.success('Приглашение мастера сохранено');
          }
        })
        .catch((err: unknown) => {
          const status = (err as { response?: { status?: number } }).response?.status;
          if (!status || status === 401 || status === 429 || status >= 500) {
            localStorage.setItem(REFERRAL_CLICK_KEY, raw);
          }
        });
    } catch {
      /* malformed storage — ignore */
    }
  }, [location.pathname, location.search]);

  return (
    <ErrorBoundary>
      <div className={`app ${isAdminRoute ? 'admin-app' : 'public-app'}`}>
        <Routes>
          {/* Public routes (eager — loaded on first paint) */}
          <Route path="/" element={<HomePage />} />
          <Route path="/booking" element={<BookingPage />} />
          <Route path="/privacy" element={<PrivacyPolicyPage />} />
          <Route path="/offer" element={<OfferPage />} />
          <Route path="/master-rules" element={<MasterRulesPage />} />
          <Route path="/r/:code" element={<ReferralPage />} />
          <Route path="/ref/:code" element={<ReferralPage />} />
          <Route path="/auth/vk/callback" element={<VkCallbackPage />} />
          <Route path="/auth/yandex/callback" element={<YandexCallbackPage />} />

          {/* Client cabinet (lazy) */}
          <Route
            path="/cabinet"
            element={
              <RequireClient>
                <Suspense fallback={<PageLoader />}>
                  <ClientLayout />
                </Suspense>
              </RequireClient>
            }
          >
            <Route
              index
              element={
                <Suspense fallback={<PageLoader />}>
                  <CabinetPage />
                </Suspense>
              }
            />
            <Route
              path="book"
              element={
                <Suspense fallback={<PageLoader />}>
                  <CabinetBookPage />
                </Suspense>
              }
            />
            <Route
              path="coupons"
              element={
                <Suspense fallback={<PageLoader />}>
                  <ClientCouponsPage />
                </Suspense>
              }
            />
            <Route
              path="notifications"
              element={
                <Suspense fallback={<PageLoader />}>
                  <CabinetNotificationsPage />
                </Suspense>
              }
            />
            <Route
              path="profile"
              element={
                <Suspense fallback={<PageLoader />}>
                  <ClientProfilePage />
                </Suspense>
              }
            />
            <Route path="become-master" element={<LegacyMasterDraftEntry />} />
          </Route>

          {/* Inactive master cabinet (lazy) */}
          <Route
            path={DRAFT_MASTER_ROOT}
            element={
              <RequireMasterDraft>
                <Suspense fallback={<PageLoader />}>
                  <MasterDraftLayout navItems={masterDraftNavItems} />
                </Suspense>
              </RequireMasterDraft>
            }
          >
            <Route
              index
              element={
                <Suspense fallback={<PageLoader />}>
                  <ProfilePage mode="draft" />
                </Suspense>
              }
            />
            <Route path="dashboard" element={<MasterDraftLockedPage title="Обзор" />} />
            <Route path="appointments" element={<MasterDraftLockedPage title="Мои записи" />} />
            <Route path="services" element={<MasterDraftLockedPage title="Мои услуги" />} />
            <Route path="clients" element={<MasterDraftLockedPage title="Клиенты" />} />
            <Route path="schedule" element={<MasterDraftLockedPage title="Расписание" />} />
            <Route path="notifications" element={<MasterDraftLockedPage title="Уведомления" />} />
          </Route>

          {/* Logins happen via modal on home */}
          <Route path="/admin/login" element={<Navigate to="/" replace />} />
          <Route path="/super/login" element={<Navigate to="/" replace />} />

          {/* Master section (lazy pages) */}
          <Route
            path="/admin"
            element={
              <RequireMasterSection>
                <Suspense fallback={<PageLoader />}>
                  <AdminLayout navItems={masterNavItems} />
                </Suspense>
              </RequireMasterSection>
            }
          >
            <Route index element={<Navigate to="/admin/dashboard" replace />} />
            <Route
              path="dashboard"
              element={
                <Suspense fallback={<PageLoader />}>
                  <DashboardPage />
                </Suspense>
              }
            />
            <Route
              path="appointments"
              element={
                <Suspense fallback={<PageLoader />}>
                  <AppointmentsPage />
                </Suspense>
              }
            />
            <Route
              path="services"
              element={
                <Suspense fallback={<PageLoader />}>
                  <ServicesPage />
                </Suspense>
              }
            />
            <Route
              path="clients"
              element={
                <Suspense fallback={<PageLoader />}>
                  <ClientsPage />
                </Suspense>
              }
            />
            <Route
              path="schedule"
              element={
                <Suspense fallback={<PageLoader />}>
                  <SchedulePage />
                </Suspense>
              }
            />
            <Route
              path="billing"
              element={
                <Suspense fallback={<PageLoader />}>
                  <BillingPage />
                </Suspense>
              }
            />
            <Route
              path="notifications"
              element={
                <Suspense fallback={<PageLoader />}>
                  <NotificationsPage />
                </Suspense>
              }
            />
            <Route
              path="profile"
              element={
                <Suspense fallback={<PageLoader />}>
                  <ProfilePage />
                </Suspense>
              }
            />
          </Route>

          {/* Superadmin section (lazy pages) */}
          <Route
            path="/super"
            element={
              <RequireSuperAdmin>
                <Suspense fallback={<PageLoader />}>
                  <SuperAdminLayout />
                </Suspense>
              </RequireSuperAdmin>
            }
          >
            <Route index element={<Navigate to="/super/dashboard" replace />} />
            <Route
              path="dashboard"
              element={
                <Suspense fallback={<PageLoader />}>
                  <DashboardPage />
                </Suspense>
              }
            />
            <Route
              path="revenue"
              element={
                <Suspense fallback={<PageLoader />}>
                  <RevenuePage />
                </Suspense>
              }
            />
            <Route
              path="billing"
              element={
                <Suspense fallback={<PageLoader />}>
                  <SuperBillingPage />
                </Suspense>
              }
            />
            <Route
              path="masters"
              element={
                <Suspense fallback={<PageLoader />}>
                  <MastersPage />
                </Suspense>
              }
            />
            <Route
              path="masters/:id"
              element={
                <Suspense fallback={<PageLoader />}>
                  <MasterDetailPage />
                </Suspense>
              }
            />
            <Route
              path="appointments"
              element={
                <Suspense fallback={<PageLoader />}>
                  <AppointmentsPage />
                </Suspense>
              }
            />
            <Route
              path="clients"
              element={
                <Suspense fallback={<PageLoader />}>
                  <ClientsPage />
                </Suspense>
              }
            />
            <Route
              path="schedule"
              element={
                <Suspense fallback={<PageLoader />}>
                  <SchedulePage />
                </Suspense>
              }
            />
            <Route
              path="notifications"
              element={
                <Suspense fallback={<PageLoader />}>
                  <NotificationsPage />
                </Suspense>
              }
            />
            <Route
              path="logs"
              element={
                <Suspense fallback={<PageLoader />}>
                  <LogsPage />
                </Suspense>
              }
            />
            <Route
              path="profile"
              element={
                <Suspense fallback={<PageLoader />}>
                  <ProfilePage />
                </Suspense>
              }
            />
          </Route>

          {/* Catch all */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </div>
      <Toaster position="top-right" richColors />
    </ErrorBoundary>
  );
}

export default App;
