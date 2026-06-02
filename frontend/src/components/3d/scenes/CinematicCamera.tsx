'use client';

import { useFrame, useThree } from '@react-three/fiber';
import { useMemo, useRef } from 'react';
import * as THREE from 'three';

import { MODULES } from '@/lib/modules';
import { useSceneStore } from '@/lib/store/use-scene-store';

/**
 * Scroll-driven camera choreography (ADR-017).
 *
 * The narrative is a sequence of waypoints in scroll space. Between
 * adjacent waypoints we evaluate a smooth-step on the local parameter and
 * lerp position + lookAt — Catmull-Rom would smooth tangents further but
 * smoothstep already eliminates first-derivative shock, which is the only
 * visible artefact. Mouse parallax adds a subtle camera shoulder-shake.
 *
 * `useScroll().offset` is preferred over `useSceneStore().scrollOffset`
 * because drei's ScrollControls applies damping, giving the path that
 * cinematic "weight" we want.
 */

type Waypoint = {
  t: number;
  position: THREE.Vector3;
  lookAt: THREE.Vector3;
  /** When in this segment, also rotate the camera roll for tension. */
  roll?: number;
};

const ORBIT_RADIUS = 8;

/** Camera offset relative to a module planet so the planet sits front-left. */
function offsetFor(angle: number): THREE.Vector3 {
  const theta = angle * Math.PI * 2;
  // Place camera outside the orbit, looking inward.
  return new THREE.Vector3(
    Math.cos(theta) * (ORBIT_RADIUS + 4),
    1.5,
    Math.sin(theta) * (ORBIT_RADIUS + 4),
  );
}

/** Where the module planet currently sits (used as lookAt). */
function planetPos(angle: number): THREE.Vector3 {
  const theta = angle * Math.PI * 2;
  return new THREE.Vector3(
    Math.cos(theta) * ORBIT_RADIUS,
    Math.sin(theta * 0.7) * 1.2,
    Math.sin(theta) * ORBIT_RADIUS,
  );
}

function buildPath(): Waypoint[] {
  const HERO_END = 0.15;
  const CTA_START = 0.9;
  const span = CTA_START - HERO_END;
  const stride = span / MODULES.length;

  // Hero: wide-shot of the galaxy from a low angle, looking toward the core.
  const path: Waypoint[] = [
    {
      t: 0,
      position: new THREE.Vector3(0, 4.5, 22),
      lookAt: new THREE.Vector3(0, 0, 0),
    },
    {
      t: HERO_END,
      position: new THREE.Vector3(0, 3, 18),
      lookAt: new THREE.Vector3(0, 0, 0),
    },
  ];

  // One waypoint per module: camera dollies in close to that planet.
  MODULES.forEach((m, i) => {
    const enter = HERO_END + i * stride + stride * 0.15;
    const linger = HERO_END + i * stride + stride * 0.7;
    path.push({
      t: enter,
      position: offsetFor(m.orbitAngle),
      lookAt: planetPos(m.orbitAngle),
      roll: (i % 2 === 0 ? -1 : 1) * 0.04,
    });
    path.push({
      t: linger,
      position: offsetFor(m.orbitAngle).multiplyScalar(0.85),
      lookAt: planetPos(m.orbitAngle),
      roll: (i % 2 === 0 ? -1 : 1) * 0.02,
    });
  });

  // CTA: pull back and rise — the camera "ascends" above the system.
  path.push({
    t: CTA_START,
    position: new THREE.Vector3(0, 6, 22),
    lookAt: new THREE.Vector3(0, 0, 0),
  });
  path.push({
    t: 1,
    position: new THREE.Vector3(0, 10, 28),
    lookAt: new THREE.Vector3(0, 0, 0),
  });

  return path;
}

function smoothstep(x: number): number {
  return x * x * (3 - 2 * x);
}

export default function CinematicCamera() {
  const { camera } = useThree();
  const path = useMemo(() => buildPath(), []);

  // Pre-allocated working vectors — never reallocate inside useFrame.
  const work = useRef({
    pos: new THREE.Vector3(),
    look: new THREE.Vector3(),
    parallax: new THREE.Vector3(),
  });

  // PERF (TASK-039): cache the last segment index. Scroll moves
  // monotonically most of the time, so the next frame's `t` almost
  // always falls in the same segment as the previous frame. Starting
  // the linear scan from the cached index turns the average case
  // from O(N) (full sweep of 14 waypoints) into O(1) (single
  // bracket check). Fallback branches walk forward/backward only
  // when the scroll has actually crossed a waypoint boundary.
  const segIdxRef = useRef(0);

  useFrame((_, dt) => {
    const { mouseX, mouseY, prefersReducedMotion, scrollOffset } = useSceneStore.getState();
    const t = scrollOffset;

    // Try the cached segment first; if t still bracketed, O(1).
    let i = segIdxRef.current;
    if (i < 0 || i >= path.length - 1) i = 0;
    if (t < path[i]!.t) {
      while (i > 0 && t < path[i]!.t) i--;
    } else if (t > path[i + 1]!.t) {
      while (i < path.length - 2 && t > path[i + 1]!.t) i++;
    }
    segIdxRef.current = i;
    const a = path[i]!;
    const b = path[i + 1]!;

    const segLen = Math.max(1e-6, b.t - a.t);
    const local = smoothstep(Math.min(1, Math.max(0, (t - a.t) / segLen)));

    work.current.pos.copy(a.position).lerp(b.position, local);
    work.current.look.copy(a.lookAt).lerp(b.lookAt, local);

    // Mouse parallax: small camera shoulder offset for "alive" feel.
    if (!prefersReducedMotion) {
      work.current.parallax.set(mouseX * 0.6, mouseY * 0.4, 0);
      work.current.pos.add(work.current.parallax);
    }

    // Damp position + lookAt toward target for buttery motion.
    const damp = 1 - Math.pow(0.001, dt); // dt-independent lerp
    camera.position.lerp(work.current.pos, damp);

    // Apply lookAt; preserve a small roll if specified.
    camera.lookAt(work.current.look);
    if (!prefersReducedMotion && a.roll !== undefined) {
      camera.rotation.z = a.roll * (1 - local) + (b.roll ?? 0) * local;
    }
  });

  return null;
}
