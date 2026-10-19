import BaseLayout from './BaseLayout';
import { SUPER_PREFIX } from '../../utils/section';
import './SuperAdminLayout.css';

const SUPER_NAV = [
  { path: `${SUPER_PREFIX}/dashboard`, label: '📊 Обзор' },
  // Personal profile (bindings, password, contacts) — second, same as the
  // master nav, so it is never lost among the global sections.
  { path: `${SUPER_PREFIX}/profile`, label: '👤 Профиль' },
  { path: `${SUPER_PREFIX}/revenue`, label: '💰 Доход' },
  { path: `${SUPER_PREFIX}/masters`, label: '👨‍💼 Мастера' },
  { path: `${SUPER_PREFIX}/appointments`, label: '📅 Все записи' },
  { path: `${SUPER_PREFIX}/clients`, label: '👥 Все клиенты' },
  { path: `${SUPER_PREFIX}/schedule`, label: '🕐 Расписание' },
  { path: `${SUPER_PREFIX}/notifications`, label: '🔔 Уведомления' },
  { path: `${SUPER_PREFIX}/logs`, label: '📋 Логи' },
];

/**
 * Standalone superadmin shell: own URL section (/super), own navigation,
 * own visual theme. Never renders master UI — masters live under /admin.
 */
function SuperAdminLayout() {
  return (
    <BaseLayout
      navItems={SUPER_NAV}
      layoutTitle="🛡️ Суперпанель"
      userRole="Суперпользователь"
      userFallbackName="Суперпользователь"
      themeClass="super-layout"
    />
  );
}

export default SuperAdminLayout;
