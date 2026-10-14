import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { authApi } from '../../api/client';
import { AddressSelect } from '../../components/common';
import { getApiErrorMessage } from '../../utils/apiError';

/** Master application: strict verification, no instant access.
 *
 * The profile is created INACTIVE — it appears publicly and opens the
 * panel only after a superadmin approves it. Stay in the cabinet meanwhile.
 */
function BecomeMasterPage() {
  const navigate = useNavigate();
  const [address, setAddress] = useState('');
  const [description, setDescription] = useState('');
  const [experience, setExperience] = useState('');
  const [sending, setSending] = useState(false);
  const [sent, setSent] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSending(true);
    try {
      await authApi.becomeMaster({
        cabinet_address: address.trim() || undefined,
        description: description.trim() || undefined,
        experience_years: experience.trim() === '' ? undefined : Number(experience),
      });
      setSent(true);
      toast.success('Заявка отправлена! Профиль появится после проверки.');
    } catch (err: unknown) {
      toast.error(getApiErrorMessage(err, 'Не удалось отправить заявку'));
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="client-profile-page">
      <div className="page-header">
        <div>
          <h1>✨ Стать мастером</h1>
          <p>Заявка на проверку — панель откроется после одобрения администратором</p>
        </div>
      </div>

      {sent ? (
        <div className="card">
          <h3>✅ Заявка принята</h3>
          <p style={{ fontSize: 14, color: '#555' }}>
            Мы проверяем заявки вручную. Как только администратор одобрит профиль, в меню появится
            «Панель мастера». Продолжайте пользоваться кабинетом клиента.
          </p>
          <button className="btn btn-primary" onClick={() => navigate('/cabinet')}>
            В кабинет
          </button>
        </div>
      ) : (
        <form onSubmit={handleSubmit}>
          <div className="card" style={{ marginBottom: 16 }}>
            <div className="form-group">
              <AddressSelect
                value={address}
                onChange={(a) => setAddress(a)}
                label="Адрес кабинета"
                placeholder="Город, улица, дом..."
              />
            </div>
            <div className="form-row">
              <div className="form-group">
                <label>Опыт (лет)</label>
                <input
                  type="number"
                  min={0}
                  max={80}
                  value={experience}
                  onChange={(e) => setExperience(e.target.value)}
                  placeholder="5"
                />
              </div>
            </div>
            <div className="form-group">
              <label>О себе</label>
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                rows={3}
                placeholder="Специализация, подход к работе..."
              />
            </div>
          </div>

          <div className="form-actions">
            <button type="submit" className="btn btn-primary" disabled={sending}>
              {sending ? 'Отправка…' : 'Отправить заявку'}
            </button>
          </div>
        </form>
      )}
    </div>
  );
}

export default BecomeMasterPage;
