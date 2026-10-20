import { useLocation } from 'react-router-dom';
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
  const { pathname } = useLocation();
  const isDraft = pathname.startsWith('/cabinet/become-master');
  // An activated master may still use the client cabinet (dual role); the
  // sidebar should say «Мастер», not «Клиент». A client filling the draft is
  // a master-in-progress — say so without pretending the role is active yet.
  const role = getUserRole();
  const userRole = role === 'MASTER' ? 'Мастер' : isDraft ? 'Мастер · черновик' : 'Клиент';

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
