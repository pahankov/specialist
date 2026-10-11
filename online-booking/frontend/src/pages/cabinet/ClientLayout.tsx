import BaseLayout from '../admin/BaseLayout';
import './ClientLayout.css';

const CLIENT_NAV = [
  { path: '/cabinet', label: '📅 Мои записи' },
  { path: '/booking', label: '💅 Записаться' },
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
