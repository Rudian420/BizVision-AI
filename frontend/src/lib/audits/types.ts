/**
 * Hand-written audit-log contract types.
 *
 * Mirror `backend/src/api/v1/schemas/audit.py`. Kept local until the
 * OpenAPI generator runs against the live backend — same posture as
 * `lib/chatbot/types.ts` and `lib/recruitment/types.ts`.
 */

import type { AIModule } from '@bizvision/contracts';

export type AuditModuleName = AIModule;

/** Risk tier shape — string-typed so each backend module can extend
 * its taxonomy without an `ALTER TYPE` (per ADR-031). Today the
 * surfaced values are the recruitment + sustainability risk levels;
 * `string` lets future tiers (e.g. `regulatory_critical`) flow
 * through without a contract bump while still keeping the well-known
 * 4 names highlighted to readers. */
export type AuditRiskTier = 'low' | 'medium' | 'high' | 'critical' | string;

export type AuditLogRead = {
  id: string;
  user_id: string;
  module: AuditModuleName;
  action: string;
  reference_id: string | null;
  reference_type: string | null;
  request_summary: Record<string, unknown>;
  response_summary: Record<string, unknown>;
  explanation_summary: Record<string, unknown> | null;
  fairness_summary: Record<string, unknown> | null;
  risk_tier: AuditRiskTier | null;
  model_version: string;
  latency_ms: number;
  created_at: string; // ISO-8601
};

export type AuditLogPage = {
  items: AuditLogRead[];
  total: number;
  page: number;
  page_size: number;
};

export type AuditModuleCount = {
  module: AuditModuleName;
  count: number;
};

export type AuditRiskCount = {
  risk_tier: string;
  count: number;
};

export type AuditSummary = {
  user_id: string;
  window_start: string | null;
  total_decisions: number;
  by_module: AuditModuleCount[];
  by_risk_tier: AuditRiskCount[];
  latest_decision_at: string | null;
};

export type AuditListFilters = {
  module?: AuditModuleName | null;
  risk_tier?: string | null;
  /** Inclusive lower bound on created_at (ISO-8601). TASK-038. */
  since?: string | null;
  /** Inclusive upper bound on created_at (ISO-8601). TASK-038. */
  until?: string | null;
  page?: number;
  page_size?: number;
};

/** One protected-attribute bucket from `/api/v1/audits/fairness`.
 * `decision_count` is the number of audit rows in which this attribute
 * was audited (one decision = one row, per ADR-031). */
export type FairnessAttributeRollup = {
  attribute: string;
  decision_count: number;
  pass_count: number;
  fail_count: number;
  pass_rate: number; // [0, 1]
};

/** One cell of the intersectional fairness grid (TASK-043, FE-017):
 * the pivot of audit `fairness_summary.attributes[*].metrics[*]` onto
 * an `(attribute, metric_name)` key. `avg_value` is the mean of the
 * raw metric value across all decisions in this cell; `threshold` is
 * cached from the first observation (constant per metric). */
export type FairnessCell = {
  attribute: string;
  metric_name: string;
  decision_count: number;
  pass_count: number;
  pass_rate: number; // [0, 1]
  avg_value: number | null;
  threshold: number | null;
};

export type FairnessAggregate = {
  user_id: string;
  window_start: string | null;
  total_audited_decisions: number;
  by_attribute: FairnessAttributeRollup[];
  by_attribute_metric: FairnessCell[];
};
