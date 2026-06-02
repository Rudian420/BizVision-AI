/**
 * `useSceneStore` — central client-side state for the cinematic landing.
 *
 * Exists so React-Three-Fiber components can subscribe to a few primitives
 * (tier, reduced-motion, active module, scroll offset, mouse) without
 * prop-drilling through Canvas. Reads are O(1) via Zustand's selector
 * subscription model — `useFrame` callbacks read directly from
 * `useSceneStore.getState()` to avoid re-renders.
 */

import { create } from 'zustand';

import { RenderTier, TIER_PROFILES, type TierProfile } from '@/lib/render-tier';

type SceneState = {
  // ── render policy ────────────────────────────────────────────
  tier: RenderTier;
  profile: TierProfile;
  prefersReducedMotion: boolean;
  ready: boolean; // true once tier detection has run on the client

  // ── scroll / story ──────────────────────────────────────────
  /** 0..1 across the full landing scroll length. */
  scrollOffset: number;
  /** Index into MODULES of the currently-active section (or -1 for hero/cta). */
  activeModuleIdx: number;

  // ── input ────────────────────────────────────────────────────
  /** Mouse position in NDC (-1..1) — written by useFrame, read by scenes. */
  mouseX: number;
  mouseY: number;

  // ── actions ──────────────────────────────────────────────────
  setTier: (tier: RenderTier) => void;
  setPrefersReducedMotion: (v: boolean) => void;
  setScroll: (offset: number) => void;
  setActiveModule: (idx: number) => void;
  setMouse: (x: number, y: number) => void;
};

export const useSceneStore = create<SceneState>((set) => ({
  tier: RenderTier.MED,
  profile: TIER_PROFILES[RenderTier.MED],
  prefersReducedMotion: false,
  ready: false,
  scrollOffset: 0,
  activeModuleIdx: -1,
  mouseX: 0,
  mouseY: 0,

  setTier: (tier) => set({ tier, profile: TIER_PROFILES[tier], ready: true }),
  setPrefersReducedMotion: (prefersReducedMotion) => set({ prefersReducedMotion }),
  setScroll: (scrollOffset) => set({ scrollOffset }),
  setActiveModule: (activeModuleIdx) => set({ activeModuleIdx }),
  setMouse: (mouseX, mouseY) => set({ mouseX, mouseY }),
}));

/** Convenience selectors (stable references). */
export const selectProfile = (s: SceneState): TierProfile => s.profile;
export const selectTier = (s: SceneState): RenderTier => s.tier;
export const selectReady = (s: SceneState): boolean => s.ready;
