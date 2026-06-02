'use client';

import { useEffect, useRef } from 'react';

import { useSceneStore } from '@/lib/store/use-scene-store';

/**
 * One-pixel-tall scroll progress line pinned to the top of the viewport.
 * Reads `scrollOffset` from the scene store and drives `transform: scaleX`
 * directly on the DOM node — never re-renders, never allocates.
 */
export function ScrollProgress() {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    return useSceneStore.subscribe((s) => {
      el.style.transform = `scaleX(${s.scrollOffset})`;
    });
  }, []);

  return (
    <div className="pointer-events-none fixed inset-x-0 top-0 z-50 h-px overflow-hidden">
      <div
        ref={ref}
        className="h-full origin-left bg-gradient-to-r from-cyan via-violet to-coral"
        style={{ transform: 'scaleX(0)' }}
      />
    </div>
  );
}
