import { useEffect, useRef, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import './Modal.css'

interface ModalProps {
  open: boolean
  onClose: () => void
  title?: ReactNode
  children: ReactNode
  /** Extra class for the dialog box (e.g. "login-modal"). */
  className?: string
  /** Wider dialog (forms with many fields). */
  wide?: boolean
}

/** Single modal implementation: portal, Esc, overlay click, scroll lock, aria. */
export default function Modal({ open, onClose, title, children, className = '', wide = false }: ModalProps) {
  const boxRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKey)
    const prevOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    boxRef.current?.focus()
    return () => {
      document.removeEventListener('keydown', onKey)
      document.body.style.overflow = prevOverflow
    }
  }, [open, onClose])

  if (!open) return null

  return createPortal(
    <div className="modal-overlay" onClick={onClose}>
      <div
        ref={boxRef}
        className={`modal${wide ? ' modal--wide' : ''}${className ? ` ${className}` : ''}`}
        role="dialog"
        aria-modal="true"
        tabIndex={-1}
        onClick={(e) => e.stopPropagation()}
      >
        {(title !== undefined) && (
          <div className="modal-header">
            <h3 className="modal-title">{title}</h3>
            <button type="button" className="modal-close" onClick={onClose} aria-label="Закрыть">
              ✕
            </button>
          </div>
        )}
        {children}
      </div>
    </div>,
    document.body,
  )
}
