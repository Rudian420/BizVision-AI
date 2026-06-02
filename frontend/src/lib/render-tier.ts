/**
 * Render-tier policy (ADR-016).
 *
 * Three discrete tiers map to GPU capability and drive every expensive
 * decision in the cinematic landing: particle counts, post-processing
 * stack depth, DPR, draw distance, and shadow quality.
 *
 *      LOW    — integrated GPU / mobile          (1K..20K particles, no postFX)
 *      MED    — dedicated GPU                    (50K particles, bloom)
 *      HIGH   — recent discrete / Apple Silicon  (100K particles, full postFX)
 *
 * Detection happens once on mount via a throw-away WebGL context and
 * `WEBGL_debug_renderer_info` (most browsers expose it). The result is
 * stored in `localStorage` (`bv:tier`) so subsequent loads skip detection.
 *
 * Users (and dev/debug) can override via the scene store.
 */

import { RenderTier } from '@bizvision/contracts';

export { RenderTier };

const STORAGE_KEY = 'bv:tier';

/** Per-tier knobs consumed by 3D scenes + postFX. Keep in one place. */
export const TIER_PROFILES = {
  [RenderTier.LOW]: {
    particles: 20_000,
    dpr: [1, 1.25] as [number, number],
    bloom: false,
    chromaticAberration: false,
    vignette: true,
    noise: false,
    starCount: 800,
    connectionsPerPlanet: 0,
    cameraDamping: 0.2,
  },
  [RenderTier.MED]: {
    particles: 50_000,
    dpr: [1, 1.5] as [number, number],
    bloom: true,
    chromaticAberration: false,
    vignette: true,
    noise: false,
    starCount: 2_000,
    connectionsPerPlanet: 32,
    cameraDamping: 0.15,
  },
  [RenderTier.HIGH]: {
    particles: 100_000,
    dpr: [1, 2] as [number, number],
    bloom: true,
    chromaticAberration: true,
    vignette: true,
    noise: true,
    starCount: 4_000,
    connectionsPerPlanet: 64,
    cameraDamping: 0.12,
  },
} as const;

export type TierProfile = (typeof TIER_PROFILES)[RenderTier];

// Heuristics. Discrete GPU vendor keywords are the strongest signal; presence
// of "Intel HD/UHD/Iris" or generic "ANGLE … Intel(R)" implies integrated.
const HIGH_GPU = /(nvidia|geforce|radeon\s*r[xa-z]|apple m\d|adreno\s*7\d{2})/i;
const LOW_GPU = /(intel\s*(hd|uhd|iris)|microsoft basic render|swiftshader|llvmpipe|mali|powervr)/i;

/**
 * Run a one-shot GPU detection. Safe in SSR (returns MED) and tolerant of
 * environments where WEBGL_debug_renderer_info is masked.
 */
export function detectRenderTier(): RenderTier {
  if (typeof window === 'undefined') return RenderTier.MED;

  const cached = window.localStorage?.getItem(STORAGE_KEY);
  if (cached === RenderTier.LOW || cached === RenderTier.MED || cached === RenderTier.HIGH) {
    return cached;
  }

  let tier: RenderTier = RenderTier.MED;
  try {
    const canvas = document.createElement('canvas');
    const gl =
      (canvas.getContext('webgl2') as WebGL2RenderingContext | null) ??
      (canvas.getContext('webgl') as WebGLRenderingContext | null);

    if (gl) {
      const ext = gl.getExtension('WEBGL_debug_renderer_info');
      const renderer =
        (ext && (gl.getParameter(ext.UNMASKED_RENDERER_WEBGL) as string)) ||
        (gl.getParameter(gl.RENDERER) as string);

      if (renderer) {
        if (HIGH_GPU.test(renderer)) tier = RenderTier.HIGH;
        else if (LOW_GPU.test(renderer)) tier = RenderTier.LOW;
      }
      // Cap mobile / small viewport to MED at most.
      if (window.innerWidth < 768 && tier === RenderTier.HIGH) tier = RenderTier.MED;
      if (window.innerWidth < 480) tier = RenderTier.LOW;
    }
  } catch {
    /* fall through to MED */
  }

  try {
    window.localStorage?.setItem(STORAGE_KEY, tier);
  } catch {
    /* private mode */
  }
  return tier;
}

export function clearTierCache(): void {
  try {
    window.localStorage?.removeItem(STORAGE_KEY);
  } catch {
    /* noop */
  }
}
