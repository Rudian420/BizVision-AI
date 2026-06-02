'use client';

import { useState, type FormEvent } from 'react';

import { FormField } from '@/components/auth/FormField';
import { TextArea } from '@/components/recruitment/TextArea';
import type { ESGScoreRequest } from '@/lib/sustainability/types';

const DEFAULT_ENV = `energy_efficiency: 0.65
waste_diversion: 0.55`;
const DEFAULT_SOC = `dei_index: 0.6
labor_compliance: 0.8`;
const DEFAULT_GOV = `board_independence: 0.7
transparency: 0.65`;

const INDUSTRIES = [
  'manufacturing',
  'retail',
  'technology',
  'logistics',
  'agriculture',
  'finance',
  'healthcare',
] as const;

type ScoreFormProps = {
  onSubmit: (request: ESGScoreRequest) => void;
  submitting: boolean;
};

export function ScoreForm({ onSubmit, submitting }: ScoreFormProps) {
  const [companyName, setCompanyName] = useState('Acme Corp');
  const [industry, setIndustry] = useState<string>('technology');
  const [annualRevenue, setAnnualRevenue] = useState('5000000');
  const [employeeCount, setEmployeeCount] = useState('42');
  const [envText, setEnvText] = useState(DEFAULT_ENV);
  const [socText, setSocText] = useState(DEFAULT_SOC);
  const [govText, setGovText] = useState(DEFAULT_GOV);
  const [error, setError] = useState<string | null>(null);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (submitting) return;
    setError(null);

    const revenue = Number(annualRevenue);
    if (!Number.isFinite(revenue) || revenue < 0) {
      setError('Annual revenue must be a non-negative number.');
      return;
    }
    const headcount = Number(employeeCount);
    if (!Number.isFinite(headcount) || headcount < 1) {
      setError('Employee count must be at least 1.');
      return;
    }

    const request: ESGScoreRequest = {
      company_name: companyName.trim() || 'Unknown',
      industry: industry.trim() || 'general',
      annual_revenue: revenue,
      employee_count: Math.round(headcount),
      environmental_indicators: parseIndicators(envText),
      social_indicators: parseIndicators(socText),
      governance_indicators: parseIndicators(govText),
    };
    onSubmit(request);
  }

  return (
    <form onSubmit={handleSubmit} noValidate className="space-y-4">
      <FormField
        label="Company name"
        type="text"
        name="company_name"
        required
        value={companyName}
        onChange={(e) => setCompanyName(e.target.value)}
      />

      <div>
        <label
          htmlFor="industry"
          className="mb-1 block font-ui text-xs uppercase tracking-wider text-text-secondary"
        >
          Industry
        </label>
        <select
          id="industry"
          name="industry"
          value={industry}
          onChange={(e) => setIndustry(e.target.value)}
          className="w-full rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2 font-ui text-sm text-text-primary outline-none transition focus:border-emerald focus:ring-1 focus:ring-emerald/40"
        >
          {INDUSTRIES.map((i) => (
            <option key={i} value={i}>
              {i.charAt(0).toUpperCase() + i.slice(1)}
            </option>
          ))}
        </select>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <FormField
          label="Annual revenue"
          type="number"
          name="annual_revenue"
          required
          min={0}
          step="1000"
          value={annualRevenue}
          onChange={(e) => setAnnualRevenue(e.target.value)}
        />
        <FormField
          label="Employee count"
          type="number"
          name="employee_count"
          required
          min={1}
          step={1}
          value={employeeCount}
          onChange={(e) => setEmployeeCount(e.target.value)}
        />
      </div>

      <TextArea
        label="Environmental indicators (one per line)"
        name="environmental_indicators"
        rows={4}
        hint="key: 0–1 score"
        value={envText}
        onChange={(e) => setEnvText(e.target.value)}
      />
      <TextArea
        label="Social indicators (one per line)"
        name="social_indicators"
        rows={4}
        hint="key: 0–1 score"
        value={socText}
        onChange={(e) => setSocText(e.target.value)}
      />
      <TextArea
        label="Governance indicators (one per line)"
        name="governance_indicators"
        rows={4}
        hint="key: 0–1 score"
        value={govText}
        onChange={(e) => setGovText(e.target.value)}
      />

      {error && (
        <p
          role="alert"
          className="mb-2 rounded-md border border-coral/40 bg-coral/10 px-3 py-2 font-ui text-xs text-coral"
        >
          {error}
        </p>
      )}

      <button
        type="submit"
        disabled={submitting}
        className="w-full rounded-lg bg-emerald px-4 py-2 font-ui text-sm font-medium text-void shadow-glow-emerald transition hover:bg-emerald/90 disabled:cursor-not-allowed disabled:opacity-60"
      >
        {submitting ? 'Scoring ESG profile…' : 'Score ESG profile'}
      </button>
    </form>
  );
}

// ── Helpers ────────────────────────────────────────────────────────

/**
 * Parse a textarea of `key: value` (or `key = value`) lines into a
 * `Record<string, number>`. Tolerates blank lines, whitespace
 * around the separator, and skips entries that don't look like a
 * key + numeric value. Multiple lines with the same key keep the
 * last one — same convention as `Object.fromEntries`.
 *
 * Empty input maps to an empty object, not `undefined`, so the
 * backend always receives a concrete dict.
 */
export function parseIndicators(raw: string): Record<string, number> {
  const out: Record<string, number> = {};
  for (const line of raw.split('\n')) {
    const trimmed = line.trim();
    if (trimmed.length === 0) continue;
    const match = trimmed.match(/^([^=:]+?)\s*[:=]\s*(.+)$/);
    if (!match) continue;
    const key = match[1].trim();
    if (key.length === 0) continue;
    const value = Number(match[2].trim());
    if (!Number.isFinite(value)) continue;
    out[key] = value;
  }
  return out;
}
