import type { ReactNode } from 'react';
import Modal from './Modal';

interface ConfirmDialogProps {
  open: boolean;
  onClose: () => void;
  title: ReactNode;
  message?: ReactNode;
  children?: ReactNode;
  confirmLabel: string;
  onConfirm: () => void;
  /** Red confirm button (destructive). Default: primary. */
  danger?: boolean;
  /** Disable confirm button (e.g. empty required input). */
  confirmDisabled?: boolean;
  /** Hide cancel button (info/error dialogs). */
  hideCancel?: boolean;
  cancelLabel?: string;
}

/** Shared confirmation dialog (delete / cancel / no-show / info). */
export default function ConfirmDialog({
  open,
  onClose,
  title,
  message,
  children,
  confirmLabel,
  onConfirm,
  danger = false,
  confirmDisabled = false,
  hideCancel = false,
  cancelLabel = 'Отмена',
}: ConfirmDialogProps) {
  return (
    <Modal open={open} onClose={onClose} title={title}>
      {message !== undefined && <p className="modal-message">{message}</p>}
      {children}
      <div className="modal-actions">
        {!hideCancel && (
          <button type="button" className="btn btn-ghost" onClick={onClose}>
            {cancelLabel}
          </button>
        )}
        <button
          type="button"
          className={danger ? 'btn btn-delete' : 'btn btn-primary'}
          onClick={onConfirm}
          disabled={confirmDisabled}
        >
          {confirmLabel}
        </button>
      </div>
    </Modal>
  );
}
