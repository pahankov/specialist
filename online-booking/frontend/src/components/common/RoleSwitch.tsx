/** Segmented Клиент/Мастер switch (login, registration, sidebar). */
import './RoleSwitch.css';

export type RoleChoice = 'client' | 'master';

interface RoleSwitchProps {
  value: RoleChoice;
  onChange: (v: RoleChoice) => void;
  labels?: { client?: string; master?: string };
}

export default function RoleSwitch({ value, onChange, labels = {} }: RoleSwitchProps) {
  const clientLabel = labels.client ?? '👤 Клиент';
  const masterLabel = labels.master ?? '💼 Мастер';
  return (
    <div className="role-switch" role="group" aria-label="Выбор роли">
      <button
        type="button"
        className={`role-switch-btn${value === 'client' ? ' active' : ''}`}
        onClick={() => onChange('client')}
        aria-pressed={value === 'client'}
      >
        {clientLabel}
      </button>
      <button
        type="button"
        className={`role-switch-btn${value === 'master' ? ' active' : ''}`}
        onClick={() => onChange('master')}
        aria-pressed={value === 'master'}
      >
        {masterLabel}
      </button>
    </div>
  );
}
