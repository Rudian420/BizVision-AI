'use client';

import { moduleMetaById } from '@/lib/chatbot/format';
import type { SourceReference } from '@/lib/chatbot/types';

type SourcesListProps = {
  sources: SourceReference[];
};

/**
 * Inline source-attribution chip strip + summary list for an
 * assistant message. Each source maps back to one of the BizVision
 * modules — the chip uses that module's accent colour from
 * `MODULES`, so a glance tells the user which module's data backed
 * the answer.
 */
export function SourcesList({ sources }: SourcesListProps) {
  if (!sources || sources.length === 0) return null;

  return (
    <div className="mt-3 rounded-md border border-white/10 bg-white/[0.03] p-3">
      <div className="mb-2 font-ui text-[10px] uppercase tracking-widest text-text-secondary">
        Sources
      </div>
      <ul className="space-y-2">
        {sources.map((source, i) => {
          const meta = moduleMetaById(source.module);
          const accent = meta?.accent ?? '#7C3AED';
          const label = meta?.label ?? source.module;
          return (
            <li
              key={`${source.module}-${source.reference_id}-${i}`}
              className="flex gap-3 font-ui text-xs"
            >
              <span
                className="mt-0.5 inline-flex h-5 shrink-0 items-center gap-1 rounded-full border px-2 font-data text-[10px] uppercase tracking-widest"
                style={{
                  color: accent,
                  borderColor: `${accent}55`,
                  backgroundColor: `${accent}11`,
                }}
              >
                <span aria-hidden>{meta?.glyph ?? '?'}</span>
                <span>{label}</span>
              </span>
              <div className="min-w-0">
                <div className="font-data text-text-secondary/70">{source.reference_id}</div>
                <p className="mt-0.5 text-text-primary">{source.summary}</p>
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
