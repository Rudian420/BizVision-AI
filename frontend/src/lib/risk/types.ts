/**
 * Shared RiskLevel type — used by every module that reports a
 * categorical risk band. Mirrors the backend's
 * `src.api.v1.schemas.common.RiskLevel` enum.
 */
export type RiskLevel = 'low' | 'medium' | 'high' | 'critical';
