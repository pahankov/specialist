import { describe, it, expect } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import Pagination from '../components/common/Pagination'

describe('Pagination', () => {
  it('renders with correct page number', () => {
    render(
      <Pagination
        currentPage={0}
        totalItems={50}
        pageSize={10}
        onPageChange={vi.fn()}
        hasMore={true}
      />
    )
    // Text is split across elements, so check for partial text
    expect(screen.getByText(/Страница 1 из/)).toBeInTheDocument()
  })

  it('disables previous button on first page', () => {
    const onPageChange = vi.fn()
    render(
      <Pagination
        currentPage={0}
        totalItems={50}
        pageSize={10}
        onPageChange={onPageChange}
        hasMore={true}
      />
    )
    const prevButton = screen.getByText('← Назад')
    expect(prevButton).toBeDisabled()
  })

  it('disables next button when no more pages', () => {
    const onPageChange = vi.fn()
    render(
      <Pagination
        currentPage={4}
        totalItems={50}
        pageSize={10}
        onPageChange={onPageChange}
        hasMore={false}
      />
    )
    const nextButton = screen.getByText('Вперёд →')
    expect(nextButton).toBeDisabled()
  })

  it('calls onPageChange when next is clicked', () => {
    const onPageChange = vi.fn()
    render(
      <Pagination
        currentPage={0}
        totalItems={50}
        pageSize={10}
        onPageChange={onPageChange}
        hasMore={true}
      />
    )
    const nextButton = screen.getByText('Вперёд →')
    fireEvent.click(nextButton)
    expect(onPageChange).toHaveBeenCalledWith(1)
  })

  it('calls onPageChange when previous is clicked', () => {
    const onPageChange = vi.fn()
    render(
      <Pagination
        currentPage={2}
        totalItems={50}
        pageSize={10}
        onPageChange={onPageChange}
        hasMore={true}
      />
    )
    const prevButton = screen.getByText('← Назад')
    fireEvent.click(prevButton)
    expect(onPageChange).toHaveBeenCalledWith(1)
  })
})
