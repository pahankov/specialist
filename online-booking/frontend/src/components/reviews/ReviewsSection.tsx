import { useEffect, useState } from 'react'
import { reviewsApi } from '../../api/client'
import type { Review, AverageRating } from '../../api/types'
import ReviewCard from './ReviewCard'
import './ReviewsSection.css'

interface ReviewsSectionProps {
  masterId?: number
}

function ReviewsSection({ masterId }: ReviewsSectionProps) {
  const [reviews, setReviews] = useState<Review[]>([])
  const [avgRating, setAvgRating] = useState<AverageRating | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchReviews = async () => {
      try {
        setLoading(true)
        const [reviewsRes, avgRes] = await Promise.all([
          reviewsApi.getAll(masterId),
          masterId ? reviewsApi.getAverage(masterId) : Promise.resolve({ data: null }),
        ])
        setReviews(reviewsRes.data)
        setAvgRating(avgRes.data)
      } catch {
        // Silently fail — reviews are optional
      } finally {
        setLoading(false)
      }
    }

    fetchReviews()
  }, [masterId])

  if (loading) return null
  if (reviews.length === 0) return null

  return (
    <section className="reviews-section">
      <div className="container">
        <h2>Отзывы клиентов</h2>

        {avgRating && (avgRating.average_rating !== null) && (
          <div className="reviews-summary">
            <span className="reviews-average">
              {'★'.repeat(Math.round(avgRating.average_rating!))}
              {'☆'.repeat(5 - Math.round(avgRating.average_rating!))}
            </span>
            <span className="reviews-count">
              {avgRating.average_rating} · {avgRating.review_count} {pluralize(avgRating.review_count, 'отзыв', 'отзыва', 'отзывов')}
            </span>
          </div>
        )}

        <div className="reviews-grid">
          {reviews.slice(0, 6).map((review) => (
            <ReviewCard key={review.id} review={review} />
          ))}
        </div>
      </div>
    </section>
  )
}

function pluralize(n: number, one: string, few: string, many: string): string {
  const mod10 = n % 10
  const mod100 = n % 100
  if (mod10 === 1 && mod100 !== 11) return one
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 10 || mod100 >= 20)) return few
  return many
}

export default ReviewsSection
