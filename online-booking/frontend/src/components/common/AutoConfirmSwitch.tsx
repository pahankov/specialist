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
    <label
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 8,
        fontSize: 13,
        cursor: 'pointer',
      }}
      title="Новые заявки из кабинета и с сайта сразу станут подтверждёнными"
    >
      <input type="checkbox" checked={value} disabled={saving} onChange={flip} />⚡
      Автоподтверждение
    </label>
  );
}
