import { createContext, useContext, useState, useCallback, useRef } from 'react'

export type ToastType = 'success' | 'error' | 'info' | 'warning'

interface Toast {
  id: number
  type: ToastType
  message: string
  undoAction?: () => void
  undoLabel?: string
}

interface ToastContextValue {
  toasts: Toast[]
  addToast: (message: string, type?: ToastType, undoAction?: () => void, undoLabel?: string) => void
  removeToast: (id: number) => void
}

const ToastContext = createContext<ToastContextValue | null>(null)

const MAX_TOASTS = 3
const TOAST_DURATION = 5000
const UNDO_DURATION = 5000

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])
  const timers = useRef<Map<number, ReturnType<typeof setTimeout>>>(new Map())
  const pausedIds = useRef<Set<number>>(new Set())

  const removeToast = useCallback((id: number) => {
    const timer = timers.current.get(id)
    if (timer) {
      clearTimeout(timer)
      timers.current.delete(id)
    }
    setToasts(prev => prev.filter(t => t.id !== id))
  }, [])

  const addToast = useCallback((
    message: string,
    type: ToastType = 'info',
    undoAction?: () => void,
    undoLabel = 'Отменить'
  ) => {
    setToasts(prev => {
      // De-duplicate: if same message exists, skip
      if (prev.some(t => t.message === message)) return prev

      const id = Date.now() + Math.random()
      const newToasts = [...prev, { id, type, message, undoAction, undoLabel }]

      // Keep only last N toasts, remove oldest
      const trimmed = newToasts.slice(-MAX_TOASTS)

      // Clear timers for removed toasts
      trimmed.forEach((t) => {
        const oldTimer = timers.current.get(t.id)
        if (oldTimer) {
          clearTimeout(oldTimer)
          timers.current.delete(t.id)
        }
        if (!pausedIds.current.has(t.id)) {
          const timer = setTimeout(() => removeToast(t.id), TOAST_DURATION)
          timers.current.set(t.id, timer)
        }
      })

      return trimmed
    })

    // Set up undo timer
    if (undoAction) {
      const undoTimer = setTimeout(() => {
        // Clear the undo action so the button won't work after timeout
        setToasts(prev =>
          prev.map(t =>
            t.id === (Date.now() + Math.random()) ? { ...t, undoAction: undefined } : t
          )
        )
      }, UNDO_DURATION)
      timers.current.set(Date.now() + Math.random(), undoTimer)
    }
  }, [removeToast])

  const handleUndo = useCallback((toast: Toast) => {
    if (toast.undoAction) {
      toast.undoAction()
    }
    // Clear the auto-dismiss timer
    const timer = timers.current.get(toast.id)
    if (timer) {
      clearTimeout(timer)
      timers.current.delete(toast.id)
    }
    removeToast(toast.id)
  }, [removeToast])

  const pauseToast = useCallback((id: number) => {
    const timer = timers.current.get(id)
    if (timer) {
      clearTimeout(timer)
      pausedIds.current.add(id)
    }
  }, [])

  const resumeToast = useCallback((id: number) => {
    pausedIds.current.delete(id)
    const timer = setTimeout(() => removeToast(id), TOAST_DURATION)
    timers.current.set(id, timer)
  }, [removeToast])

  return (
    <ToastContext.Provider value={{ toasts, addToast, removeToast }}>
      {children}
      <div className="toast-container">
        {toasts.map((toast) => (
          <div
            key={toast.id}
            className={`toast toast-${toast.type}`}
            onMouseEnter={() => pauseToast(toast.id)}
            onMouseLeave={() => resumeToast(toast.id)}
            onClick={(e) => {
              // Don't remove if clicking undo button
              if ((e.target as HTMLElement).className === 'toast-undo') return
              removeToast(toast.id)
            }}
          >
            <span className="toast-icon">
              {toast.type === 'success' && '✅'}
              {toast.type === 'error' && '❌'}
              {toast.type === 'info' && 'ℹ️'}
              {toast.type === 'warning' && '⚠️'}
            </span>
            <span className="toast-message">{toast.message}</span>
            {toast.undoAction && (
              <button
                className="toast-undo"
                onClick={(e) => {
                  e.stopPropagation()
                  handleUndo(toast)
                }}
              >
                {toast.undoLabel}
              </button>
            )}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}

export function useToast() {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToast must be used inside ToastProvider')
  return ctx
}
