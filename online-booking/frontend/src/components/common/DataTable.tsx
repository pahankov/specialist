import { useCallback, useLayoutEffect, useRef, useState } from 'react';
import {
  flexRender,
  getCoreRowModel,
  useReactTable,
  type ColumnDef,
  type VisibilityState,
} from '@tanstack/react-table';

/**
 * Shared admin table: columns fit their content by default, stay resizable
 * and hideable — one component for every summary table, no more per-page
 * width wars.
 *
 * - Auto-fit: on mount (and when data/columns change) every column without
 *   a stored width is measured in the DOM (header + sampled body cells)
 *   and clamped to [minWidth, maxWidth]. Content fits a priori.
 * - Manual resize via the right-edge handle, persisted in localStorage
 *   (key `colwidths:<tableId>` — same as the legacy ResizableTh, so old
 *   user layouts carry over).
 * - "Столбцы" menu: show/hide columns (persisted as `colvis:<tableId>`)
 *   plus a one-click layout reset.
 * - Sticky header, horizontal scroll, ellipsis + title tooltips.
 */
export interface FitColumnMeta {
  /** Floor for auto-fit and manual resize (default 64). */
  minWidth?: number;
  /** Ceiling for auto-fit (default 420). Manual resize can exceed it. */
  maxWidth?: number;
  /** Width used when measuring is impossible (jsdom) or as dbl-click reset. */
  defaultWidth?: number;
  /** Show in the "Столбцы" menu (default true). */
  hideable?: boolean;
  /** No resize handle, width pinned to defaultWidth (checkbox columns). */
  resizable?: boolean;
  /** Label in the "Столбцы" menu (default: header text or column id). */
  label?: string;
}

export type FitColumnDef<T> = ColumnDef<T> & {
  meta?: FitColumnMeta;
};

interface DataTableProps<T> {
  tableId: string;
  columns: FitColumnDef<T>[];
  data: T[];
  /** Rows sampled per column for auto-fit (default 50). */
  fitSample?: number;
}

const FALLBACK_MIN = 64;
const FALLBACK_MAX = 420;
const FALLBACK_DEFAULT = 140;

function readStored<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key);
    if (raw) return { ...(fallback as object), ...JSON.parse(raw) } as T;
  } catch {
    /* private mode */
  }
  return fallback;
}

function writeStored(key: string, value: object) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    /* ignore */
  }
}

/** Canvas text measurement for header fallback (jsdom-safe). */
function measureText(text: string): number {
  try {
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');
    if (!ctx) return text.length * 8;
    return ctx.measureText(text).width;
  } catch {
    return text.length * 8;
  }
}

