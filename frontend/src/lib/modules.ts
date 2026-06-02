/**
 * Module metadata — single source of truth for the five AI modules.
 *
 * Used by: ModuleShowcase, ModulePlanets, Navigation, HudOverlay.
 * Order here defines the cinematic scroll narrative.
 *
 * Accent colors mirror the design bible (ui-ux-direction.md) and the
 * shared `@bizvision/contracts` enums; if a colour changes update both.
 */

import { AI_MODULES, type AIModule } from '@bizvision/contracts';

/** A single hex colour and its packed `vec3` form for shader uniforms. */
export type Hex = `#${string}`;

export type ModuleMeta = {
  id: AIModule;
  /** Display label */
  label: string;
  /** One-line tagline used as section subtitle */
  tagline: string;
  /** 2–3 sentence cinematic blurb */
  blurb: string;
  /** Hero stat string (e.g. "100K candidates / sec") */
  stat: string;
  /** Stat caption */
  statLabel: string;
  /** Primary accent colour (used by HUD + glow + planet) */
  accent: Hex;
  /** Secondary / dim accent for gradients */
  accentDim: Hex;
  /** Tailwind glow utility (matches tailwind.config.ts boxShadow keys) */
  glowClass: string;
  /** Tailwind text-color utility */
  textClass: string;
  /** Single-character glyph used in HUD chips */
  glyph: string;
  /** Normalised orbit angle (0..1) — placement of the module planet */
  orbitAngle: number;
};

/**
 * Convert "#RRGGBB" → [r, g, b] in 0..1 space (shader-uniform friendly).
 * Memoised by reference to avoid per-frame allocation downstream.
 */
const cache = new Map<Hex, readonly [number, number, number]>();
export function hexToVec3(hex: Hex): readonly [number, number, number] {
  const cached = cache.get(hex);
  if (cached) return cached;
  const n = parseInt(hex.slice(1), 16);
  const v = [((n >> 16) & 0xff) / 255, ((n >> 8) & 0xff) / 255, (n & 0xff) / 255] as const;
  cache.set(hex, v);
  return v;
}

export const MODULES: readonly ModuleMeta[] = [
  {
    id: 'recruitment',
    label: 'Recruitment Intelligence',
    tagline: 'Semantic candidate ranking, fairness-audited.',
    blurb:
      'A real sentence-transformers MPNet semantic ranker fused with an XGBoost ensemble scores every applicant; SHAP attributions surface the strongest skills-match drivers; demographic parity is persisted to the cross-module audit log on every ranking.',
    stat: 'SBERT',
    statLabel: 'MPNet + XGBoost ranker',
    accent: '#00F5FF',
    accentDim: '#00B8BF',
    glowClass: 'shadow-glow-cyan',
    textClass: 'text-cyan',
    glyph: '◈',
    orbitAngle: 0.0,
  },
  {
    id: 'pricing',
    label: 'Smart Pricing Advisor',
    tagline: 'Elasticity-aware revenue at the edge.',
    blurb:
      'A LightGBM grid-search demand model paired with constant-elasticity estimation and Monte-Carlo simulation. Recommendations come with confidence intervals, a full revenue/profit curve, and 37 ms warm inference.',
    stat: '+6.58%',
    statLabel: 'measured revenue uplift',
    accent: '#FFB800',
    accentDim: '#CC9200',
    glowClass: 'shadow-glow-gold',
    textClass: 'text-gold',
    glyph: '◆',
    orbitAngle: 0.2,
  },
  {
    id: 'forecasting',
    label: 'Profit Forecasting',
    tagline: 'Base. Bull. Bear. With confidence.',
    blurb:
      'A Theta forecaster (StatsModels) projects up to 180 days ahead with prediction intervals; base / bull / bear scenarios are generated for every horizon, with backtested MAPE returned per series.',
    stat: '3.32%',
    statLabel: 'MAPE backtest',
    accent: '#7C3AED',
    accentDim: '#5B21B6',
    glowClass: 'shadow-glow-violet',
    textClass: 'text-violet',
    glyph: '◭',
    orbitAngle: 0.4,
  },
  {
    id: 'sustainability',
    label: 'Green Business Scorer',
    tagline: 'ESG that actually drives action.',
    blurb:
      'A sklearn LinearLogistic multi-label classifier scores Environmental, Social, and Governance pillars; SHAP attributions surface the strongest drivers; a carbon estimator covers Scope 1/2/3.',
    stat: '25 ms',
    statLabel: 'warm ESG assessment',
    accent: '#10F07C',
    accentDim: '#059669',
    glowClass: 'shadow-glow-emerald',
    textClass: 'text-emerald',
    glyph: '◉',
    orbitAngle: 0.6,
  },
  {
    id: 'chatbot',
    label: 'Financial Advisory AI',
    tagline: 'An executive AI that reasons across modules.',
    blurb:
      'A retrieval-augmented advisor with hash-embedding semantic search and a keyword router across the business-intelligence corpus. Optional plug-in for a hosted LLM (Anthropic / OpenAI) when an API key is configured.',
    stat: 'RAG',
    statLabel: 'multi-module retrieval',
    accent: '#FF3B6B',
    accentDim: '#E11D48',
    glowClass: 'shadow-glow-coral',
    textClass: 'text-coral',
    glyph: '✦',
    orbitAngle: 0.8,
  },
] as const;

// Cheap runtime guard that the module array and the contract stay in lock-step.
if (MODULES.length !== AI_MODULES.length) {
  // eslint-disable-next-line no-console
  console.warn('[modules] MODULES vs AI_MODULES length mismatch — update both.');
}

export function moduleById(id: AIModule): ModuleMeta {
  const m = MODULES.find((x) => x.id === id);
  if (!m) throw new Error(`Unknown module: ${id}`);
  return m;
}
