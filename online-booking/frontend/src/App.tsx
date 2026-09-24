import { Routes, Route, Navigate, useLocation } from 'react-router-dom'
import { HomePage, BookingPage } from './pages/public'
import { AdminLayout, DashboardPage, AppointmentsPage, ServicesPage, ClientsPage, SchedulePage, LogsPage } from './pages/admin'
import MastersPage from './pages/admin/MastersPage'
import ErrorBoundary from './components/ErrorBoundary'
import { ToastProvider } from './components/Toast'
import './App.css'

function getIsAuthenticated() {
  return !!document.cookie.includes('access_token=')
}

function getIsAdmin() {
  const match = document.cookie.match(new RegExp('(^| )' + 'access_token' + '=([^;]+)'))
  if (!match) return false
  try {
    const payload = JSON.parse(atob(match[2].split('.')[1]))
    return payload.is_admin === true
  } catch {
    return false
  }
}

function AdminRoute({ children }: { children: React.ReactNode }) {
  if (!getIsAuthenticated()) {
    return <Navigate to="/admin/login" replace />
  }
  return <>{children}</>
}

function App() {
  const location = useLocation()
  const isAdminRoute = location.pathname.startsWith('/admin')
  const isAdminUser = getIsAdmin()

  // Superadmin navigation items
  const superadminNavItems = [
    { path: '/admin/dashboard', label: '📊 Дашборд' },
    { path: '/admin/masters', label: '👨‍💼 Мастера' },
    { path: '/admin/appointments', label: '📅 Все записи' },
    { path: '/admin/clients', label: '👥 Все клиенты' },
    { path: '/admin/schedule', label: '🕐 Расписание' },
    { path: '/admin/logs', label: '📋 Логи' },
  ]

  // Regular master navigation items
  const masterNavItems = [
    { path: '/admin/dashboard', label: '📊 Дашборд' },
    { path: '/admin/appointments', label: '📅 Мои записи' },
    { path: '/admin/services', label: '💇 Мои услуги' },
    { path: '/admin/clients', label: '👥 Клиенты' },
    { path: '/admin/schedule', label: '🕐 Расписание' },
  ]

  const navItems = isAdminUser ? superadminNavItems : masterNavItems

  return (
    <ErrorBoundary>
      <ToastProvider>
        <div className={`app ${isAdminRoute ? 'admin-app' : 'public-app'}`}>
        <Routes>
        {/* Public routes */}
        <Route path="/" element={<HomePage />} />
        <Route path="/booking" element={<BookingPage />} />

        {/* Master/Superadmin login — redirect to home (LoginModal opens from there) */}
        <Route path="/admin/login" element={<Navigate to="/" replace />} />

        {/* Protected admin routes */}
        <Route
          path="/admin"
          element={
            <AdminRoute>
              <AdminLayout navItems={navItems} isAdmin={isAdminUser} />
            </AdminRoute>
          }
        >
          <Route index element={<Navigate to="/admin/dashboard" replace />} />
          <Route path="dashboard" element={<DashboardPage />} />
          <Route path="appointments" element={<AppointmentsPage />} />
          <Route path="services" element={<ServicesPage />} />
          <Route path="clients" element={<ClientsPage />} />
          <Route path="schedule" element={<SchedulePage />} />
          <Route path="logs" element={<LogsPage />} />
          {/* Superadmin-only routes */}
          {isAdminUser && (
            <Route path="masters" element={<MastersPage />} />
          )}
        </Route>

        {/* Catch all */}
        <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
        </div>
      </ToastProvider>
    </ErrorBoundary>
    )
  }

export default App
