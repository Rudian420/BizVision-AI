'use client';

import { Canvas } from '@react-three/fiber';
import { Suspense } from 'react';

import { LoadingScreen } from '@/components/ui/LoadingScreen';
import { useActiveModule } from '@/hooks/use-active-module';
import { useMouseParallax } from '@/hooks/use-mouse-parallax';
import { useReducedMotion } from '@/hooks/use-reduced-motion';
import { useRenderTier } from '@/hooks/use-render-tier';
import { useSceneStore } from '@/lib/store/use-scene-store';

import AmbientStars from './AmbientStars';
import CinematicCamera from './CinematicCamera';
import EnergyConnections from './EnergyConnections';
import ModulePlanets from './ModulePlanets';
import NeuralGalaxy from './NeuralGalaxy';
import PostProcessing from '../postfx/PostProcessing';

/**
 * The single 3D entry point for the landing experience. Owns the WebGL
 * context and decides — once tier detection has run — what to render and at
 * what fidelity.
 *
 * Mounted as a fixed-position element behind the HTML overlay (see
 * `page.tsx`). Pointer events are off so the HTML layer remains interactive.
 *
 * Scroll architecture (ADR-018): the **window scroll** is the single source
 * of truth — Lenis smooths it, `useActiveModule` normalises it to 0..1, and
 * 3D scenes read `useSceneStore.getState().scrollOffset` inside `useFrame`.
 * Drei's `ScrollControls` is intentionally NOT used to avoid dual scroll.
 */
export function SceneStage() {
  // Side-effect hooks: must run on the HTML layer so they have window access
  // (not legal inside Canvas). They publish into the Zustand scene store.
  useRenderTier();
  useReducedMotion();
  useActiveModule();
  useMouseParallax();

  const ready = useSceneStore((s) => s.ready);
  const profile = useSceneStore((s) => s.profile);
  const prefersReducedMotion = useSceneStore((s) => s.prefersReducedMotion);

  if (!ready) {
    return <LoadingScreen />;
  }

  return (
    <Canvas
      gl={{
        antialias: true,
        // ACESFilmic tone-mapping for the cinematic look.
        toneMapping: 4,
        toneMappingExposure: 1.18,
        powerPreference: 'high-performance',
      }}
      camera={{ position: [0, 4.5, 22], fov: 55, near: 0.1, far: 200 }}
      dpr={profile.dpr}
      frameloop={prefersReducedMotion ? 'demand' : 'always'}
    >
      <Suspense fallback={null}>
        <ambientLight intensity={0.08} />
        <pointLight position={[0, 0, 0]} intensity={2.4} color="#00F5FF" distance={40} decay={2} />
        <pointLight position={[6, 6, -6]} intensity={0.6} color="#7C3AED" distance={30} />

        <AmbientStars />
        <NeuralGalaxy />
        <EnergyConnections />
        <ModulePlanets />

        <CinematicCamera />
      </Suspense>

      <PostProcessing />
    </Canvas>
  );
}
