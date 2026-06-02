'use client';

import { useEffect, useMemo, useRef } from 'react';
import * as THREE from 'three';

import { useSceneStore } from '@/lib/store/use-scene-store';

/**
 * Cheap, far-field starfield rendered as a single `Points` cloud.
 * Provides depth to the void at zero per-frame cost (no animation uniforms;
 * static positions, additive blend). Count comes from the render-tier profile.
 */
export default function AmbientStars() {
  const count = useMemo(() => useSceneStore.getState().profile.starCount, []);
  const pointsRef = useRef<THREE.Points>(null);

  const positions = useMemo(() => {
    const arr = new Float32Array(count * 3);
    for (let i = 0; i < count; i++) {
      // Random distribution on a sphere shell at ~80–120 units.
      const r = 80 + Math.random() * 40;
      const phi = Math.random() * Math.PI;
      const theta = Math.random() * Math.PI * 2;
      arr[i * 3] = Math.sin(phi) * Math.cos(theta) * r;
      arr[i * 3 + 1] = Math.cos(phi) * r;
      arr[i * 3 + 2] = Math.sin(phi) * Math.sin(theta) * r;
    }
    return arr;
  }, [count]);

  // PERF: dispose GPU buffers on unmount (TASK-039 audit).
  useEffect(() => {
    const points = pointsRef.current;
    return () => {
      if (!points) return;
      const geo = points.geometry as THREE.BufferGeometry | null;
      const mat = points.material as THREE.PointsMaterial | null;
      geo?.dispose();
      mat?.dispose();
    };
  }, []);

  return (
    <points ref={pointsRef}>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" args={[positions, 3]} />
      </bufferGeometry>
      <pointsMaterial
        size={0.06}
        color={0xb8d4f0}
        sizeAttenuation
        transparent
        opacity={0.75}
        depthWrite={false}
        blending={THREE.AdditiveBlending}
      />
    </points>
  );
}
