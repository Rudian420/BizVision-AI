/**
 * Holographic planet shader — drives the five module orbs.
 *
 * • Fresnel-driven rim glow tinted by `uAccent`
 * • Scanline pattern (animated by `uTime`) — the "data" texture
 * • Iridescent core via cosine palette
 * • Activation: when `uActivation` → 1, brightness + chromatic intensity ramp
 *   up; used by the camera choreography to "spotlight" the active module.
 *
 * Cost: cheap fragment work (no noise, no loops); safe on LOW tier.
 */

import { SNOISE_3D } from './noise';

export const holographicVertex = /* glsl */ `
  varying vec3 vNormal;
  varying vec3 vViewPosition;
  varying vec2 vUv;

  void main() {
    vUv = uv;
    vec4 mv = modelViewMatrix * vec4(position, 1.0);
    vViewPosition = -mv.xyz;
    vNormal = normalize(normalMatrix * normal);
    gl_Position = projectionMatrix * mv;
  }
`;

export const holographicFragment = /* glsl */ `
  uniform float uTime;
  uniform float uActivation;        // 0..1, rises when this module is in focus
  uniform vec3  uAccent;            // module accent colour
  uniform vec3  uAccentDim;
  uniform float uScanlineDensity;   // lines per unit (≈ 60)

  varying vec3 vNormal;
  varying vec3 vViewPosition;
  varying vec2 vUv;

  ${SNOISE_3D}

  // Inigo Quilez cosine palette
  vec3 palette(float t, vec3 a, vec3 b, vec3 c, vec3 d) {
    return a + b * cos(6.2831853 * (c * t + d));
  }

  void main() {
    vec3 N = normalize(vNormal);
    vec3 V = normalize(vViewPosition);
    float fres = pow(1.0 - max(dot(N, V), 0.0), 2.2);

    // Animated holographic scanlines along the surface UV.
    float scan = smoothstep(0.48, 0.52,
                  fract(vUv.y * uScanlineDensity - uTime * 0.4));
    float jitter = snoise(vec3(vUv * 8.0, uTime * 0.5)) * 0.5 + 0.5;

    // Core iridescence — slow cosine palette modulated by noise.
    vec3 core = palette(
      jitter * 0.6 + uTime * 0.04,
      uAccentDim,
      uAccent * 0.6,
      vec3(0.8, 0.8, 0.8),
      vec3(0.0, 0.33, 0.67)
    );

    // Activation increases brightness + tightens scan contrast.
    float boost = mix(0.55, 1.4, uActivation);
    vec3 col = core * boost;
    col += uAccent * fres * (1.2 + uActivation);
    col *= 1.0 - 0.18 * scan;

    // Edge halo — additive ring that pops on activation.
    float halo = smoothstep(0.7, 1.0, fres) * (0.4 + uActivation * 0.8);
    col += uAccent * halo;

    gl_FragColor = vec4(col, 0.92);
  }
`;

/** Uniform schema reused by the React material; keep keys in sync. */
export type HolographicUniforms = {
  uTime: { value: number };
  uActivation: { value: number };
  uAccent: { value: [number, number, number] };
  uAccentDim: { value: [number, number, number] };
  uScanlineDensity: { value: number };
};
