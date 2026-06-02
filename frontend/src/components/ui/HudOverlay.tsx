'use client';

import { memo, useEffect, useState } from 'react';

import { MODULES } from '@/lib/modules';
import { useSceneStore } from '@/lib/store/use-scene-store';

/**
 * Cinematic HUD chrome — corner brackets, top-status strip, bottom data
 * ticker. Purely presentational; doesn't block pointer events.
 *
 * Reads the active module to drive an accent line that slides between
 * module markers as the user scrolls.
 *
 * **Perf posture (TASK-039)**: the 1Hz clock is isolated into its own
 * `<ClockReadout>` so its tick does NOT re-render the four corner
 * brackets, the static label spans, the tier readout, or the module
 * ticker. Before the split, `setClock` fired the whole `HudOverlay` →
 * reconciling every DOM child every second for no visible benefit.
 */
export function HudOverlay() {
  const activeIdx = useSceneStore((s) => s.activeModuleIdx);
  const tier = useSceneStore((s) => s.tier);

  return (
    <div className="pointer-events-none fixed inset-0 z-40 select-none">
      {/* ── Corner brackets ──────────────────────────────────── */}
      <Bracket className="left-6 top-6" corner="tl" />
      <Bracket className="right-6 top-6" corner="tr" />
      <Bracket className="left-6 bottom-6" corner="bl" />
      <Bracket className="right-6 bottom-6" corner="br" />

      {/* ── Top status strip ─────────────────────────────────── */}
      <div className="absolute inset-x-0 top-3 flex items-center justify-center gap-6 font-data text-2xs uppercase tracking-[0.4em] text-text-muted">
        <span>BV-AI / NEURAL CORE</span>
        <span className="h-1 w-1 rounded-full bg-cyan ai-pulse" />
        <span>TIER · {tier.toUpperCase()}</span>
        <span className="h-1 w-1 rounded-full bg-cyan ai-pulse" />
        <ClockReadout />
      </div>

      {/* ── Bottom module ticker ─────────────────────────────── */}
      <ModuleTicker activeIdx={activeIdx} />
    </div>
  );
}

/** 1Hz UTC clock — isolated so its tick doesn't ripple through the
 * rest of the HUD. */
function ClockReadout() {
  const [clock, setClock] = useState('');
  useEffect(() => {
    const fmt = () => new Date().toISOString().slice(11, 19);
    setClock(fmt());
    const id = setInterval(() => setClock(fmt()), 1000);
    return () => clearInterval(id);
  }, []);
  return <span>UTC {clock}</span>;
}

/** Memoised so the ticker only reconciles when `activeIdx` changes. */
const ModuleTicker = memo(function ModuleTicker({
  activeIdx,
}: {
  activeIdx: number;
}) {
  return (
    <div className="absolute inset-x-0 bottom-8 flex justify-center">
      <div className="flex items-center gap-3 rounded-full border border-border bg-abyss/60 px-5 py-2 backdrop-blur-sm">
        {MODULES.map((m, i) => {
          const active = i === activeIdx;
          return (
            <div
              key={m.id}
              className="flex items-center gap-2 font-data text-2xs uppercase tracking-widest transition-colors"
              style={{ color: active ? m.accent : 'var(--color-text-muted)' }}
            >
              <span>{m.glyph}</span>
              <span className="hidden md:inline">{m.id}</span>
              {i < MODULES.length - 1 ? (
                <span className="mx-2 text-text-disabled">·</span>
              ) : null}
            </div>
          );
        })}
      </div>
    </div>
  );
});

/** Static decoration — `memo` skips reconciliation entirely. */
const Bracket = memo(function Bracket({
  className,
  corner,
}: {
  className: string;
  corner: 'tl' | 'tr' | 'bl' | 'br';
}) {
  const cn: Record<typeof corner, string> = {
    tl: 'border-l border-t',
    tr: 'border-r border-t',
    bl: 'border-l border-b',
    br: 'border-r border-b',
  };
  return (
    <span className={`absolute h-5 w-5 border-cyan/40 ${cn[corner]} ${className}`} aria-hidden />
  );
});
