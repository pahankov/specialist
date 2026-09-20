import { Routes, Route, Navigate, useLocation } from 'react-router-dom'
import { HomePage, BookingPage } from './pages/public'
import { LoginPage, AdminLayout, DashboardPage, AppointmentsPage, ServicesPage, ClientsPage, SchedulePage, LogsPage } from './pages/admin'
import ErrorBoundary from './components/ErrorBoundary'
import './App.css'

function getIsAuthenticated() {
  return !!localStorage.getItem('access_token')
}

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  if (!getIsAuthenticated()) {
    return <Navigate to="/admin/login" replace />
  }
  return <>{children}</>
}

function App() {
  const location = useLocation()
  const isAdminRoute = location.pathname.startsWith('/admin')
  return (
    <ErrorBoundary>
      <div className={`app ${isAdminRoute ? 'admin-app' : 'public-app'}`}>
        <Routes>
        {/* Public routes */}
        <Route path="/" element={<HomePage />} />
        <Route path="/booking" element={<BookingPage />} />

        {/* Master login */}
        <Route path="/admin/login" element={<LoginPage />} />

        {/* Protected master admin routes */}
        <Route
          path="/admin"
          element={
            <ProtectedRoute>
              <AdminLayout />
            </ProtectedRoute>
          }
        >
          <Route index element={<Navigate to="/admin/dashboard" replace />} />
          <Route path="dashboard" element={<DashboardPage />} />
          <Route path="appointments" element={<AppointmentsPage />} />
          <Route path="services" element={<ServicesPage />} />
          <Route path="clients" element={<ClientsPage />} />
          <Route path="schedule" element={<SchedulePage />} />
          <Route path="logs" element={<LogsPage />} />
        </Route>

        {/* Catch all */}
        <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
        </div>
      </ErrorBoundary>
    )
  }

export default App
