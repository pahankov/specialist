import { useState, useRef, useEffect } from 'react';
import { createPortal } from 'react-dom';
import './SharedComponents.css';

interface TooltipProps {
  content: string;
  position?: 'top' | 'bottom' | 'left' | 'right';
  children: React.ReactNode;
  delay?: number;
}

const MAX_W = 320;
const GAP = 10;

/**
 * Tooltip rendered into document.body (portal + position:fixed), so no
 * clipping ancestor (overflow:hidden cells, scrolled table wrappers) can
 * cut the text off. Long texts wrap instead of running off-screen.
 */
export default function Tooltip({
  content,
  position = 'top',
  children,
  delay = 200,
}: TooltipProps) {
  const [visible, setVisible] = useState(false);
  const [coords, setCoords] = useState<{ top: number; left: number } | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout>>();
  const triggerRef = useRef<HTMLDivElement>(null);

  const place = () => {
    const el = triggerRef.current;
    if (!el) return;
    const r = el.getBoundingClientRect();
    const w = Math.min(MAX_W, window.innerWidth - 16);
    let top = 0;
    let left = 0;
    if (position === 'bottom') {
      top = r.bottom + GAP;
      left = Math.min(Math.max(8, r.left + r.width / 2 - w / 2), window.innerWidth - w - 8);
    } else if (position === 'left') {
      top = Math.max(8, r.top + r.height / 2 - 20);
      left = Math.max(8, r.left - w - GAP);
    } else if (position === 'right') {
      top = Math.max(8, r.top + r.height / 2 - 20);
      left = Math.min(window.innerWidth - w - 8, r.right + GAP);
    } else {
      top = Math.max(8, r.top - GAP);
      left = Math.min(Math.max(8, r.left + r.width / 2 - w / 2), window.innerWidth - w - 8);
    }
    setCoords({ top, left });
  };

  const show = () => {
    timerRef.current = setTimeout(() => {
      place();
      setVisible(true);
    }, delay);
  };

  const hide = () => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
    }
    setVisible(false);
    setCoords(null);
  };

  useEffect(() => {
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, []);

  // Keep the bubble glued while scrolling/resizing underneath it.
  useEffect(() => {
    if (!visible) return;
    const sync = () => place();
    window.addEventListener('scroll', sync, true);
    window.addEventListener('resize', sync);
    return () => {
      window.removeEventListener('scroll', sync, true);
      window.removeEventListener('resize', sync);
    };
  }, [visible]);

  return (
    <div
      ref={triggerRef}
      className="tooltip-trigger"
      onMouseEnter={show}
      onMouseLeave={hide}
      onFocus={show}
      onBlur={hide}
      tabIndex={0}
    >
      {children}
      {visible &&
        coords &&
        createPortal(
          <div
            className={`tooltip-portal tooltip-portal-${position}`}
            style={{ top: coords.top, left: coords.left, maxWidth: MAX_W }}
            role="tooltip"
          >
            {content}
          </div>,
          document.body,
        )}
    </div>
  );
}
