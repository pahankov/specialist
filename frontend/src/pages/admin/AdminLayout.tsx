import { useEffect, useState } from 'react'
import { Outlet, Link, useNavigate, useLocation } from 'react-router-dom'
import { adminApi } from '../../api/client'
import './AdminLayout.css'

interface MasterInfo {
  id: number
  name: string
  is_admin: boolean
}

function getCookie(name: string): string | null {
  const match = document.cookie.match(new RegExp('(^| )' + name + '=([^;]+)'))
  return match ? match[2] : null
}

function decodeJwtPayload(token: string): any {
  try {
    const payload = token.split('.')[1]
    return JSON.parse(atob(payload))
  } catch {
    return null
  }
}

function AdminLayout() {
  const navigate = useNavigate()
  const location = useLocation()
  const [master, setMaster] = useState<MasterInfo | null>(null)

  useEffect(() => {
    const token = getCookie('access_token')
    if (!token) return

    try {
      const payload = decodeJwtPayload(token)
      if (payload) {
        const masterId = parseInt(payload.sub)
        const isAdmin = payload.is_admin === true
        const name = payload.name || 'Мастер'
        setMaster({ id: masterId, name, is_admin: isAdmin })
      }
    } catch {
      adminApi.getDashboard().catch(() => {})
    }
  }, [])

  const handleLogout = async () => {
    try {
      await adminApi.getDashboard() // just to trigger, won't be used
    } catch { /* ignore */ }
    
    document.cookie = 'access_token=; path=/; max-age=0'
    // Backend will also clear refresh_token cookie via /api/v1/auth/logout
    navigate('/')
  }

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
