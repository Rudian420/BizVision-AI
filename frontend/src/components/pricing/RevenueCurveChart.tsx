'use client';

import {
  curveScale,
  formatCurrency,
  pickY,
  projectPoint,
  yAxisLabel,
} from '@/lib/pricing/format';
import type { PricePoint, PricingObjective } from '@/lib/pricing/types';

type RevenueCurveChartProps = {
  curve: PricePoint[];
  objective: PricingObjective;
  currentPrice: number;
  recommendedPrice: number;
  /** SVG viewport width in pixels. The container responsively scales. */
  width?: number;
  /** SVG viewport height in pixels. */
  height?: number;
};

const PADDING = { top: 12, right: 24, bottom: 28, left: 24 } as const;

/**
 * SVG-based revenue curve chart.
 *
 * Same discipline as the SHAP panel — no chart library. Renders a
 * gold polyline through the (price, y) projections; vertical markers
 * highlight the current price (dim) and recommended price (full
 * accent); the y-axis label reflects the active objective.
 *
 * The chart scales by `viewBox` so its width fills the container at
 * any breakpoint. `width` / `height` here set the *internal viewBox*
 * aspect ratio, not the rendered pixel size.
 */
export function RevenueCurveChart({
  curve,
  objective,
  currentPrice,
  recommendedPrice,
  width = 640,
  height = 240,
}: RevenueCurveChartProps) {
  if (!curve || curve.length < 2) {
    return (
      <p className="font-ui text-xs text-text-secondary">
        Revenue curve needs at least two price points to render.
      </p>
    );
  }

  const innerWidth = width - PADDING.left - PADDING.right;
  const innerHeight = height - PADDING.top - PADDING.bottom;
  const scale = curveScale(curve, objective);

  const points = curve.map((p) =>
    projectPoint({ x: p.price, y: pickY(p, objective) }, scale, innerWidth, innerHeight),
  );

  // SVG path: M start, then L for each subsequent point.
  const pathD = points
    .map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x.toFixed(2)},${p.y.toFixed(2)}`)
    .join(' ');

  // Vertical markers — x-positions on the inner chart area.
  const currentX = projectPoint(
    { x: currentPrice, y: 0 },
    scale,
    innerWidth,
    innerHeight,
  ).x;
  const recommendedX = projectPoint(
    { x: recommendedPrice, y: 0 },
    scale,
    innerWidth,
    innerHeight,
  ).x;

  const currentInRange = currentPrice >= scale.xMin && currentPrice <= scale.xMax;
  const recommendedInRange =
    recommendedPrice >= scale.xMin && recommendedPrice <= scale.xMax;

  return (
    <figure>
      <figcaption className="mb-2 flex items-baseline justify-between font-ui text-[10px] uppercase tracking-widest text-text-secondary">
        <span>{yAxisLabel(objective)} vs price</span>
        <span className="font-data normal-case text-text-secondary/70">
          {curve.length} points
        </span>
      </figcaption>

      <svg
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-label={`${yAxisLabel(objective)} curve from ${formatCurrency(scale.xMin)} to ${formatCurrency(scale.xMax)}`}
        className="h-auto w-full"
        preserveAspectRatio="none"
      >
        {/* Inner plot area */}
        <g transform={`translate(${PADDING.left} ${PADDING.top})`}>
          {/* Baseline + frame */}
          <rect
            x={0}
            y={0}
            width={innerWidth}
            height={innerHeight}
            fill="rgba(255,255,255,0.01)"
            stroke="rgba(255,255,255,0.06)"
            strokeWidth={1}
          />

          {/* Current price marker (dim) */}
          {currentInRange && (
            <line
              x1={currentX}
              x2={currentX}
              y1={0}
              y2={innerHeight}
              stroke="rgba(255,255,255,0.25)"
              strokeDasharray="4 4"
              strokeWidth={1}
            />
          )}

          {/* Recommended price marker (gold accent) */}
          {recommendedInRange && (
            <line
              x1={recommendedX}
              x2={recommendedX}
              y1={0}
              y2={innerHeight}
              stroke="#FFB800"
              strokeWidth={1.5}
            />
          )}

          {/* Curve */}
          <path
            d={pathD}
            fill="none"
            stroke="#FFB800"
            strokeWidth={2}
            strokeLinejoin="round"
            strokeLinecap="round"
          />

          {/* Endpoint dots for clarity */}
          {points.length > 0 && (
            <>
              <circle cx={points[0].x} cy={points[0].y} r={3} fill="#FFB800" />
              <circle
                cx={points[points.length - 1].x}
                cy={points[points.length - 1].y}
                r={3}
                fill="#FFB800"
              />
            </>
          )}
        </g>

        {/* X-axis price labels */}
        <text
          x={PADDING.left}
          y={height - 8}
          fill="rgba(255,255,255,0.4)"
          fontSize={10}
          fontFamily="JetBrains Mono"
        >
          {formatCurrency(scale.xMin)}
        </text>
        <text
          x={width - PADDING.right}
          y={height - 8}
          fill="rgba(255,255,255,0.4)"
          fontSize={10}
          fontFamily="JetBrains Mono"
          textAnchor="end"
        >
          {formatCurrency(scale.xMax)}
        </text>
      </svg>

      <ul className="mt-2 flex flex-wrap gap-x-5 gap-y-1 font-ui text-[10px] uppercase tracking-widest text-text-secondary">
        <li className="flex items-center gap-2">
          <span aria-hidden className="inline-block h-0.5 w-4 bg-gold" />
          <span>recommended {formatCurrency(recommendedPrice)}</span>
        </li>
        <li className="flex items-center gap-2">
          <span aria-hidden className="inline-block h-0.5 w-4 border-t border-dashed border-white/40" />
          <span>current {formatCurrency(currentPrice)}</span>
        </li>
      </ul>
    </figure>
  );
}
