import { useRef, useState, type ReactNode, type ThHTMLAttributes } from 'react'

/**
 * Persisted manual column widths. Widths survive reloads via localStorage
 * (key `colwidths:<table>`), so every admin table keeps the user's layout.
 */
export function useColumnWidths(table: string, defaults: Record<string, number>) {
  const [widths, setWidths] = useState<Record<string, number>>(() => {
    try {
      const raw = localStorage.getItem(`colwidths:${table}`)
      if (raw) return { ...defaults, ...JSON.parse(raw) }
    } catch { /* private mode — fall back to defaults */ }
    return defaults
  })

  const setWidth = (col: string, w: number) => {
    setWidths(prev => {
      const next = { ...prev, [col]: Math.max(48, Math.round(w)) }
      try {
        localStorage.setItem(`colwidths:${table}`, JSON.stringify(next))
      } catch { /* ignore */ }
      return next
    })
  }

  const resetWidths = () => {
    setWidths(defaults)
    try {
      localStorage.removeItem(`colwidths:${table}`)
    } catch { /* ignore */ }
  }

  return { widths, setWidth, resetWidths }
}

interface ResizableThProps extends ThHTMLAttributes<HTMLTableCellElement> {
  width: number
  onResize: (w: number) => void
  children?: ReactNode
}

/** Table header cell with a right-edge drag handle for manual resizing. */
export default function ResizableTh({ width, onResize, children, style, onClick, ...rest }: ResizableThProps) {
  const moved = useRef(false)

  const startDrag = (e: React.MouseEvent) => {
    e.preventDefault()
    e.stopPropagation()
    moved.current = false
    const x0 = e.clientX
    const w0 = width
    const onMove = (ev: MouseEvent) => {
      if (Math.abs(ev.clientX - x0) > 3) moved.current = true
      onResize(w0 + ev.clientX - x0)
    }
    const onUp = () => {
      window.removeEventListener('mousemove', onMove)
      window.removeEventListener('mouseup', onUp)
    }
    window.addEventListener('mousemove', onMove)
    window.addEventListener('mouseup', onUp)
  }

  // A drag must not trigger column sort: swallow the click after a move
  const swallowAfterDrag = (e: React.MouseEvent) => {
    if (moved.current) {
      e.stopPropagation()
      e.preventDefault()
      moved.current = false
    }
  }

  return (
    <th {...rest} onClick={onClick} onClickCapture={swallowAfterDrag} style={{ ...style, width, minWidth: width, maxWidth: width }}>
      {children}
      <span
        className="col-resizer"
        onMouseDown={startDrag}
        title="Потяните, чтобы изменить ширину"
        aria-hidden
      />
    </th>
  )
}
