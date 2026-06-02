'use client';

import { useState, type FormEvent } from 'react';

import { FormField } from '@/components/auth/FormField';
import { TextArea } from '@/components/recruitment/TextArea';
import type { ForecastRequest, TimeSeriesPoint } from '@/lib/forecasting/types';

const DEFAULT_HISTORY = `2026-01-01, 100
2026-01-02, 102
2026-01-03, 104
2026-01-04, 106
2026-01-05, 108
2026-01-06, 109
2026-01-07, 111`;

type ForecastFormProps = {
  onSubmit: (request: ForecastRequest) => void;
  submitting: boolean;
};

export function ForecastForm({ onSubmit, submitting }: ForecastFormProps) {
  const [seriesName, setSeriesName] = useState('profit');
  const [historyText, setHistoryText] = useState(DEFAULT_HISTORY);
  const [horizonDays, setHorizonDays] = useState('90');
  const [error, setError] = useState<string | null>(null);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (submitting) return;
    setError(null);

    const history = parseHistory(historyText);
    if (history.length < 3) {
      setError('Need at least 3 history points (date, value per line).');
      return;
    }

    const horizon = Number(horizonDays);
    if (!Number.isFinite(horizon) || horizon < 7 || horizon > 365) {
      setError('Horizon must be between 7 and 365 days.');
      return;
    }

    const request: ForecastRequest = {
      series_name: seriesName.trim() || 'profit',
      history,
      forecast_horizon_days: Math.round(horizon),
      include_scenarios: true,
    };
    onSubmit(request);
  }

  return (
    <form onSubmit={handleSubmit} noValidate className="space-y-4">
      <FormField
        label="Series name"
        type="text"
        name="series_name"
        required
        value={seriesName}
        onChange={(e) => setSeriesName(e.target.value)}
      />

      <TextArea
        label="History (date, value per line)"
        name="history"
        rows={10}
        required
        hint="ISO date · ≥ 3 rows"
        placeholder="2026-01-01, 100"
        value={historyText}
        onChange={(e) => setHistoryText(e.target.value)}
      />

      <FormField
        label="Horizon (days)"
        type="number"
        name="forecast_horizon_days"
        required
        min={7}
        max={365}
        step={1}
        value={horizonDays}
        onChange={(e) => setHorizonDays(e.target.value)}
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
        className="w-full rounded-lg bg-violet px-4 py-2 font-ui text-sm font-medium text-white shadow-glow-violet transition hover:bg-violet/90 disabled:cursor-not-allowed disabled:opacity-60"
      >
        {submitting ? 'Generating forecast…' : 'Generate forecast'}
      </button>
    </form>
  );
}

// ── Helpers ────────────────────────────────────────────────────────

const ISO_DATE_RE = /^(\d{4})-(\d{2})-(\d{2})$/;

/**
 * Parse a textarea of `YYYY-MM-DD, value` lines into a
 * `TimeSeriesPoint[]`. Tolerates blank lines, tab/whitespace
 * separators, and lines that fail to parse (skipped silently — the
 * outer form rejects the whole submission if fewer than 3 points
 * make it through).
 */
export function parseHistory(raw: string): TimeSeriesPoint[] {
  const points: TimeSeriesPoint[] = [];
  for (const rawLine of raw.split('\n')) {
    const line = rawLine.trim();
    if (line.length === 0) continue;
    // Split on the first comma OR run of whitespace.
    const match = line.match(/^([^,\s]+)[,\s]+(.+)$/);
    if (!match) continue;
    const dateStr = match[1].trim();
    const valueStr = match[2].trim();
    if (!ISO_DATE_RE.test(dateStr)) continue;
    const value = Number(valueStr);
    if (!Number.isFinite(value)) continue;
    points.push({ ds: dateStr, y: value });
  }
  return points;
}
