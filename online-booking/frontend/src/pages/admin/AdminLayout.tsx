import BaseLayout, { type BaseNavItem } from './BaseLayout';

interface AdminLayoutProps {
  navItems: BaseNavItem[];
}

/** Master section shell (/admin) — nav comes from App, chrome from BaseLayout. */
function AdminLayout({ navItems }: AdminLayoutProps) {
  return (
    <BaseLayout
      navItems={navItems}
      layoutTitle="🍬 Мастерская"
      userRole="Мастер"
      userFallbackName="Мастер"
      themeClass="master-layout"
    />
  );
}

export default AdminLayout;
