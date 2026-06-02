'use client';

import { QueryClientProvider } from '@tanstack/react-query';
import { ReactQueryDevtools } from '@tanstack/react-query-devtools';
import { type ReactNode, useState } from 'react';

import { installAuthBridge } from '@/lib/auth/bridge';
import { makeQueryClient } from '@/lib/query-client';

// Wire the auth store into the api-client's interceptors at module
// load. `installAuthBridge` is idempotent, so re-runs during fast-
// refresh are harmless. The store stays out of the api-client's
// import graph (avoiding a cycle).
installAuthBridge();

/** App-wide client providers (React Query + devtools in dev). */
export function Providers({ children }: { children: ReactNode }) {
  const [queryClient] = useState(() => makeQueryClient());

  return (
    <QueryClientProvider client={queryClient}>
      {children}
      {process.env.NODE_ENV === 'development' && <ReactQueryDevtools initialIsOpen={false} />}
    </QueryClientProvider>
  );
}
