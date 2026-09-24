import { useState, useEffect } from 'react'
import { Outlet, Link, useNavigate, useLocation } from 'react-router-dom'
import { adminApi } from '../../api/client'
import { Breadcrumb, KeyboardShortcutsHint } from '../../components/common'
import './AdminLayout.css'

interface MasterInfo {
  id: number
  name: string
  is_admin: boolean
}

interface NavItem {
  path: string
  label: string
}

interface AdminLayoutProps {
  navItems: NavItem[]
  isAdmin: boolean
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

function AdminLayout({ navItems, isAdmin }: AdminLayoutProps) {
  const navigate = useNavigate()
  const location = useLocation()
  const [master, setMaster] = useState<MasterInfo | null>(null)
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)

  useEffect(() => {
    const token = getCookie('access_token')
    if (!token) return

    try {
      const payload = decodeJwtPayload(token)
      if (payload) {
        const masterId = parseInt(payload.sub)
        const isAdminUser = payload.is_admin === true
        const name = payload.name || 'Мастер'
        setMaster({ id: masterId, name, is_admin: isAdminUser })
      }
    } catch {
      adminApi.getDashboard().catch(() => {})
    }
  }, [])

  // Close mobile menu on route change
  useEffect(() => {
    setMobileMenuOpen(false)
  }, [location.pathname])

  // Close mobile menu on resize to desktop
  useEffect(() => {
    const handleResize = () => {
      if (window.innerWidth > 1024) {
        setMobileMenuOpen(false)
      }
    }
    window.addEventListener('resize', handleResize)
    return () => window.removeEventListener('resize', handleResize)
  }, [])

  const handleLogout = async () => {
    try {
      await adminApi.getDashboard()
    } catch { /* ignore */ }
    
    document.cookie = 'access_token=; path=/; max-age=0'
    navigate('/')
  }

  const isActive = (path: string) => location.pathname === path

  const layoutTitle = isAdmin ? '🍬 Админ-панель' : '🍬 Мастерская'
  const userRole = isAdmin ? 'Суперпользователь' : 'Мастер'

  // Build breadcrumb from current path
  const breadcrumbs = location.pathname.split('/').filter(Boolean).map((segment, index, array) => {
    const path = '/' + array.slice(0, index + 1).join('/')
    const label = segment.charAt(0).toUpperCase() + segment.slice(1)
    return { label, path }
  })

  return (
    <div className="admin-layout">
      {/* Mobile hamburger button */}
      <button
        className="hamburger-btn"
        onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
        aria-label="Меню"
      >
        <span className="hamburger-line"></span>
        <span className="hamburger-line"></span>
        <span className="hamburger-line"></span>
      </button>

      {/* Mobile overlay */}
      {mobileMenuOpen && (
        <div className="sidebar-overlay" onClick={() => setMobileMenuOpen(false)} />
      )}

      <aside className={`admin-sidebar ${sidebarCollapsed ? 'collapsed' : ''} ${mobileMenuOpen ? 'mobile-open' : ''}`}>
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
          </div>
          {master && !sidebarCollapsed && (
            <p className="sidebar-user">👤 {master.name}</p>
          )}
        </div>
        <nav className="sidebar-nav">
          {navItems.map((item) => (
            <Link
              key={item.path}
              to={item.path}
              className={`nav-item ${isActive(item.path) ? 'active' : ''}`}
              onClick={() => setMobileMenuOpen(false)}
              title={sidebarCollapsed ? item.label : undefined}
            >
              <span className="nav-icon">{item.label.split(' ')[0]}</span>
              {!sidebarCollapsed && <span className="nav-label">{item.label.split(' ').slice(1).join(' ')}</span>}
            </Link>
          ))}
        </nav>
        <div className="sidebar-footer">
          <button className="btn btn-ghost btn-logout" onClick={handleLogout} title="Выйти">
            <span className="nav-icon">🚪</span>
            {!sidebarCollapsed && <span className="nav-label">Выйти</span>}
          </button>
        </div>
      </aside>

      <main className="admin-main">
        {!sidebarCollapsed && breadcrumbs.length > 0 && (
          <Breadcrumb items={breadcrumbs} />
        )}
        <div className="main-content">
          <Outlet />
        </div>
      </main>

      <KeyboardShortcutsHint />
    </div>
  )
}

export default AdminLayout
