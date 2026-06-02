'use client';

import { useRouter } from 'next/navigation';
import { useEffect, type ReactNode } from 'react';

import { useAuthStore } from '@/lib/store/use-auth-store';

/**
 * Client-side guard for the post-login `(app)` route group.
 *
 * Hydrates the auth store from localStorage on mount, then redirects
 * to `/login` if no session is present. While hydration is in
 * progress we render a placeholder so the dashboard doesn't flash
 * before the redirect fires.
 *
 * This is deliberately *not* a server-side guard — the access token
 * lives in localStorage (per the auth-store comment), which is
 * unavailable on the server. A middleware-level guard would have to
 * read cookies; we'd need to mirror tokens there too, which is more
 * complexity than wave-1 needs. The backend enforces auth on every
 * API call regardless.
 */
type AuthGuardProps = {
  children: ReactNode;
};

export function AuthGuard({ children }: AuthGuardProps) {
  const router = useRouter();
  const hydrate = useAuthStore((s) => s.hydrate);
  const hydrated = useAuthStore((s) => s.hydrated);
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);

  useEffect(() => {
    hydrate();
  }, [hydrate]);

  useEffect(() => {
    if (hydrated && !isAuthenticated) {
      router.replace('/login');
    }
  }, [hydrated, isAuthenticated, router]);

  if (!hydrated || !isAuthenticated) {
    return (
      <div
        role="status"
        aria-live="polite"
        className="flex min-h-screen items-center justify-center bg-void font-ui text-sm text-text-secondary"
      >
        Loading workspace…
      </div>
    );
  }

  return <>{children}</>;
}
