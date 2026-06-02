/**
 * Tests for `<LimePanel>` — the LIME explainability counterpart to
 * `<ShapPanel>` (TASK-044 / FE-016).
 *
 * The component is mostly a CSS-only bar-chart so the interesting
 * behaviour is around: (1) the empty-state contract, (2) the sign-
 * dependent rail used to pick text colour, and (3) deterministic
 * key generation that lets React Query refresh in place.
 */

import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import type { SHAPFeature } from '@/lib/shap/types';

import { LimePanel } from './LimePanel';

const feature = (over: Partial<SHAPFeature> = {}): SHAPFeature => ({
  feature_name: 'price',
  shap_value: 0.42,
  feature_value: 0.42,
  contribution_direction: 'positive',
  importance_rank: 1,
  ...over,
});

describe('<LimePanel>', () => {
  it('renders the default empty message when given an empty feature list', () => {
    render(<LimePanel features={[]} />);
    expect(screen.getByText('No LIME attributions available.')).toBeInTheDocument();
  });

  it('renders a custom empty message when supplied', () => {
    render(<LimePanel features={[]} emptyMessage="Try again after re-training the model." />);
    expect(
      screen.getByText('Try again after re-training the model.'),
    ).toBeInTheDocument();
  });

  it('renders one row per feature with rank prefix + signed magnitude', () => {
    render(
      <LimePanel
        features={[
          feature({ feature_name: 'price', shap_value: 0.42, importance_rank: 1 }),
          feature({
            feature_name: 'competitor_price_gap',
            shap_value: -0.18,
            importance_rank: 2,
            contribution_direction: 'negative',
          }),
        ]}
      />,
    );
    expect(screen.getByText('price')).toBeInTheDocument();
    expect(screen.getByText('competitor_price_gap')).toBeInTheDocument();
    expect(screen.getByText('#1')).toBeInTheDocument();
    expect(screen.getByText('#2')).toBeInTheDocument();
    // Positive value rendered with '+' prefix; negative with the
    // typographic minus '−'.
    expect(screen.getByText('+0.42')).toBeInTheDocument();
    expect(screen.getByText('−0.18')).toBeInTheDocument();
  });

  it('attaches an aria label that distinguishes it from the SHAP panel', () => {
    render(<LimePanel features={[feature()]} />);
    expect(
      screen.getByLabelText('LIME feature attributions'),
    ).toBeInTheDocument();
  });

  it('renders zero-valued features without crashing the symmetric scale floor', () => {
    // All zeros means `maxAbs` would have been 0 — the component's
    // 0.05 floor prevents a divide-by-zero.
    render(
      <LimePanel
        features={[
          feature({ feature_name: 'a', shap_value: 0, importance_rank: 1 }),
          feature({ feature_name: 'b', shap_value: 0, importance_rank: 2 }),
        ]}
      />,
    );
    expect(screen.getByText('a')).toBeInTheDocument();
    expect(screen.getByText('b')).toBeInTheDocument();
  });
});
