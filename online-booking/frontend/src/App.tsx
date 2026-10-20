import { Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { Toaster } from 'sonner';
import { HomePage, BookingPage, PrivacyPolicyPage, OfferPage } from './pages/public';
import VkCallbackPage from './pages/public/VkCallbackPage';
import YandexCallbackPage from './pages/public/YandexCallbackPage';
import {
  AdminLayout,
  MasterDraftLayout,
  MasterDraftLockedPage,
  DashboardPage,
  AppointmentsPage,
  ServicesPage,
  ClientsPage,
  SchedulePage,
} from './pages/admin';
import SuperAdminLayout from './pages/admin/SuperAdminLayout';
import MastersPage from './pages/admin/MastersPage';
import MasterDetailPage from './pages/admin/MasterDetailPage';
import LogsPage from './pages/admin/LogsPage';
import RevenuePage from './pages/admin/RevenuePage';
import NotificationsPage from './pages/admin/NotificationsPage';
import ProfilePage from './pages/admin/ProfilePage';
import CabinetPage from './pages/cabinet/CabinetPage';
import CabinetBookPage from './pages/cabinet/CabinetBookPage';
import CabinetNotificationsPage from './pages/cabinet/CabinetNotificationsPage';
import ClientCouponsPage from './pages/cabinet/ClientCouponsPage';
import ClientProfilePage from './pages/cabinet/ClientProfilePage';
import ClientLayout from './pages/cabinet/ClientLayout';
import ErrorBoundary from './components/ErrorBoundary';
import { getCookie, decodeJwtPayload, getUserRole } from './utils/cookies';
import { ADMIN_PREFIX, SUPER_PREFIX } from './utils/section';
import './App.css';

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
    // Guests bounce to home, which opens login and continues to `from`.
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
  return <>{children}</>;
}

/** Client cabinet: CLIENT and MASTER roles (dual-role: masters book as clients). */
function RequireClient({ children }: { children: React.ReactNode }) {
  const location = useLocation();
  if (!getIsAuthenticated()) {
    // Guests bounce to home, which opens login and continues to `from`.
    return <Navigate to="/" replace state={{ from: location.pathname + location.search }} />;
  }
  if (getIsAdmin()) {
    return <Navigate to={`${SUPER_PREFIX}/dashboard`} replace />;
  }
  return <>{children}</>;
}

// Master navigation (section /admin). Profile sits second: settings and
// own reviews at hand, daily flow (records/services/schedule) right below.
// Order is draggable per user (persisted), this is only the fresh default.
const masterNavItems = [
  { path: `${ADMIN_PREFIX}/dashboard`, label: '📊 Обзор' },
  { path: `${ADMIN_PREFIX}/profile`, label: '👤 Профиль' },
  { path: `${ADMIN_PREFIX}/appointments`, label: '📅 Мои записи' },
  { path: `${ADMIN_PREFIX}/services`, label: '💇 Мои услуги' },
  { path: `${ADMIN_PREFIX}/clients`, label: '👥 Клиенты' },
  { path: `${ADMIN_PREFIX}/schedule`, label: '🕐 Расписание' },
  { path: `${ADMIN_PREFIX}/notifications`, label: '🔔 Уведомления' },
];

// Same master cabinet, but only the profile works until self-activation.
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

function App() {
  const location = useLocation();
  const isAdminRoute =
    location.pathname.startsWith(ADMIN_PREFIX) || location.pathname.startsWith(SUPER_PREFIX);

  return (
    <ErrorBoundary>
      <div className={`app ${isAdminRoute ? 'admin-app' : 'public-app'}`}>
        <Routes>
          {/* Public routes */}
          <Route path="/" element={<HomePage />} />
          <Route path="/booking" element={<BookingPage />} />
          <Route path="/privacy" element={<PrivacyPolicyPage />} />
          <Route path="/offer" element={<OfferPage />} />
          {/* VK ID OAuth landing: VK redirects here with ?code&device_id&state,
              the code is exchanged server-side, then we land by role. */}
          <Route path="/auth/vk/callback" element={<VkCallbackPage />} />
          {/* Yandex OAuth landing: Yandex redirects here with ?code&state,
              the code is exchanged server-side, then we land by role. */}
          <Route path="/auth/yandex/callback" element={<YandexCallbackPage />} />
          <Route
            path="/cabinet"
            element={
              <RequireClient>
                <ClientLayout />
              </RequireClient>
            }
          >
            <Route index element={<CabinetPage />} />
            <Route path="book" element={<CabinetBookPage />} />
            <Route path="coupons" element={<ClientCouponsPage />} />
            <Route path="notifications" element={<CabinetNotificationsPage />} />
            <Route path="profile" element={<ClientProfilePage />} />
            {/* Old bookmarks go to the real (inactive) master shell. */}
            <Route path="become-master" element={<Navigate to={DRAFT_MASTER_ROOT} replace />} />
          </Route>

          {/* Inactive master cabinet: full master shell for a CLIENT who is
              filling the draft. The backend role stays CLIENT until activation. */}
          <Route
            path={DRAFT_MASTER_ROOT}
            element={
              <RequireMasterDraft>
                <MasterDraftLayout navItems={masterDraftNavItems} />
              </RequireMasterDraft>
            }
          >
            <Route index element={<ProfilePage mode="draft" />} />
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

          {/* Master section */}
          <Route
            path="/admin"
            element={
              <RequireMasterSection>
                <AdminLayout navItems={masterNavItems} />
              </RequireMasterSection>
            }
          >
            <Route index element={<Navigate to="/admin/dashboard" replace />} />
            <Route path="dashboard" element={<DashboardPage />} />
            <Route path="appointments" element={<AppointmentsPage />} />
            <Route path="services" element={<ServicesPage />} />
            <Route path="clients" element={<ClientsPage />} />
            <Route path="schedule" element={<SchedulePage />} />
            <Route path="notifications" element={<NotificationsPage />} />
            <Route path="profile" element={<ProfilePage />} />
          </Route>

          {/* Superadmin section: own layout, own nav, own URLs */}
          <Route
            path="/super"
            element={
              <RequireSuperAdmin>
                <SuperAdminLayout />
              </RequireSuperAdmin>
            }
          >
            <Route index element={<Navigate to="/super/dashboard" replace />} />
            <Route path="dashboard" element={<DashboardPage />} />
            <Route path="revenue" element={<RevenuePage />} />
            <Route path="masters" element={<MastersPage />} />
            <Route path="masters/:id" element={<MasterDetailPage />} />
            <Route path="appointments" element={<AppointmentsPage />} />
            <Route path="clients" element={<ClientsPage />} />
            <Route path="schedule" element={<SchedulePage />} />
            <Route path="notifications" element={<NotificationsPage />} />
            <Route path="logs" element={<LogsPage />} />
            {/* Super's own profile: bindings + password + contacts (slim
                variant of the master profile — master blocks stay off). */}
            <Route path="profile" element={<ProfilePage />} />
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
