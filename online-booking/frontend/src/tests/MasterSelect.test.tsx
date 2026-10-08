import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import MasterSelect from '../components/common/MasterSelect'

const MASTERS = [
  { id: 1, name: 'Елена', is_active: true, tariff: 'trial' },
  { id: 2, name: 'Мария', is_active: false, tariff: 'pro' },
  { id: 3, name: 'Екатерина', is_active: true },
]

describe('MasterSelect', () => {
  it('filters by typed letters instantly', () => {
    render(<MasterSelect value="" onChange={vi.fn()} masters={MASTERS} />)
    fireEvent.focus(screen.getByLabelText('Мастер'))
    fireEvent.change(screen.getByLabelText('Мастер'), { target: { value: 'ма' } })
    expect(screen.getByText('Мария')).toBeInTheDocument()
    expect(screen.queryByText('Елена')).not.toBeInTheDocument()
    expect(screen.queryByText('Екатерина')).not.toBeInTheDocument()
  })

  it('case-insensitive cyrillic match', () => {
    render(<MasterSelect value="" onChange={vi.fn()} masters={MASTERS} />)
    fireEvent.focus(screen.getByLabelText('Мастер'))
    fireEvent.change(screen.getByLabelText('Мастер'), { target: { value: 'ЕЛЕ' } })
    expect(screen.getByText('Елена')).toBeInTheDocument()
  })

  it('shows empty state when nothing matches', () => {
    render(<MasterSelect value="" onChange={vi.fn()} masters={MASTERS} />)
    fireEvent.focus(screen.getByLabelText('Мастер'))
    fireEvent.change(screen.getByLabelText('Мастер'), { target: { value: 'zzz' } })
    expect(screen.getByText('Ничего не найдено')).toBeInTheDocument()
  })

  it('picks master and reports id', () => {
    const onChange = vi.fn()
    render(<MasterSelect value="" onChange={onChange} masters={MASTERS} />)
    fireEvent.focus(screen.getByLabelText('Мастер'))
    fireEvent.click(screen.getByText('Мария'))
    expect(onChange).toHaveBeenCalledWith(2)
  })

  it('displays selected name when closed', () => {
    render(<MasterSelect value={1} onChange={vi.fn()} masters={MASTERS} />)
    expect(screen.getByDisplayValue('Елена')).toBeInTheDocument()
  })

  it('hides "all" option when allowAll is false', () => {
    render(<MasterSelect value={1} onChange={vi.fn()} masters={MASTERS} allowAll={false} />)
    fireEvent.focus(screen.getByLabelText('Мастер'))
    expect(screen.queryByText('Все мастера')).not.toBeInTheDocument()
  })
})
