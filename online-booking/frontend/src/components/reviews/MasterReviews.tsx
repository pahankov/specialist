import { useEffect, useState } from 'react';
import { reviewsApi } from '../../api/client';
import type { AverageRating, Review } from '../../api/types';
import { EmptyState, Skeleton } from '../common';
import ReviewCard from './ReviewCard';
import Stars from './Stars';
import './ReviewsSection.css';

/** Master panel: own rating summary + every published review. */
function MasterReviews({ profileId }: { profileId: number | null }) {
  const [avg, setAvg] = useState<AverageRating | null>(null);
  const [reviews, setReviews] = useState<Review[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!profileId) {
      setLoading(false);
      return;
    }
    (async () => {
      try {
        const [avgRes, listRes] = await Promise.all([
          reviewsApi.getAverage(profileId),
          reviewsApi.getAll(profileId),
        ]);
        setAvg(avgRes.data);
        setReviews(listRes.data || []);
      } catch {
        /* section shows the empty state */
      } finally {
        setLoading(false);
      }
    })();
  }, [profileId]);

  if (loading) return <Skeleton rows={3} />;

  return (
    <div>
      {avg && avg.average_rating !== null ? (
        <div className="reviews-summary" style={{ marginBottom: 12 }}>
          <Stars value={avg.average_rating} size={28} />
          <span className="reviews-count">
            {avg.average_rating} · {avg.review_count} {avg.review_count === 1 ? 'оценка' : 'оценок'}
          </span>
        </div>
      ) : (
        <p className="hint">Оценок пока нет — появятся после первых завершённых визитов.</p>
      )}
      {reviews.length === 0 ? (
        <EmptyState title="Пока тихо" description="Отзывы клиентов появятся здесь" icon="💬" />
      ) : (
        <div className="reviews-grid">
          {reviews.map((r) => (
            <ReviewCard key={r.id} review={r} />
          ))}
        </div>
      )}
    </div>
  );
}

export default MasterReviews;
