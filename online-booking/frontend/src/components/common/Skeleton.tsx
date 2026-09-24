import './SharedComponents.css'

interface SkeletonProps {
  width?: string | number
  height?: string | number
  rows?: number
  variant?: 'text' | 'circular' | 'rectangular'
  className?: string
}

export default function Skeleton({ width, height, rows = 1, variant = 'text', className = '' }: SkeletonProps) {
  const skeletonStyle = {
    width: width || '100%',
    height: height || variant === 'circular' ? '40px' : '16px',
    borderRadius: variant === 'circular' ? '50%' : '6px',
  }

  if (rows > 1) {
    return (
      <div className={`skeleton ${className}`} style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {Array.from({ length: rows }).map((_, i) => (
          <div key={i} className="skeleton-line" style={skeletonStyle} />
        ))}
      </div>
    )
  }

  return <div className={`skeleton ${className}`} style={skeletonStyle} />
}
