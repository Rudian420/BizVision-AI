'use client';

import { toneForRisk } from '@/lib/risk/tones';
import type { RiskLevel } from '@/lib/risk/types';
import { cn } from '@/lib/utils';

type RiskBadgeProps = {
  risk: RiskLevel;
  /** Optional override label — defaults to `<risk> risk`. */
  label?: string;
  className?: string;
};

/**
 * Shared risk badge — used by every module that surfaces a
 * categorical risk band (recruitment fairness audit,
 * sustainability composite, future Phase-4 XAI dashboards).
 *
 * Extracted from `components/recruitment/RiskBadge.tsx` so
 * sustainability and chatbot can use the same palette without
 * copy-paste. The recruitment-side wrapper is now a thin re-export.
 */
export function RiskBadge({ risk, label, className }: RiskBadgeProps) {
  const tone = toneForRisk(risk);
  return (
    <span
      role="status"
      aria-label={tone.label}
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full border px-3 py-1 font-ui text-xs font-medium uppercase tracking-wider',
        tone.text,
        tone.bg,
        tone.border,
        className,
      )}
    >
      <span aria-hidden className="h-1.5 w-1.5 rounded-full bg-current" />
      {label ?? tone.label}
    </span>
  );
}
