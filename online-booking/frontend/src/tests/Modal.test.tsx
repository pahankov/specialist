import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import Modal from '../components/common/Modal'
import ConfirmDialog from '../components/common/ConfirmDialog'

describe('Modal', () => {
  it('renders title and children when open', () => {
    render(
      <Modal open={true} onClose={vi.fn()} title="Test title">
        <span>Modal content</span>
      </Modal>
    )
    expect(screen.getByText('Test title')).toBeInTheDocument()
    expect(screen.getByText('Modal content')).toBeInTheDocument()
  })

  it('renders nothing when closed', () => {
    render(
      <Modal open={false} onClose={vi.fn()} title="Hidden">
        <span>Hidden content</span>
      </Modal>
    )
    expect(screen.queryByText('Hidden content')).not.toBeInTheDocument()
  })

  it('calls onClose on overlay click but not on content click', () => {
    const onClose = vi.fn()
    render(
      <Modal open={true} onClose={onClose} title="T">
        <span>content</span>
      </Modal>
    )
    fireEvent.click(screen.getByText('content'))
    expect(onClose).not.toHaveBeenCalled()
    const overlay = document.querySelector('.modal-overlay') as HTMLElement
    fireEvent.click(overlay)
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('calls onClose on Escape and on close button', () => {
    const onClose = vi.fn()
    render(
      <Modal open={true} onClose={onClose} title="T">
        <span>content</span>
      </Modal>
    )
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(onClose).toHaveBeenCalledTimes(1)
    fireEvent.click(screen.getByLabelText('Закрыть'))
    expect(onClose).toHaveBeenCalledTimes(2)
  })

  it('exposes dialog role', () => {
    render(
      <Modal open={true} onClose={vi.fn()} title="T">
        <span>content</span>
      </Modal>
    )
    expect(screen.getByRole('dialog')).toBeInTheDocument()
  })
})

describe('ConfirmDialog', () => {
  it('confirms and cancels', () => {
    const onConfirm = vi.fn()
    const onClose = vi.fn()
    render(
      <ConfirmDialog
        open={true}
        onClose={onClose}
        title="Delete?"
        message="Sure?"
        confirmLabel="Delete"
        danger
        onConfirm={onConfirm}
      />
    )
    fireEvent.click(screen.getByText('Delete'))
    expect(onConfirm).toHaveBeenCalledTimes(1)
    fireEvent.click(screen.getByText('Отмена'))
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('disables confirm when confirmDisabled', () => {
    const onConfirm = vi.fn()
    render(
      <ConfirmDialog
        open={true}
        onClose={vi.fn()}
        title="Delete?"
        confirmLabel="Delete"
        confirmDisabled
        onConfirm={onConfirm}
      />
    )
    fireEvent.click(screen.getByText('Delete'))
    expect(onConfirm).not.toHaveBeenCalled()
  })

  it('hides cancel when hideCancel', () => {
    render(
      <ConfirmDialog
        open={true}
        onClose={vi.fn()}
        title="Note"
        confirmLabel="OK"
        hideCancel
        onConfirm={vi.fn()}
      />
    )
    expect(screen.queryByText('Отмена')).not.toBeInTheDocument()
  })
})
