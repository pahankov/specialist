import { useEffect, useRef, useState, type CSSProperties } from 'react';
import { createPortal } from 'react-dom';
import apiClient from '../../api/http';
import { dadataApi } from '../../api/dadata';
import './SelectDropdown.css';

export interface CityOption {
  id: number | null;
  name: string;
  /** Where the pick came from (dadata picks resolve to a local id on select). */
  source?: 'local' | 'dadata';
}

interface CitySelectProps {
  value: number | null;
  /** Currently selected city name (for display when value set externally). */
  valueName?: string;
  onChange: (city: CityOption | null) => void;
  label?: string;
  required?: boolean;
  style?: CSSProperties;
}

interface Row {
  key: string;
  id: number | null;
  name: string;
  source: 'local' | 'dadata';
}

/**
 * City picker: DaData suggestions first, local DB merged in.
 * A DaData pick with no local match is resolved (get-or-created) via
 * POST /cities/resolve so the master form always gets a real city_id.
 */
export default function CitySelect({
  value,
  valueName = '',
  onChange,
  label = 'Город',
  required = false,
  style,
}: CitySelectProps) {
  const [rows, setRows] = useState<Row[]>([]);
  const [query, setQuery] = useState('');
  const [open, setOpen] = useState(false);
  const [focused, setFocused] = useState(false);
  const [loading, setLoading] = useState(false);
  const [failed, setFailed] = useState(false);
  const [resolving, setResolving] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const seq = useRef(0);
  const boxRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const dropRef = useRef<HTMLDivElement>(null);
  // Viewport-relative coords: the portal uses position:fixed, so NO scroll
  // offsets here (adding scrollY pushed the dropdown off-screen on scroll).
  const [dropPos, setDropPos] = useState({ top: 0, left: 0, width: 0 });

  useEffect(() => {
    const onDown = (e: MouseEvent) => {
      const t = e.target as Node;
      // Portal dropdown lives outside boxRef — don't close when clicking it
      if (
        boxRef.current &&
        !boxRef.current.contains(t) &&
        !(dropRef.current && dropRef.current.contains(t))
      )
        setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false);
    };
    document.addEventListener('mousedown', onDown);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDown);
      document.removeEventListener('keydown', onKey);
      if (timer.current) clearTimeout(timer.current);
    };
  }, []);

  // Keep a fixed-position portal glued under the input while open
  useEffect(() => {
    if (!open) return;
    const place = () => {
      if (inputRef.current) {
        const rect = inputRef.current.getBoundingClientRect();
        setDropPos({ top: rect.bottom + 4, left: rect.left, width: rect.width });
      }
    };
    place();
    window.addEventListener('scroll', place, true);
    window.addEventListener('resize', place);
    return () => {
      window.removeEventListener('scroll', place, true);
      window.removeEventListener('resize', place);
    };
  }, [open]);

  const openDropdown = () => {
    if (inputRef.current) {
      const rect = inputRef.current.getBoundingClientRect();
      setDropPos({ top: rect.bottom + 4, left: rect.left, width: rect.width });
    }
    setOpen(true);
  };

  const search = (text: string) => {
    setQuery(text);
    setFailed(false);
    if (timer.current) clearTimeout(timer.current);
    if (text.trim().length < 2) {
      setRows([]);
      setLoading(false);
      setOpen(false);
      return;
    }
    setLoading(true);
    const cur = ++seq.current;
    timer.current = setTimeout(async () => {
      try {
        const q = text.trim();
        let dadata: { city?: string; value: string }[] = [];
        let dadataOk = true;
        let localRes: { id: number; name_ru: string }[] = [];
        let localOk = true;
        try {
          dadata = await dadataApi.searchCities(q, 7);
        } catch {
          dadataOk = false;
        }
        try {
          const r = await apiClient.get('/api/v1/cities/search/', { params: { q, limit: 10 } });
          localRes = (Array.isArray(r.data) ? r.data : []) as { id: number; name_ru: string }[];
        } catch {
          localOk = false;
        }
        if (cur !== seq.current) return;
        if (!dadataOk && !localOk) {
          setRows([]);
          setFailed(true);
          openDropdown();
          return;
        }
        const seen = new Set<string>();
        const merged: Row[] = [];
        for (const c of localRes) {
          const key = c.name_ru.toLowerCase();
          if (seen.has(key)) continue;
          seen.add(key);
          merged.push({ key: `local-${c.id}`, id: c.id, name: c.name_ru, source: 'local' });
        }
        for (const s of dadata) {
          const name = (s.city || s.value || '').trim();
          if (!name) continue;
          const key = name.toLowerCase();
          if (seen.has(key)) continue;
          seen.add(key);
          merged.push({ key: `dadata-${key}`, id: null, name, source: 'dadata' });
        }
        setRows(merged);
        setFailed(false);
        openDropdown();
      } catch {
        if (cur === seq.current) {
          setRows([]);
          setFailed(true);
          openDropdown();
        }
      } finally {
        if (cur === seq.current) setLoading(false);
      }
    }, 350);
  };

  const pick = async (row: Row) => {
    if (row.id != null) {
      onChange({ id: row.id, name: row.name, source: row.source });
      setQuery('');
      setRows([]);
      setOpen(false);
      return;
    }
    // DaData-only pick: resolve to a local id (get-or-create on the server)
    setResolving(true);
    try {
      const { data } = await apiClient.post('/api/v1/cities/resolve', { name: row.name });
      onChange({ id: data.id, name: data.name_ru ?? row.name, source: 'dadata' });
      setQuery('');
      setRows([]);
      setOpen(false);
    } catch {
      setFailed(true);
    } finally {
      setResolving(false);
    }
  };

  const selectedName = value != null ? valueName || '' : '';
  // While focused (or open) always show the live query — otherwise typed
  // characters are swallowed (input would render selectedName instead).
  const shown = focused || open ? query : selectedName;

  return (
    <div className="master-select" ref={boxRef} style={style}>
      {label ? (
        <label className="master-select-label">
          {label} {required && '*'}
        </label>
      ) : null}
      <div className="master-select-box">
        <input
          ref={inputRef}
          type="text"
          value={shown}
          onChange={(e) => {
            search(e.target.value);
            if (value != null) onChange(null);
          }}
          onFocus={() => {
            setFocused(true);
            // Restore the selected name as editable text when focusing a set value
            if (value != null && query === '') setQuery(selectedName);
            else if (query.trim().length >= 2) openDropdown();
          }}
          onBlur={() => setFocused(false)}
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
            onClick={() => {
              setQuery('');
              setRows([]);
              setOpen(false);
              setFailed(false);
              onChange(null);
            }}
          >
            ✕
          </button>
        )}
      </div>
      {open &&
        createPortal(
          <div
            ref={dropRef}
            className="master-select-dropdown"
            role="listbox"
            style={{
              position: 'fixed',
              top: dropPos.top,
              left: dropPos.left,
              width: dropPos.width,
              zIndex: 99999,
            }}
          >
            {loading ? (
              <div className="master-select-empty">Поиск…</div>
            ) : failed ? (
              <div className="master-select-empty">
                Не удалось загрузить города. Проверьте соединение.
              </div>
            ) : resolving ? (
              <div className="master-select-empty">Привязываем город…</div>
            ) : rows.length === 0 ? (
              <div className="master-select-empty">
                {query.trim().length >= 2 ? 'Ничего не найдено' : 'Введите минимум 2 буквы'}
              </div>
            ) : (
              rows.map((r) => (
                <div
                  key={r.key}
                  className="master-select-item"
                  onClick={() => pick(r)}
                  role="option"
                  aria-selected={false}
                >
                  <span className="master-select-name">{r.name}</span>
                  {r.source === 'dadata' && <span className="master-select-tariff">🌐 DaData</span>}
                </div>
              ))
            )}
          </div>,
          document.body,
        )}
    </div>
  );
}
