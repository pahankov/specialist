import React from 'react'
import './SharedComponents.css'

interface PaginationProps {
  currentPage: number
  totalItems: number
  pageSize: number
  onPageChange: (page: number) => void
  hasMore?: boolean
}

export default function Pagination({ currentPage, totalItems, pageSize, onPageChange, hasMore }: PaginationProps) {
  const totalPages = Math.ceil(totalItems / pageSize)
  
  if (totalPages <= 1) return null

  return (
    <div className="pagination">
      <button
        className="btn btn-ghost"
        onClick={() => onPageChange(currentPage - 1)}
        disabled={currentPage === 0}
        style={{ opacity: currentPage === 0 ? 0.5 : 1 }}
      >
        ← Назад
      </button>
      <span className="pagination-info">
        Страница {currentPage + 1} из {totalPages}
      </span>
      <button
        className="btn btn-ghost"
        onClick={() => onPageChange(currentPage + 1)}
        disabled={!hasMore}
        style={{ opacity: !hasMore ? 0.5 : 1 }}
      >
        Вперёд →
      </button>
    </div>
  )
}
