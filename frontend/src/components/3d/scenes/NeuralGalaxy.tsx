"use client";

/**
 * NeuralGalaxy — 100K GPU Particle System
 *
 * The cinematic hero background: a vast neural network rendered as
 * a galaxy of interconnected luminous particles in deep space.
 *
 * Architecture:
 * - BufferGeometry with instanced attributes for 100K particles
 * - Custom GLSL vertex/fragment shaders for neural glow effect
 * - ScrollControls-driven animation (particles converge on scroll)
 * - Postprocessing: bloom + chromatic aberration for cinematic look
 */

import { useEffect, useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";

import { useSceneStore } from "@/lib/store/use-scene-store";

// ── GLSL Shaders ──────────────────────────────────────────────
const vertexShader = /* glsl */ `
  uniform float uTime;
  uniform float uScrollProgress;
  uniform vec3 uMousePosition;

  attribute float aSize;
  attribute float aPhase;
  attribute vec3 aVelocity;
  attribute float aNodeType; // 0=particle, 1=neural node

  varying float vAlpha;
  varying float vNodeType;
  varying vec3 vColor;

  // Simplex noise for organic motion
  vec3 mod289(vec3 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }
  vec4 mod289(vec4 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }
  vec4 permute(vec4 x) { return mod289(((x * 34.0) + 10.0) * x); }
  vec4 taylorInvSqrt(vec4 r) { return 1.79284291400159 - 0.85373472095314 * r; }

  float snoise(vec3 v) {
    const vec2 C = vec2(1.0/6.0, 1.0/3.0);
    const vec4 D = vec4(0.0, 0.5, 1.0, 2.0);
    vec3 i = floor(v + dot(v, C.yyy));
    vec3 x0 = v - i + dot(i, C.xxx);
    vec3 g = step(x0.yzx, x0.xyz);
    vec3 l = 1.0 - g;
    vec3 i1 = min(g.xyz, l.zxy);
    vec3 i2 = max(g.xyz, l.zxy);
    vec3 x1 = x0 - i1 + C.xxx;
    vec3 x2 = x0 - i2 + C.yyy;
    vec3 x3 = x0 - D.yyy;
    i = mod289(i);
    vec4 p = permute(permute(permute(
      i.z + vec4(0.0, i1.z, i2.z, 1.0))
      + i.y + vec4(0.0, i1.y, i2.y, 1.0))
      + i.x + vec4(0.0, i1.x, i2.x, 1.0));
    float n_ = 0.142857142857;
    vec3 ns = n_ * D.wyz - D.xzx;
    vec4 j = p - 49.0 * floor(p * ns.z * ns.z);
    vec4 x_ = floor(j * ns.z);
    vec4 y_ = floor(j - 7.0 * x_);
    vec4 x = x_ * ns.x + ns.yyyy;
    vec4 y = y_ * ns.x + ns.yyyy;
    vec4 h = 1.0 - abs(x) - abs(y);
    vec4 b0 = vec4(x.xy, y.xy);
    vec4 b1 = vec4(x.zw, y.zw);
    vec4 s0 = floor(b0) * 2.0 + 1.0;
    vec4 s1 = floor(b1) * 2.0 + 1.0;
    vec4 sh = -step(h, vec4(0.0));
    vec4 a0 = b0.xzyw + s0.xzyw * sh.xxyy;
    vec4 a1 = b1.xzyw + s1.xzyw * sh.zzww;
    vec3 p0 = vec3(a0.xy, h.x);
    vec3 p1 = vec3(a0.zw, h.y);
    vec3 p2 = vec3(a1.xy, h.z);
    vec3 p3 = vec3(a1.zw, h.w);
    vec4 norm = taylorInvSqrt(vec4(dot(p0,p0), dot(p1,p1), dot(p2,p2), dot(p3,p3)));
    p0 *= norm.x; p1 *= norm.y; p2 *= norm.z; p3 *= norm.w;
    vec4 m = max(0.6 - vec4(dot(x0,x0), dot(x1,x1), dot(x2,x2), dot(x3,x3)), 0.0);
    m = m * m;
    return 42.0 * dot(m*m, vec4(dot(p0,x0), dot(p1,x1), dot(p2,x2), dot(p3,x3)));
  }

  void main() {
    // Organic drift using noise
    float noiseX = snoise(position * 0.1 + uTime * 0.05 + aPhase);
    float noiseY = snoise(position * 0.1 + uTime * 0.07 + aPhase + 100.0);
    float noiseZ = snoise(position * 0.1 + uTime * 0.03 + aPhase + 200.0);

    vec3 displaced = position + vec3(noiseX, noiseY, noiseZ) * 0.5;

    // Scroll convergence: particles fly toward center on scroll
    float convergence = uScrollProgress * uScrollProgress; // Ease-in-quad
    displaced = mix(displaced, aVelocity * 2.0, convergence * 0.4);

    // Mouse attraction (subtle)
    vec3 toMouse = uMousePosition - displaced;
    float mouseDist = length(toMouse);
    displaced += normalize(toMouse) * (1.0 / (mouseDist + 1.0)) * 0.2;

    vec4 mvPosition = modelViewMatrix * vec4(displaced, 1.0);
    gl_Position = projectionMatrix * mvPosition;

    // Size: neural nodes are larger, pulse with time
    float pulse = sin(uTime * 2.0 + aPhase * 6.28318) * 0.3 + 0.7;
    gl_PointSize = aSize * pulse * (300.0 / -mvPosition.z);

    // Alpha: fade based on depth + scroll
    vAlpha = (1.0 - smoothstep(20.0, 50.0, -mvPosition.z)) * (1.0 - convergence * 0.3);
    vNodeType = aNodeType;

    // Color gradient: core (cyan) → edge (violet)
    float distFromCenter = length(position) / 30.0;
    vColor = mix(
      vec3(0.0, 0.96, 1.0),   // Cyan center
      vec3(0.48, 0.23, 0.93), // Violet edge
      clamp(distFromCenter, 0.0, 1.0)
    );
  }
`;

const fragmentShader = /* glsl */ `
  varying float vAlpha;
  varying float vNodeType;
  varying vec3 vColor;

  void main() {
    // Circular point with soft edge
    vec2 center = gl_PointCoord - 0.5;
    float dist = length(center);

    if (dist > 0.5) discard;

    // Glow: bright core, soft falloff
    float glow = 1.0 - smoothstep(0.0, 0.5, dist);
    glow = pow(glow, 1.5); // Sharpen core

    // Neural nodes have extra halo
    float halo = vNodeType > 0.5
      ? (1.0 - smoothstep(0.2, 0.5, dist)) * 0.5
      : 0.0;

    float alpha = (glow + halo) * vAlpha;
    gl_FragColor = vec4(vColor, alpha);
  }
`;

// ── React Component ────────────────────────────────────────────
export default function NeuralGalaxy() {
  const meshRef = useRef<THREE.Points>(null);
  // Pull particle budget from the render-tier policy (ADR-016).
  // Captured once on mount via Zustand snapshot → particle buffer never reallocates.
  const particleCount = useMemo(() => useSceneStore.getState().profile.particles, []);
  const reducedMotion = useMemo(
    () => useSceneStore.getState().prefersReducedMotion,
    [],
  );

  const { positions, sizes, phases, velocities, nodeTypes } = useMemo(() => {
    const positions = new Float32Array(particleCount * 3);
    const sizes = new Float32Array(particleCount);
    const phases = new Float32Array(particleCount);
    const velocities = new Float32Array(particleCount * 3);
    const nodeTypes = new Float32Array(particleCount);

    for (let i = 0; i < particleCount; i++) {
      const i3 = i * 3;

      // Galaxy spiral distribution
      const arm = Math.floor(Math.random() * 3); // 3 spiral arms
      const radius = Math.pow(Math.random(), 0.5) * 40; // Denser toward center
      const theta = arm * (Math.PI * 2 / 3) + radius * 0.3 + Math.random() * 0.5;
      const height = (Math.random() - 0.5) * 8 * (1 - radius / 40); // Thinner at edges

      positions[i3]     = Math.cos(theta) * radius + (Math.random() - 0.5) * 4;
      positions[i3 + 1] = height;
      positions[i3 + 2] = Math.sin(theta) * radius + (Math.random() - 0.5) * 4;

      // 5% are neural nodes (larger, brighter)
      const isNode = Math.random() < 0.05;
      nodeTypes[i] = isNode ? 1.0 : 0.0;
      sizes[i] = isNode ? 3.0 + Math.random() * 4 : 0.5 + Math.random() * 1.5;

      phases[i] = Math.random() * Math.PI * 2;

      // Convergence target (toward center, scattered like a logo)
      const logoAngle = Math.random() * Math.PI * 2;
      const logoRadius = Math.random() * 5;
      velocities[i3]     = Math.cos(logoAngle) * logoRadius;
      velocities[i3 + 1] = (Math.random() - 0.5) * 3;
      velocities[i3 + 2] = Math.sin(logoAngle) * logoRadius;
    }

    return { positions, sizes, phases, velocities, nodeTypes };
  }, [particleCount]);

  const uniforms = useMemo(() => ({
    uTime: { value: 0 },
    uScrollProgress: { value: 0 },
    uMousePosition: { value: new THREE.Vector3() },
  }), []);

  useFrame(({ clock }) => {
    if (!meshRef.current) return;
    const mat = meshRef.current.material as THREE.ShaderMaterial;
    const { mouseX, mouseY, scrollOffset } = useSceneStore.getState();

    mat.uniforms.uTime.value = clock.getElapsedTime() * (reducedMotion ? 0.2 : 1);
    mat.uniforms.uScrollProgress.value = scrollOffset;
    mat.uniforms.uMousePosition.value.set(
      reducedMotion ? 0 : mouseX * 20,
      reducedMotion ? 0 : mouseY * 10,
      0,
    );
  });

  // PERF: explicit GPU-resource teardown on unmount (TASK-039).
  // BufferGeometry + ShaderMaterial own GPU buffers + compiled shader
  // programs; React-three-fiber does NOT auto-dispose them, so a
  // route-change away from the landing leaks 100K particles' worth of
  // VRAM until the GC runs (which on long-lived tabs may never).
  useEffect(() => {
    const points = meshRef.current;
    return () => {
      if (!points) return;
      const geo = points.geometry as THREE.BufferGeometry | null;
      const mat = points.material as THREE.ShaderMaterial | null;
      geo?.dispose();
      mat?.dispose();
    };
  }, []);

  return (
    <points ref={meshRef}>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" args={[positions, 3]} />
        <bufferAttribute attach="attributes-aSize"     args={[sizes, 1]} />
        <bufferAttribute attach="attributes-aPhase"    args={[phases, 1]} />
        <bufferAttribute attach="attributes-aVelocity" args={[velocities, 3]} />
        <bufferAttribute attach="attributes-aNodeType" args={[nodeTypes, 1]} />
      </bufferGeometry>
      <shaderMaterial
        vertexShader={vertexShader}
        fragmentShader={fragmentShader}
        uniforms={uniforms}
        transparent
        depthWrite={false}
        blending={THREE.AdditiveBlending}
      />
    </points>
  );
}
