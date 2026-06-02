'use client';

import { motion, useReducedMotion } from 'framer-motion';
import type { ComponentProps, ReactNode } from 'react';

type Props = Omit<ComponentProps<typeof motion.div>, 'initial' | 'animate' | 'whileInView'> & {
  children: ReactNode;
  /** Stagger sub-elements by this many seconds. */
  stagger?: number;
  /** Initial Y offset in px. Higher = more dramatic entrance. */
  offsetY?: number;
};

/**
 * Reusable in-view reveal wrapper. Triggers once when the section enters the
 * viewport — uses framer-motion's intersection observer with `amount: 0.3`.
 * Respects `prefers-reduced-motion` by collapsing to an instant fade.
 */
export function SectionReveal({
  children,
  stagger = 0.08,
  offsetY = 28,
  className,
  ...rest
}: Props) {
  const reducedMotion = useReducedMotion();

  return (
    <motion.div
      initial="hidden"
      whileInView="visible"
      viewport={{ once: true, amount: 0.3 }}
      variants={{
        hidden: {},
        visible: { transition: { staggerChildren: reducedMotion ? 0 : stagger } },
      }}
      className={className}
      {...rest}
    >
      <motion.div
        variants={{
          hidden: { opacity: 0, y: reducedMotion ? 0 : offsetY },
          visible: {
            opacity: 1,
            y: 0,
            transition: { duration: reducedMotion ? 0.01 : 0.8, ease: [0.25, 0.46, 0.45, 0.94] },
          },
        }}
      >
        {children}
      </motion.div>
    </motion.div>
  );
}
