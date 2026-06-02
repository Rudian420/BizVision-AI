'use client';

import { motion, useReducedMotion } from 'framer-motion';

const HEAD_EASE = [0.76, 0, 0.24, 1] as const;

/**
 * Hero headline overlaid on the neural-galaxy canvas.
 *
 * The lines reveal in a staggered mask-up sequence — translateY + opacity
 * on each. Eyebrow letter-spaces out; subtitle fades up after the heading.
 */
export function HeroText() {
  const rm = useReducedMotion();
  const lineVariants = {
    hidden: { y: rm ? 0 : 64, opacity: 0 },
    show: (i: number) => ({
      y: 0,
      opacity: 1,
      transition: { delay: rm ? 0 : 0.25 + i * 0.18, duration: rm ? 0.01 : 1.0, ease: HEAD_EASE },
    }),
  };

  return (
    <div className="relative px-6 text-center">
      <motion.p
        initial={{ opacity: 0, letterSpacing: '0.2em' }}
        animate={{ opacity: 1, letterSpacing: '0.5em' }}
        transition={{ duration: rm ? 0.01 : 1.6, ease: 'easeOut' }}
        className="mb-6 font-data text-2xs uppercase text-text-secondary"
      >
        DECISION INTELLIGENCE FOR SME
      </motion.p>

      <h1 className="font-ui text-4xl font-bold leading-[0.95] text-text-primary md:text-6xl lg:text-hero">
        <span className="block overflow-hidden">
          <motion.span
            variants={lineVariants}
            custom={0}
            initial="hidden"
            animate="show"
            className="block"
          >
            Enterprise intelligence,
          </motion.span>
        </span>

        <span className="block overflow-hidden">
          <motion.span
            variants={lineVariants}
            custom={1}
            initial="hidden"
            animate="show"
            className="block bg-gradient-to-r from-cyan via-violet to-gold bg-clip-text text-transparent"
          >
            for every SME.
          </motion.span>
        </span>
      </h1>

      <motion.p
        initial={{ opacity: 0, y: rm ? 0 : 18 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: rm ? 0 : 0.85, duration: rm ? 0.01 : 0.9, ease: 'easeOut' }}
        className="mx-auto mt-8 max-w-2xl font-ui text-base text-text-secondary md:text-lg"
      >
        Recruitment, pricing, forecasting, ESG and an executive AI advisor —
        explainable, fair, and unified in one cinematic platform.
      </motion.p>

      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: rm ? 0 : 1.6, duration: 0.8 }}
        className="pointer-events-none mt-16 flex flex-col items-center gap-2"
      >
        <span className="font-data text-2xs uppercase tracking-[0.4em] text-text-muted">
          scroll
        </span>
        <span className="h-8 w-px bg-gradient-to-b from-cyan/60 to-transparent" />
      </motion.div>
    </div>
  );
}
