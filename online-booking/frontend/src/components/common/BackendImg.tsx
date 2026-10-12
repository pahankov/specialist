import { useEffect, useState } from 'react';

interface BackendImgProps {
  src?: string | null;
  alt: string;
  className?: string;
  /** Placeholder glyph when missing or failed (no more silent voids). */
  fallbackEmoji?: string;
  title?: string;
}

/**
 * Backend-served image with an explicit fallback: a missing/deleted file
 * renders a placeholder (and warns in console) instead of a broken icon
 * or an empty void nobody can diagnose.
 */
function BackendImg({ src, alt, className, fallbackEmoji = '🖼️', title }: BackendImgProps) {
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    setFailed(false);
  }, [src]);

  if (!src || failed) {
    if (src && failed) {
      // eslint-disable-next-line no-console
      console.warn(`[BackendImg] file not served: ${src}`);
    }
    return (
      <span className={className} role="img" aria-label={alt} title={title || alt}>
        {fallbackEmoji}
      </span>
    );
  }
  return (
    <img src={src} alt={alt} className={className} title={title} onError={() => setFailed(true)} />
  );
}

export default BackendImg;
