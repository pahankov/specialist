import BaseLayout from '../admin/BaseLayout';
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
  return (
    <BaseLayout
      navItems={CLIENT_NAV}
      layoutTitle="💅 Кабинет"
      userRole="Клиент"
      userFallbackName="Гость"
      themeClass="client-layout"
    />
  );
}

export default ClientLayout;
