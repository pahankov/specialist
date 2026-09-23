import { describe, it, expect } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import Modal from '../components/common/Modal'

describe('Modal', () => {
  it('renders children when open', () => {
    render(
      <Modal
        isOpen={true}
        onClose={vi.fn()}
        title="Test Modal"
        actions={[{ label: 'OK', onClick: vi.fn() }]}
      >
        <span>Modal content</span>
      </Modal>
    )
    expect(screen.getByText('Test Modal')).toBeInTheDocument()
    expect(screen.getByText('Modal content')).toBeInTheDocument()
  })

  it('does not render when closed', () => {
    render(
      <Modal
        isOpen={false}
        onClose={vi.fn()}
        title="Hidden Modal"
        actions={[{ label: 'OK', onClick: vi.fn() }]}
      >
        <span>Hidden content</span>
      </Modal>
    )
    expect(screen.queryByText('Hidden content')).not.toBeInTheDocument()
  })

  it('calls onClose when overlay is clicked', () => {
    const onClose = vi.fn()
    render(
      <Modal
        isOpen={true}
        onClose={onClose}
        title="Test"
        actions={[{ label: 'OK', onClick: vi.fn() }]}
      >
        Content
      </Modal>
    )
    const overlay = document.querySelector('.modal-overlay')
    overlay?.click()
    expect(onClose).toHaveBeenCalled()
  })

  it('does not call onClose when modal content is clicked', () => {
    const onClose = vi.fn()
    render(
      <Modal
        isOpen={true}
        onClose={onClose}
        title="Test"
        actions={[{ label: 'OK', onClick: vi.fn() }]}
      >
        <div className="modal-body">
          <span>Inner content</span>
        </div>
      </Modal>
    )
    const modalBody = document.querySelector('.modal-body')
    modalBody?.click()
    expect(onClose).not.toHaveBeenCalled()
  })
})
