'use client';

import { motion } from 'framer-motion';

import { MODULES } from '@/lib/modules';
import { useSceneStore } from '@/lib/store/use-scene-store';

/**
 * Fixed top navigation. The module list is rendered as small dot indicators
 * that fill with the module's accent colour as scroll enters that section —
 * a glanceable progress map.
 */
export function Navigation() {
  const activeIdx = useSceneStore((s) => s.activeModuleIdx);

  return (
    <motion.nav
      initial={{ opacity: 0, y: -12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.8, ease: 'easeOut', delay: 0.4 }}
      className="pointer-events-auto fixed inset-x-0 top-0 z-30 flex items-center justify-between px-6 py-5 md:px-10"
    >
      <a href="#" className="flex items-center gap-3" aria-label="BizVision AI home">
        <span className="grid h-7 w-7 place-items-center rounded-md border border-cyan/40 bg-cyan/10 font-data text-xs text-cyan">
          BV
        </span>
        <span className="hidden font-ui text-sm font-semibold tracking-tight text-text-primary md:inline">
          BizVision AI
        </span>
      </a>

      {/* Module dot map */}
      <div className="hidden items-center gap-2 md:flex" aria-hidden>
        {MODULES.map((m, i) => {
          const active = i === activeIdx;
          return (
            <a
              key={m.id}
              href={`#${m.id}`}
              className="group flex items-center gap-2 px-2"
            >
              <span
                className="h-1.5 w-1.5 rounded-full transition-all duration-500"
                style={{
                  backgroundColor: active ? m.accent : 'rgba(138, 160, 184, 0.35)',
                  boxShadow: active ? `0 0 12px ${m.accent}` : 'none',
                  transform: active ? 'scale(1.4)' : 'scale(1)',
                }}
              />
              <span
                className="hidden font-data text-2xs uppercase tracking-widest text-text-muted transition-colors group-hover:text-text-primary lg:inline"
                style={active ? { color: m.accent } : undefined}
              >
                {m.id}
              </span>
            </a>
          );
        })}
      </div>

      <a
        href="/dashboard"
        className="pointer-events-auto rounded-full border border-cyan/40 bg-cyan/5 px-4 py-2 font-data text-2xs uppercase tracking-widest text-cyan transition-all hover:bg-cyan/10 hover:shadow-glow-cyan"
      >
        Launch
      </a>
    </motion.nav>
  );
}
