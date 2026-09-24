import { useEffect, useState, useMemo } from 'react'
import { reviewsApi } from '../../api/client'
import type { Review, AverageRating } from '../../api/types'
import ReviewCard from './ReviewCard'
import './ReviewsSection.css'

// Helper: shuffle array (Fisher-Yates)
function shuffleArray<T>(array: T[]): T[] {
  const shuffled = [...array]
  for (let i = shuffled.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1))
    ;[shuffled[i], shuffled[j]] = [shuffled[j], shuffled[i]]
  }
  return shuffled
}

interface ReviewsSectionProps {
  masterId?: number
}

function ReviewsSection({ masterId }: ReviewsSectionProps) {
  const [allReviews, setAllReviews] = useState<Review[]>([])
  const [avgRating, setAvgRating] = useState<AverageRating | null>(null)
  const [loading, setLoading] = useState(true)

  // Random selection on each page load (memoized)
  const randomReviews = useMemo(() => shuffleArray(allReviews).slice(0, 6), [allReviews])

  useEffect(() => {
    const fetchReviews = async () => {
      try {
        setLoading(true)
        const [reviewsRes, avgRes] = await Promise.all([
          reviewsApi.getAll(masterId),
          masterId ? reviewsApi.getAverage(masterId) : Promise.resolve({ data: null }),
        ])
        setAllReviews(reviewsRes.data)
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
  if (randomReviews.length === 0) return null

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
          {randomReviews.map((review) => (
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
