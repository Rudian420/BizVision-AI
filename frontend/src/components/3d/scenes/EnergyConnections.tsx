'use client';

import { useFrame } from '@react-three/fiber';
import { useEffect, useMemo, useRef } from 'react';
import * as THREE from 'three';

import { hexToVec3, MODULES } from '@/lib/modules';
import { useSceneStore } from '@/lib/store/use-scene-store';
import {
  connectionFragment,
  connectionVertex,
  type ConnectionUniforms,
} from '@/shaders/connection-line';

const ORBIT_RADIUS = 8;
const SEGMENTS = 32; // line resolution per connection

/**
 * Animated tendrils running from the neural-galaxy core out to each module
 * planet. Each line is a `LineSegments` strip with two instance attributes:
 * `aT` (0..1 along the line) and `aSeed` (per-line random).
 *
 * Travelling pulses (sliding gaussian in the fragment shader) make the
 * connections feel like data is flowing toward the modules. When a module
 * activates, its line's `uActivation` ramps up — and only that line lights.
 *
 * Rendered as one combined `LineSegments` per module so we issue 5 draw calls
 * total (cheap on every tier).
 */
export default function EnergyConnections() {
  // Build a typed-array buffer for each module: a polyline from origin to the
  // planet's static rest position, with parametric attributes.
  const lines = useMemo(() => {
    return MODULES.map((m) => {
      const theta = m.orbitAngle * Math.PI * 2;
      const target = new THREE.Vector3(
        Math.cos(theta) * ORBIT_RADIUS,
        Math.sin(theta * 0.7) * 1.2,
        Math.sin(theta) * ORBIT_RADIUS,
      );

      const positions = new Float32Array(SEGMENTS * 2 * 3); // line segments
      const tAttr = new Float32Array(SEGMENTS * 2);
      const seedAttr = new Float32Array(SEGMENTS * 2);
      const seed = Math.random();

      for (let i = 0; i < SEGMENTS; i++) {
        const t0 = i / SEGMENTS;
        const t1 = (i + 1) / SEGMENTS;
        const p0 = new THREE.Vector3().lerpVectors(new THREE.Vector3(), target, t0);
        const p1 = new THREE.Vector3().lerpVectors(new THREE.Vector3(), target, t1);
        const o = i * 6;
        positions[o] = p0.x;
        positions[o + 1] = p0.y;
        positions[o + 2] = p0.z;
        positions[o + 3] = p1.x;
        positions[o + 4] = p1.y;
        positions[o + 5] = p1.z;
        tAttr[i * 2] = t0;
        tAttr[i * 2 + 1] = t1;
        seedAttr[i * 2] = seed;
        seedAttr[i * 2 + 1] = seed;
      }

      const uniforms: ConnectionUniforms = {
        uTime: { value: 0 },
        uActivation: { value: 0 },
        uAccent: { value: [...hexToVec3(m.accent)] as [number, number, number] },
      };
      return { positions, tAttr, seedAttr, uniforms, id: m.id };
    });
  }, []);

  const materials = useRef<THREE.ShaderMaterial[]>([]);
  const groupRef = useRef<THREE.Group>(null);

  // PERF: dispose all per-module geometries + materials on unmount
  // (TASK-039 audit). 5 lineSegments meshes × (1 BufferGeometry + 1
  // ShaderMaterial) = 10 GPU resources to release.
  useEffect(() => {
    const group = groupRef.current;
    return () => {
      if (!group) return;
      group.traverse((obj) => {
        const line = obj as THREE.LineSegments;
        const geo = line.geometry as THREE.BufferGeometry | undefined;
        const mat = line.material as THREE.ShaderMaterial | undefined;
        geo?.dispose?.();
        mat?.dispose?.();
      });
    };
  }, []);

  useFrame(({ clock }, dt) => {
    const t = clock.getElapsedTime();
    const { activeModuleIdx, prefersReducedMotion } = useSceneStore.getState();
    materials.current.forEach((mat, i) => {
      if (!mat) return;
      mat.uniforms.uTime.value = prefersReducedMotion ? 0 : t;
      const target = activeModuleIdx === i ? 1 : 0;
      const cur = mat.uniforms.uActivation.value;
      mat.uniforms.uActivation.value = cur + (target - cur) * Math.min(1, dt * 3);
    });
  });

  return (
    <group ref={groupRef}>
      {lines.map((line, i) => (
        <lineSegments key={line.id}>
          <bufferGeometry>
            <bufferAttribute attach="attributes-position" args={[line.positions, 3]} />
            <bufferAttribute attach="attributes-aT" args={[line.tAttr, 1]} />
            <bufferAttribute attach="attributes-aSeed" args={[line.seedAttr, 1]} />
          </bufferGeometry>
          <shaderMaterial
            ref={(m) => {
              if (m) materials.current[i] = m;
            }}
            vertexShader={connectionVertex}
            fragmentShader={connectionFragment}
            uniforms={line.uniforms as unknown as Record<string, THREE.IUniform>}
            transparent
            depthWrite={false}
            blending={THREE.AdditiveBlending}
          />
        </lineSegments>
      ))}
    </group>
  );
}
