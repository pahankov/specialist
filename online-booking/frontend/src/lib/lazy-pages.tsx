import { Suspense } from 'react';

/**
 * Shared fallback shown while a lazy-loaded page is being fetched.
 * Uses the project's existing skeleton animation.
 */
export function PageLoader() {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        height: '60vh',
        color: '#a0aec0',
        fontSize: '1.1rem',
      }}
    >
      Загрузка...
    </div>
  );
}

/**
 * Wrap a lazy component with Suspense + PageLoader.
 * Usage: <Suspense fallback={<PageLoader />}> {lazyComponent} </Suspense>
 */
export { Suspense };
