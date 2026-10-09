import { useState, type Dispatch, type SetStateAction } from 'react'

/**
 * useState persisted to sessionStorage: filter state survives tab switches
 * (route unmounts) but resets when the browser tab closes. JSON-serializable
 * values only.
 */
export function usePersistentState<T>(
  key: string,
  initial: T,
): [T, Dispatch<SetStateAction<T>>] {
  const [value, setValue] = useState<T>(() => {
    try {
      const raw = sessionStorage.getItem(`ui:${key}`)
      if (raw != null) return JSON.parse(raw) as T
    } catch { /* private mode or corrupt — fall back to initial */ }
    return initial
  })

  const set: Dispatch<SetStateAction<T>> = (v) => {
    setValue(prev => {
      const next = typeof v === 'function' ? (v as (p: T) => T)(prev) : v
      try {
        sessionStorage.setItem(`ui:${key}`, JSON.stringify(next))
      } catch { /* ignore */ }
      return next
    })
  }

  return [value, set]
}
