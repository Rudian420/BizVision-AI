'use client';

import { useAuth } from '@/hooks/use-auth';

/**
 * Compact top bar — user identity + sign-out.
 *
 * Kept intentionally minimal in wave 1; later waves will add a global
 * command palette, notifications, and module-aware breadcrumbs.
 */
export function Topbar() {
  const { user, logout } = useAuth();

  const initials = (() => {
    const name = user?.full_name?.trim();
    if (name) {
      const parts = name.split(/\s+/);
      const first = parts[0]?.[0] ?? '';
      const last = parts.length > 1 ? parts[parts.length - 1]?.[0] ?? '' : '';
      return (first + last).toUpperCase() || '?';
    }
    return user?.email?.[0]?.toUpperCase() ?? '?';
  })();

  return (
    <header className="flex h-16 items-center justify-between border-b border-white/10 bg-white/[0.02] px-6">
      <h1 className="font-ui text-sm uppercase tracking-widest text-text-secondary">Command Center</h1>

      <div className="flex items-center gap-4">
        <div className="hidden text-right md:block">
          <div className="font-ui text-sm text-text-primary">{user?.full_name || user?.email}</div>
          {user?.full_name && <div className="font-ui text-xs text-text-secondary">{user.email}</div>}
        </div>
        <div
          aria-hidden
          className="flex h-9 w-9 items-center justify-center rounded-full border border-cyan/30 bg-cyan/10 font-ui text-sm font-medium text-cyan"
        >
          {initials}
        </div>
        <button
          type="button"
          onClick={() => {
            void logout();
          }}
          className="rounded-md border border-white/10 px-3 py-1 font-ui text-xs text-text-secondary transition hover:border-coral/40 hover:text-coral"
        >
          Sign out
        </button>
      </div>
    </header>
  );
}
