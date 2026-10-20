import { useEffect, useState } from 'react';
import { toast } from 'sonner';
import { adminApi } from '../../api/client';
import { getApiErrorMessage } from '../../utils/apiError';
import { getCookie, decodeJwtPayload } from '../../utils/cookies';

/** Auto-confirm switch for client-initiated bookings.
 *
 * Lives where bookings live (Schedule / Appointments headers), not buried
 * in Profile: ON = cabinet + public bookings land "confirmed", OFF = "pending".
 */
export default function AutoConfirmSwitch() {
  const [value, setValue] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const { data } = await adminApi.getProfile();
        setValue(data.auto_confirm === true);
      } catch {
        /* panel without a master profile (superadmin): hide */
      } finally {
        setLoaded(true);
      }
    })();
  }, []);

  // Superadmins have no master profile — nothing to toggle.
  const isSuper = decodeJwtPayload(getCookie('access_token') ?? '')?.is_admin === true;
  if (!loaded || isSuper) return null;

  const flip = async () => {
    const next = !value;
    setValue(next);
    setSaving(true);
    try {
      await adminApi.updateProfile({ auto_confirm: next });
      toast.success(next ? 'Автоподтверждение включено' : 'Автоподтверждение выключено');
    } catch (err: unknown) {
      setValue(!next);
      toast.error(getApiErrorMessage(err, 'Не удалось сохранить'));
    } finally {
      setSaving(false);
    }
  };

  return (
    <button
      type="button"
      onClick={flip}
      disabled={saving}
      title="Новые заявки из кабинета и с сайта сразу станут подтверждёнными"
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 8,
        minHeight: 44,
        padding: '8px 16px',
        borderRadius: 999,
        border: `2px solid ${value ? '#667eea' : '#e0e0e0'}`,
        background: value ? '#667eea' : '#fff',
        color: value ? '#fff' : '#555',
        fontSize: 14,
        fontWeight: 600,
        cursor: saving ? 'wait' : 'pointer',
        opacity: saving ? 0.7 : 1,
      }}
    >
      <span
        aria-hidden
        style={{
          display: 'inline-block',
          width: 34,
          height: 20,
          borderRadius: 999,
          background: value ? '#fff' : '#cfd4de',
          position: 'relative',
          flexShrink: 0,
        }}
      >
        <span
          style={{
            position: 'absolute',
            top: 2,
            left: value ? 16 : 2,
            width: 16,
            height: 16,
            borderRadius: '50%',
            background: value ? '#667eea' : '#fff',
            boxShadow: '0 1px 3px rgba(0,0,0,0.25)',
          }}
        />
      </span>
      ⚡ Автоподтверждение {value ? 'вкл' : 'выкл'}
    </button>
  );
}
