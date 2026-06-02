'use client';

import Link from 'next/link';

import type { ModuleMeta } from '@/lib/modules';

/**
 * Module summary card on the dashboard.
 *
 * Renders the module's accent palette and stat. Clicking navigates
 * to the module's dedicated route — the placeholder pages in wave 1,
 * the full module UIs (FE-011..015) in wave 2.
 */
export function ModuleCard({ module }: { module: ModuleMeta }) {
  return (
    <Link
      href={`/modules/${module.id}`}
      className="group relative flex flex-col rounded-2xl border border-white/10 bg-white/[0.02] p-6 transition hover:border-white/20"
      style={{ boxShadow: `inset 0 1px 0 rgba(255,255,255,0.04)` }}
    >
      <div className="mb-4 flex items-center justify-between">
        <span className="font-data text-2xl" style={{ color: module.accent }}>
          {module.glyph}
        </span>
        <span className="font-ui text-[10px] uppercase tracking-widest text-text-secondary">{module.id}</span>
      </div>

      <h3 className="font-ui text-lg font-semibold text-text-primary">{module.label}</h3>
      <p className="mt-1 font-ui text-sm text-text-secondary">{module.tagline}</p>

      <div className="mt-6 flex items-end justify-between">
        <div>
          <div className="font-data text-2xl font-semibold" style={{ color: module.accent }}>
            {module.stat}
          </div>
          <div className="font-ui text-xs text-text-secondary">{module.statLabel}</div>
        </div>
        <div
          className="font-ui text-xs text-text-secondary opacity-0 transition group-hover:opacity-100"
          style={{ color: module.accent }}
        >
          Open →
        </div>
      </div>
    </Link>
  );
}
