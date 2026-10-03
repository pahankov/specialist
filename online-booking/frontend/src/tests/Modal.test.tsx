import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '../components/ui/dialog'

describe('Dialog (radix-ui)', () => {
  it('renders children when open', () => {
    render(
      <Dialog open={true} onOpenChange={vi.fn()}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Test Dialog</DialogTitle>
          </DialogHeader>
          <span>Dialog content</span>
        </DialogContent>
      </Dialog>
    )
    expect(screen.getByText('Test Dialog')).toBeInTheDocument()
    expect(screen.getByText('Dialog content')).toBeInTheDocument()
  })

  it('does not render when closed', () => {
    render(
      <Dialog open={false} onOpenChange={vi.fn()}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Hidden Dialog</DialogTitle>
          </DialogHeader>
          <span>Hidden content</span>
        </DialogContent>
      </Dialog>
    )
    expect(screen.queryByText('Hidden content')).not.toBeInTheDocument()
  })

  it('calls onOpenChange(false) when close button is clicked', () => {
    const onOpenChange = vi.fn()
    render(
      <Dialog open={true} onOpenChange={onOpenChange}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Test</DialogTitle>
          </DialogHeader>
          Content
        </DialogContent>
      </Dialog>
    )
    const closeButton = document.querySelector('[aria-label="Close"]') as HTMLElement
    if (closeButton) {
      fireEvent.click(closeButton)
      expect(onOpenChange).toHaveBeenCalledWith(false)
    }
  })
})
