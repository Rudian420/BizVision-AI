'use client';

import { MODULES, moduleById } from '@/lib/modules';
import { MODULE_ORDER, RISK_TIER_ORDER, formatAuditTimestamp, formatRiskTierLabel } from '@/lib/audits/format';
import type { AuditSummary } from '@/lib/audits/types';
import { toneForRisk } from '@/lib/risk/tones';
import type { RiskLevel } from '@/lib/risk/types';
import { cn } from '@/lib/utils';

type AuditSummaryCardsProps = {
  summary: AuditSummary | undefined;
  isLoading: boolean;
};

/**
 * Three-card summary band: total decisions, per-module histogram,
 * per-risk-tier histogram. Powers the Phase-4 ML Decision Feed page
 * (TASK-030). Pure consumer of `/api/v1/audits/summary`.
 *
 * Visual posture mirrors the module workspaces — coral/cyan/gold
 * accents per module, RiskBadge palette for the risk tiers. Each
 * histogram bar is normalised against the max bucket so the relative
 * shape of the distribution is the headline value.
 */
export function AuditSummaryCards({ summary, isLoading }: AuditSummaryCardsProps) {
  if (isLoading && !summary) {
    return <SummarySkeleton />;
  }

  const total = summary?.total_decisions ?? 0;
  const latest = summary?.latest_decision_at ?? null;

  const moduleCounts = new Map(
    (summary?.by_module ?? []).map((row) => [row.module, row.count]),
  );
  const moduleMax = Math.max(1, ...Array.from(moduleCounts.values()));

  const riskCounts = new Map(
    (summary?.by_risk_tier ?? []).map((row) => [row.risk_tier, row.count]),
  );
  const riskMax = Math.max(1, ...Array.from(riskCounts.values()));

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
      {/* ── Total decisions ─────────────────────────────────── */}
      <article className="rounded-2xl border border-white/10 bg-white/[0.02] p-5">
        <header className="mb-3 font-ui text-[10px] uppercase tracking-widest text-text-secondary">
          Total decisions
        </header>
        <div className="font-data text-5xl text-text-primary">{total.toLocaleString()}</div>
        <p className="mt-3 font-ui text-xs text-text-secondary">
          {latest
            ? `Latest ${formatAuditTimestamp(latest)}`
            : 'No decisions recorded yet.'}
        </p>
      </article>

      {/* ── Per-module histogram ────────────────────────────── */}
      <article className="rounded-2xl border border-white/10 bg-white/[0.02] p-5">
        <header className="mb-3 font-ui text-[10px] uppercase tracking-widest text-text-secondary">
          Decisions by module
        </header>
        <ul className="space-y-2.5">
          {MODULE_ORDER.map((mod) => {
            const count = moduleCounts.get(mod) ?? 0;
            const meta = moduleById(mod);
            const widthPct = count > 0 ? Math.max(4, (count / moduleMax) * 100) : 0;
            return (
              <li key={mod} className="flex items-center gap-3 font-ui text-xs">
                <span
                  className="w-24 truncate uppercase tracking-widest"
                  style={{ color: meta.accent }}
                >
                  <span className="mr-1.5 font-data">{meta.glyph}</span>
                  {mod}
                </span>
                <span
                  className="h-1.5 flex-1 overflow-hidden rounded-full bg-white/[0.06]"
                >
                  <span
                    className="block h-full rounded-full transition-all"
                    style={{ width: `${widthPct}%`, backgroundColor: meta.accent }}
                  />
                </span>
                <span className="w-8 text-right font-data text-text-primary">{count}</span>
              </li>
            );
          })}
        </ul>
        {/* Footer caption — keeps the 5-module gauge stable when
            module coverage is sparse. */}
        <p className="mt-3 font-ui text-[10px] uppercase tracking-widest text-text-secondary">
          {MODULES.length} modules · max {moduleMax}
        </p>
      </article>

      {/* ── Per-risk-tier histogram ─────────────────────────── */}
      <article className="rounded-2xl border border-white/10 bg-white/[0.02] p-5">
        <header className="mb-3 font-ui text-[10px] uppercase tracking-widest text-text-secondary">
          Decisions by risk tier
        </header>
        {riskCounts.size === 0 ? (
          <p className="font-ui text-xs text-text-secondary">
            No risk-tiered decisions yet. Pricing, forecasting, and chatbot don&apos;t
            populate risk tiers; recruitment + sustainability do.
          </p>
        ) : (
          <ul className="space-y-2.5">
            {RISK_TIER_ORDER.map((tier) => {
              const count = riskCounts.get(tier) ?? 0;
              const widthPct = count > 0 ? Math.max(4, (count / riskMax) * 100) : 0;
              const tone = toneForRisk(tier as RiskLevel);
              return (
                <li key={tier} className="flex items-center gap-3 font-ui text-xs">
                  <span className={cn('w-24 uppercase tracking-widest', tone.text)}>
                    {formatRiskTierLabel(tier)}
                  </span>
                  <span className="h-1.5 flex-1 overflow-hidden rounded-full bg-white/[0.06]">
                    <span
                      className={cn('block h-full rounded-full transition-all', tone.bg)}
                      style={{ width: `${widthPct}%` }}
                    />
                  </span>
                  <span className="w-8 text-right font-data text-text-primary">{count}</span>
                </li>
              );
            })}
          </ul>
        )}
      </article>
    </div>
  );
}

function SummarySkeleton() {
  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-3" aria-hidden>
      {[0, 1, 2].map((i) => (
        <div
          key={i}
          className="h-48 animate-pulse rounded-2xl border border-white/10 bg-white/[0.02]"
        />
      ))}
    </div>
  );
}
