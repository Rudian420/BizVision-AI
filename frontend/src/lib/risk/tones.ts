/**
 * Shared risk-tone palette — used by every module that renders a
 * `RiskBadge` or risk-coloured affordance.
 *
 * Promoted from `lib/recruitment/format.ts` so sustainability (and
 * any future module with a categorical risk band) reuses the same
 * cyan / gold / coral / coral-deep palette without duplication.
 */

import type { RiskLevel } from './types';

export type RiskTone = {
  /** Tailwind text colour utility */
  text: string;
  /** Tailwind background utility */
  bg: string;
  /** Tailwind border utility */
  border: string;
  /** Plain-English label for accessibility */
  label: string;
};

export const RISK_TONES: Readonly<Record<RiskLevel, RiskTone>> = {
  low: {
    text: 'text-emerald',
    bg: 'bg-emerald/10',
    border: 'border-emerald/40',
    label: 'low risk',
  },
  medium: {
    text: 'text-gold',
    bg: 'bg-gold/10',
    border: 'border-gold/40',
    label: 'medium risk',
  },
  high: {
    text: 'text-coral',
    bg: 'bg-coral/10',
    border: 'border-coral/40',
    label: 'high risk',
  },
  critical: {
    text: 'text-coral',
    bg: 'bg-coral/15',
    border: 'border-coral/60',
    label: 'critical risk',
  },
} as const;

export function toneForRisk(risk: RiskLevel): RiskTone {
  return RISK_TONES[risk];
}
