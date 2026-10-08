import { Routes, Route, Navigate, useLocation } from 'react-router-dom'
import { Toaster } from 'sonner'
import { HomePage, BookingPage } from './pages/public'
import { AdminLayout, DashboardPage, AppointmentsPage, ServicesPage, ClientsPage, SchedulePage } from './pages/admin'
import SuperAdminLayout from './pages/admin/SuperAdminLayout'
import MastersPage from './pages/admin/MastersPage'
import MasterDetailPage from './pages/admin/MasterDetailPage'
import LogsPage from './pages/admin/LogsPage'
import RevenuePage from './pages/admin/RevenuePage'
import ErrorBoundary from './components/ErrorBoundary'
import { getCookie, decodeJwtPayload } from './utils/cookies'
import { ADMIN_PREFIX, SUPER_PREFIX } from './utils/section'
import './App.css'

function getIsAuthenticated() {
  return !!document.cookie.includes('access_token=')
}

function getIsAdmin() {
  const token = getCookie('access_token')
  if (!token) return false
  try {
    return decodeJwtPayload(token)?.is_admin === true
  } catch {
    return false
  }
}

/** Superadmin section: non-admins are sent to their own home. */
function RequireSuperAdmin({ children }: { children: React.ReactNode }) {
  if (!getIsAuthenticated()) {
    return <Navigate to="/" replace />
  }
  if (!getIsAdmin()) {
    return <Navigate to={`${ADMIN_PREFIX}/dashboard`} replace />
  }
  return <>{children}</>
}

/** Master section: superadmins have their own section under /super. */
function RequireMasterSection({ children }: { children: React.ReactNode }) {
  if (!getIsAuthenticated()) {
    return <Navigate to="/" replace />
  }
  if (getIsAdmin()) {
    return <Navigate to={`${SUPER_PREFIX}/dashboard`} replace />
  }
  return <>{children}</>
}

// Master navigation (section /admin)
const masterNavItems = [
  { path: `${ADMIN_PREFIX}/dashboard`, label: '📊 Дашборд' },
  { path: `${ADMIN_PREFIX}/appointments`, label: '📅 Мои записи' },
  { path: `${ADMIN_PREFIX}/services`, label: '💇 Мои услуги' },
  { path: `${ADMIN_PREFIX}/clients`, label: '👥 Клиенты' },
  { path: `${ADMIN_PREFIX}/schedule`, label: '🕐 Расписание' },
]

function App() {
  const location = useLocation()
  const isAdminRoute = location.pathname.startsWith(ADMIN_PREFIX) || location.pathname.startsWith(SUPER_PREFIX)

  return (
    <ErrorBoundary>
      <div className={`app ${isAdminRoute ? 'admin-app' : 'public-app'}`}>
        <Routes>
        {/* Public routes */}
        <Route path="/" element={<HomePage />} />
        <Route path="/booking" element={<BookingPage />} />

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
          <Route path="logs" element={<LogsPage />} />
        </Route>

        {/* Catch all */}
        <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </div>
      <Toaster position="top-right" richColors />
    </ErrorBoundary>
    )
  }

export default App
