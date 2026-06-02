/**
 * Cross-language enums — kept in lock-step with the Python source of truth in
 * `backend/src/api/v1/schemas/common.py` and `.../recruitment.py`.
 *
 * If you change an enum here, change it in Python too (and vice-versa). CI runs
 * a drift check (see `.github/workflows/ci-frontend.yml`).
 */

export enum RiskLevel {
  LOW = 'low',
  MEDIUM = 'medium',
  HIGH = 'high',
  CRITICAL = 'critical',
}

export enum ScenarioType {
  BASE = 'base',
  BULL = 'bull',
  BEAR = 'bear',
}

export enum ExperienceLevel {
  ENTRY = 'entry',
  MID = 'mid',
  SENIOR = 'senior',
  LEAD = 'lead',
  EXECUTIVE = 'executive',
}

export enum UserRole {
  ADMIN = 'admin',
  ANALYST = 'analyst',
  VIEWER = 'viewer',
}

/** 3D adaptive rendering tiers — see ADR-010. */
export enum RenderTier {
  LOW = 'low',
  MED = 'med',
  HIGH = 'high',
}

export const AI_MODULES = [
  'recruitment',
  'pricing',
  'forecasting',
  'sustainability',
  'chatbot',
] as const;

export type AIModule = (typeof AI_MODULES)[number];
