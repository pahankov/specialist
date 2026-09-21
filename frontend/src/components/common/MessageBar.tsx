import React from 'react'
import './SharedComponents.css'

interface MessageBarProps {
  type: 'success' | 'error' | 'warning' | 'info'
  message: string
  onDismiss?: () => void
}

export default function MessageBar({ type, message, onDismiss }: MessageBarProps) {
  if (!message) return null

  return (
    <div className={`message-bar message-${type}`}>
      {message}
      {onDismiss && (
        <button className="message-dismiss" onClick={onDismiss}>×</button>
      )}
    </div>
  )
}
