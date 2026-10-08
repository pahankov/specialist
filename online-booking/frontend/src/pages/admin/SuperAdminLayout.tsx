import { useState, useEffect } from 'react'
import { Outlet, Link, useNavigate, useLocation } from 'react-router-dom'
import { authApi } from '../../api/client'
import { Breadcrumb, KeyboardShortcutsHint } from '../../components/common'
import { getCookie, decodeJwtPayload, clearAuthCookies } from '../../utils/cookies'
import { getImpersonation, stopImpersonation } from '../../utils/impersonation'
import { SUPER_PREFIX } from '../../utils/section'
import './SuperAdminLayout.css'

interface SuperInfo {
  id: number
  name: string
}

const SUPER_NAV = [
  { path: `${SUPER_PREFIX}/dashboard`, label: '📊 Дашборд' },
  { path: `${SUPER_PREFIX}/revenue`, label: '💰 Доход' },
  { path: `${SUPER_PREFIX}/masters`, label: '👨‍💼 Мастера' },
  { path: `${SUPER_PREFIX}/appointments`, label: '📅 Все записи' },
  { path: `${SUPER_PREFIX}/clients`, label: '👥 Все клиенты' },
  { path: `${SUPER_PREFIX}/schedule`, label: '🕐 Расписание' },
  { path: `${SUPER_PREFIX}/logs`, label: '📋 Логи' },
]

function getSuperInfo(): SuperInfo | null {
  const token = getCookie('access_token')
  if (!token) return null
  const payload = decodeJwtPayload(token)
  if (!payload?.sub) return null
  return { id: parseInt(payload.sub, 10), name: payload.name || 'Суперпользователь' }
}

/**
 * Standalone superadmin shell: own URL section (/super), own navigation,
 * own visual theme. Never renders master UI — masters live under /admin.
 */
function SuperAdminLayout() {
  const navigate = useNavigate()
  const location = useLocation()
  const [superUser, setSuperUser] = useState<SuperInfo | null>(null)
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const [impersonatedName, setImpersonatedName] = useState<string | null>(null)

  const exitImpersonation = () => {
    stopImpersonation()
    setImpersonatedName(null)
    window.location.href = `${SUPER_PREFIX}/masters`
  }

  useEffect(() => {
    setSuperUser(getSuperInfo())
    setImpersonatedName(getImpersonation()?.masterName ?? null)
  }, [])

  useEffect(() => {
    setMobileMenuOpen(false)
  }, [location.pathname])

  const handleLogout = async () => {
    try {
      await authApi.logout()
    } catch { /* ignore: proceed with local cleanup anyway */ }
    clearAuthCookies()
    navigate('/')
  }

  const isActive = (path: string) => location.pathname === path

  const breadcrumbs = location.pathname.split('/').filter(Boolean).map((segment, index, array) => {
    const path = '/' + array.slice(0, index + 1).join('/')
    const label = segment.charAt(0).toUpperCase() + segment.slice(1)
    return { label, path }
  })

  return (
    <div className="admin-layout super-layout">
      <button
        className="hamburger-btn"
        onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
        aria-label="Меню"
      >
        <span className="hamburger-line"></span>
        <span className="hamburger-line"></span>
        <span className="hamburger-line"></span>
      </button>

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
              <h2>🛡️ Суперпанель</h2>
              {!sidebarCollapsed && <p className="sidebar-subtitle">Суперпользователь</p>}
            </div>
          </div>
          {superUser && !sidebarCollapsed && (
            <p className="sidebar-user">👤 {superUser.name}</p>
          )}
        </div>
        <nav className="sidebar-nav">
          {SUPER_NAV.map((item) => (
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

export default SuperAdminLayout
