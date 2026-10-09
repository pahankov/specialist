import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import Pager from '../components/common/Pager'

describe('Pager', () => {
  it('jumps to first and last page', () => {
    const onChange = vi.fn()
    render(<Pager page={3} totalPages={10} onChange={onChange} />)
    fireEvent.click(screen.getByTitle('В начало'))
    expect(onChange).toHaveBeenCalledWith(0)
    fireEvent.click(screen.getByTitle('В конец'))
    expect(onChange).toHaveBeenCalledWith(9)
  })

  it('disables edges on first page', () => {
    render(<Pager page={0} totalPages={5} onChange={vi.fn()} />)
    expect(screen.getByTitle('В начало')).toBeDisabled()
    expect(screen.getByTitle('Назад')).toBeDisabled()
    expect(screen.getByTitle('В конец')).not.toBeDisabled()
  })
})
