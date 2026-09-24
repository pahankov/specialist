import { describe, it, expect } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import FilterBar from '../components/common/FilterBar'

describe('FilterBar', () => {
  const options = [
    { value: '', label: 'Все' },
    { value: 'active', label: 'Активные' },
    { value: 'inactive', label: 'Неактивные' },
  ]

  it('renders all filter buttons', () => {
    render(<FilterBar options={options} active="" onChange={vi.fn()} />)
    expect(screen.getByText('Все')).toBeInTheDocument()
    expect(screen.getByText('Активные')).toBeInTheDocument()
    expect(screen.getByText('Неактивные')).toBeInTheDocument()
  })

  it('applies active class to selected filter', () => {
    render(<FilterBar options={options} active="active" onChange={vi.fn()} />)
    const activeBtn = screen.getByText('Активные')
    expect(activeBtn).toHaveClass('active')
  })

  it('calls onChange when filter is clicked', () => {
    const onChange = vi.fn()
    render(<FilterBar options={options} active="" onChange={onChange} />)
    fireEvent.click(screen.getByText('Активные'))
    expect(onChange).toHaveBeenCalledWith('active')
  })
})
