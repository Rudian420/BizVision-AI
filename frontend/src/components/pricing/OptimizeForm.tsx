'use client';

import { useState, type FormEvent } from 'react';

import { FormField } from '@/components/auth/FormField';
import type {
  PriceOptimizationRequest,
  PricingObjective,
} from '@/lib/pricing/types';

const OBJECTIVES: { value: PricingObjective; label: string }[] = [
  { value: 'revenue', label: 'Revenue' },
  { value: 'profit', label: 'Profit' },
  { value: 'volume', label: 'Volume' },
];

type OptimizeFormProps = {
  onSubmit: (request: PriceOptimizationRequest) => void;
  submitting: boolean;
};

export function OptimizeForm({ onSubmit, submitting }: OptimizeFormProps) {
  const [productId, setProductId] = useState('sku-001');
  const [currentPrice, setCurrentPrice] = useState('19.99');
  const [unitCost, setUnitCost] = useState('7.50');
  const [demandText, setDemandText] = useState('120, 118, 122, 117, 121');
  const [competitorText, setCompetitorText] = useState('21.00, 20.50, 22.00');
  const [objective, setObjective] = useState<PricingObjective>('revenue');
  const [minPrice, setMinPrice] = useState('');
  const [maxPrice, setMaxPrice] = useState('');
  const [error, setError] = useState<string | null>(null);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (submitting) return;
    setError(null);

    const cp = Number(currentPrice);
    const uc = Number(unitCost);
    if (!Number.isFinite(cp) || cp <= 0) {
      setError('Current price must be a positive number.');
      return;
    }
    if (!Number.isFinite(uc) || uc < 0) {
      setError('Unit cost must be a non-negative number.');
      return;
    }
    if (uc >= cp) {
      setError('Unit cost should be lower than the current price.');
      return;
    }

    const minPriceNum = parseOptionalPositive(minPrice);
    const maxPriceNum = parseOptionalPositive(maxPrice);
    if (
      minPriceNum !== undefined &&
      maxPriceNum !== undefined &&
      minPriceNum >= maxPriceNum
    ) {
      setError('Min price must be lower than max price.');
      return;
    }

    const request: PriceOptimizationRequest = {
      product_id: productId.trim() || 'sku-001',
      current_price: cp,
      unit_cost: uc,
      historical_demand: parseNumberList(demandText),
      competitor_prices: parseNumberList(competitorText),
      min_price: minPriceNum ?? null,
      max_price: maxPriceNum ?? null,
      objective,
    };
    onSubmit(request);
  }

  return (
    <form onSubmit={handleSubmit} noValidate className="space-y-4">
      <FormField
        label="Product / SKU id"
        type="text"
        name="product_id"
        required
        value={productId}
        onChange={(e) => setProductId(e.target.value)}
      />

      <div className="grid grid-cols-2 gap-3">
        <FormField
          label="Current price"
          type="number"
          name="current_price"
          required
          min={0}
          step="0.01"
          value={currentPrice}
          onChange={(e) => setCurrentPrice(e.target.value)}
        />
        <FormField
          label="Unit cost"
          type="number"
          name="unit_cost"
          required
          min={0}
          step="0.01"
          value={unitCost}
          onChange={(e) => setUnitCost(e.target.value)}
        />
      </div>

      <FormField
        label="Historical demand (comma-separated)"
        type="text"
        name="historical_demand"
        placeholder="120, 118, 122, 117, 121"
        value={demandText}
        onChange={(e) => setDemandText(e.target.value)}
      />

      <FormField
        label="Competitor prices (comma-separated)"
        type="text"
        name="competitor_prices"
        placeholder="21.00, 20.50, 22.00"
        value={competitorText}
        onChange={(e) => setCompetitorText(e.target.value)}
      />

      <div className="grid grid-cols-2 gap-3">
        <FormField
          label="Min price (optional)"
          type="number"
          name="min_price"
          min={0}
          step="0.01"
          value={minPrice}
          onChange={(e) => setMinPrice(e.target.value)}
        />
        <FormField
          label="Max price (optional)"
          type="number"
          name="max_price"
          min={0}
          step="0.01"
          value={maxPrice}
          onChange={(e) => setMaxPrice(e.target.value)}
        />
      </div>

      <div>
        <label
          htmlFor="objective"
          className="mb-1 block font-ui text-xs uppercase tracking-wider text-text-secondary"
        >
          Objective
        </label>
        <select
          id="objective"
          name="objective"
          value={objective}
          onChange={(e) => setObjective(e.target.value as PricingObjective)}
          className="w-full rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2 font-ui text-sm text-text-primary outline-none transition focus:border-cyan focus:ring-1 focus:ring-cyan/40"
        >
          {OBJECTIVES.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      </div>

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
        className="w-full rounded-lg bg-gold px-4 py-2 font-ui text-sm font-medium text-void shadow-glow-gold transition hover:bg-gold/90 disabled:cursor-not-allowed disabled:opacity-60"
      >
        {submitting ? 'Optimising price…' : 'Optimise price'}
      </button>
    </form>
  );
}

// ── Helpers ────────────────────────────────────────────────────────

/** Parse a comma-separated list of numbers, dropping empty / invalid entries.
 *  Note: `Number('')` is 0, not NaN — we filter empty strings explicitly
 *  so a blank input doesn't masquerade as a zero demand observation. */
export function parseNumberList(raw: string): number[] {
  return raw
    .split(',')
    .map((part) => part.trim())
    .filter((part) => part.length > 0)
    .map((part) => Number(part))
    .filter((n) => Number.isFinite(n));
}

/**
 * Parse an optional positive number from a string input. Returns
 * `undefined` for empty strings or invalid inputs — the form treats
 * either as "no constraint."
 */
export function parseOptionalPositive(raw: string): number | undefined {
  const trimmed = raw.trim();
  if (trimmed === '') return undefined;
  const value = Number(trimmed);
  if (!Number.isFinite(value) || value <= 0) return undefined;
  return value;
}
