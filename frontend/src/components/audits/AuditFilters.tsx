'use client';

import { MODULE_ORDER, RISK_TIER_ORDER, formatRiskTierLabel } from '@/lib/audits/format';
import type { AuditModuleName } from '@/lib/audits/types';
import { moduleById } from '@/lib/modules';
import { toneForRisk } from '@/lib/risk/tones';
import type { RiskLevel } from '@/lib/risk/types';
import { cn } from '@/lib/utils';

type AuditFiltersProps = {
  activeModule: AuditModuleName | null;
  activeRiskTier: string | null;
  onModuleChange: (mod: AuditModuleName | null) => void;
  onRiskTierChange: (tier: string | null) => void;
};

/**
 * Two filter strips — module chips and risk-tier chips — for the ML
 * Decision Feed page (TASK-030). Each chip toggles a query parameter
 * on the `/audits` listing query.
 *
 * Single-select per strip: clicking the active chip clears the filter.
 * "All" is implicit (no chip pressed). Visual posture matches the
 * chatbot composer's context chip multi-select.
 */
export function AuditFilters({
  activeModule,
  activeRiskTier,
  onModuleChange,
  onRiskTierChange,
}: AuditFiltersProps) {
  return (
    <div className="flex flex-col gap-3" role="toolbar" aria-label="Audit filters">
      <section>
        <h3 className="mb-2 font-ui text-[10px] uppercase tracking-widest text-text-secondary">
          Module
        </h3>
        <div className="flex flex-wrap gap-2">
          <FilterChip
            label="All modules"
            active={activeModule === null}
            onClick={() => onModuleChange(null)}
          />
          {MODULE_ORDER.map((mod) => {
            const meta = moduleById(mod);
            const isActive = activeModule === mod;
            return (
              <FilterChip
                key={mod}
                label={mod}
                glyph={meta.glyph}
                active={isActive}
                accent={meta.accent}
                onClick={() => onModuleChange(isActive ? null : mod)}
              />
            );
          })}
        </div>
      </section>

      <section>
        <h3 className="mb-2 font-ui text-[10px] uppercase tracking-widest text-text-secondary">
          Risk tier
        </h3>
        <div className="flex flex-wrap gap-2">
          <FilterChip
            label="Any tier"
            active={activeRiskTier === null}
            onClick={() => onRiskTierChange(null)}
          />
          {RISK_TIER_ORDER.map((tier) => {
            const isActive = activeRiskTier === tier;
            const tone = toneForRisk(tier as RiskLevel);
            return (
              <FilterChip
                key={tier}
                label={formatRiskTierLabel(tier)}
                active={isActive}
                toneClass={tone.text}
                onClick={() => onRiskTierChange(isActive ? null : tier)}
              />
            );
          })}
        </div>
      </section>
    </div>
  );
}

type FilterChipProps = {
  label: string;
  glyph?: string;
  active: boolean;
  accent?: string;
  toneClass?: string;
  onClick: () => void;
};

function FilterChip({ label, glyph, active, accent, toneClass, onClick }: FilterChipProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full border px-3 py-1 font-ui text-xs uppercase tracking-widest transition',
        active
          ? 'border-white/30 bg-white/[0.08] text-text-primary'
          : 'border-white/10 bg-white/[0.02] text-text-secondary hover:border-white/20 hover:text-text-primary',
        !active && toneClass,
      )}
      style={active && accent ? { boxShadow: `inset 2px 0 0 ${accent}`, color: accent } : undefined}
    >
      {glyph && <span className="font-data">{glyph}</span>}
      <span>{label}</span>
    </button>
  );
}
