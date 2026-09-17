import { Outlet, Link, useNavigate, useLocation } from 'react-router-dom'
import './AdminLayout.css'

function AdminLayout() {
  const navigate = useNavigate()
  const location = useLocation()
  const handleLogout = () => { localStorage.removeItem('access_token'); navigate('/') }
  const isActive = (path: string) => location.pathname === path
  const navItems = [
    { path: '/admin/dashboard', label: '📊 Дашборд' },
    { path: '/admin/appointments', label: '📅 Записи' },
    { path: '/admin/services', label: '💇 Услуги' },
    { path: '/admin/clients', label: '👥 Клиенты' },
    { path: '/admin/schedule', label: '🕐 Расписание' },
    { path: '/admin/logs', label: '📋 Логи' },
  ]
  return (
    <div className="admin-layout">
      <aside className="admin-sidebar">
        <div className="sidebar-header">
          <h2>🍬 Sugar Booking</h2>
          <p className="sidebar-subtitle">Админ-панель</p>
        </div>
        <nav className="sidebar-nav">
          {navItems.map((item) => (
            <Link key={item.path} to={item.path} className={`nav-item ${isActive(item.path) ? 'active' : ''}`}>{item.label}</Link>
          ))}
        </nav>
        <div className="sidebar-footer">
          <button className="btn btn-ghost btn-logout" onClick={handleLogout}>🚪 Выйти</button>
        </div>
      </aside>
      <main className="admin-main"><Outlet /></main>
    </div>
  )
}
export default AdminLayout
