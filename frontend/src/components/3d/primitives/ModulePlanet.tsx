'use client';

import { useFrame } from '@react-three/fiber';
import { useEffect, useMemo, useRef } from 'react';
import * as THREE from 'three';

import { hexToVec3, type ModuleMeta } from '@/lib/modules';
import { useSceneStore } from '@/lib/store/use-scene-store';
import {
  holographicFragment,
  holographicVertex,
  type HolographicUniforms,
} from '@/shaders/holographic';

type Props = {
  module: ModuleMeta;
  /** This planet's index within the MODULES array (drives activation matching). */
  index: number;
  /** Orbit radius from the origin. */
  radius: number;
  /** Base scale. */
  scale?: number;
};

/**
 * A single holographic module planet. Geometry choice is module-specific
 * (recruitment → octahedron / pricing → torus knot, etc.) — bespoke silhouettes
 * read at a glance from far camera distances and re-enforce module identity.
 *
 * Activation lerps when the module becomes active (see `useActiveModule`):
 * camera lingers, accent ramps, scanline contrast tightens.
 */
export function ModulePlanet({ module, index, radius, scale = 1 }: Props) {
  const groupRef = useRef<THREE.Group>(null);
  const materialRef = useRef<THREE.ShaderMaterial>(null);

  const uniforms: HolographicUniforms = useMemo(
    () => ({
      uTime: { value: 0 },
      uActivation: { value: 0 },
      uAccent: { value: [...hexToVec3(module.accent)] as [number, number, number] },
      uAccentDim: { value: [...hexToVec3(module.accentDim)] as [number, number, number] },
      uScanlineDensity: { value: 60 },
    }),
    [module.accent, module.accentDim],
  );

  // Phase the orbit so planets aren't bunched in space.
  const orbitTheta = module.orbitAngle * Math.PI * 2;
  const initialPosition = useMemo<THREE.Vector3>(
    () =>
      new THREE.Vector3(
        Math.cos(orbitTheta) * radius,
        Math.sin(orbitTheta * 0.7) * 1.2,
        Math.sin(orbitTheta) * radius,
      ),
    [orbitTheta, radius],
  );

  // PERF: dispose mesh geometry + shader material on unmount
  // (TASK-039 audit). React-three-fiber does NOT auto-dispose primitive
  // children — without this each route-change leaks one geometry + one
  // shader program per planet (5 × landings = 10 leaks per round trip).
  useEffect(() => {
    const group = groupRef.current;
    return () => {
      if (!group) return;
      group.traverse((obj) => {
        const mesh = obj as THREE.Mesh;
        const geo = mesh.geometry as THREE.BufferGeometry | undefined;
        const mat = mesh.material as THREE.ShaderMaterial | undefined;
        geo?.dispose?.();
        mat?.dispose?.();
      });
    };
  }, []);

  useFrame(({ clock }, dt) => {
    if (!groupRef.current || !materialRef.current) return;
    const t = clock.getElapsedTime();
    const { activeModuleIdx, prefersReducedMotion } = useSceneStore.getState();

    materialRef.current.uniforms.uTime.value = t * (prefersReducedMotion ? 0.2 : 1);

    // Activation eases toward 1 when this module is in focus.
    const target = activeModuleIdx === index ? 1 : 0;
    const cur = materialRef.current.uniforms.uActivation.value;
    materialRef.current.uniforms.uActivation.value =
      cur + (target - cur) * Math.min(1, dt * 3);

    // Gentle orbit — full revolution every ~120s. Reduced motion stops it.
    if (!prefersReducedMotion) {
      const omega = 0.05;
      const theta = orbitTheta + t * omega;
      groupRef.current.position.set(
        Math.cos(theta) * radius,
        Math.sin(theta * 0.7) * 1.2,
        Math.sin(theta) * radius,
      );
      groupRef.current.rotation.y += dt * 0.2;
    }
  });

  // Bespoke silhouettes per module.
  const geometry = useMemo(() => {
    switch (module.id) {
      case 'recruitment':
        return <octahedronGeometry args={[1, 2]} />;
      case 'pricing':
        return <torusKnotGeometry args={[0.7, 0.22, 96, 16]} />;
      case 'forecasting':
        return <icosahedronGeometry args={[1, 2]} />;
      case 'sustainability':
        return <dodecahedronGeometry args={[1, 0]} />;
      case 'chatbot':
      default:
        return <sphereGeometry args={[1, 48, 48]} />;
    }
  }, [module.id]);

  return (
    <group ref={groupRef} position={initialPosition} scale={scale}>
      <mesh>
        {geometry}
        <shaderMaterial
          ref={materialRef}
          vertexShader={holographicVertex}
          fragmentShader={holographicFragment}
          uniforms={uniforms as unknown as Record<string, THREE.IUniform>}
          transparent
          side={THREE.DoubleSide}
          depthWrite={false}
        />
      </mesh>
    </group>
  );
}
