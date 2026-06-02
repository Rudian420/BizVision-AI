'use client';

import { useEffect } from 'react';

import { detectRenderTier } from '@/lib/render-tier';
import { useSceneStore } from '@/lib/store/use-scene-store';

/**
 * Runs once on mount: detects GPU tier and publishes it to the scene store.
 * Idempotent — re-mounting won't re-detect since the store flips `ready`.
 */
export function useRenderTier(): void {
  useEffect(() => {
    if (useSceneStore.getState().ready) return;
    const tier = detectRenderTier();
    useSceneStore.getState().setTier(tier);
  }, []);
}
