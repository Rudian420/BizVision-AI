'use client';

import { motion, useReducedMotion } from 'framer-motion';

/**
 * Closing CTA — emerges from the void as the camera pulls back over the
 * neural galaxy. Multi-layer reveal: an eyebrow line, a two-line headline
 * with gradient sweep, then the launch button with a cyan glow ring.
 */
export function CTASection() {
  const rm = useReducedMotion();

  return (
    <section
      data-scroll-section="cta"
      className="flex h-screen flex-col items-center justify-center px-6 text-center"
    >
      <motion.span
        initial={{ opacity: 0, letterSpacing: '0.2em' }}
        whileInView={{ opacity: 1, letterSpacing: '0.5em' }}
        viewport={{ once: true, amount: 0.5 }}
        transition={{ duration: rm ? 0.01 : 1.2, ease: 'easeOut' }}
        className="mb-8 font-data text-2xs uppercase text-text-secondary"
      >
        — INITIALISE
      </motion.span>

      <h2 className="font-ui text-4xl font-bold leading-[0.95] text-text-primary md:text-5xl lg:text-hero">
        <motion.span
          initial={{ opacity: 0, y: rm ? 0 : 40 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, amount: 0.5 }}
          transition={{ duration: rm ? 0.01 : 0.9, ease: [0.76, 0, 0.24, 1] }}
          className="block"
        >
          See your business,
        </motion.span>
        <motion.span
          initial={{ opacity: 0, y: rm ? 0 : 40 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, amount: 0.5 }}
          transition={{
            delay: rm ? 0 : 0.18,
            duration: rm ? 0.01 : 0.9,
            ease: [0.76, 0, 0.24, 1],
          }}
          className="block bg-gradient-to-r from-cyan via-violet to-coral bg-clip-text text-transparent"
        >
          with intelligence.
        </motion.span>
      </h2>

      <motion.div
        initial={{ opacity: 0, scale: rm ? 1 : 0.92 }}
        whileInView={{ opacity: 1, scale: 1 }}
        viewport={{ once: true, amount: 0.5 }}
        transition={{ delay: rm ? 0 : 0.5, duration: rm ? 0.01 : 0.8, ease: 'easeOut' }}
        className="pointer-events-auto mt-12 flex flex-col items-center gap-4"
      >
        <a
          href="/dashboard"
          className="group relative inline-flex items-center gap-2 rounded-full bg-cyan px-8 py-3 font-ui font-semibold text-void shadow-glow-cyan transition-transform hover:scale-[1.03]"
        >
          <span>Launch BizVision AI</span>
          <span className="transition-transform group-hover:translate-x-1">→</span>
        </a>
        <span className="font-data text-2xs uppercase tracking-[0.3em] text-text-muted">
          no credit card · 60-second setup
        </span>
      </motion.div>
    </section>
  );
}
