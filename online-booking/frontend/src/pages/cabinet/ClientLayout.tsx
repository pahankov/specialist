import BaseLayout from '../admin/BaseLayout';
import { getUserRole } from '../../utils/cookies';
import './ClientLayout.css';

const CLIENT_NAV = [
  { path: '/cabinet', label: '📅 Мои записи' },
  { path: '/cabinet/book', label: '💅 Записаться' },
  { path: '/cabinet/coupons', label: '🎟 Мои купоны' },
  { path: '/cabinet/notifications', label: '🔔 Уведомления' },
  { path: '/cabinet/profile', label: '👤 Профиль' },
];

/**
 * Client section shell (/cabinet): same BaseLayout as master/superadmin,
 * own navigation and teal theme. Never renders master UI.
 */
function ClientLayout() {
  // An activated master may still use the client cabinet (dual role); the
  // sidebar should say «Мастер», not «Клиент». The master draft now has its
  // own panel shell and never renders inside this layout.
  const role = getUserRole();
  const userRole = role === 'MASTER' ? 'Мастер' : 'Клиент';

  return (
    <BaseLayout
      navItems={CLIENT_NAV}
      layoutTitle="💅 Кабинет"
      userRole={userRole}
      userFallbackName="Гость"
      themeClass="client-layout"
    />
  );
}

export default ClientLayout;
