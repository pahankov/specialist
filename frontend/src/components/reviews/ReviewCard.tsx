import type { Review } from '../../api/types'
import './ReviewCard.css'

interface ReviewCardProps {
  review: Review
}

function ReviewCard({ review }: ReviewCardProps) {
  const stars = Array.from({ length: 5 }, (_, i) => (
    <span key={i} className={`star ${i < Math.round(review.rating) ? 'filled' : ''}`}>
      ★
    </span>
  ))

  const formatDate = (dateStr: string) => {
    try {
      const date = new Date(dateStr)
      return date.toLocaleDateString('ru-RU', {
        day: 'numeric',
        month: 'long',
        year: 'numeric',
      })
    } catch {
      return dateStr
    }
  }

  return (
    <div className="review-card card">
      <div className="review-header">
        <div className="review-client">
          <span className="review-client-name">{review.client_name}</span>
          <span className="review-date">{formatDate(review.created_at)}</span>
        </div>
        <div className="review-stars">{stars}</div>
      </div>
      {review.comment && <p className="review-comment">{review.comment}</p>}
    </div>
  )
}

export default ReviewCard
