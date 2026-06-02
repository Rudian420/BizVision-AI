/**
 * Shared chart geometry — used by every module that renders an SVG
 * line chart (pricing's revenue curve, forecasting's scenario lines,
 * and the upcoming sustainability + chatbot trend visualisations).
 *
 * Pure functions, no React. Each function takes a `ChartScale` (data
 * domain) + pixel dimensions and returns the SVG-pixel projection.
 * The SVG y-axis grows downward; `projectPoint` flips it so larger
 * data y reads upward in the rendered chart.
 */

export type ChartScale = {
  xMin: number;
  xMax: number;
  yMin: number;
  yMax: number;
};

/**
 * Map a (data x, data y) point to (svg x, svg y) given a scale and
 * the chart's inner pixel width / height.
 *
 * Tolerates a zero-width or zero-height domain by treating the
 * divisor as 1 — callers get the lower-left of the chart instead of
 * a NaN, which is the right thing for degenerate data.
 */
export function projectPoint(
  point: { x: number; y: number },
  scale: ChartScale,
  width: number,
  height: number,
): { x: number; y: number } {
  const xRange = scale.xMax - scale.xMin || 1;
  const yRange = scale.yMax - scale.yMin || 1;
  const x = ((point.x - scale.xMin) / xRange) * width;
  const y = height - ((point.y - scale.yMin) / yRange) * height;
  return { x, y };
}

/**
 * Compute a numeric scale over an arbitrary collection given two
 * projector functions `getX` / `getY`. Pads the y range by
 * `yPaddingFraction` on each side (default 5%) so the curve doesn't
 * touch the chart frame; guards against a zero-height domain when
 * every y is identical.
 *
 * Each module wraps this with a domain-specific helper (pricing's
 * `curveScale(curve, objective)`, forecasting's `scenarioScale(...)`)
 * so callers don't repeat the projector boilerplate.
 */
export function scaleFor<T>(
  items: readonly T[],
  getX: (item: T) => number,
  getY: (item: T) => number,
  yPaddingFraction = 0.05,
): ChartScale {
  if (items.length === 0) {
    return { xMin: 0, xMax: 1, yMin: 0, yMax: 1 };
  }
  let xMin = Infinity;
  let xMax = -Infinity;
  let yMin = Infinity;
  let yMax = -Infinity;
  for (const item of items) {
    const x = getX(item);
    const y = getY(item);
    if (x < xMin) xMin = x;
    if (x > xMax) xMax = x;
    if (y < yMin) yMin = y;
    if (y > yMax) yMax = y;
  }
  if (yMin === yMax) {
    yMin -= 1;
    yMax += 1;
  }
  const yRange = yMax - yMin;
  const pad = yRange * yPaddingFraction;
  return { xMin, xMax, yMin: yMin - pad, yMax: yMax + pad };
}

/**
 * Build an SVG path "M…L…" string from an iterable of already-
 * projected pixel coordinates. Extracted here because every line
 * chart we render produces the same string shape.
 */
export function polylinePath(points: readonly { x: number; y: number }[]): string {
  if (points.length === 0) return '';
  return points
    .map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x.toFixed(2)},${p.y.toFixed(2)}`)
    .join(' ');
}

/**
 * Build a closed SVG path for a confidence band — upper edge forward,
 * lower edge backward, closed with Z. Used by the forecasting
 * scenario chart to fill the area between yhat_lower and yhat_upper.
 */
export function bandPath(
  upper: readonly { x: number; y: number }[],
  lower: readonly { x: number; y: number }[],
): string {
  if (upper.length === 0 || upper.length !== lower.length) return '';
  const forward = upper
    .map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x.toFixed(2)},${p.y.toFixed(2)}`)
    .join(' ');
  const backward = lower
    .slice()
    .reverse()
    .map((p) => `L${p.x.toFixed(2)},${p.y.toFixed(2)}`)
    .join(' ');
  return `${forward} ${backward} Z`;
}

/**
 * Convert an ISO date string (`YYYY-MM-DD`) to a serial day number
 * usable as an x coordinate. Stable across timezones — uses Date.UTC
 * with parsed year/month/day so daylight-saving and local-time shifts
 * can't perturb the chart layout.
 */
export function isoDateToDayNumber(iso: string): number {
  const m = iso.match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (!m) return Number.NaN;
  const year = Number(m[1]);
  const month = Number(m[2]) - 1;
  const day = Number(m[3]);
  return Math.floor(Date.UTC(year, month, day) / 86_400_000);
}
