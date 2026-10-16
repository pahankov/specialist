import { useEffect, useMemo, useState } from 'react';
import { reviewsApi } from '../../api/client';
import type { AverageRating, Review } from '../../api/types';
import { EmptyState, Skeleton } from '../common';
import ReviewCard from './ReviewCard';
import Stars from './Stars';
import './ReviewsSection.css';

/** Master panel: own rating summary + every published review. */
const PAGE_SIZE = 20;

function MasterReviews({ profileId }: { profileId: number | null }) {
  const [avg, setAvg] = useState<AverageRating | null>(null);
  const [reviews, setReviews] = useState<Review[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  // Public endpoint returns a bare array (no total) — a full page means more.
  const [hasMore, setHasMore] = useState(false);
  // Star filter (chips under the summary) — client-side, like everywhere.
  const [starFilter, setStarFilter] = useState<number | null>(null);

  useEffect(() => {
    if (!profileId) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setReviews([]);
    setStarFilter(null);
    (async () => {
      try {
        const [avgRes, listRes] = await Promise.all([
          reviewsApi.getAverage(profileId),
          reviewsApi.getAll(profileId, true, PAGE_SIZE, 0),
        ]);
        setAvg(avgRes.data);
        const list = listRes.data || [];
        setReviews(list);
        setHasMore(list.length === PAGE_SIZE);
      } catch {
        /* section shows the empty state */
      } finally {
        setLoading(false);
      }
    })();
  }, [profileId]);

  const loadMore = async () => {
    if (!profileId || loadingMore) return;
    setLoadingMore(true);
    try {
      const { data } = await reviewsApi.getAll(profileId, true, PAGE_SIZE, reviews.length);
      const list = data || [];
      // Offset may overlap on concurrent writes — dedupe by id.
      setReviews((prev) => {
        const known = new Set(prev.map((r) => r.id));
        return [...prev, ...list.filter((r) => !known.has(r.id))];
      });
      setHasMore(list.length === PAGE_SIZE);
    } catch {
      /* keep what we have */
    } finally {
      setLoadingMore(false);
    }
  };

  const starCounts = useMemo(() => {
    const counts: Record<number, number> = { 5: 0, 4: 0, 3: 0, 2: 0, 1: 0 };
    for (const r of reviews) {
      const bucket = Math.min(5, Math.max(1, Math.round(r.rating)));
      counts[bucket] += 1;
    }
    return counts;
  }, [reviews]);
  const visibleReviews =
    starFilter === null ? reviews : reviews.filter((r) => Math.round(r.rating) === starFilter);

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
        <>
          <div className="star-filter" role="group" aria-label="Фильтр по оценке">
            <button
              type="button"
              className={`star-chip${starFilter === null ? ' active' : ''}`}
              onClick={() => setStarFilter(null)}
            >
              Все · {reviews.length}
            </button>
            {[5, 4, 3, 2, 1].map((s) => (
              <button
                key={s}
                type="button"
                className={`star-chip${starFilter === s ? ' active' : ''}`}
                onClick={() => setStarFilter(starFilter === s ? null : s)}
                title={`Показать оценки ${s}`}
                disabled={starCounts[s] === 0}
              >
                ★ {s} · {starCounts[s]}
              </button>
            ))}
          </div>
          {visibleReviews.length === 0 ? (
            <EmptyState title="Пусто" description="С такой оценкой отзывов нет" icon="💬" />
          ) : (
            <>
              <div className="reviews-grid">
                {visibleReviews.map((r) => (
                  <ReviewCard key={r.id} review={r} />
                ))}
              </div>
              {/* Paging pauses under a star filter: "more" belongs to all. */}
              {starFilter === null && hasMore && (
                <div style={{ display: 'flex', justifyContent: 'center', marginTop: 12 }}>
                  <button
                    type="button"
                    className="btn btn-ghost"
                    onClick={loadMore}
                    disabled={loadingMore}
                  >
                    {loadingMore ? 'Загружаем…' : `Показать ещё (уже ${reviews.length})`}
                  </button>
                </div>
              )}
            </>
          )}
        </>
      )}
    </div>
  );
}

export default MasterReviews;
