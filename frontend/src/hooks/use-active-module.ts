'use client';

import { useEffect } from 'react';

import { MODULES } from '@/lib/modules';
import { useSceneStore } from '@/lib/store/use-scene-store';

/**
 * Bridges the window scroll into the scene store:
 *   • normalises `scrollY` to a 0..1 offset across the page
 *   • derives the currently-active module index from that offset
 *
 * The narrative is segmented as:
 *
 *     [ 0 .. .15 )  hero          activeModule = -1
 *     [ .15 .. .9 ) MODULES        activeModule = 0..N-1
 *     [ .9  .. 1  ] CTA            activeModule = -1
 *
 * Listener uses `requestAnimationFrame` coalescing so wheel-bursts collapse
 * into one store write per frame.
 */
const HERO_END = 0.15;
const CTA_START = 0.9;

export function useActiveModule(): void {
  useEffect(() => {
    if (typeof window === 'undefined') return;
    let raf = 0;
    let queued = false;

    const tick = () => {
      queued = false;
      const doc = document.documentElement;
      const scrollable = doc.scrollHeight - window.innerHeight;
      const offset = scrollable > 0 ? window.scrollY / scrollable : 0;
      const clamped = Math.min(1, Math.max(0, offset));

      let idx = -1;
      if (clamped >= HERO_END && clamped < CTA_START) {
        const localT = (clamped - HERO_END) / (CTA_START - HERO_END);
        idx = Math.min(MODULES.length - 1, Math.floor(localT * MODULES.length));
      }

      const state = useSceneStore.getState();
      if (state.scrollOffset !== clamped) state.setScroll(clamped);
      if (state.activeModuleIdx !== idx) state.setActiveModule(idx);
    };

    const onScroll = () => {
      if (queued) return;
      queued = true;
      raf = requestAnimationFrame(tick);
    };

    tick(); // initialise
    window.addEventListener('scroll', onScroll, { passive: true });
    window.addEventListener('resize', onScroll, { passive: true });
    return () => {
      window.removeEventListener('scroll', onScroll);
      window.removeEventListener('resize', onScroll);
      cancelAnimationFrame(raf);
    };
  }, []);
}
