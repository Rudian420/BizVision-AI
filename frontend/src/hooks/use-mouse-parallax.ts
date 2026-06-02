'use client';

import { useEffect } from 'react';

import { useSceneStore } from '@/lib/store/use-scene-store';

/**
 * Tracks the pointer in normalised device coords (-1..1) and publishes to the
 * scene store. 3D scenes lerp toward this target inside `useFrame` to avoid
 * jitter — see `ModulePlanets` and `NeuralGalaxy`.
 *
 * Disabled when the user prefers reduced motion.
 */
export function useMouseParallax(): void {
  useEffect(() => {
    if (typeof window === 'undefined') return;
    if (useSceneStore.getState().prefersReducedMotion) return;

    const onMove = (e: PointerEvent) => {
      const x = (e.clientX / window.innerWidth) * 2 - 1;
      const y = -((e.clientY / window.innerHeight) * 2 - 1);
      useSceneStore.getState().setMouse(x, y);
    };
    window.addEventListener('pointermove', onMove, { passive: true });
    return () => window.removeEventListener('pointermove', onMove);
  }, []);
}
