import { createContext, useContext, useState, useCallback, useRef } from 'react'

export type ToastType = 'success' | 'error' | 'info'

interface Toast {
  id: number
  type: ToastType
  message: string
}

interface ToastContextValue {
  toasts: Toast[]
  addToast: (message: string, type?: ToastType) => void
  removeToast: (id: number) => void
}

const ToastContext = createContext<ToastContextValue | null>(null)

const MAX_TOASTS = 3
const TOAST_DURATION = 5000

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])
  const timers = useRef<Map<number, NodeJS.Timeout>>(new Map())
  const pausedIds = useRef<Set<number>>(new Set())

  const removeToast = useCallback((id: number) => {
    const timer = timers.current.get(id)
    if (timer) {
      clearTimeout(timer)
      timers.current.delete(id)
    }
    setToasts(prev => prev.filter(t => t.id !== id))
  }, [])

  const addToast = useCallback((message: string, type: ToastType = 'info') => {
    setToasts(prev => {
      // De-duplicate: if same message exists, skip
      if (prev.some(t => t.message === message)) return prev

      const id = Date.now() + Math.random()
      const newToasts = [...prev, { id, type, message }]

      // Keep only last N toasts, remove oldest
      const trimmed = newToasts.slice(-MAX_TOASTS)

      // Clear timers for removed toasts
      trimmed.forEach((t, i) => {
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
            onClick={() => removeToast(toast.id)}
          >
            <span className="toast-icon">
              {toast.type === 'success' && '✅'}
              {toast.type === 'error' && '❌'}
              {toast.type === 'info' && 'ℹ️'}
            </span>
            <span className="toast-message">{toast.message}</span>
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
