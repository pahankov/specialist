import { Routes, Route, Navigate } from 'react-router-dom'
import HomePage from './pages/HomePage'
import BookingPage from './pages/BookingPage'
import LoginPage from './pages/LoginPage'
import AdminLayout from './pages/AdminLayout'
import DashboardPage from './pages/DashboardPage'
import AppointmentsPage from './pages/AppointmentsPage'
import ServicesPage from './pages/ServicesPage'
import SchedulePage from './pages/SchedulePage'
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
  return (
    <div className="app">
      <Routes>
        {/* Public routes */}
        <Route path="/" element={<HomePage />} />
        <Route path="/booking" element={<BookingPage />} />

        {/* Admin login */}
        <Route path="/admin/login" element={<LoginPage />} />

        {/* Protected admin routes */}
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
          <Route path="schedule" element={<SchedulePage />} />
        </Route>

        {/* Catch all */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </div>
  )
}

export default App
