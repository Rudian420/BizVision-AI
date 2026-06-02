'use client';

/**
 * BizVision AI — Cinematic Landing
 *
 * Composition:
 *   • SmoothScroll       — Lenis wraps the entire page
 *   • SceneStage         — fixed-position WebGL canvas, behind everything
 *   • HudOverlay         — corner brackets, status strip, module ticker
 *   • Navigation         — top bar with active-module dots
 *   • HTML scroll story  — Hero → 5 module sections → CTA
 *   • ScrollProgress     — top progress line
 *
 * Why no `<ScrollControls>`: see ADR-018 — window scroll is the single
 * source of truth; the scene store relays it into the R3F frame loop.
 *
 * Page height is 7× viewport to give the camera choreography room to
 * breathe between sections (1 hero + 5 modules + 1 CTA = 7).
 */

import dynamic from 'next/dynamic';
import { useRef } from 'react';

import { CTASection } from '@/components/layout/CTASection';
import { HeroText } from '@/components/layout/HeroText';
import { ModuleShowcase } from '@/components/layout/ModuleShowcase';
import { Navigation } from '@/components/layout/Navigation';
import { SmoothScroll } from '@/components/layout/SmoothScroll';
import { HudOverlay } from '@/components/ui/HudOverlay';
import { LoadingScreen } from '@/components/ui/LoadingScreen';
import { ScrollProgress } from '@/components/ui/ScrollProgress';

// 3D stage is client-only and heavy — dynamic-import without SSR so the
// HTML overlay paints first.
const SceneStage = dynamic(
  () => import('@/components/3d/scenes/SceneStage').then((m) => m.SceneStage),
  { ssr: false, loading: () => <LoadingScreen /> },
);

export default function LandingPage() {
  const containerRef = useRef<HTMLDivElement>(null);

  return (
    <SmoothScroll>
      <ScrollProgress />
      <Navigation />
      <HudOverlay />

      {/* Fixed-position 3D background (pointer-events disabled so HTML wins) */}
      <div className="pointer-events-none fixed inset-0 z-0">
        <SceneStage />
      </div>

      {/* HTML narrative — 7 screen-heights of scroll story */}
      <main
        ref={containerRef}
        className="relative z-10 bg-transparent"
        style={{ height: '700vh' }}
      >
        {/* Section 1 — Hero */}
        <section
          data-scroll-section="hero"
          className="flex h-screen items-center justify-center"
        >
          <HeroText />
        </section>

        {/* Sections 2–6 — Modules */}
        <ModuleShowcase />

        {/* Section 7 — CTA */}
        <CTASection />
      </main>
    </SmoothScroll>
  );
}
