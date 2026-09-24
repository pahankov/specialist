import { Link } from 'react-router-dom'
import './SharedComponents.css'

interface BreadcrumbItem {
  label: string
  path: string
}

interface BreadcrumbProps {
  items: BreadcrumbItem[]
}

export default function Breadcrumb({ items }: BreadcrumbProps) {
  if (items.length === 0) return null

  return (
    <nav className="breadcrumb" aria-label="Навигационная цепочка">
      <Link to="/admin/dashboard" className="breadcrumb-home">
        🏠
      </Link>
      {items.map((item, index) => (
        <span key={item.path} className="breadcrumb-item">
          <span className="breadcrumb-sep">/</span>
          {index === items.length - 1 ? (
            <span className="breadcrumb-current">{item.label}</span>
          ) : (
            <Link to={item.path}>{item.label}</Link>
          )}
        </span>
      ))}
    </nav>
  )
}
