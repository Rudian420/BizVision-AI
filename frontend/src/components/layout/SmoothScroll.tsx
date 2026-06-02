'use client';

import Lenis from 'lenis';
import { useEffect } from 'react';

import { useSceneStore } from '@/lib/store/use-scene-store';

/**
 * Window-scroll smoothing (ADR-018).
 *
 * Lenis runs a single RAF loop, attaches to the document, and delegates
 * wheel/touch into a damped scrollTop animation. The R3F frame loop and
 * framer-motion's `useScroll` both still read `window.scrollY` so they
 * stay in lock-step — no second source of truth.
 *
 * Disabled entirely under `prefers-reduced-motion`.
 */
export function SmoothScroll({ children }: { children: React.ReactNode }) {
  const prefersReducedMotion = useSceneStore((s) => s.prefersReducedMotion);

  useEffect(() => {
    if (prefersReducedMotion) return;

    const lenis = new Lenis({
      duration: 1.05,
      easing: (t) => Math.min(1, 1.001 - Math.pow(2, -10 * t)), // expoOut
      lerp: 0.1,
      smoothWheel: true,
      wheelMultiplier: 1.0,
      touchMultiplier: 1.4,
    });

    let raf = 0;
    const tick = (time: number) => {
      lenis.raf(time);
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);

    return () => {
      cancelAnimationFrame(raf);
      lenis.destroy();
    };
  }, [prefersReducedMotion]);

  return <>{children}</>;
}
