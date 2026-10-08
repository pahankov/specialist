import { useEffect, useRef, useState, type CSSProperties } from 'react'
import apiClient from '../../api/http'
import './MasterSelect.css'

export interface CityOption {
  id: number
  name: string
}

interface CitySelectProps {
  value: number | null
  /** Currently selected city name (for display when value set externally). */
  valueName?: string
  onChange: (city: CityOption | null) => void
  label?: string
  required?: boolean
  style?: CSSProperties
}

/** City picker over the local DB (no DaData quota burn). */
export default function CitySelect({
  value,
  valueName = '',
  onChange,
  label = 'Город',
  required = false,
  style,
}: CitySelectProps) {
  const [options, setOptions] = useState<CityOption[]>([])
  const [query, setQuery] = useState('')
  const [open, setOpen] = useState(false)
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const seq = useRef(0)
  const boxRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const onDown = (e: MouseEvent) => {
      if (boxRef.current && !boxRef.current.contains(e.target as Node)) setOpen(false)
    }
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', onDown)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDown)
      document.removeEventListener('keydown', onKey)
      if (timer.current) clearTimeout(timer.current)
    }
  }, [])

  const search = (text: string) => {
    setQuery(text)
    if (timer.current) clearTimeout(timer.current)
    if (text.trim().length < 2) {
      setOptions([])
      setOpen(false)
      return
    }
    const cur = ++seq.current
    timer.current = setTimeout(async () => {
      try {
        const { data } = await apiClient.get('/api/v1/cities/search/', {
          params: { q: text.trim(), limit: 10 },
        })
        if (cur !== seq.current) return
        const list = (Array.isArray(data) ? data : []) as { id: number; name_ru: string }[]
        setOptions(list.map(c => ({ id: c.id, name: c.name_ru })))
        setOpen(true)
      } catch {
        if (cur === seq.current) {
          setOptions([])
          setOpen(false)
        }
      }
    }, 350)
  }

  const selectedName = value != null ? (valueName || options.find(o => o.id === value)?.name || '') : ''

  return (
    <div className="master-select" ref={boxRef} style={style}>
      <label className="master-select-label">
        {label} {required && '*'}
      </label>
      <div className="master-select-box">
        <input
          type="text"
          value={open ? query : selectedName}
          onChange={(e) => {
            search(e.target.value)
            if (value != null) onChange(null)
          }}
          onFocus={() => { if (query.trim().length >= 2) setOpen(true) }}
          placeholder="Начните вводить город..."
          className="master-select-input"
          aria-label={label}
          required={required && value == null}
        />
        {(selectedName || query) && (
          <button
            type="button"
            className="master-select-clear"
            aria-label="Сбросить"
            onClick={() => { setQuery(''); setOptions([]); setOpen(false); onChange(null) }}
          >
            ✕
          </button>
        )}
      </div>
      {open && (
        <div className="master-select-dropdown" role="listbox">
          {options.length === 0 ? (
            <div className="master-select-empty">Ничего не найдено</div>
          ) : (
            options.map(o => (
              <div
                key={o.id}
                className={`master-select-item${o.id === value ? ' selected' : ''}`}
                onClick={() => { onChange(o); setQuery(''); setOptions([]); setOpen(false) }}
                role="option"
                aria-selected={o.id === value}
              >
                <span className="master-select-name">{o.name}</span>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  )
}
