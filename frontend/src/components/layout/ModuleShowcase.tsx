'use client';

import { motion } from 'framer-motion';

import { SectionReveal } from '@/components/ui/SectionReveal';
import { MODULES, type ModuleMeta } from '@/lib/modules';

/**
 * Module showcase sections — one per AI module — pinned vertically as the
 * camera dollies between planets in the 3D scene. Each section uses its
 * module accent colour for the glow, eyebrow, and stat block.
 *
 * Layout: text column on alternating sides per section so the 3D planet
 * (positioned in scene space by orbit angle) reads as the "subject" while
 * the copy sits in negative space.
 */
export function ModuleShowcase() {
  return (
    <>
      {MODULES.map((m, i) => (
        <ModuleSection key={m.id} module={m} flip={i % 2 === 1} />
      ))}
    </>
  );
}

function ModuleSection({ module, flip }: { module: ModuleMeta; flip: boolean }) {
  const side = flip ? 'md:justify-end' : 'md:justify-start';
  return (
    <section
      id={module.id}
      data-scroll-section={module.id}
      className={`flex h-screen items-center px-6 md:px-16 ${side}`}
    >
      <SectionReveal className="pointer-events-auto max-w-xl">
        <motion.div
          className="flex items-center gap-3"
          variants={{ hidden: { opacity: 0 }, visible: { opacity: 1 } }}
        >
          <span
            className="font-data text-2xs uppercase tracking-[0.4em]"
            style={{ color: module.accent }}
          >
            {module.glyph} {module.id}
          </span>
          <span className="h-px flex-1 bg-gradient-to-r from-current/40 to-transparent" />
        </motion.div>

        <motion.h2
          variants={{ hidden: { opacity: 0, y: 24 }, visible: { opacity: 1, y: 0 } }}
          className="mt-4 font-ui text-3xl font-bold text-text-primary md:text-5xl"
        >
          {module.label}
        </motion.h2>

        <motion.p
          variants={{ hidden: { opacity: 0, y: 18 }, visible: { opacity: 1, y: 0 } }}
          className="mt-3 font-ui text-lg italic"
          style={{ color: module.accentDim }}
        >
          {module.tagline}
        </motion.p>

        <motion.p
          variants={{ hidden: { opacity: 0, y: 18 }, visible: { opacity: 1, y: 0 } }}
          className="mt-6 font-ui text-base leading-relaxed text-text-secondary"
        >
          {module.blurb}
        </motion.p>

        {/* Stat block — large numeric over compact label */}
        <motion.div
          variants={{ hidden: { opacity: 0, y: 18 }, visible: { opacity: 1, y: 0 } }}
          className="mt-8 inline-flex items-baseline gap-3 rounded-lg border bg-abyss/40 px-5 py-4 backdrop-blur-sm"
          style={{ borderColor: `${module.accent}33` }}
        >
          <span
            className="font-ui text-4xl font-bold leading-none"
            style={{ color: module.accent, textShadow: `0 0 24px ${module.accent}55` }}
          >
            {module.stat}
          </span>
          <span className="font-data text-2xs uppercase tracking-widest text-text-secondary">
            {module.statLabel}
          </span>
        </motion.div>
      </SectionReveal>
    </section>
  );
}
