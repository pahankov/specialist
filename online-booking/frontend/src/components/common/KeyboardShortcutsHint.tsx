import { useEffect, useState } from 'react'
import './SharedComponents.css'

interface KeyboardShortcutsHintProps {
  onSearch?: () => void
}

export default function KeyboardShortcutsHint({ onSearch }: KeyboardShortcutsHintProps) {
  const [showHint, setShowHint] = useState(false)
  const [searchOpen, setSearchOpen] = useState(false)

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Ctrl+K or Cmd+K for search
      if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault()
        if (onSearch) {
          onSearch()
        } else {
          setSearchOpen(true)
          setShowHint(false)
        }
      }

      // Escape to close modals/search
      if (e.key === 'Escape') {
        setSearchOpen(false)
        setShowHint(false)
      }

      // ? to show keyboard shortcuts hint
      if (e.key === '?' && !e.ctrlKey && !e.metaKey) {
        const target = e.target as HTMLElement
        if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA') return
        setShowHint(prev => !prev)
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [onSearch])

  if (!showHint && !searchOpen) return null

  return (
    <>
      {/* Backdrop */}
      <div className="keyboard-hint-backdrop" onClick={() => { setShowHint(false); setSearchOpen(false) }} />

      {/* Search modal */}
      {searchOpen && (
        <div className="search-modal">
          <div className="search-modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="search-input-wrapper">
              <span className="search-icon">🔍</span>
              <input
                type="text"
                className="search-input"
                placeholder="Поиск..."
                autoFocus
                onKeyDown={(e) => {
                  if (e.key === 'Escape') setSearchOpen(false)
                }}
              />
              <button className="search-close" onClick={() => setSearchOpen(false)}>
                Esc
              </button>
            </div>
            <div className="search-hint">
              <span>Нажмите <kbd>Esc</kbd> для закрытия</span>
            </div>
          </div>
        </div>
      )}

      {/* Keyboard shortcuts hint */}
      {showHint && (
        <div className="keyboard-hint-modal">
          <div className="keyboard-hint-content" onClick={(e) => e.stopPropagation()}>
            <h3>⌨️ Горячие клавиши</h3>
            <div className="shortcut-list">
              <div className="shortcut-item">
                <kbd>Ctrl</kbd> + <kbd>K</kbd>
                <span>Открыть поиск</span>
              </div>
              <div className="shortcut-item">
                <kbd>Esc</kbd>
                <span>Закрыть модальное окно</span>
              </div>
              <div className="shortcut-item">
                <kbd>?</kbd>
                <span>Показать подсказку</span>
              </div>
            </div>
            <button className="btn btn-ghost btn-close-hint" onClick={() => setShowHint(false)}>
              Закрыть
            </button>
          </div>
        </div>
      )}
    </>
  )
}
