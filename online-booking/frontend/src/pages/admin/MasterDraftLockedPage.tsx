import { useLocation, useNavigate } from 'react-router-dom';
import { EmptyState } from '../../components/common';
import './ProfilePage.css';

interface MasterDraftLockedPageProps {
  title: string;
}

/**
 * One of the master-panel sections before activation. It keeps the full
 * cabinet navigation honest: the link exists, but the section explains why
 * it cannot be used yet instead of silently bouncing to the client cabinet.
 */
function MasterDraftLockedPage({ title }: MasterDraftLockedPageProps) {
  const navigate = useNavigate();
  const location = useLocation();

  return (
    <div className="profile-page">
      <div className="page-header">
        <div>
          <h1>🔒 {title}</h1>
          <p>Раздел откроется сразу после активации кабинета мастера</p>
        </div>
      </div>
      <div className="card">
        <EmptyState
          icon="🔒"
          title="Сначала активируйте кабинет"
          description="Заполните профиль мастера и выполните все условия активации. Это займёт пару минут — одобрение администратора не нужно."
          actionLabel="Перейти к профилю"
          onAction={() => navigate('/admin/become-master', { state: location.state })}
        />
      </div>
    </div>
  );
}

export default MasterDraftLockedPage;
