import { useState, useEffect } from 'react'
import { Outlet, Link, useNavigate, useLocation } from 'react-router-dom'
import { authApi } from '../../api/client'
import { Breadcrumb, KeyboardShortcutsHint } from '../../components/common'
import { getCookie, decodeJwtPayload, clearAuthCookies } from '../../utils/cookies'
import { getImpersonation, stopImpersonation } from '../../utils/impersonation'
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

function getMasterInfo(): MasterInfo | null {
  const token = getCookie('access_token')
  if (!token) return null
  const payload = decodeJwtPayload(token)
  if (!payload?.sub) return null
  return {
    id: parseInt(payload.sub, 10),
    name: payload.name || 'Мастер',
    is_admin: payload.is_admin === true,
  }
}

function AdminLayout({ navItems, isAdmin }: AdminLayoutProps) {
  const navigate = useNavigate()
  const location = useLocation()
  const [master, setMaster] = useState<MasterInfo | null>(null)
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const [impersonatedName, setImpersonatedName] = useState<string | null>(null)

  const exitImpersonation = () => {
    stopImpersonation()
    setImpersonatedName(null)
    navigate('/admin/masters')
    window.location.reload()
  }

  useEffect(() => {
    setMaster(getMasterInfo())
    setImpersonatedName(getImpersonation()?.masterName ?? null)
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
    // Revoke server-side (httpOnly refresh cookie) first, then drop the
    // readable access token. Old code called getDashboard() — no-op leak.
    try {
      await authApi.logout()
    } catch { /* ignore: proceed with local cleanup anyway */ }

    clearAuthCookies()
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
        {impersonatedName !== null && (
          <div className="impersonation-banner" role="alert">
            <span>👁 Вы смотрите глазами мастера <strong>{impersonatedName}</strong> (режим поддержки)</span>
            <button className="btn btn-sm btn-primary" onClick={exitImpersonation}>
              Выйти из режима
            </button>
          </div>
        )}
        {breadcrumbs.length > 0 && (
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
