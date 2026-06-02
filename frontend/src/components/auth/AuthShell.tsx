'use client';

import Link from 'next/link';
import type { ReactNode } from 'react';

/**
 * Visual chrome shared by the login + register pages.
 *
 * Renders a centred card on the deep-space background plus a small
 * brand mark + footer link. Keeps the auth pages themselves pure
 * forms.
 */
type AuthShellProps = {
  title: string;
  subtitle: string;
  footer: ReactNode;
  children: ReactNode;
};

export function AuthShell({ title, subtitle, footer, children }: AuthShellProps) {
  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-void px-4 py-12">
      {/* Ambient gradient — cheaper static version of the landing's tier-adaptive bg */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 -z-10"
        style={{
          background:
            'radial-gradient(circle at 30% 20%, rgba(0,245,255,0.08), transparent 50%), radial-gradient(circle at 70% 80%, rgba(255,184,0,0.06), transparent 60%)',
        }}
      />

      <div className="w-full max-w-md">
        <Link
          href="/"
          className="mb-8 inline-flex items-center gap-2 font-ui text-sm text-text-secondary hover:text-cyan"
        >
          <span className="font-data text-cyan">◈</span>
          BizVision AI
        </Link>

        <div className="rounded-2xl border border-white/10 bg-white/[0.02] p-8 shadow-glow-cyan backdrop-blur-sm">
          <h1 className="font-ui text-2xl font-semibold tracking-tight text-text-primary">{title}</h1>
          <p className="mt-1 font-ui text-sm text-text-secondary">{subtitle}</p>

          <div className="mt-6">{children}</div>
        </div>

        <p className="mt-6 text-center font-ui text-sm text-text-secondary">{footer}</p>
      </div>
    </div>
  );
}
