import { useEffect, useRef, type ReactNode } from 'react';
import { createPortal } from 'react-dom';
import './Modal.css';

interface ModalProps {
  open: boolean;
  onClose: () => void;
  title?: ReactNode;
  children: ReactNode;
  /** Extra class for the dialog box (e.g. "login-modal"). */
  className?: string;
  /** Wider dialog (forms with many fields). */
  wide?: boolean;
}

/**
 * Ref-counted body scroll lock. Stacked modals (e.g. confirm-over-booking)
 * each used to save/restore `body.overflow` on their own; closing two in one
 * commit left the page permanently unscrollable. Now the first opener saves
 * the value and only the last closer restores it.
 */
let scrollLocks = 0;
let savedOverflow = '';

function lockScroll() {
  if (scrollLocks === 0) {
    savedOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
  }
  scrollLocks += 1;
}

function unlockScroll() {
  scrollLocks = Math.max(0, scrollLocks - 1);
  if (scrollLocks === 0) document.body.style.overflow = savedOverflow;
}

/** Single modal implementation: portal, Esc, overlay click, scroll lock, aria.
 *
 * Modals close ONLY via Esc or a click on the overlay (owner's rule: no ✕
 * anywhere) — the header keeps just the title. */
export default function Modal({
  open,
  onClose,
  title,
  children,
  className = '',
  wide = false,
}: ModalProps) {
  const boxRef = useRef<HTMLDivElement>(null);
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;
  const wasOpen = useRef(false);

  useEffect(() => {
    if (!open) {
      wasOpen.current = false;
      return;
    }
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onCloseRef.current();
    };
    document.addEventListener('keydown', onKey);
    lockScroll();
    // Focus the dialog ONCE when it opens (never on re-renders, or typing
    // in form fields would lose focus after every keystroke).
    if (!wasOpen.current) boxRef.current?.focus();
    wasOpen.current = true;
    return () => {
      document.removeEventListener('keydown', onKey);
      unlockScroll();
    };
  }, [open]);

  if (!open) return null;

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
        {title !== undefined && (
          <div className="modal-header">
            <h3 className="modal-title">{title}</h3>
          </div>
        )}
        {children}
      </div>
    </div>,
    document.body,
  );
}