export default function DataTable<T>({
  tableId,
  columns,
  data,
  fitSample = 50,
}: DataTableProps<T>) {
  const widthsKey = `colwidths:${tableId}`;
  const visKey = `colvis:${tableId}`;
  const wrapRef = useRef<HTMLDivElement>(null);
  const userSized = useRef<Set<string>>(
    // Seed synchronously (not in an effect): auto-fit runs in a layout
    // effect and must never override widths restored from storage.
    new Set(Object.keys(readStored<Record<string, number>>(widthsKey, {}))),
  );
  const fittedSig = useRef<string>('');
  const dragMoved = useRef(false);
  const [menuOpen, setMenuOpen] = useState(false);

  const [columnSizing, setColumnSizing] = useState<Record<string, number>>(() =>
    readStored<Record<string, number>>(widthsKey, {}),
  );
  const [columnVisibility, setColumnVisibility] = useState<VisibilityState>(() =>
    readStored<VisibilityState>(visKey, {}),
  );

  const table = useReactTable({
    data,
    columns,
    state: { columnSizing, columnVisibility },
    onColumnSizingChange: (updater) => {
      setColumnSizing((prev) => {
        const next = typeof updater === 'function' ? updater(prev) : updater;
        writeStored(widthsKey, next);
        return next;
      });
    },
    onColumnVisibilityChange: (updater) => {
      setColumnVisibility((prev) => {
        const next = typeof updater === 'function' ? updater(prev) : updater;
        writeStored(visKey, next);
        return next;
      });
    },
    columnResizeMode: 'onChange',
    getCoreRowModel: getCoreRowModel(),
    enableSorting: false,
  });

  // Auto-fit columns that the user never sized manually.
  // Fixed (resizable:false) columns always take their defaultWidth.
  useLayoutEffect(() => {
    const sig = `${tableId}|${columns.map((c) => c.id).join(',')}|${data.length}`;
    if (sig === fittedSig.current) return;
    fittedSig.current = sig;
    const root = wrapRef.current;
    if (!root) return;

    const next: Record<string, number> = {};
    for (const col of table.getAllLeafColumns()) {
      if (!col.getIsVisible()) continue;
      if (userSized.current.has(col.id)) continue;
      const meta = (col.columnDef as FitColumnDef<T>).meta ?? {};
      if (meta.resizable === false) {
        next[col.id] = meta.defaultWidth ?? meta.minWidth ?? FALLBACK_DEFAULT;
        continue;
      }
      const min = meta.minWidth ?? FALLBACK_MIN;
      const max = meta.maxWidth ?? FALLBACK_MAX;
      const fallback = meta.defaultWidth ?? FALLBACK_DEFAULT;

      let best = 0;
      const head = root.querySelector(`th[data-col="${col.id}"]`);
      if (head) best = Math.max(best, head.scrollWidth);
      const cells = root.querySelectorAll(`td[data-col="${col.id}"]`);
      const n = Math.min(cells.length, fitSample);
      for (let i = 0; i < n; i++) {
        best = Math.max(best, (cells[i] as HTMLElement).scrollWidth);
      }
      if (best <= 0) {
        // No layout (jsdom/tests): estimate from header text.
        const label = typeof col.columnDef.header === 'string' ? col.columnDef.header : col.id;
        best = measureText(label) + 32;
      }
      next[col.id] = Math.round(Math.min(max, Math.max(min, best || fallback)));
    }
    if (Object.keys(next).length > 0) {
      setColumnSizing((prev) => {
        const merged = { ...prev, ...next };
        writeStored(widthsKey, merged);
        return merged;
      });
    }
  }, [tableId, columns, data]);

  const resetLayout = useCallback(() => {
    userSized.current = new Set();
    fittedSig.current = '';
    setColumnSizing({});
    setColumnVisibility({});
    try {
      localStorage.removeItem(widthsKey);
      localStorage.removeItem(visKey);
    } catch {
      /* ignore */
    }
    setMenuOpen(false);
  }, [widthsKey, visKey]);

  // Derived fresh every render from props + state: memoizing column
  // objects from a previous table instance shows stale checkboxes
  // (the "menu does nothing" bug) because they read old state.
  const hideable = table
    .getAllLeafColumns()
    .filter((c) => ((c.columnDef as FitColumnDef<T>).meta ?? {}).hideable !== false);

  const menuLabel = (colId: string): string => {
    const col = table.getColumn(colId);
    const meta = (col?.columnDef as FitColumnDef<T> | undefined)?.meta ?? {};
    if (meta.label) return meta.label;
    const h = col?.columnDef.header;
    return typeof h === 'string' ? h : colId;
  };

  const isVisible = (colId: string): boolean => columnVisibility[colId] !== false;

  const setVisible = (colId: string, v: boolean) => {
    setColumnVisibility((prev) => {
      const next = { ...prev, [colId]: v };
      writeStored(visKey, next);
      return next;
    });
  };

  const total = table.getTotalSize();

  return (
    <div className="datatable-wrap" ref={wrapRef}>
      <div className="datatable-toolbar">
        <div className="datatable-menu-anchor">
          <button
            type="button"
            className="btn btn-sm btn-ghost"
            onClick={() => setMenuOpen((v) => !v)}
            title="Показать/скрыть столбцы"
          >
            🧾 Столбцы
          </button>
          {menuOpen && (
            <div className="datatable-menu" role="menu">
              {hideable.map((c) => (
                <label key={c.id} className="datatable-menu-item">
                  <input
                    type="checkbox"
                    checked={isVisible(c.id)}
                    onChange={(e) => setVisible(c.id, e.target.checked)}
                  />
                  {menuLabel(c.id)}
                </label>
              ))}
              <button type="button" className="btn btn-sm btn-ghost" onClick={resetLayout}>
                ↺ Сбросить layout
              </button>
            </div>
          )}
        </div>
      </div>
      <div style={{ overflowX: 'auto' }}>
        {/* Exact total width: freed space must NOT redistribute to other
            columns (the "shrinking col 3 grows col 1" bug). */}
        <table className="datatable" style={{ width: total }}>
          <thead>
            {table.getHeaderGroups().map((hg) => (
              <tr key={hg.id}>
                {hg.headers.map((h) => {
                  const meta = (h.column.columnDef as FitColumnDef<T>).meta ?? {};
                  const size = h.getSize();
                  return (
                    <th
                      key={h.id}
                      data-col={h.column.id}
                      style={{ width: size, minWidth: size, maxWidth: size }}
                      title={
                        typeof h.column.columnDef.header === 'string'
                          ? h.column.columnDef.header
                          : undefined
                      }
                      // A resize drag must not trigger header sorting.
                      onClickCapture={(e) => {
                        if (dragMoved.current) {
                          e.stopPropagation();
                          e.preventDefault();
                          dragMoved.current = false;
                        }
                      }}
                    >
                      {flexRender(h.column.columnDef.header, h.getContext())}
                      {meta.resizable !== false && (
                        <span
                          className="col-resizer"
                          onMouseDown={(e) => {
                            userSized.current.add(h.column.id);
                            dragMoved.current = false;
                            const x0 = e.clientX;
                            const onMove = (ev: MouseEvent) => {
                              if (Math.abs(ev.clientX - x0) > 3) dragMoved.current = true;
                            };
                            const onUp = () => {
                              window.removeEventListener('mousemove', onMove);
                              window.removeEventListener('mouseup', onUp);
                            };
                            window.addEventListener('mousemove', onMove);
                            window.addEventListener('mouseup', onUp);
                            h.getResizeHandler()(e);
                          }}
                          onDoubleClick={(e) => {
                            e.stopPropagation();
                            userSized.current.delete(h.column.id);
                            fittedSig.current = '';
                            const fallback = meta.defaultWidth ?? meta.minWidth ?? FALLBACK_DEFAULT;
                            setColumnSizing((prev) => {
                              const next = { ...prev, [h.column.id]: fallback };
                              writeStored(widthsKey, next);
                              return next;
                            });
                          }}
                          title="Потяните, чтобы изменить ширину (двойной клик — сброс)"
                          aria-hidden
                        />
                      )}
                    </th>
                  );
                })}
              </tr>
            ))}
          </thead>
          <tbody>
            {table.getRowModel().rows.map((row) => (
              <tr key={row.id}>
                {row.getVisibleCells().map((cell) => (
                  <td
                    key={cell.id}
                    data-col={cell.column.id}
                    title={
                      typeof cell.getValue() === 'string' ? (cell.getValue() as string) : undefined
                    }
                  >
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
