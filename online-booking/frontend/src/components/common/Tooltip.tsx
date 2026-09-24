import { useState, useRef, useEffect } from 'react'
import './SharedComponents.css'

interface TooltipProps {
  content: string
  position?: 'top' | 'bottom' | 'left' | 'right'
  children: React.ReactNode
  delay?: number
}

export default function Tooltip({ content, position = 'top', children, delay = 200 }: TooltipProps) {
  const [visible, setVisible] = useState(false)
  const timerRef = useRef<ReturnType<typeof setTimeout>>()
  const triggerRef = useRef<HTMLDivElement>(null)

  const show = () => {
    timerRef.current = setTimeout(() => setVisible(true), delay)
  }

  const hide = () => {
    if (timerRef.current) {
      clearTimeout(timerRef.current)
    }
    setVisible(false)
  }

  useEffect(() => {
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current)
    }
  }, [])

  const positionClass = `tooltip-${position}`

  return (
    <div
      ref={triggerRef}
      className={`tooltip-trigger ${visible ? 'tooltip-trigger-active' : ''}`}
      onMouseEnter={show}
      onMouseLeave={hide}
      onFocus={show}
      onBlur={hide}
      tabIndex={0}
    >
      {children}
      {visible && (
        <div className={`tooltip tooltip-${positionClass}`}>
          {content}
        </div>
      )}
    </div>
  )
}
