import { useEffect, useMemo, useRef, useState, type CSSProperties } from 'react'
import { superAdminApi } from '../../api/client'
import './SelectDropdown.css'

export interface MasterOption {
  id: number
  name: string
  is_active?: boolean
  tariff?: string
}

interface MasterSelectProps {
  value: number | ''
  onChange: (id: number | '') => void
  label?: string
  /** Show "Все мастера" reset option. Default true. */
  allowAll?: boolean
  allLabel?: string
  masters?: MasterOption[]
  style?: CSSProperties
}

let cachedMasters: MasterOption[] | null = null

/** Master picker with live name filtering (replaces 4 copy-pasted selects). */
export default function MasterSelect({
  value,
  onChange,
  label = 'Мастер',
  allowAll = true,
  allLabel = 'Все мастера',
  masters: mastersProp,
  style,
}: MasterSelectProps) {
  const [masters, setMasters] = useState<MasterOption[]>(mastersProp ?? cachedMasters ?? [])
  const [query, setQuery] = useState('')
  const [open, setOpen] = useState(false)
  const boxRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (mastersProp) {
      setMasters(mastersProp)
      return
    }
    if (cachedMasters) {
      setMasters(cachedMasters)
      return
    }
    let cancelled = false
    superAdminApi.getAllMasters()
      .then(r => {
        if (cancelled) return
        const list = (r.data as MasterOption[]).map(m => ({
          id: m.id, name: m.name, is_active: m.is_active, tariff: m.tariff,
        }))
        cachedMasters = list
        setMasters(list)
      })
      .catch(() => { /* ignore: empty list */ })
    return () => { cancelled = true }
  }, [mastersProp])

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
    }
  }, [])

  const selected = masters.find(m => m.id === value) ?? null
  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) return masters
    return masters.filter(m => m.name.toLowerCase().includes(q))
  }, [masters, query])

  const pick = (id: number | '') => {
    onChange(id)
    setQuery('')
    setOpen(false)
  }

  return (
    <div className="master-select" ref={boxRef} style={style}>
      <label className="master-select-label">{label}</label>
      <div className="master-select-box">
        <input
          type="text"
          value={open ? query : (selected?.name ?? '')}
          onChange={(e) => { setQuery(e.target.value); setOpen(true) }}
          onFocus={() => setOpen(true)}
          placeholder={allowAll ? allLabel : 'Выберите мастера...'}
          className="master-select-input"
          aria-label={label}
        />
        {(selected || query) && (
          <button
            type="button"
            className="master-select-clear"
            aria-label="Сбросить"
            onClick={() => pick('')}
          >
            ✕
          </button>
        )}
      </div>
      {open && (
        <div className="master-select-dropdown" role="listbox">
          {allowAll && (
            <div
              className={`master-select-item${value === '' ? ' selected' : ''}`}
              onClick={() => pick('')}
              role="option"
              aria-selected={value === ''}
            >
              {allLabel}
            </div>
          )}
          {filtered.length === 0 ? (
            <div className="master-select-empty">Ничего не найдено</div>
          ) : (
            filtered.map(m => (
              <div
                key={m.id}
                className={`master-select-item${m.id === value ? ' selected' : ''}`}
                onClick={() => pick(m.id)}
                role="option"
                aria-selected={m.id === value}
              >
                <span className={`master-select-dot${m.is_active === false ? ' off' : ''}`} />
                <span className="master-select-name">{m.name}</span>
                {m.tariff && m.tariff !== 'trial' && (
                  <span className="master-select-tariff">{m.tariff}</span>
                )}
              </div>
            ))
          )}
        </div>
      )}
    </div>
  )
}
