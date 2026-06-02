'use client';

import { useEffect } from 'react';

import { useSceneStore } from '@/lib/store/use-scene-store';

/**
 * Subscribes to the user's `prefers-reduced-motion` setting and mirrors it
 * into the scene store so 3D scenes can dampen / disable motion in concert
 * with framer-motion's HTML reveals.
 */
export function useReducedMotion(): void {
  useEffect(() => {
    if (typeof window === 'undefined') return;
    const mq = window.matchMedia('(prefers-reduced-motion: reduce)');
    const apply = () => useSceneStore.getState().setPrefersReducedMotion(mq.matches);
    apply();
    mq.addEventListener('change', apply);
    return () => mq.removeEventListener('change', apply);
  }, []);
}
