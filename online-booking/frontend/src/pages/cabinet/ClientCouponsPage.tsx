import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { cabinetApi } from '../../api/client';
import { EmptyState, Skeleton } from '../../components/common';
import { getApiErrorMessage } from '../../utils/apiError';
import './CabinetPage.css';

interface MyCoupon {
  id: number;
  code: string;
  kind: string;
  value: number;
  uses_left: number | null;
  valid_until: string | null;
  terms: string;
  master_id: number;
}

/** Client's coupon wallet: every usable code in one place. */
function ClientCouponsPage() {
  const navigate = useNavigate();
  const [coupons, setCoupons] = useState<MyCoupon[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const { data } = await cabinetApi.myCoupons();
        setCoupons(data || []);
      } catch (err: unknown) {
        toast.error(getApiErrorMessage(err, 'Не удалось загрузить купоны'));
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  if (loading) {
    return (
      <div className="cabinet-page">
        <Skeleton rows={4} />
      </div>
    );
  }

  return (
    <div className="cabinet-page">
      <div className="page-header">
        <h1>🎟 Мои купоны{coupons.length > 0 ? ` (${coupons.length})` : ''}</h1>
      </div>
      {coupons.length === 0 ? (
        <EmptyState
          title="Купонов пока нет"
          description="Мастер выдаст персональный код — он появится здесь и в колокольчике"
        />
      ) : (
        <div className="cabinet-list">
          {coupons.map((c) => (
            <div key={c.id} className="cabinet-card">
              <div className="cabinet-card-main">
                <strong>
                  {c.terms} · код {c.code}
                </strong>
                <span className="cabinet-card-date">
                  {[
                    c.valid_until
                      ? `до ${new Date(c.valid_until).toLocaleString('ru-RU')}`
                      : 'бессрочно',
                    c.uses_left !== null ? `осталось: ${c.uses_left}` : null,
                  ]
                    .filter(Boolean)
                    .join(' · ')}
                </span>
              </div>
              <div className="cabinet-card-side">
                <button
                  className="btn btn-sm btn-primary"
                  onClick={() => navigate(`/cabinet/book?master_id=${c.master_id}`)}
                >
                  Записаться
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default ClientCouponsPage;
