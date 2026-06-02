import type { ReactNode } from 'react';

import { AuthGuard } from '@/components/shell/AuthGuard';
import { Sidebar } from '@/components/shell/Sidebar';
import { Topbar } from '@/components/shell/Topbar';

/**
 * Post-login shell — sidebar + topbar + content slot.
 *
 * Wrapped in `<AuthGuard>` so any anonymous visit redirects to
 * `/login` before the children mount. Layouts in this group share
 * the global `<Providers>` from the root layout (auth bridge, query
 * client) — no nested provider needed.
 */
export default function AppLayout({ children }: { children: ReactNode }) {
  return (
    <AuthGuard>
      <div className="flex min-h-screen bg-void">
        <Sidebar />
        <div className="flex min-h-screen flex-1 flex-col">
          <Topbar />
          <main className="flex-1 px-6 py-8">
            <div className="mx-auto max-w-6xl">{children}</div>
          </main>
        </div>
      </div>
    </AuthGuard>
  );
}
