import { useEffect, useState } from 'react'
import { Outlet, Link, useNavigate, useLocation } from 'react-router-dom'
import { adminApi } from '../../api/client'
import './AdminLayout.css'

interface MasterInfo {
  id: number
  name: string
  is_admin: boolean
}

function AdminLayout() {
  const navigate = useNavigate()
  const location = useLocation()
  const [master, setMaster] = useState<MasterInfo | null>(null)

  useEffect(() => {
    const token = localStorage.getItem('access_token')
    if (!token) return

    // Try to get master info from token payload
    try {
      const payload = JSON.parse(atob(token.split('.')[1]))
      const masterId = parseInt(payload.sub)
      const isAdmin = payload.is_admin === true
      const name = payload.name || 'Мастер'
      setMaster({ id: masterId, name, is_admin: isAdmin })
    } catch {
      // If we can't parse token, try to fetch
      adminApi.getDashboard()
        .catch(() => {})
    }
  }, [])

  const handleLogout = () => { localStorage.removeItem('access_token'); navigate('/') }
  const isActive = (path: string) => location.pathname === path
  const navItems = [
    { path: '/admin/dashboard', label: '📊 Дашборд' },
    { path: '/admin/appointments', label: '📅 Записи' },
    { path: '/admin/services', label: '💇 Услуги' },
    { path: '/admin/clients', label: '👥 Клиенты' },
    { path: '/admin/schedule', label: '🕐 Расписание' },
  ]
  const bottomNavItems = [
    { path: '/admin/logs', label: '📋 Логи' },
  ]
  return (
    <div className="admin-layout">
      <aside className="admin-sidebar">
        <div className="sidebar-header">
          <h2>🍬 Мастерская</h2>
          <p className="sidebar-subtitle">{master?.is_admin ? 'Суперпользователь' : 'Админ-панель'}</p>
          {master && <p className="sidebar-user">👤 {master.name}</p>}
        </div>
        <nav className="sidebar-nav">
          {navItems.map((item) => (
            <Link key={item.path} to={item.path} className={`nav-item ${isActive(item.path) ? 'active' : ''}`}>{item.label}</Link>
          ))}
          <div className="sidebar-divider" />
          {bottomNavItems.map((item) => (
            <Link key={item.path} to={item.path} className={`nav-item nav-item-bottom ${isActive(item.path) ? 'active' : ''}`}>{item.label}</Link>
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
