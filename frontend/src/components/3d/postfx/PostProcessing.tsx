'use client';

import {
  Bloom,
  ChromaticAberration,
  EffectComposer,
  Noise,
  Vignette,
} from '@react-three/postprocessing';
import { BlendFunction, KernelSize } from 'postprocessing';
import { useMemo } from 'react';
import { Vector2 } from 'three';

import { useSceneStore } from '@/lib/store/use-scene-store';

/**
 * Tier-aware post-processing stack (ADR-016).
 *
 *   LOW  — vignette only (1 pass)
 *   MED  — vignette + bloom (2 passes)
 *   HIGH — vignette + bloom + chromatic aberration + film-grain noise (4)
 *
 * Reduced motion strips noise + chromatic aberration even on HIGH.
 *
 * `EffectComposer` cost dominates frame time on this app; this single
 * switch is the highest-leverage perf knob.
 */
export default function PostProcessing() {
  const profile = useSceneStore((s) => s.profile);
  const prefersReducedMotion = useSceneStore((s) => s.prefersReducedMotion);

  const chromaticOffset = useMemo(() => new Vector2(0.0008, 0.0008), []);

  // Bloom only on MED/HIGH.
  const useBloom = profile.bloom;
  const useCA = profile.chromaticAberration && !prefersReducedMotion;
  const useNoise = profile.noise && !prefersReducedMotion;
  const useVignette = profile.vignette;

  // If nothing is enabled (rare) we can skip the composer entirely.
  if (!useBloom && !useCA && !useNoise && !useVignette) return null;

  return (
    <EffectComposer multisampling={0}>
      {useBloom ? (
        <Bloom
          intensity={1.1}
          luminanceThreshold={0.32}
          luminanceSmoothing={0.18}
          mipmapBlur
          kernelSize={KernelSize.LARGE}
        />
      ) : (
        <></>
      )}
      {useCA ? (
        <ChromaticAberration
          blendFunction={BlendFunction.NORMAL}
          offset={chromaticOffset}
          radialModulation={false}
          modulationOffset={0.5}
        />
      ) : (
        <></>
      )}
      {useNoise ? <Noise opacity={0.025} blendFunction={BlendFunction.OVERLAY} /> : <></>}
      {useVignette ? <Vignette eskil={false} offset={0.18} darkness={0.85} /> : <></>}
    </EffectComposer>
  );
}
