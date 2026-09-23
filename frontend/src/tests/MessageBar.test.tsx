import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import MessageBar from '../components/common/MessageBar'

describe('MessageBar', () => {
  it('renders success message', () => {
    render(<MessageBar type="success" message="Успешно!" onDismiss={vi.fn()} />)
    expect(screen.getByText('Успешно!')).toBeInTheDocument()
  })

  it('renders error message', () => {
    render(<MessageBar type="error" message="Ошибка!" onDismiss={vi.fn()} />)
    expect(screen.getByText('Ошибка!')).toBeInTheDocument()
  })

  it('renders warning message', () => {
    render(<MessageBar type="warning" message="Внимание!" onDismiss={vi.fn()} />)
    expect(screen.getByText('Внимание!')).toBeInTheDocument()
  })

  it('renders info message', () => {
    render(<MessageBar type="info" message="Информация" onDismiss={vi.fn()} />)
    expect(screen.getByText('Информация')).toBeInTheDocument()
  })

  it('does not render when message is empty', () => {
    render(<MessageBar type="success" message="" onDismiss={vi.fn()} />)
    expect(screen.queryByText('Test')).not.toBeInTheDocument()
  })
})
