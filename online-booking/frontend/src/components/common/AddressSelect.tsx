import { useEffect, useRef, useState, type CSSProperties } from 'react';
import { createPortal } from 'react-dom';
import { dadataApi } from '../../api/dadata';
import './SelectDropdown.css';

interface AddressSelectProps {
  value: string;
  onChange: (address: string, city?: string) => void;
  label?: string;
  placeholder?: string;
  required?: boolean;
  style?: CSSProperties;
}

/** Cabinet address picker: DaData suggest/address via the backend proxy
 * (secret never leaves the server). Plain string value, debounced search. */
export default function AddressSelect({
  value,
  onChange,
  label = 'Адрес кабинета',
  placeholder = 'Начните вводить адрес...',
  required = false,
  style,
}: AddressSelectProps) {
  const [rows, setRows] = useState<{ value: string; city?: string }[]>([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [dropPos, setDropPos] = useState({ top: 0, left: 0, width: 0 });
  const boxRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const dropRef = useRef<HTMLDivElement>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const seq = useRef(0);

  useEffect(() => {
    const onDown = (e: MouseEvent) => {
      const t = e.target as Node;
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

  const place = () => {
    if (inputRef.current) {
      const rect = inputRef.current.getBoundingClientRect();
      setDropPos({ top: rect.bottom + 4, left: rect.left, width: rect.width });
    }
  };

  const search = (text: string) => {
    onChange(text);
    if (timer.current) clearTimeout(timer.current);
    if (text.trim().length < 3) {
      setRows([]);
      setOpen(false);
      setLoading(false);
      return;
    }
    setLoading(true);
    const cur = ++seq.current;
    timer.current = setTimeout(async () => {
      const found = await dadataApi.searchAddresses(text.trim(), 8);
      if (cur !== seq.current) return;
      setRows(found);
      setLoading(false);
      place();
      setOpen(true);
    }, 400);
  };

  const pick = (row: { value: string; city?: string }) => {
    onChange(row.value, row.city);
    setRows([]);
    setOpen(false);
    if (timer.current) clearTimeout(timer.current);
  };

  return (
    <div className="master-select" ref={boxRef} style={style}>
      {label ? <label className="master-select-label">{label}</label> : null}
      <div className="master-select-box">
        <input
          ref={inputRef}
          type="text"
          value={value}
          onChange={(e) => search(e.target.value)}
          onFocus={() => {
            if (rows.length > 0) {
              place();
              setOpen(true);
            }
          }}
          placeholder={placeholder}
          className="master-select-input"
          aria-label={label}
          required={required && value.trim() === ''}
        />
        {value && (
          <button
            type="button"
            className="master-select-clear"
            aria-label="Сбросить"
            onClick={() => {
              onChange('');
              setRows([]);
              setOpen(false);
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
            ) : rows.length === 0 ? (
              <div className="master-select-empty">
                Ничего не найдено — можно ввести адрес вручную
              </div>
            ) : (
              rows.map((r) => (
                <div
                  key={r.value}
                  className="master-select-item"
                  onClick={() => pick(r)}
                  role="option"
                  aria-selected={false}
                >
                  <span className="master-select-name">{r.value}</span>
                </div>
              ))
            )}
          </div>,
          document.body,
        )}
    </div>
  );
}
