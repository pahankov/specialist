import { Link } from 'react-router-dom';
import BaseLayout, { type BaseNavItem } from './BaseLayout';
import './MasterDraftLayout.css';

interface MasterDraftLayoutProps {
  navItems: BaseNavItem[];
}

/**
 * Inactive master cabinet (/admin/become-master).
 *
 * The person is still a CLIENT in the backend, but the shell is the real
 * master panel: all sections are visible, the profile is editable, and the
 * rest stays locked until self-activation.  This is deliberately separate
 * from ClientLayout — «Стать мастером» must not look like the client cabinet.
 */
function MasterDraftLayout({ navItems }: MasterDraftLayoutProps) {
  return (
    <BaseLayout
      navItems={navItems}
      layoutTitle="🍬 Мастерская"
      userRole="Мастер · неактивен"
      userFallbackName="Мастер"
      themeClass="master-layout"
      draftMode
      notice={
        <div className="master-draft-banner" role="status">
          <div className="master-draft-banner-text">
            <strong>Кабинет мастера неактивен</strong>
            <span>
              Заполните профиль и выполните условия — кабинет активируется автоматически, без
              администратора. До активации вы остаётесь клиентом, записи, услуги и расписание
              закрыты.
            </span>
          </div>
          <Link to="/cabinet" className="btn btn-sm btn-ghost">
            Кабинет клиента
          </Link>
        </div>
      }
    />
  );
}

export default MasterDraftLayout;
