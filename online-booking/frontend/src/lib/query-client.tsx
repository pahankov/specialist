import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useState } from 'react';

/**
 * Create a QueryClient with sensible defaults.
 *
 * - staleTime: 5 min — data is considered fresh for 5 minutes,
 *   reducing unnecessary refetches on tab switches.
 * - gcTime: 30 min — cached data is kept for 30 minutes before GC.
 */
function createQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 5 * 60 * 1000,
        gcTime: 30 * 60 * 1000,
        retry: 1,
        refetchOnWindowFocus: false,
      },
    },
  });
}

let browserQueryClient: QueryClient | undefined = undefined;

function getQueryClient() {
  if (typeof window === 'undefined') {
    // Server: always create a new QueryClient
    return createQueryClient();
  }
  // Browser: use singleton
  if (!browserQueryClient) {
    browserQueryClient = createQueryClient();
  }
  return browserQueryClient;
}

export function QueryProvider({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(getQueryClient);

  return (
    <QueryClientProvider client={queryClient}>
      {children}
      {/* Devtools only in development */}
      {/* ReactQueryDevtools available via `npm i -D @tanstack/react-query-devtools` */}
    </QueryClientProvider>
  );
}
