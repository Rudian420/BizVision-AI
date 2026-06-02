'use client';

import { MODULES } from '@/lib/modules';

import { ModulePlanet } from '../primitives/ModulePlanet';

const ORBIT_RADIUS = 8;

/**
 * The five module planets in their orbital arrangement. Replaces the
 * Phase-1 placeholder of identical icosahedrons — each module now has a
 * bespoke silhouette + holographic shader + activation-driven lighting.
 *
 * Phase-5 (3D-001..005) will replace each planet with its full bespoke
 * module experience (candidate constellation, price surface, etc.).
 */
export default function ModulePlanets() {
  return (
    <group>
      {MODULES.map((module, i) => (
        <ModulePlanet
          key={module.id}
          module={module}
          index={i}
          radius={ORBIT_RADIUS}
          scale={module.id === 'chatbot' ? 0.95 : 0.85}
        />
      ))}
    </group>
  );
}
