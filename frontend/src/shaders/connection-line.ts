/**
 * Energy-connection shader — animated tendrils running from the neural core
 * out to each module planet. Implemented as a parameterised line strip whose
 * vertex shader displaces along the segment normal using time-based noise,
 * and whose fragment shader paints a travelling-pulse gradient.
 *
 * `aT` (0..1 along the line) and `aSeed` (per-line random) are instance
 * attributes set on the BufferGeometry.
 */

import { SNOISE_3D } from './noise';

export const connectionVertex = /* glsl */ `
  uniform float uTime;
  uniform float uActivation;

  attribute float aT;
  attribute float aSeed;

  varying float vT;
  varying float vSeed;

  ${SNOISE_3D}

  void main() {
    vT = aT;
    vSeed = aSeed;

    // Small lateral wobble that grows toward the midpoint.
    float wob = sin(aT * 3.14159) * 0.35;
    vec3 wobble = vec3(
      snoise(vec3(aT * 4.0, aSeed * 5.0, uTime * 0.6)),
      snoise(vec3(aT * 4.0, aSeed * 5.0 + 1.0, uTime * 0.6)),
      snoise(vec3(aT * 4.0, aSeed * 5.0 + 2.0, uTime * 0.6))
    ) * wob * (0.6 + uActivation * 0.8);

    vec4 mv = modelViewMatrix * vec4(position + wobble, 1.0);
    gl_Position = projectionMatrix * mv;
  }
`;

export const connectionFragment = /* glsl */ `
  uniform float uTime;
  uniform float uActivation;
  uniform vec3  uAccent;

  varying float vT;
  varying float vSeed;

  void main() {
    // Travelling pulse: a gaussian bump that walks along t.
    float head = fract(uTime * 0.4 + vSeed);
    float pulse = exp(-pow((vT - head) * 8.0, 2.0));

    // Soft base intensity along the whole line, brighter when activated.
    float base = (0.18 + uActivation * 0.45) * smoothstep(0.0, 0.05, vT) * smoothstep(1.0, 0.95, vT);

    float a = clamp(pulse * (0.8 + uActivation) + base, 0.0, 1.0);
    gl_FragColor = vec4(uAccent, a);
  }
`;

export type ConnectionUniforms = {
  uTime: { value: number };
  uActivation: { value: number };
  uAccent: { value: [number, number, number] };
};
